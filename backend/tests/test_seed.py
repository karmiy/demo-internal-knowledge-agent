from collections.abc import Iterator
import hashlib
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import (
    Base,
    Document,
    DocumentChunk,
    DocumentPermission,
    DocumentStatus,
    SubjectType,
    User,
)
from app.seed import _seed_documents


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
    _seed_documents(
        session,
        admin,
        seed_root=seed_root,
        target_root=target_root,
        document_specs=((title, "guide.md", permissions),),
    )
    session.flush()


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
    assert upload_path.read_bytes() == content


def test_database_failure_leaves_existing_target_untouched(
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
    original_checksum = document.checksum

    source.write_bytes(b"new bytes")

    def fail_commit() -> None:
        raise RuntimeError("injected commit failure")

    monkeypatch.setattr(session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="injected commit failure"):
        seed_one(session, admin, seed_root, target_root)

    assert (target_root / "guide.md").read_bytes() == b"old bytes"
    assert not list(target_root.glob(".guide.md.*.tmp"))
    stored = session.scalar(select(Document))
    assert stored is not None
    assert stored.checksum == original_checksum
    assert stored.status is DocumentStatus.READY


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
    assert stored.status is DocumentStatus.PENDING
    assert (target_root / "guide.md").read_bytes() == b"old bytes"
    assert not list(target_root.glob(".guide.md.*.tmp"))

    monkeypatch.setattr(os, "replace", real_replace)
    seed_one(session, admin, seed_root, target_root)

    assert (target_root / "guide.md").read_bytes() == b"new bytes"
    assert stored.status is DocumentStatus.PENDING


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
