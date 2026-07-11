from collections.abc import Generator
from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth.passwords import hash_password
from app.db import get_session
from app.main import app
from app.models import Department, Role, User, UserRole


class StubSession:
    def __init__(self, user: User) -> None:
        self.user = user

    def scalar(self, _statement: object) -> User:
        return self.user


def make_user() -> User:
    department = Department(id=uuid4(), name="engineering")
    role = Role(id=uuid4(), name="programmer")
    user = User(
        id=uuid4(),
        username="alice.programmer",
        password_hash=hash_password("demo-password"),
        department_id=department.id,
        department=department,
        is_active=True,
    )
    user.role_links.append(UserRole(user=user, role=role))
    return user


def test_login_and_current_user_round_trip() -> None:
    user = make_user()

    def override_session() -> Generator[StubSession, None, None]:
        yield StubSession(user)

    app.dependency_overrides[get_session] = override_session
    try:
        client = TestClient(app)
        login = client.post(
            "/api/auth/login",
            json={"username": user.username, "password": "demo-password"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]

        current = client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert current.status_code == 200
        assert current.json() == {
            "id": str(user.id),
            "username": "alice.programmer",
            "department": "engineering",
            "roles": ["programmer"],
        }
    finally:
        app.dependency_overrides.clear()


def test_login_rejects_invalid_credentials_without_detail_leak() -> None:
    user = make_user()

    def override_session() -> Generator[StubSession, None, None]:
        yield StubSession(user)

    app.dependency_overrides[get_session] = override_session
    try:
        response = TestClient(app).post(
            "/api/auth/login",
            json={"username": user.username, "password": "wrong"},
        )
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid username or password"}
    finally:
        app.dependency_overrides.clear()
