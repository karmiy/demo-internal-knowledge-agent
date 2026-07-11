from collections.abc import Generator
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.chat import get_agent_runner
from app.auth.dependencies import get_current_user
from app.db import get_session
from app.main import app
from app.models import ThreadOwner


class StubSession:
    def __init__(self, owner: ThreadOwner | None = None) -> None:
        self.owner = owner
        self.added: list[object] = []
        self.commits = 0

    def get(self, _model: object, _id: object) -> ThreadOwner | None:
        return self.owner

    def add(self, value: object) -> None:
        self.added.append(value)

    def commit(self) -> None:
        self.commits += 1


def test_chat_creates_owned_thread_and_returns_safe_activity() -> None:
    user = SimpleNamespace(id=uuid4(), username="alice.programmer")
    session = StubSession()

    def session_override() -> Generator[StubSession, None, None]:
        yield session

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_agent_runner] = lambda: (
        lambda **_kwargs: {
            "answer": "Use the release checklist.",
            "citations": [],
            "activity": ["searched_documents"],
        }
    )
    try:
        response = TestClient(app).post("/api/chat", json={"message": "发布流程？"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["activity"] == ["searched_documents"]
    assert isinstance(session.added[0], ThreadOwner)
    assert session.added[0].user_id == user.id
    assert session.commits == 1


def test_chat_hides_thread_owned_by_another_user() -> None:
    user = SimpleNamespace(id=uuid4(), username="alice.programmer")
    owner = ThreadOwner(thread_id=uuid4(), user_id=uuid4())
    session = StubSession(owner)

    def session_override() -> Generator[StubSession, None, None]:
        yield session

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_agent_runner] = lambda: lambda **_kwargs: {}
    try:
        response = TestClient(app).post(
            "/api/chat", json={"message": "hello", "thread_id": str(owner.thread_id)}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Thread not found"}
