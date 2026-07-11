from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.tokens import InvalidAccessToken, decode_access_token
from app.db import get_session
from app.models import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)
SessionDependency = Annotated[Session, Depends(get_session)]


def get_current_user(
    session: SessionDependency,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidAccessToken as exc:
        raise unauthorized from exc

    user = session.scalar(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.department),
            selectinload(User.role_links).selectinload(UserRole.role),
        )
    )
    if user is None or not user.is_active:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

