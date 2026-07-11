from typing import Protocol

from pwdlib import PasswordHash
from sqlalchemy import select

from app.models import User

password_hash = PasswordHash.recommended()


class ScalarSession(Protocol):
    def scalar(self, statement: object) -> User | None: ...


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    return password_hash.verify(password, encoded_hash)


def authenticate_user(
    session: ScalarSession, username: str, password: str
) -> User | None:
    user = session.scalar(select(User).where(User.username == username))
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user

