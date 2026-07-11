from dataclasses import dataclass

from app.models import User


@dataclass(frozen=True)
class SalaryDecision:
    allowed: bool
    reason: str


def can_read_salary(actor: User, target: User) -> SalaryDecision:
    if actor.id == target.id:
        return SalaryDecision(allowed=True, reason="salary_self_access")
    if actor.role_names.intersection({"hr", "admin"}):
        return SalaryDecision(allowed=True, reason="salary_privileged_access")
    return SalaryDecision(allowed=False, reason="salary_access_denied")

