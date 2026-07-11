from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.audit import record_audit
from app.models import Salary, User, UserRole
from app.policies.salaries import can_read_salary

SAFE_DENIAL_MESSAGE = "无法根据您当前有权限访问的信息回答该问题。"


class ToolSession(Protocol):
    def scalar(self, statement: object) -> object | None: ...

    def add(self, value: object) -> None: ...


@dataclass(frozen=True)
class SalaryToolResult:
    allowed: bool
    message: str
    amount: Decimal | None = None
    currency: str | None = None


def get_salary(
    actor: User, target_username: str, session: ToolSession
) -> SalaryToolResult:
    started_at = perf_counter()
    target = session.scalar(
        select(User)
        .where(User.username == target_username)
        .options(
            selectinload(User.department),
            selectinload(User.role_links).selectinload(UserRole.role),
        )
    )
    if not isinstance(target, User):
        _audit_salary(
            session,
            actor=actor,
            target_username=target_username,
            allowed=False,
            reason="salary_target_not_found",
            started_at=started_at,
        )
        return SalaryToolResult(allowed=False, message=SAFE_DENIAL_MESSAGE)

    decision = can_read_salary(actor, target)
    if not decision.allowed:
        _audit_salary(
            session,
            actor=actor,
            target_username=target_username,
            allowed=False,
            reason=decision.reason,
            started_at=started_at,
        )
        return SalaryToolResult(allowed=False, message=SAFE_DENIAL_MESSAGE)

    salary = session.scalar(select(Salary).where(Salary.user_id == target.id))
    if not isinstance(salary, Salary):
        _audit_salary(
            session,
            actor=actor,
            target_username=target_username,
            allowed=True,
            reason="salary_data_missing",
            started_at=started_at,
        )
        return SalaryToolResult(allowed=True, message=SAFE_DENIAL_MESSAGE)

    _audit_salary(
        session,
        actor=actor,
        target_username=target_username,
        allowed=True,
        reason=decision.reason,
        started_at=started_at,
    )
    return SalaryToolResult(
        allowed=True,
        message=f"{target.username} 当前薪资为 {salary.amount:.2f} {salary.currency}。",
        amount=salary.amount,
        currency=salary.currency,
    )


def _audit_salary(
    session: ToolSession,
    *,
    actor: User,
    target_username: str,
    allowed: bool,
    reason: str,
    started_at: float,
) -> None:
    record_audit(
        session,
        user_id=actor.id,
        action="salary.read",
        resource_type="salary",
        resource_id=target_username,
        allowed=allowed,
        reason=reason,
        latency_ms=max(0, round((perf_counter() - started_at) * 1000)),
    )
