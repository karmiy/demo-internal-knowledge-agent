from fastapi import APIRouter
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, SessionDependency
from app.models import ThreadOwner
from app.schemas import ThreadResponse

router = APIRouter(prefix="/api", tags=["threads"])


@router.get("/threads", response_model=list[ThreadResponse])
def list_threads(user: CurrentUser, session: SessionDependency) -> list[ThreadResponse]:
    owners = session.scalars(
        select(ThreadOwner)
        .where(ThreadOwner.user_id == user.id)
        .order_by(ThreadOwner.created_at.desc())
    ).all()
    return [ThreadResponse(thread_id=owner.thread_id) for owner in owners]
