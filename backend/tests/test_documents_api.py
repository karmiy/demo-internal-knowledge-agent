from collections.abc import Generator
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.api.documents import get_document_root
from app.auth.dependencies import get_current_user
from app.db import get_session
from app.main import app


class StubSession:
    def __init__(
        self,
        document: object | None = None,
        *,
        commit_error: Exception | None = None,
    ) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self.document = document
        self.commit_error = commit_error
        self.scalar_bind_values: list[object] = []

    def scalar(self, statement: object) -> object | None:
        bind_values = list(statement.compile().params.values())  # type: ignore[attr-defined]
        self.scalar_bind_values.extend(bind_values)
        if self.document is None:
            return None
        if getattr(self.document, "is_seed", False) and "is_seed" in str(statement):
            return None
        return self.document if self.document.id in bind_values else None

    def add_all(self, values: list[object]) -> None:
        self.added.extend(values)

    def commit(self) -> None:
        self.commits += 1
        if self.commit_error is not None:
            raise self.commit_error

    def rollback(self) -> None:
        self.rollbacks += 1


def override_session(session: StubSession) -> Generator[StubSession, None, None]:
    yield session


def test_programmer_cannot_upload_document(tmp_path: Path) -> None:
    user = SimpleNamespace(id=uuid4(), role_names=frozenset({"programmer"}))
    session = StubSession()

    def session_override() -> Generator[StubSession, None, None]:
        yield session

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_document_root] = lambda: tmp_path
    try:
        response = TestClient(app).post(
            "/api/admin/documents", files={"file": ("x.md", b"# x")},
            data={"title": "X", "subjects": '[{"type":"authenticated","id":null}]'},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_admin_upload_creates_pending_document(tmp_path: Path) -> None:
    user = SimpleNamespace(id=uuid4(), role_names=frozenset({"admin"}))
    session = StubSession()

    def session_override() -> Generator[StubSession, None, None]:
        yield session

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_document_root] = lambda: tmp_path
    try:
        response = TestClient(app).post(
            "/api/admin/documents",
            files={"file": ("guide.md", b"# Guide\nSafe content")},
            data={
                "title": "Guide",
                "subjects": '[{"type":"authenticated","id":null}]',
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    assert len(session.added) == 2
    assert session.commits == 1
    assert len(list(tmp_path.glob("*.md"))) == 1


def test_admin_upload_rejects_duplicate_checksum(tmp_path: Path) -> None:
    content = b"# Existing guide"
    checksum = hashlib.sha256(content).hexdigest()
    user = SimpleNamespace(id=uuid4(), role_names=frozenset({"admin"}))
    session = StubSession(SimpleNamespace(id=checksum))

    def session_override() -> Generator[StubSession, None, None]:
        yield session

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_document_root] = lambda: tmp_path
    try:
        response = TestClient(app).post(
            "/api/admin/documents",
            files={"file": ("guide.md", content)},
            data={
                "title": "Guide",
                "subjects": '[{"type":"authenticated","id":null}]',
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json() == {"detail": "Document already exists"}
    assert session.added == []
    assert list(tmp_path.iterdir()) == []


def test_admin_upload_can_match_seed_checksum(tmp_path: Path) -> None:
    content = b"# Seed guide"
    checksum = hashlib.sha256(content).hexdigest()
    user = SimpleNamespace(id=uuid4(), role_names=frozenset({"admin"}))
    session = StubSession(SimpleNamespace(id=checksum, is_seed=True))

    def session_override() -> Generator[StubSession, None, None]:
        yield session

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_document_root] = lambda: tmp_path
    try:
        response = TestClient(app).post(
            "/api/admin/documents",
            files={"file": ("guide.md", content)},
            data={
                "title": "Guide",
                "subjects": '[{"type":"authenticated","id":null}]',
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert len(session.added) == 2
    assert len(list(tmp_path.iterdir())) == 1


def test_admin_upload_integrity_race_returns_conflict(tmp_path: Path) -> None:
    user = SimpleNamespace(id=uuid4(), role_names=frozenset({"admin"}))
    session = StubSession(
        commit_error=IntegrityError("INSERT documents", {}, Exception("unique"))
    )

    def session_override() -> Generator[StubSession, None, None]:
        yield session

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_document_root] = lambda: tmp_path
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/admin/documents",
            files={"file": ("guide.md", b"# Concurrent")},
            data={
                "title": "Guide",
                "subjects": '[{"type":"authenticated","id":null}]',
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json() == {"detail": "Document already exists"}
    assert session.rollbacks == 1
    assert list(tmp_path.iterdir()) == []


def test_upload_rejects_unsupported_extension(tmp_path: Path) -> None:
    user = SimpleNamespace(id=uuid4(), role_names=frozenset({"admin"}))
    session = StubSession()

    def session_override() -> Generator[StubSession, None, None]:
        yield session

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_document_root] = lambda: tmp_path
    try:
        response = TestClient(app).post(
            "/api/admin/documents",
            files={"file": ("page.html", b"<script>x</script>")},
            data={"title": "Bad", "subjects": "[]"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


def test_admin_can_get_document_detail() -> None:
    document_id = uuid4()
    timestamp = datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    document = SimpleNamespace(
        id=document_id,
        title="Engineering Guide",
        status="ready",
        error=None,
        source_path="/private/engineering-guide.md",
        checksum="secret-checksum",
        created_at=timestamp,
        updated_at=timestamp,
        permissions=[
            SimpleNamespace(subject_type="user", subject_id="user-2"),
            SimpleNamespace(subject_type="role", subject_id="admin"),
        ],
        chunks=[
            SimpleNamespace(
                chunk_index=2,
                section=None,
                page_number=3,
                content="Second chunk",
                embedding=[0.2, 0.3],
            ),
            SimpleNamespace(
                chunk_index=1,
                section="Overview",
                page_number=1,
                content="First chunk",
                embedding=[0.1, 0.2],
            ),
        ],
    )
    user = SimpleNamespace(id=uuid4(), role_names=frozenset({"admin"}))
    session = StubSession(document)

    def session_override() -> Generator[StubSession, None, None]:
        yield session

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = session_override
    try:
        response = TestClient(app).get(f"/api/admin/documents/{document_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "id": str(document_id),
        "title": "Engineering Guide",
        "status": "ready",
        "error": None,
        "created_at": "2025-01-02T03:04:05Z",
        "updated_at": "2025-01-02T03:04:05Z",
        "permissions": [
            {"subject_type": "role", "subject_id": "admin"},
            {"subject_type": "user", "subject_id": "user-2"},
        ],
        "chunk_count": 2,
        "chunks": [
            {
                "chunk_index": 1,
                "section": "Overview",
                "page_number": 1,
                "content": "First chunk",
            },
            {
                "chunk_index": 2,
                "section": None,
                "page_number": 3,
                "content": "Second chunk",
            },
        ],
    }
    assert "source_path" not in response.text
    assert "checksum" not in response.text
    assert "embedding" not in response.text
    assert session.scalar_bind_values == [document_id]


def test_programmer_cannot_get_document_detail() -> None:
    user = SimpleNamespace(id=uuid4(), role_names=frozenset({"programmer"}))
    session = StubSession()

    def session_override() -> Generator[StubSession, None, None]:
        yield session

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = session_override
    try:
        response = TestClient(app).get(f"/api/admin/documents/{uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_missing_document_detail_returns_not_found() -> None:
    user = SimpleNamespace(id=uuid4(), role_names=frozenset({"admin"}))
    session = StubSession()

    def session_override() -> Generator[StubSession, None, None]:
        yield session

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = session_override
    try:
        response = TestClient(app).get(f"/api/admin/documents/{uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}
