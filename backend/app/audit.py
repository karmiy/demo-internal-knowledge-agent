from uuid import UUID

from app.models import AuditLog


def record_audit(
    session: object,
    *,
    user_id: UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    allowed: bool,
    reason: str,
    latency_ms: int | None = None,
) -> None:
    session.add(
        AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            allowed=allowed,
            reason=reason,
            latency_ms=latency_ms,
        )
    )

