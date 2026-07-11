from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.documents import get_document_root
from app.auth.dependencies import get_current_user
from app.db import get_session
from app.main import app


class StubSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0

    def scalar(self, _statement: object) -> None:
        return None

    def add_all(self, values: list[object]) -> None:
        self.added.extend(values)

    def commit(self) -> None:
        self.commits += 1


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
