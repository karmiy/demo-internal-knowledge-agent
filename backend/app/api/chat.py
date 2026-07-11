from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, SessionDependency
from app.config import Settings, get_settings
from app.embeddings import build_local_embedder
from app.graph.state import AgentState
from app.graph.workflow import KnowledgeAgent
from app.models import ThreadOwner, User
from app.retrieval.search import search_documents
from app.schemas import ChatRequest, ChatResponse
from app.tools.salary import get_salary

router = APIRouter(prefix="/api", tags=["chat"])
AgentRunner = Callable[..., AgentState]


class RuntimeServices:
    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        api_key = (
            settings.anthropic_api_key.get_secret_value()
            if settings.anthropic_api_key
            else None
        )
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        self.embedder = build_local_embedder()
        self.model = ChatAnthropic(
            model=settings.chat_model,
            api_key=api_key,
            temperature=0,
            max_tokens=settings.chat_max_tokens,
        )

    def compose(self, system_prompt: str, question: str) -> str:
        response = self.model.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=question)]
        )
        return _message_text(response.content)


def _message_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    text_blocks = [
        block["text"]
        for block in content
        if isinstance(block, dict)
        and block.get("type") == "text"
        and isinstance(block.get("text"), str)
    ]
    return "\n".join(text_blocks)


@lru_cache
def get_runtime_services() -> RuntimeServices:
    return RuntimeServices()


def get_agent_runner() -> AgentRunner:
    def run(*, message: str, actor: User, session: Session, thread_id: UUID) -> AgentState:
        try:
            services = get_runtime_services()
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Agent model is not configured",
            ) from exc
        agent = KnowledgeAgent(
            document_search=lambda query, user, db: search_documents(
                query, user, db, services.embedder
            ),
            salary_lookup=get_salary,
            composer=services.compose,
        )
        return agent.invoke(
            message=message, actor=actor, session=session, thread_id=thread_id
        )

    return run


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    user: CurrentUser,
    session: SessionDependency,
    runner: Annotated[AgentRunner, Depends(get_agent_runner)],
) -> ChatResponse:
    thread_id = _owned_thread(payload.thread_id, user, session)
    result = runner(
        message=payload.message.strip(), actor=user, session=session, thread_id=thread_id
    )
    session.commit()
    return ChatResponse(
        thread_id=thread_id,
        answer=result["answer"],
        citations=result.get("citations", []),
        activity=result.get("activity", []),
    )


def _owned_thread(requested_id: UUID | None, user: User, session: Session) -> UUID:
    if requested_id is None:
        thread_id = uuid4()
        session.add(ThreadOwner(thread_id=thread_id, user_id=user.id))
        return thread_id
    owner = session.get(ThreadOwner, requested_id)
    if owner is None or owner.user_id != user.id:
        raise HTTPException(status_code=404, detail="Thread not found")
    return requested_id
