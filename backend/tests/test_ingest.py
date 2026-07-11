from pathlib import Path
from uuid import uuid4

import pytest

from app.models import Document, DocumentStatus
from app.retrieval.ingest import (
    DocumentParseError,
    ParsedSection,
    chunk_sections,
    ingest_document,
    parse_document,
)


def test_markdown_sections_keep_heading_metadata(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    path.write_text(
        "# Deploy\nUse Docker.\n\n## Rollback\nRestore backup.",
        encoding="utf-8",
    )

    sections = parse_document(path)

    assert [(item.section, item.content) for item in sections] == [
        ("Deploy", "Use Docker."),
        ("Rollback", "Restore backup."),
    ]


def test_text_parser_groups_paragraphs(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("First paragraph.\n\nSecond paragraph.", encoding="utf-8")

    sections = parse_document(path)

    assert [item.content for item in sections] == [
        "First paragraph.",
        "Second paragraph.",
    ]


def test_chunking_has_overlap_and_keeps_locator() -> None:
    sections = [
        ParsedSection(content="one two three four five six", section="Deploy")
    ]

    chunks = chunk_sections(sections, max_tokens=4, overlap_tokens=2)

    assert len(chunks) == 2
    assert chunks[0].section == "Deploy"
    assert chunks[0].content.split()[-2:] == chunks[1].content.split()[:2]


def test_rejects_unsupported_file_type(tmp_path: Path) -> None:
    path = tmp_path / "unsafe.html"
    path.write_text("<script>alert(1)</script>", encoding="utf-8")

    with pytest.raises(DocumentParseError, match="unsupported"):
        parse_document(path)


class FakeEmbedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(index), 0.5] for index, _text in enumerate(texts)]


class FakeSession:
    def __init__(self, document: Document) -> None:
        self.document = document
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.flush_count = 0

    def get(self, _model: object, document_id: object) -> Document | None:
        return self.document if document_id == self.document.id else None

    def add_all(self, values: list[object]) -> None:
        self.added.extend(values)

    def delete(self, value: object) -> None:
        self.deleted.append(value)

    def flush(self) -> None:
        self.flush_count += 1


def test_ingest_transitions_document_to_ready(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    path.write_text("# Deploy\nUse the release checklist.", encoding="utf-8")
    document = Document(
        id=uuid4(),
        title="Guide",
        source_path=str(path),
        checksum="a" * 64,
        created_by=uuid4(),
        status=DocumentStatus.PENDING,
    )
    session = FakeSession(document)

    ingest_document(document.id, session, FakeEmbedder())

    assert document.status is DocumentStatus.READY
    assert document.error is None
    assert len(session.added) == 1
    assert session.flush_count >= 2


def test_ingest_sanitizes_failure_and_marks_failed(tmp_path: Path) -> None:
    missing_path = tmp_path / "secret-folder" / "missing.md"
    document = Document(
        id=uuid4(),
        title="Missing",
        source_path=str(missing_path),
        checksum="b" * 64,
        created_by=uuid4(),
        status=DocumentStatus.PENDING,
    )
    session = FakeSession(document)

    with pytest.raises(DocumentParseError):
        ingest_document(document.id, session, FakeEmbedder())

    assert document.status is DocumentStatus.FAILED
    assert document.error == "document_processing_failed"
    assert "secret-folder" not in document.error
