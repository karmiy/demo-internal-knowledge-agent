from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import CurrentUser, SessionDependency
from app.auth.passwords import authenticate_user
from app.auth.tokens import create_access_token
from app.schemas import CurrentUserResponse, LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: SessionDependency) -> TokenResponse:
    user = authenticate_user(session, payload.username, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=CurrentUserResponse)
def current_user(user: CurrentUser) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=user.id,
        username=user.username,
        department=user.department.name,
        roles=sorted(user.role_names),
    )
