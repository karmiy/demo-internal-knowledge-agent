from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.models import Department, Role, User, UserRole
from app.policies.documents import document_access_clause
from app.policies.salaries import can_read_salary


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


def test_programmer_can_read_own_salary() -> None:
    programmer = make_user("alice.programmer", "programmer", "engineering")

    assert can_read_salary(programmer, programmer).allowed is True


def test_programmer_cannot_read_another_salary() -> None:
    programmer = make_user("alice.programmer", "programmer", "engineering")
    hr_user = make_user("helen.hr", "hr", "people")

    decision = can_read_salary(programmer, hr_user)

    assert decision.allowed is False
    assert decision.reason == "salary_access_denied"


def test_hr_can_read_another_salary() -> None:
    programmer = make_user("alice.programmer", "programmer", "engineering")
    hr_user = make_user("helen.hr", "hr", "people")

    assert can_read_salary(hr_user, programmer).allowed is True


def test_admin_can_read_another_salary() -> None:
    programmer = make_user("alice.programmer", "programmer", "engineering")
    admin = make_user("andy.admin", "admin", "operations")

    assert can_read_salary(admin, programmer).allowed is True


def test_document_access_clause_contains_user_acl_dimensions() -> None:
    programmer = make_user("alice.programmer", "programmer", "engineering")

    clause = document_access_clause(programmer)
    sql = str(
        clause.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )

    assert "document_permissions" in sql
    assert str(programmer.id) in sql
    assert "engineering" in sql
    assert "programmer" in sql
