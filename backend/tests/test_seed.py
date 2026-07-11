from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import (
    Base,
    Document,
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


def test_unchanged_seed_keeps_ready_document(
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

    seed_one(session, admin, seed_root, target_root)

    assert document.status is DocumentStatus.READY


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
