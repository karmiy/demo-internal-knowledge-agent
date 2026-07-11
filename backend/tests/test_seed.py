from collections.abc import Iterator
import hashlib
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app import seed as seed_module
from app.ingestion.worker import claim_pending_document
from app.models import (
    Base,
    Document,
    DocumentChunk,
    DocumentPermission,
    DocumentStatus,
    SubjectType,
    User,
)
from app.seed import _prepare_seed_documents


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def admin() -> User:
    return User(
        id=uuid4(),
        username="admin",
        password_hash="unused",
        department_id=uuid4(),
    )


def seed_one(
    session: Session,
    admin: User,
    seed_root: Path,
    target_root: Path,
    *,
    title: str = "Guide",
    permissions: tuple[tuple[SubjectType, str], ...] = (
        (SubjectType.AUTHENTICATED, "*"),
    ),
) -> None:
    session.commit()
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
    seed_module.reconcile_seed_documents(
        admin.id,
        session_factory=factory,
        seed_root=seed_root,
        target_root=target_root,
        document_specs=((title, "guide.md", permissions),),
    )
    session.expire_all()


def test_seed_lookup_compiles_postgresql_row_lock(tmp_path: Path) -> None:
    statement = seed_module._seed_document_for_update_statement(
        tmp_path / "guide.md"
    )

    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE" in sql


def test_live_reconciler_lock_blocks_second_protocol(
    session: Session, admin: User, tmp_path: Path
) -> None:
    seed_root = tmp_path / "seed"
    target_root = tmp_path / "documents"
    seed_root.mkdir()
    (seed_root / "guide.md").write_bytes(b"locked")
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)

    with seed_module._seed_reconciliation_lock(target_root, timeout_seconds=0):
        with pytest.raises(seed_module.SeedReconciliationBusy):
            seed_module.reconcile_seed_documents(
                admin.id,
                session_factory=factory,
                seed_root=seed_root,
                target_root=target_root,
                document_specs=(
                    (
                        "Guide",
                        "guide.md",
                        ((SubjectType.AUTHENTICATED, "*"),),
                    ),
                ),
                reconciliation_lock_timeout=0,
            )

    assert session.scalar(select(Document)) is None
    assert not (target_root / "guide.md").exists()


def test_wrong_staging_token_cannot_finalize_or_replace(
    session: Session, admin: User, tmp_path: Path
) -> None:
    seed_root = tmp_path / "seed"
    target_root = tmp_path / "documents"
    seed_root.mkdir()
    (seed_root / "guide.md").write_bytes(b"token protected")
    preparation = seed_module._prepare_seed_documents(
        session,
        admin,
        seed_root=seed_root,
        target_root=target_root,
        document_specs=(
            (
                "Guide",
                "guide.md",
                ((SubjectType.AUTHENTICATED, "*"),),
            ),
        ),
    )
    session.commit()
    operation = preparation.operations[0]
    document = session.get(Document, operation.document_id)
    assert document is not None
    document.error = f"{seed_module.SEED_FILE_STAGING_ERROR}:different-token"
    session.commit()

    with pytest.raises(seed_module.SeedOperationLost, match="token"):
        seed_module._finalize_seed_preparation(session, preparation)

    session.rollback()
    assert not operation.target.exists()
    assert operation.staged is not None and operation.staged.exists()
    preparation.cleanup()


def test_seed_preparation_uses_unique_token_per_document(
    session: Session, admin: User, tmp_path: Path
) -> None:
    seed_root = tmp_path / "seed"
    target_root = tmp_path / "documents"
    seed_root.mkdir()
    (seed_root / "one.md").write_bytes(b"one")
    (seed_root / "two.md").write_bytes(b"two")

    preparation = _prepare_seed_documents(
        session,
        admin,
        seed_root=seed_root,
        target_root=target_root,
        document_specs=(
            ("One", "one.md", ((SubjectType.AUTHENTICATED, "*"),)),
            ("Two", "two.md", ((SubjectType.AUTHENTICATED, "*"),)),
        ),
    )

    tokens = [operation.token for operation in preparation.operations]
    assert len(tokens) == 2
    assert len(set(tokens)) == 2
    markers = set(session.scalars(select(Document.error)).all())
    assert markers == {
        f"{seed_module.SEED_FILE_STAGING_ERROR}:{token}" for token in tokens
    }
    session.rollback()
    preparation.cleanup()


def test_seed_busy_retry_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps: list[float] = []

    def always_busy(*_args, **_kwargs) -> None:
        nonlocal attempts
        attempts += 1
        raise seed_module.SeedDocumentBusy("worker still owns document")

    monkeypatch.setattr(seed_module, "reconcile_seed_documents", always_busy)
    monkeypatch.setattr(seed_module.time, "sleep", sleeps.append)

    with pytest.raises(seed_module.SeedDocumentBusy, match="after 3 attempts"):
        seed_module._reconcile_seed_documents_with_retry(
            uuid4(), max_attempts=3, retry_delay=0.01
        )

    assert attempts == 3
    assert sleeps == [0.01, 0.01]


def test_seed_helper_does_not_commit_caller_transaction(
    session: Session, admin: User, tmp_path: Path
) -> None:
    seed_root = tmp_path / "seed"
    target_root = tmp_path / "documents"
    seed_root.mkdir()
    (seed_root / "guide.md").write_bytes(b"uncommitted")

    preparation = _prepare_seed_documents(
        session,
        admin,
        seed_root=seed_root,
        target_root=target_root,
        document_specs=(
            (
                "Guide",
                "guide.md",
                ((SubjectType.AUTHENTICATED, "*"),),
            ),
        ),
    )

    assert session.in_transaction()
    session.rollback()
    preparation.cleanup()
    assert session.scalar(select(Document)) is None
    assert not (target_root / "guide.md").exists()


def test_seed_is_unclaimable_until_file_is_installed(
    session: Session,
    admin: User,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_root = tmp_path / "seed"
    target_root = tmp_path / "documents"
    seed_root.mkdir()
    (seed_root / "guide.md").write_bytes(b"staged bytes")
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
    real_replace = os.replace
    observed: list[tuple[DocumentStatus, str | None]] = []

    def observe_replace(source_path: str | Path, target_path: str | Path) -> None:
        with factory() as observer:
            document = observer.scalar(select(Document))
            assert document is not None
            observed.append((document.status, document.error))
            assert claim_pending_document(observer) is None
        real_replace(source_path, target_path)

    monkeypatch.setattr(os, "replace", observe_replace)
    seed_module.reconcile_seed_documents(
        admin.id,
        session_factory=factory,
        seed_root=seed_root,
        target_root=target_root,
        document_specs=(
            (
                "Guide",
                "guide.md",
                ((SubjectType.AUTHENTICATED, "*"),),
            ),
        ),
    )

    assert len(observed) == 1
    assert observed[0][0] is DocumentStatus.PROCESSING
    assert observed[0][1] is not None
    assert observed[0][1].startswith(
        f"{seed_module.SEED_FILE_STAGING_ERROR}:"
    )
    session.expire_all()
    document = session.scalar(select(Document))
    assert document is not None
    assert document.status is DocumentStatus.PENDING
    assert document.error is None


def test_changed_seed_updates_same_document_and_requeues(
    session: Session, admin: User, tmp_path: Path
) -> None:
    seed_root = tmp_path / "seed"
    target_root = tmp_path / "documents"
    seed_root.mkdir()
    source = seed_root / "guide.md"
    source.write_bytes(b"first version")
    seed_one(session, admin, seed_root, target_root)

    document = session.scalar(select(Document))
    assert document is not None
    original_id = document.id
    original_checksum = document.checksum
    document.status = DocumentStatus.READY
    document.error = "old failure"
    session.flush()

    source.write_bytes(b"second version")
    seed_one(session, admin, seed_root, target_root)

    documents = session.scalars(select(Document)).all()
    assert len(documents) == 1
    assert documents[0].id == original_id
    assert documents[0].checksum != original_checksum
    assert (target_root / "guide.md").read_bytes() == b"second version"
    assert documents[0].status is DocumentStatus.PENDING
    assert documents[0].error is None


def test_seed_checksum_can_match_user_uploaded_document(
    session: Session, admin: User, tmp_path: Path
) -> None:
    content = b"shared content"
    checksum = hashlib.sha256(content).hexdigest()
    upload_path = tmp_path / "uploads" / "user-guide.md"
    upload_path.parent.mkdir()
    upload_path.write_bytes(content)
    uploaded = Document(
        title="User upload",
        source_path=str(upload_path),
        checksum=checksum,
        created_by=admin.id,
    )
    session.add(uploaded)
    session.flush()

    seed_root = tmp_path / "seed"
    target_root = tmp_path / "documents"
    seed_root.mkdir()
    (seed_root / "guide.md").write_bytes(content)

    seed_one(session, admin, seed_root, target_root)

    documents = session.scalars(select(Document).order_by(Document.title)).all()
    assert [(document.title, document.source_path) for document in documents] == [
        ("Guide", str(target_root / "guide.md")),
        ("User upload", str(upload_path)),
    ]
    assert {document.checksum for document in documents} == {checksum}
    assert [document.is_seed for document in documents] == [True, False]
    assert upload_path.read_bytes() == content


def test_model_rejects_two_uploaded_documents_with_same_checksum(
    session: Session, admin: User, tmp_path: Path
) -> None:
    checksum = "f" * 64
    session.add_all(
        [
            Document(
                title="Upload one",
                source_path=str(tmp_path / "one.md"),
                checksum=checksum,
                created_by=admin.id,
                is_seed=False,
            ),
            Document(
                title="Upload two",
                source_path=str(tmp_path / "two.md"),
                checksum=checksum,
                created_by=admin.id,
                is_seed=False,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_database_failure_leaves_existing_target_untouched(
    session: Session, admin: User, tmp_path: Path
) -> None:
    seed_root = tmp_path / "seed"
    target_root = tmp_path / "documents"
    seed_root.mkdir()
    source = seed_root / "guide.md"
    source.write_bytes(b"old bytes")
    seed_one(session, admin, seed_root, target_root)
    document = session.scalar(select(Document))
    assert document is not None
    document.status = DocumentStatus.READY
    session.commit()
    original_checksum = document.checksum

    source.write_bytes(b"new bytes")

    base_factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)

    def failing_factory() -> Session:
        failing_session = base_factory()

        def fail_commit() -> None:
            raise RuntimeError("injected commit failure")

        failing_session.commit = fail_commit  # type: ignore[method-assign]
        return failing_session

    with pytest.raises(RuntimeError, match="injected commit failure"):
        seed_module.reconcile_seed_documents(
            admin.id,
            session_factory=failing_factory,
            seed_root=seed_root,
            target_root=target_root,
            document_specs=(
                (
                    "Guide",
                    "guide.md",
                    ((SubjectType.AUTHENTICATED, "*"),),
                ),
            ),
        )

    assert (target_root / "guide.md").read_bytes() == b"old bytes"
    assert not list(target_root.glob(".guide.md.*.tmp"))
    stored = session.scalar(select(Document))
    assert stored is not None
    assert stored.checksum == original_checksum
    assert stored.status is DocumentStatus.READY


def test_seed_defers_changed_document_owned_by_worker(
    session: Session, admin: User, tmp_path: Path
) -> None:
    seed_root = tmp_path / "seed"
    target_root = tmp_path / "documents"
    seed_root.mkdir()
    source = seed_root / "guide.md"
    source.write_bytes(b"old bytes")
    seed_one(session, admin, seed_root, target_root)
    document = session.scalar(select(Document))
    assert document is not None
    document.status = DocumentStatus.PROCESSING
    document.error = None
    session.commit()
    original_checksum = document.checksum

    source.write_bytes(b"new bytes")
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)

    with pytest.raises(seed_module.SeedDocumentBusy, match="being processed"):
        seed_module.reconcile_seed_documents(
            admin.id,
            session_factory=factory,
            seed_root=seed_root,
            target_root=target_root,
            document_specs=(
                (
                    "Guide",
                    "guide.md",
                    ((SubjectType.AUTHENTICATED, "*"),),
                ),
            ),
        )

    session.expire_all()
    assert document.status is DocumentStatus.PROCESSING
    assert document.error is None
    assert document.checksum == original_checksum
    assert (target_root / "guide.md").read_bytes() == b"old bytes"
    assert not list(target_root.glob(".guide.md.*.tmp"))


def test_atomic_replace_failure_leaves_pending_and_retries(
    session: Session, admin: User, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_root = tmp_path / "seed"
    target_root = tmp_path / "documents"
    seed_root.mkdir()
    source = seed_root / "guide.md"
    source.write_bytes(b"old bytes")
    seed_one(session, admin, seed_root, target_root)
    document = session.scalar(select(Document))
    assert document is not None
    document.status = DocumentStatus.READY
    session.commit()

    source.write_bytes(b"new bytes")
    expected_checksum = hashlib.sha256(b"new bytes").hexdigest()
    real_replace = os.replace

    def fail_replace(source_path: str | Path, target_path: str | Path) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected replace failure"):
        seed_one(session, admin, seed_root, target_root)

    session.expire_all()
    stored = session.scalar(select(Document))
    assert stored is not None
    assert stored.checksum == expected_checksum
    assert stored.status is DocumentStatus.PROCESSING
    assert stored.error is not None
    assert stored.error.startswith(f"{seed_module.SEED_FILE_STAGING_ERROR}:")
    assert (target_root / "guide.md").read_bytes() == b"old bytes"
    assert not list(target_root.glob(".guide.md.*.tmp"))

    monkeypatch.setattr(os, "replace", real_replace)
    seed_one(session, admin, seed_root, target_root)

    assert (target_root / "guide.md").read_bytes() == b"new bytes"
    assert stored.status is DocumentStatus.PENDING
    assert stored.error is None


def test_finalization_failure_recovers_after_file_was_installed(
    session: Session,
    admin: User,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_root = tmp_path / "seed"
    target_root = tmp_path / "documents"
    seed_root.mkdir()
    (seed_root / "guide.md").write_bytes(b"installed before finalization")
    base_factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
    factory_calls = 0

    def finalization_failing_factory() -> Session:
        nonlocal factory_calls
        factory_calls += 1
        created_session = base_factory()
        if factory_calls == 2:

            def fail_commit() -> None:
                raise RuntimeError("injected finalization failure")

            created_session.commit = fail_commit  # type: ignore[method-assign]
        return created_session

    with pytest.raises(RuntimeError, match="injected finalization failure"):
        seed_module.reconcile_seed_documents(
            admin.id,
            session_factory=finalization_failing_factory,
            seed_root=seed_root,
            target_root=target_root,
            document_specs=(
                (
                    "Guide",
                    "guide.md",
                    ((SubjectType.AUTHENTICATED, "*"),),
                ),
            ),
        )

    session.expire_all()
    document = session.scalar(select(Document))
    assert document is not None
    assert document.status is DocumentStatus.PROCESSING
    assert document.error is not None
    assert document.error.startswith(f"{seed_module.SEED_FILE_STAGING_ERROR}:")
    crashed_token = document.error
    assert (target_root / "guide.md").read_bytes() == b"installed before finalization"

    real_finalize = seed_module._finalize_seed_preparation
    takeover_tokens: list[str] = []

    def observe_takeover(session: Session, preparation) -> None:
        takeover_tokens.extend(
            operation.token for operation in preparation.operations
        )
        real_finalize(session, preparation)

    monkeypatch.setattr(
        seed_module, "_finalize_seed_preparation", observe_takeover
    )

    seed_module.reconcile_seed_documents(
        admin.id,
        session_factory=base_factory,
        seed_root=seed_root,
        target_root=target_root,
        document_specs=(
            (
                "Guide",
                "guide.md",
                ((SubjectType.AUTHENTICATED, "*"),),
            ),
        ),
    )

    session.expire_all()
    assert takeover_tokens
    assert all(token not in crashed_token for token in takeover_tokens)
    assert document.status is DocumentStatus.PENDING
    assert document.error is None


def test_title_only_change_requeues_document(
    session: Session, admin: User, tmp_path: Path
) -> None:
    seed_root = tmp_path / "seed"
    target_root = tmp_path / "documents"
    seed_root.mkdir()
    (seed_root / "guide.md").write_bytes(b"unchanged")
    seed_one(session, admin, seed_root, target_root)

    document = session.scalar(select(Document))
    assert document is not None
    document.status = DocumentStatus.READY
    session.flush()

    seed_one(session, admin, seed_root, target_root, title="Renamed guide")

    assert document.title == "Renamed guide"
    assert document.status is DocumentStatus.PENDING


@pytest.mark.parametrize(
    "status",
    [DocumentStatus.READY, DocumentStatus.PROCESSING, DocumentStatus.FAILED],
)
def test_unchanged_seed_preserves_status_and_chunks(
    session: Session,
    admin: User,
    tmp_path: Path,
    status: DocumentStatus,
) -> None:
    seed_root = tmp_path / "seed"
    target_root = tmp_path / "documents"
    seed_root.mkdir()
    (seed_root / "guide.md").write_bytes(b"unchanged")
    seed_one(session, admin, seed_root, target_root)

    document = session.scalar(select(Document))
    assert document is not None
    document.status = status
    document.error = "existing error" if status is DocumentStatus.FAILED else None
    chunk = DocumentChunk(
        content="existing chunk",
        chunk_index=0,
        chunk_metadata={"embedding_version": "test"},
        embedding=[0.0],
    )
    document.chunks.append(chunk)
    session.commit()
    chunk_id = chunk.id

    seed_one(session, admin, seed_root, target_root)

    assert document.status is status
    assert [item.id for item in document.chunks] == [chunk_id]
    assert document.chunks[0].content == "existing chunk"
    if status is DocumentStatus.FAILED:
        assert document.error == "existing error"


def test_seed_synchronizes_permissions_exactly(
    session: Session, admin: User, tmp_path: Path
) -> None:
    seed_root = tmp_path / "seed"
    target_root = tmp_path / "documents"
    seed_root.mkdir()
    (seed_root / "guide.md").write_bytes(b"same content")
    seed_one(session, admin, seed_root, target_root)

    desired = (
        (SubjectType.ROLE, "hr"),
        (SubjectType.ROLE, "admin"),
    )
    seed_one(
        session,
        admin,
        seed_root,
        target_root,
        permissions=desired,
    )

    permissions = session.scalars(select(DocumentPermission)).all()
    assert {(item.subject_type, item.subject_id) for item in permissions} == set(desired)


def test_seed_retains_matching_permission_row(
    session: Session, admin: User, tmp_path: Path
) -> None:
    seed_root = tmp_path / "seed"
    target_root = tmp_path / "documents"
    seed_root.mkdir()
    (seed_root / "guide.md").write_bytes(b"same content")
    desired = ((SubjectType.ROLE, "admin"),)
    seed_one(
        session,
        admin,
        seed_root,
        target_root,
        permissions=desired,
    )
    permission = session.scalar(select(DocumentPermission))
    assert permission is not None
    permission_id = permission.id

    seed_one(
        session,
        admin,
        seed_root,
        target_root,
        permissions=desired,
    )

    permission = session.scalar(select(DocumentPermission))
    assert permission is not None
    assert permission.id == permission_id
