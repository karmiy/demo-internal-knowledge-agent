from decimal import Decimal
from uuid import uuid4

from app.models import Department, Role, Salary, User, UserRole
from app.tools.salary import SAFE_DENIAL_MESSAGE, get_salary


def make_user(username: str, role_name: str, department_name: str) -> User:
    department = Department(id=uuid4(), name=department_name)
    role = Role(id=uuid4(), name=role_name)
    user = User(
        id=uuid4(),
        username=username,
        password_hash="not-used",
        department_id=department.id,
        department=department,
    )
    user.role_links.append(UserRole(user=user, role=role))
    return user


class QueueSession:
    def __init__(self, *responses: object) -> None:
        self.responses = list(responses)
        self.scalar_calls = 0
        self.added: list[object] = []

    def scalar(self, _statement: object) -> object | None:
        self.scalar_calls += 1
        return self.responses.pop(0) if self.responses else None

    def add(self, value: object) -> None:
        self.added.append(value)


def test_denied_salary_result_never_queries_or_contains_amount() -> None:
    programmer = make_user("alice.programmer", "programmer", "engineering")
    hr_user = make_user("helen.hr", "hr", "people")
    session = QueueSession(hr_user)

    result = get_salary(programmer, hr_user.username, session)

    assert result.allowed is False
    assert result.amount is None
    assert result.message == SAFE_DENIAL_MESSAGE
    assert session.scalar_calls == 1
    assert len(session.added) == 1


def test_self_salary_result_contains_authorized_value() -> None:
    programmer = make_user("alice.programmer", "programmer", "engineering")
    salary = Salary(
        user_id=programmer.id,
        amount=Decimal("28000.00"),
        currency="CNY",
    )
    session = QueueSession(programmer, salary)

    result = get_salary(programmer, programmer.username, session)

    assert result.allowed is True
    assert result.amount == Decimal("28000.00")
    assert result.currency == "CNY"
    assert session.scalar_calls == 2
    assert len(session.added) == 1


def test_unknown_target_uses_same_safe_denial() -> None:
    programmer = make_user("alice.programmer", "programmer", "engineering")
    session = QueueSession(None)

    result = get_salary(programmer, "unknown.user", session)

    assert result.allowed is False
    assert result.message == SAFE_DENIAL_MESSAGE
    assert result.amount is None
