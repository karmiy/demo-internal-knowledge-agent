from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserResponse(BaseModel):
    id: UUID
    username: str
    department: str
    roles: list[str]


class CitationResponse(BaseModel):
    evidence_id: str
    document_title: str
    source_locator: str
    snippet: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: UUID | None = None


class ChatResponse(BaseModel):
    thread_id: UUID
    answer: str
    citations: list[CitationResponse]
    activity: list[str]


class ThreadResponse(BaseModel):
    thread_id: UUID
