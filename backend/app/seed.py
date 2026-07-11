from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import (
    Department,
    Document,
    DocumentPermission,
    DocumentStatus,
    Role,
    Salary,
    SubjectType,
    User,
    UserRole,
    SEED_FILE_STAGING_ERROR,
)

DEMO_PASSWORD = "demo-password"
DEMO_USERS = (
    ("alice.programmer", "engineering", ("programmer",), Decimal("28000.00")),
    ("helen.hr", "people", ("hr",), Decimal("32000.00")),
    ("andy.admin", "operations", ("admin",), Decimal("36000.00")),
)
DEMO_DOCUMENTS = (
    (
        "员工手册",
        "employee-handbook.md",
        ((SubjectType.AUTHENTICATED, "*"),),
    ),
    (
        "工程团队指南",
        "engineering-guide.md",
        ((SubjectType.DEPARTMENT, "engineering"),),
    ),
    (
        "HR 薪酬制度",
        "hr-compensation-policy.md",
        ((SubjectType.ROLE, "hr"), (SubjectType.ROLE, "admin")),
    ),
)


class SeedDocumentBusy(RuntimeError):
    """A worker currently owns a seed document row."""


@dataclass(frozen=True)
class SeedPreparation:
    document_ids: tuple[UUID, ...]
    replacements: tuple[tuple[Path, Path], ...]

    def cleanup(self) -> None:
        for staged, _target in self.replacements:
            staged.unlink(missing_ok=True)


def _get_or_create_department(session: Session, name: str) -> Department:
    department = session.scalar(select(Department).where(Department.name == name))
    if department is None:
        department = Department(name=name)
        session.add(department)
        session.flush()
    return department


def _get_or_create_role(session: Session, name: str) -> Role:
    role = session.scalar(select(Role).where(Role.name == name))
    if role is None:
        role = Role(name=name)
        session.add(role)
        session.flush()
    return role


def _seed_users(session: Session) -> dict[str, User]:
    password_hash = PasswordHash.recommended()
    users: dict[str, User] = {}

    for username, department_name, role_names, amount in DEMO_USERS:
        department = _get_or_create_department(session, department_name)
        user = session.scalar(select(User).where(User.username == username))
        if user is None:
            user = User(
                username=username,
                password_hash=password_hash.hash(DEMO_PASSWORD),
                department=department,
            )
            session.add(user)
            session.flush()

        for role_name in role_names:
            role = _get_or_create_role(session, role_name)
            link = session.get(UserRole, (user.id, role.id))
            if link is None:
                session.add(UserRole(user=user, role=role))

        if session.get(Salary, user.id) is None:
            session.add(
                Salary(
                    user_id=user.id,
                    amount=amount,
                    currency="CNY",
                    effective_date=date(2026, 1, 1),
                )
            )
        users[username] = user

    return users


def _seed_document_for_update_statement(target: Path):
    return (
        select(Document)
        .where(Document.source_path == str(target))
        .with_for_update()
    )


def _seed_documents(
    session: Session,
    admin: User | UUID,
    *,
    seed_root: str | Path | None = None,
    target_root: str | Path | None = None,
    document_specs: tuple[
        tuple[str, str, tuple[tuple[SubjectType, str], ...]], ...
    ]
    | None = None,
) -> SeedPreparation:
    seed_root = Path("/seed-documents") if seed_root is None else Path(seed_root)
    target_root = (
        Path(get_settings().document_root)
        if target_root is None
        else Path(target_root)
    )
    document_specs = DEMO_DOCUMENTS if document_specs is None else document_specs
    target_root.mkdir(parents=True, exist_ok=True)
    staged_targets: list[tuple[Path, Path]] = []
    staged_document_ids: list[UUID] = []
    admin_id = admin.id if isinstance(admin, User) else admin

    try:
        for title, filename, permissions in document_specs:
            source = seed_root / filename
            if not source.exists():
                continue

            content = source.read_bytes()
            checksum = hashlib.sha256(content).hexdigest()
            target = target_root / filename
            file_changed = not target.exists() or target.read_bytes() != content
            document = session.scalar(_seed_document_for_update_statement(target))
            metadata_changed = document is None or (
                document.title != title or document.checksum != checksum
            )
            if (
                document is not None
                and document.status is DocumentStatus.PROCESSING
                and document.error != SEED_FILE_STAGING_ERROR
                and (metadata_changed or file_changed)
            ):
                raise SeedDocumentBusy(f"seed document is being processed: {target}")

            recovering_staged_document = (
                document is not None
                and document.status is DocumentStatus.PROCESSING
                and document.error == SEED_FILE_STAGING_ERROR
            )
            requires_staging = (
                metadata_changed or file_changed or recovering_staged_document
            )

            if file_changed:
                descriptor, staged_name = tempfile.mkstemp(
                    dir=target.parent,
                    prefix=f".{target.name}.",
                    suffix=".tmp",
                )
                staged = Path(staged_name)
                try:
                    with os.fdopen(descriptor, "wb") as staged_file:
                        staged_file.write(content)
                except Exception:
                    staged.unlink(missing_ok=True)
                    raise
                staged_targets.append((staged, target))

            if document is None:
                document = Document(
                    title=title,
                    source_path=str(target),
                    checksum=checksum,
                    created_by=admin_id,
                    is_seed=True,
                    status=DocumentStatus.PROCESSING,
                    error=SEED_FILE_STAGING_ERROR,
                )
                session.add(document)
                session.flush()
            else:
                document.title = title
                document.checksum = checksum
                document.is_seed = True
                if requires_staging:
                    document.status = DocumentStatus.PROCESSING
                    document.error = SEED_FILE_STAGING_ERROR

            if requires_staging:
                staged_document_ids.append(document.id)

            desired = set(permissions)
            existing = {
                (item.subject_type, item.subject_id): item
                for item in document.permissions
            }
            for pair, permission in existing.items():
                if pair not in desired:
                    session.delete(permission)
            for subject_type, subject_id in desired:
                if (subject_type, subject_id) not in existing:
                    session.add(
                        DocumentPermission(
                            document=document,
                            subject_type=subject_type,
                            subject_id=subject_id,
                        )
                    )

        return SeedPreparation(
            document_ids=tuple(staged_document_ids),
            replacements=tuple(staged_targets),
        )
    except Exception:
        for staged, _target in staged_targets:
            staged.unlink(missing_ok=True)
        raise


def _install_seed_files(preparation: SeedPreparation) -> None:
    try:
        for staged, target in preparation.replacements:
            os.replace(staged, target)
    except Exception:
        preparation.cleanup()
        raise


def _finalize_seed_documents(
    session: Session, document_ids: tuple[UUID, ...]
) -> None:
    if not document_ids:
        return
    documents = session.scalars(
        select(Document)
        .where(Document.id.in_(document_ids))
        .with_for_update()
    ).all()
    for document in documents:
        if (
            document.status is DocumentStatus.PROCESSING
            and document.error == SEED_FILE_STAGING_ERROR
        ):
            document.status = DocumentStatus.PENDING
            document.error = None


def reconcile_seed_documents(
    admin_id: UUID,
    *,
    session_factory: Callable[[], Session] = SessionLocal,
    seed_root: str | Path | None = None,
    target_root: str | Path | None = None,
    document_specs: tuple[
        tuple[str, str, tuple[tuple[SubjectType, str], ...]], ...
    ]
    | None = None,
) -> None:
    preparation: SeedPreparation | None = None
    with session_factory() as session:
        try:
            preparation = _seed_documents(
                session,
                admin_id,
                seed_root=seed_root,
                target_root=target_root,
                document_specs=document_specs,
            )
            session.commit()
        except Exception:
            if preparation is not None:
                preparation.cleanup()
            session.rollback()
            raise

    assert preparation is not None
    _install_seed_files(preparation)

    with session_factory() as session:
        try:
            _finalize_seed_documents(session, preparation.document_ids)
            session.commit()
        except Exception:
            session.rollback()
            raise


def seed() -> None:
    with SessionLocal.begin() as session:
        users = _seed_users(session)
        admin_id = users["andy.admin"].id
    reconcile_seed_documents(admin_id)


if __name__ == "__main__":
    seed()
    print("Demo data is ready.")
