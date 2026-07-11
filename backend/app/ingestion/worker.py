from __future__ import annotations

import time
from collections.abc import Callable
from uuid import UUID

from sqlalchemy import exists, select, update
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.embeddings import LocalHashEmbeddings, build_local_embedder
from app.models import (
    SEED_FILE_STAGING_ERROR,
    Document,
    DocumentChunk,
    DocumentStatus,
)
from app.retrieval.ingest import INDEX_VERSION, ingest_document


def build_embedder() -> LocalHashEmbeddings:
    return build_local_embedder()


def mark_stale_documents_pending(session: Session) -> int:
    current_chunk_exists = (
        exists()
        .where(
            DocumentChunk.document_id == Document.id,
            DocumentChunk.chunk_metadata["embedding_version"].as_string()
            == INDEX_VERSION,
        )
        .correlate(Document)
    )
    result = session.execute(
        update(Document)
        .where(
            Document.status == DocumentStatus.READY,
            ~current_chunk_exists,
        )
        .values(status=DocumentStatus.PENDING)
    )
    session.commit()
    return result.rowcount  # type: ignore[attr-defined, no-any-return]


def claim_pending_document(session: Session) -> UUID | None:
    statement = (
        select(Document)
        .where(Document.status == DocumentStatus.PENDING)
        .order_by(Document.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    document = session.scalar(statement)
    if document is None:
        return None
    document.status = DocumentStatus.PROCESSING
    session.commit()
    return document.id


def mark_document_failed(session: Session, document_id: UUID) -> bool:
    document = session.scalar(
        select(Document)
        .where(Document.id == document_id)
        .with_for_update()
    )
    if document is None or (
        document.status is DocumentStatus.PROCESSING
        and document.error == SEED_FILE_STAGING_ERROR
    ):
        session.commit()
        return False
    document.status = DocumentStatus.FAILED
    document.error = "document_processing_failed"
    session.commit()
    return True


def run_worker(
    *,
    once: bool = False,
    poll_seconds: float = 2.0,
    session_factory: Callable[[], Session] = SessionLocal,
    embedder: object | None = None,
) -> None:
    active_embedder = embedder or build_embedder()
    with session_factory() as startup_session:
        mark_stale_documents_pending(startup_session)
    while True:
        with session_factory() as claim_session:
            document_id = claim_pending_document(claim_session)
        if document_id is None:
            if once:
                return
            time.sleep(poll_seconds)
            continue

        with session_factory() as ingest_session:
            try:
                ingest_document(document_id, ingest_session, active_embedder)
                ingest_session.commit()
            except Exception:
                ingest_session.rollback()
                mark_document_failed(ingest_session, document_id)
        if once:
            return
