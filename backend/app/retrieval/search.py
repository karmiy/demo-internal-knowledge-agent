from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk, DocumentStatus, User
from app.policies.documents import document_access_clause


@dataclass(frozen=True)
class RetrievedChunk:
    evidence_id: str
    chunk_id: UUID
    document_id: UUID
    document_title: str
    source_locator: str
    snippet: str
    content: str
    distance: float


def build_search_statement(
    query_embedding: list[float], user: User, *, limit: int = 5
) -> Select[tuple[object, ...]]:
    if not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")

    access_granted = document_access_clause(user)
    distance = DocumentChunk.embedding.cosine_distance(query_embedding)
    return (
        select(
            DocumentChunk.id.label("chunk_id"),
            Document.id.label("document_id"),
            Document.title.label("document_title"),
            DocumentChunk.content,
            DocumentChunk.page_number,
            DocumentChunk.section,
            distance.label("distance"),
            access_granted.label("access_granted"),
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.status == DocumentStatus.READY,
            access_granted,
        )
        .order_by(distance)
        .limit(limit)
    )


def search_documents(
    query: str,
    user: User,
    session: Session,
    embedder: object,
    limit: int = 5,
) -> list[RetrievedChunk]:
    normalized_query = query.strip()
    if not normalized_query:
        return []
    query_embedding = embedder.embed_query(normalized_query)  # type: ignore[attr-defined]
    rows = session.execute(
        build_search_statement(query_embedding, user, limit=limit)
    ).all()

    results: list[RetrievedChunk] = []
    for row in rows:
        if row.access_granted is not True:
            continue
        locator = _source_locator(row.page_number, row.section)
        results.append(
            RetrievedChunk(
                evidence_id=f"doc:{row.chunk_id}",
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                document_title=row.document_title,
                source_locator=locator,
                snippet=_snippet(row.content),
                content=row.content,
                distance=float(row.distance),
            )
        )
    return results


def _source_locator(page_number: int | None, section: str | None) -> str:
    parts: list[str] = []
    if section:
        parts.append(section)
    if page_number is not None:
        parts.append(f"第 {page_number} 页")
    return " · ".join(parts) or "文档"


def _snippet(content: str, limit: int = 500) -> str:
    normalized = " ".join(content.split())
    return normalized if len(normalized) <= limit else f"{normalized[:limit].rstrip()}…"
