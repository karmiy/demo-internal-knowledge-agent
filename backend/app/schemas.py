from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field


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


class DocumentResponse(BaseModel):
    id: UUID
    title: str
    status: str
    error: str | None = None


class DocumentPermissionResponse(BaseModel):
    subject_type: str
    subject_id: str


class DocumentChunkResponse(BaseModel):
    chunk_index: int
    section: str | None
    page_number: int | None
    content: str


class DocumentDetailResponse(DocumentResponse):
    created_at: AwareDatetime
    updated_at: AwareDatetime
    permissions: list[DocumentPermissionResponse]
    chunk_count: int
    chunks: list[DocumentChunkResponse]
