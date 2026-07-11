from __future__ import annotations

from typing import Any, Literal, TypedDict
from uuid import UUID


class Citation(TypedDict):
    evidence_id: str
    document_title: str
    source_locator: str
    snippet: str


class AgentState(TypedDict, total=False):
    message: str
    actor: Any
    actor_id: UUID
    thread_id: UUID
    session: Any
    route: Literal["documents", "employee_data", "mixed"]
    document_evidence: list[Any]
    tool_evidence: Any
    citations: list[Citation]
    answer: str
    activity: list[str]
