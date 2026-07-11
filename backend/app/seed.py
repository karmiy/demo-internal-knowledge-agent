from __future__ import annotations

import fcntl
import hashlib
import os
import tempfile
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

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
    is_seed_file_staging_error,
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
        "考勤与休假制度",
        "attendance-leave-policy.md",
        ((SubjectType.AUTHENTICATED, "*"),),
    ),
    (
        "差旅与报销制度",
        "travel-expense-policy.md",
        ((SubjectType.AUTHENTICATED, "*"),),
    ),
    (
        "信息安全规范",
        "information-security-policy.md",
        ((SubjectType.AUTHENTICATED, "*"),),
    ),
    (
        "远程办公指南",
        "remote-work-guide.md",
        ((SubjectType.AUTHENTICATED, "*"),),
    ),
    (
        "新员工入职指南",
        "onboarding-guide.md",
        ((SubjectType.AUTHENTICATED, "*"),),
    ),
    (
        "工程研发规范",
        "engineering-guide.md",
        ((SubjectType.DEPARTMENT, "engineering"),),
    ),
    (
        "发布与变更管理",
        "release-change-management.md",
        ((SubjectType.DEPARTMENT, "engineering"),),
    ),
    (
        "故障响应与值班手册",
        "incident-response-oncall.md",
        ((SubjectType.DEPARTMENT, "engineering"),),
    ),
    (
        "薪酬与职级制度",
        "hr-compensation-policy.md",
        ((SubjectType.ROLE, "hr"), (SubjectType.ROLE, "admin")),
    ),
    (
        "绩效评估制度",
        "performance-review-policy.md",
        ((SubjectType.ROLE, "hr"), (SubjectType.ROLE, "admin")),
    ),
    (
        "采购与供应商管理制度",
        "procurement-vendor-policy.md",
        ((SubjectType.ROLE, "admin"),),
    ),
)


class SeedDocumentBusy(RuntimeError):
    """A worker currently owns a seed document row."""


class SeedReconciliationBusy(RuntimeError):
    """Another live process owns the seed reconciliation protocol."""


class SeedOperationLost(RuntimeError):
    """A seed operation no longer owns its document staging marker."""


@dataclass(frozen=True)
class SeedDocumentOperation:
    document_id: UUID
    token: str
    staged: Path | None
    target: Path


@dataclass(frozen=True)
class SeedPreparation:
    operations: tuple[SeedDocumentOperation, ...]

    def cleanup(self) -> None:
        for operation in self.operations:
            if operation.staged is not None:
                operation.staged.unlink(missing_ok=True)


def _seed_staging_marker(token: str) -> str:
    return f"{SEED_FILE_STAGING_ERROR}:{token}"


@contextmanager
def _seed_reconciliation_lock(
    target_root: Path,
    *,
    timeout_seconds: float = 5.0,
    poll_seconds: float = 0.05,
):
    """Serialize this local-volume demo on Linux/macOS using advisory flock."""
    target_root.mkdir(parents=True, exist_ok=True)
    lock_path = target_root / ".seed-reconciliation.lock"
    deadline = time.monotonic() + timeout_seconds
    with lock_path.open("a+b") as lock_file:
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise SeedReconciliationBusy(
                        f"seed reconciliation lock is busy: {lock_path}"
                    ) from exc
                time.sleep(min(poll_seconds, remaining))
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


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


def _prepare_seed_documents(
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
    operations: list[SeedDocumentOperation] = []
    unassigned_staged: Path | None = None
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
                and not is_seed_file_staging_error(document.error)
                and (metadata_changed or file_changed)
            ):
                raise SeedDocumentBusy(f"seed document is being processed: {target}")

            recovering_staged_document = (
                document is not None
                and document.status is DocumentStatus.PROCESSING
                and is_seed_file_staging_error(document.error)
            )
            requires_staging = (
                metadata_changed or file_changed or recovering_staged_document
            )

            staged: Path | None = None
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
                unassigned_staged = staged

            token = uuid4().hex if requires_staging else None
            if requires_staging:
                assert token is not None

            if document is None:
                document = Document(
                    title=title,
                    source_path=str(target),
                    checksum=checksum,
                    created_by=admin_id,
                    is_seed=True,
                    status=DocumentStatus.PROCESSING,
                    error=_seed_staging_marker(token),
                )
                session.add(document)
                session.flush()
            else:
                document.title = title
                document.checksum = checksum
                document.is_seed = True
                if requires_staging:
                    document.status = DocumentStatus.PROCESSING
                    document.error = _seed_staging_marker(token)

            if requires_staging:
                operations.append(
                    SeedDocumentOperation(
                        document_id=document.id,
                        token=token,
                        staged=staged,
                        target=target,
                    )
                )
                unassigned_staged = None

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

        return SeedPreparation(operations=tuple(operations))
    except Exception:
        SeedPreparation(operations=tuple(operations)).cleanup()
        if unassigned_staged is not None:
            unassigned_staged.unlink(missing_ok=True)
        raise


def _finalize_seed_preparation(
    session: Session, preparation: SeedPreparation
) -> None:
    if not preparation.operations:
        return
    documents: dict[UUID, Document] = {}
    for operation in preparation.operations:
        document = session.scalar(
            select(Document)
            .where(Document.id == operation.document_id)
            .with_for_update()
        )
        expected_marker = _seed_staging_marker(operation.token)
        if (
            document is None
            or document.status is not DocumentStatus.PROCESSING
            or document.error != expected_marker
        ):
            raise SeedOperationLost(
                f"seed staging token no longer owns document {operation.document_id}"
            )
        documents[operation.document_id] = document

    for operation in preparation.operations:
        if operation.staged is not None:
            os.replace(operation.staged, operation.target)
        document = documents[operation.document_id]
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
    reconciliation_lock_timeout: float = 5.0,
) -> None:
    resolved_target_root = (
        Path(get_settings().document_root)
        if target_root is None
        else Path(target_root)
    )
    with _seed_reconciliation_lock(
        resolved_target_root,
        timeout_seconds=reconciliation_lock_timeout,
    ):
        preparation: SeedPreparation | None = None
        with session_factory() as session:
            try:
                preparation = _prepare_seed_documents(
                    session,
                    admin_id,
                    seed_root=seed_root,
                    target_root=resolved_target_root,
                    document_specs=document_specs,
                )
                session.commit()
            except Exception:
                if preparation is not None:
                    preparation.cleanup()
                session.rollback()
                raise

        assert preparation is not None
        with session_factory() as session:
            try:
                _finalize_seed_preparation(session, preparation)
                session.commit()
            except Exception:
                preparation.cleanup()
                session.rollback()
                raise


def _reconcile_seed_documents_with_retry(
    admin_id: UUID,
    *,
    max_attempts: int = 3,
    retry_delay: float = 0.5,
) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            reconcile_seed_documents(admin_id)
            return
        except SeedDocumentBusy as exc:
            if attempt == max_attempts:
                raise SeedDocumentBusy(
                    f"seed documents remained worker-owned after {max_attempts} attempts"
                ) from exc
            time.sleep(retry_delay)


def seed() -> None:
    with SessionLocal.begin() as session:
        users = _seed_users(session)
        admin_id = users["andy.admin"].id
    _reconcile_seed_documents_with_retry(admin_id)


if __name__ == "__main__":
    seed()
    print("Demo data is ready.")
