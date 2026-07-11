from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.config import get_settings


class InvalidAccessToken(ValueError):
    pass


def create_access_token(
    user_id: UUID, *, expires_delta: timedelta | None = None
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + (
        expires_delta or timedelta(minutes=settings.access_token_minutes)
    )
    payload = {"sub": str(user_id), "iat": now, "exp": expires_at}
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> UUID:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        return UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise InvalidAccessToken("Invalid access token") from exc

