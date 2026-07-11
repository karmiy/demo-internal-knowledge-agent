from datetime import timedelta
from uuid import uuid4

import pytest

from app.auth.passwords import authenticate_user, hash_password, verify_password
from app.auth.tokens import InvalidAccessToken, create_access_token, decode_access_token
from app.models import User


class StubSession:
    def __init__(self, user: User | None) -> None:
        self.user = user

    def scalar(self, _statement: object) -> User | None:
        return self.user


def test_password_hash_round_trip() -> None:
    password_hash = hash_password("demo-password")

    assert password_hash != "demo-password"
    assert verify_password("demo-password", password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


def test_access_token_round_trip() -> None:
    user_id = uuid4()

    token = create_access_token(user_id)

    assert decode_access_token(token) == user_id


def test_expired_access_token_is_rejected() -> None:
    token = create_access_token(uuid4(), expires_delta=timedelta(seconds=-1))

    with pytest.raises(InvalidAccessToken):
        decode_access_token(token)


def test_authenticate_user_rejects_inactive_account() -> None:
    user = User(
        id=uuid4(),
        username="disabled.user",
        password_hash=hash_password("demo-password"),
        department_id=uuid4(),
        is_active=False,
    )

    assert authenticate_user(StubSession(user), user.username, "demo-password") is None


def test_authenticate_user_rejects_wrong_password() -> None:
    user = User(
        id=uuid4(),
        username="active.user",
        password_hash=hash_password("demo-password"),
        department_id=uuid4(),
        is_active=True,
    )

    assert authenticate_user(StubSession(user), user.username, "wrong") is None

