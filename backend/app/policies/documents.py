from sqlalchemy import and_, exists, or_, select, true
from sqlalchemy.sql.elements import ColumnElement

from app.models import Document, DocumentPermission, SubjectType, User


def document_access_clause(user: User) -> ColumnElement[bool]:
    if "admin" in user.role_names:
        return true()

    role_names = tuple(user.role_names)
    subject_conditions: list[ColumnElement[bool]] = [
        DocumentPermission.subject_type == SubjectType.AUTHENTICATED,
        and_(
            DocumentPermission.subject_type == SubjectType.USER,
            DocumentPermission.subject_id == str(user.id),
        ),
        and_(
            DocumentPermission.subject_type == SubjectType.DEPARTMENT,
            DocumentPermission.subject_id == user.department.name,
        ),
    ]
    if role_names:
        subject_conditions.append(
            and_(
                DocumentPermission.subject_type == SubjectType.ROLE,
                DocumentPermission.subject_id.in_(role_names),
            )
        )

    return exists(
        select(DocumentPermission.id).where(
            DocumentPermission.document_id == Document.id,
            or_(*subject_conditions),
        )
    )
