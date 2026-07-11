from __future__ import annotations

import time
from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.embeddings import LocalHashEmbeddings, build_local_embedder
from app.models import Document, DocumentStatus
from app.retrieval.ingest import ingest_document


def build_embedder() -> LocalHashEmbeddings:
    return build_local_embedder()


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


def run_worker(
    *,
    once: bool = False,
    poll_seconds: float = 2.0,
    session_factory: Callable[[], Session] = SessionLocal,
    embedder: object | None = None,
) -> None:
    active_embedder = embedder or build_embedder()
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
                failed_document = ingest_session.get(Document, document_id)
                if failed_document is not None:
                    failed_document.status = DocumentStatus.FAILED
                    failed_document.error = "document_processing_failed"
                    ingest_session.commit()
        if once:
            return
