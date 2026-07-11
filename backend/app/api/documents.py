from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, SessionDependency
from app.config import get_settings
from app.models import (
    Document,
    DocumentPermission,
    DocumentStatus,
    SubjectType,
    User,
)
from app.retrieval.ingest import MAX_DOCUMENT_BYTES, SUPPORTED_EXTENSIONS
from app.schemas import DocumentResponse

router = APIRouter(prefix="/api/admin/documents", tags=["documents"])


def get_document_root() -> Path:
    return Path(get_settings().document_root)


def require_admin(user: CurrentUser) -> User:
    if "admin" not in user.role_names:
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
DocumentRoot = Annotated[Path, Depends(get_document_root)]


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    title: Annotated[str, Form(min_length=1, max_length=255)],
    subjects: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    user: AdminUser,
    session: SessionDependency,
    root: DocumentRoot,
) -> DocumentResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported document type")
    parsed_subjects = _parse_subjects(subjects)

    root.mkdir(parents=True, exist_ok=True)
    destination = root / f"{uuid4().hex}{suffix}"
    digest = hashlib.sha256()
    written = 0
    try:
        with destination.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_DOCUMENT_BYTES:
                    raise HTTPException(status_code=413, detail="Document too large")
                digest.update(chunk)
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    checksum = digest.hexdigest()
    if session.scalar(select(Document.id).where(Document.checksum == checksum)) is not None:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail="Document already exists")

    document = Document(
        id=uuid4(),
        title=title.strip(),
        source_path=str(destination),
        checksum=checksum,
        created_by=user.id,
        status=DocumentStatus.PENDING,
    )
    permissions = [
        DocumentPermission(
            document_id=document.id,
            subject_type=subject_type,
            subject_id=subject_id,
        )
        for subject_type, subject_id in parsed_subjects
    ]
    session.add_all([document, *permissions])
    session.commit()
    return _response(document)


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    _user: AdminUser,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[DocumentResponse]:
    documents = session.scalars(
        select(Document)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [_response(document) for document in documents]


@router.post("/{document_id}/retry", response_model=DocumentResponse)
def retry_document(
    document_id: UUID, _user: AdminUser, session: SessionDependency
) -> DocumentResponse:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.status is not DocumentStatus.FAILED:
        raise HTTPException(status_code=409, detail="Only failed documents can be retried")
    document.status = DocumentStatus.PENDING
    document.error = None
    session.commit()
    return _response(document)


def _parse_subjects(raw: str) -> list[tuple[SubjectType, str]]:
    try:
        values: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid subjects") from exc
    if not isinstance(values, list) or not values:
        raise HTTPException(status_code=400, detail="At least one subject is required")

    result: list[tuple[SubjectType, str]] = []
    for item in values:
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="Invalid subjects")
        try:
            subject_type = SubjectType(item.get("type"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid subject type") from exc
        subject_id = "*" if subject_type is SubjectType.AUTHENTICATED else item.get("id")
        if not isinstance(subject_id, str) or not subject_id.strip():
            raise HTTPException(status_code=400, detail="Subject id is required")
        pair = (subject_type, subject_id.strip())
        if pair not in result:
            result.append(pair)
    return result


def _response(document: Document) -> DocumentResponse:
    status_value = (
        document.status.value
        if isinstance(document.status, DocumentStatus)
        else str(document.status)
    )
    return DocumentResponse(
        id=document.id,
        title=document.title,
        status=status_value,
        error=document.error,
    )
