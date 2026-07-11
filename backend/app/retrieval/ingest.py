from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from docx import Document as DocxDocument
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    is_seed_file_staging_error,
)

SUPPORTED_EXTENSIONS = frozenset({".pdf", ".docx", ".md", ".txt"})
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
INDEX_VERSION = "local-hash-v2"


class DocumentParseError(ValueError):
    """A document cannot be safely parsed by the supported parsers."""


@dataclass(frozen=True)
class ParsedSection:
    content: str
    page_number: int | None = None
    section: str | None = None


@dataclass(frozen=True)
class ChunkDraft:
    content: str
    page_number: int | None
    section: str | None
    chunk_index: int


def build_embedding_text(title: str, draft: ChunkDraft) -> str:
    return "\n".join(
        value
        for value in (title.strip(), (draft.section or "").strip(), draft.content)
        if value
    )


def parse_document(path: Path | str) -> list[ParsedSection]:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise DocumentParseError("unsupported_document_type")
    try:
        size = source.stat().st_size
    except OSError as exc:
        raise DocumentParseError("document_unavailable") from exc
    if size > MAX_DOCUMENT_BYTES:
        raise DocumentParseError("document_too_large")

    try:
        if suffix == ".md":
            sections = _parse_markdown(source)
        elif suffix == ".txt":
            sections = _parse_text(source)
        elif suffix == ".pdf":
            sections = _parse_pdf(source)
        else:
            sections = _parse_docx(source)
    except DocumentParseError:
        raise
    except Exception as exc:
        raise DocumentParseError("document_parse_failed") from exc

    if not sections:
        raise DocumentParseError("document_has_no_text")
    return sections


def _parse_markdown(path: Path) -> list[ParsedSection]:
    text = path.read_text(encoding="utf-8")
    heading_pattern = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
    matches = list(heading_pattern.finditer(text))
    if not matches:
        content = text.strip()
        return [ParsedSection(content=content)] if content else []

    sections: list[ParsedSection] = []
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append(ParsedSection(content=preamble))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[match.end() : end].strip()
        if content:
            sections.append(
                ParsedSection(content=content, section=match.group(1).strip())
            )
    return sections


def _parse_text(path: Path) -> list[ParsedSection]:
    text = path.read_text(encoding="utf-8")
    return [
        ParsedSection(content=paragraph.strip())
        for paragraph in re.split(r"\n\s*\n", text)
        if paragraph.strip()
    ]


def _parse_pdf(path: Path) -> list[ParsedSection]:
    reader = PdfReader(path, strict=True)
    sections: list[ParsedSection] = []
    for page_number, page in enumerate(reader.pages, start=1):
        content = (page.extract_text() or "").strip()
        if content:
            sections.append(ParsedSection(content=content, page_number=page_number))
    return sections


def _parse_docx(path: Path) -> list[ParsedSection]:
    document = DocxDocument(path)
    sections: list[ParsedSection] = []
    current_heading: str | None = None
    paragraphs: list[str] = []

    def append_section() -> None:
        content = "\n".join(paragraphs).strip()
        if content:
            sections.append(ParsedSection(content=content, section=current_heading))

    for paragraph in document.paragraphs:
        content = paragraph.text.strip()
        if not content:
            continue
        if paragraph.style and paragraph.style.name.lower().startswith("heading"):
            append_section()
            paragraphs.clear()
            current_heading = content
        else:
            paragraphs.append(content)
    append_section()
    return sections


def chunk_sections(
    sections: list[ParsedSection], max_tokens: int = 700, overlap_tokens: int = 100
) -> list[ChunkDraft]:
    if max_tokens <= 0 or overlap_tokens < 0 or overlap_tokens >= max_tokens:
        raise ValueError("overlap_tokens must be non-negative and less than max_tokens")

    chunks: list[ChunkDraft] = []
    step = max_tokens - overlap_tokens
    for section in sections:
        spans = [
            match.span()
            for match in re.finditer(
                r"[\u3400-\u9fff]|[A-Za-z0-9_]+|[^\s]", section.content
            )
        ]
        for start in range(0, len(spans), step):
            token_spans = spans[start : start + max_tokens]
            if not token_spans:
                continue
            content = section.content[token_spans[0][0] : token_spans[-1][1]].strip()
            if content:
                chunks.append(
                    ChunkDraft(
                        content=content,
                        page_number=section.page_number,
                        section=section.section,
                        chunk_index=len(chunks),
                    )
                )
            if start + max_tokens >= len(spans):
                break
    return chunks


def ingest_document(
    document_id: UUID, session: Session, embedder: object
) -> None:
    document = session.scalar(_document_for_ingestion_statement(document_id))
    if document is None:
        raise LookupError("document_not_found")
    if (
        document.status is DocumentStatus.PROCESSING
        and is_seed_file_staging_error(document.error)
    ):
        return

    document.status = DocumentStatus.PROCESSING
    document.error = None
    session.flush()
    try:
        drafts = chunk_sections(parse_document(document.source_path))
        texts = [build_embedding_text(document.title, draft) for draft in drafts]
        embeddings = embedder.embed_documents(texts)  # type: ignore[attr-defined]
        if len(embeddings) != len(drafts):
            raise RuntimeError("embedding_count_mismatch")

        new_chunks = [
            DocumentChunk(
                document_id=document.id,
                content=draft.content,
                page_number=draft.page_number,
                section=draft.section,
                chunk_index=draft.chunk_index,
                chunk_metadata={
                    "source_path": Path(document.source_path).name,
                    "embedding_version": INDEX_VERSION,
                },
                embedding=embedding,
            )
            for draft, embedding in zip(drafts, embeddings, strict=True)
        ]
        old_chunks = list(document.chunks)
        for old_chunk in old_chunks:
            session.delete(old_chunk)
        if old_chunks:
            session.flush()
        session.add_all(new_chunks)
        document.status = DocumentStatus.READY
        document.error = None
        session.flush()
    except Exception:
        document.status = DocumentStatus.FAILED
        document.error = "document_processing_failed"
        session.flush()
        raise


def _document_for_ingestion_statement(document_id: UUID):
    return (
        select(Document)
        .where(Document.id == document_id)
        .with_for_update()
    )
