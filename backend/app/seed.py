from __future__ import annotations

import hashlib
import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path

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


def _seed_documents(
    session: Session,
    admin: User,
    *,
    seed_root: str | Path | None = None,
    target_root: str | Path | None = None,
    document_specs: tuple[
        tuple[str, str, tuple[tuple[SubjectType, str], ...]], ...
    ]
    | None = None,
) -> None:
    seed_root = Path("/seed-documents") if seed_root is None else Path(seed_root)
    target_root = (
        Path(get_settings().document_root)
        if target_root is None
        else Path(target_root)
    )
    document_specs = DEMO_DOCUMENTS if document_specs is None else document_specs
    target_root.mkdir(parents=True, exist_ok=True)

    for title, filename, permissions in document_specs:
        source = seed_root / filename
        if not source.exists():
            continue

        content = source.read_bytes()
        checksum = hashlib.sha256(content).hexdigest()
        target = target_root / filename
        if not target.exists() or target.read_bytes() != content:
            shutil.copyfile(source, target)

        document = session.scalar(
            select(Document).where(Document.source_path == str(target))
        )
        if document is None:
            document = Document(
                title=title,
                source_path=str(target),
                checksum=checksum,
                created_by=admin.id,
            )
            session.add(document)
            session.flush()
        elif document.title != title or document.checksum != checksum:
            document.title = title
            document.checksum = checksum
            document.status = DocumentStatus.PENDING
            document.error = None

        desired = set(permissions)
        existing = {
            (item.subject_type, item.subject_id): item for item in document.permissions
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


def seed() -> None:
    with SessionLocal.begin() as session:
        users = _seed_users(session)
        _seed_documents(session, users["andy.admin"])


if __name__ == "__main__":
    seed()
    print("Demo data is ready.")
