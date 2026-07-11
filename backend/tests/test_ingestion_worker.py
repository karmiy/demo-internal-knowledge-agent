from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ingestion import worker
from app.models import Base, Document, DocumentChunk, DocumentStatus


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def document(status: DocumentStatus, suffix: str) -> Document:
    return Document(
        id=uuid4(),
        title=f"Guide {suffix}",
        source_path=f"/documents/{suffix}.md",
        checksum=suffix * 64,
        created_by=uuid4(),
        status=status,
    )


def test_ready_document_without_current_index_is_moved_to_pending(
    session: Session,
) -> None:
    stale = document(DocumentStatus.READY, "a")
    session.add(stale)
    session.commit()

    affected = worker.mark_stale_documents_pending(session)

    assert affected == 1
    assert stale.status is DocumentStatus.PENDING


def test_ready_document_with_current_index_remains_ready(session: Session) -> None:
    current = document(DocumentStatus.READY, "b")
    current.chunks.append(
        DocumentChunk(
            content="Use the release checklist.",
            page_number=None,
            section="Deploy",
            chunk_index=0,
            chunk_metadata={"embedding_version": "local-hash-v2"},
            embedding=[0.0] * 1536,
        )
    )
    session.add(current)
    session.commit()

    affected = worker.mark_stale_documents_pending(session)

    assert affected == 0
    assert current.status is DocumentStatus.READY


def test_pending_document_remains_eligible_for_claim(session: Session) -> None:
    pending = document(DocumentStatus.PENDING, "c")
    session.add(pending)
    session.commit()

    worker.mark_stale_documents_pending(session)
    claimed_id = worker.claim_pending_document(session)

    assert claimed_id == pending.id
    assert pending.status is DocumentStatus.PROCESSING
