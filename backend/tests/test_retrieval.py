from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.models import Department, Role, User, UserRole
from app.retrieval.search import build_search_statement, search_documents


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


class FakeEmbedder:
    def embed_query(self, _query: str) -> list[float]:
        return [0.1, 0.2]


class FakeResult:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def all(self) -> list[object]:
        return self.rows


class FakeSession:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows
        self.statement: object | None = None

    def execute(self, statement: object) -> FakeResult:
        self.statement = statement
        return FakeResult(self.rows)


def test_search_statement_applies_acl_before_vector_limit() -> None:
    programmer = make_user("alice.programmer", "programmer", "engineering")

    statement = build_search_statement([0.1, 0.2], programmer, limit=5)
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )

    assert "document_permissions" in sql
    assert "engineering" in sql
    assert "documents.status" in sql
    assert "ORDER BY" in sql
    assert "LIMIT 5" in sql
    assert sql.index("WHERE") < sql.index("ORDER BY") < sql.index("LIMIT 5")


def test_search_returns_citation_metadata() -> None:
    programmer = make_user("alice.programmer", "programmer", "engineering")
    row = SimpleNamespace(
        chunk_id=uuid4(),
        document_id=uuid4(),
        document_title="Engineering Guide",
        content="Use the release checklist before deploying.",
        page_number=None,
        section="Deploy",
        distance=0.12,
        access_granted=True,
    )

    results = search_documents(
        "how do I deploy?", programmer, FakeSession([row]), FakeEmbedder()
    )

    assert results[0].document_title == "Engineering Guide"
    assert results[0].source_locator == "Deploy"
    assert results[0].snippet == row.content
    assert results[0].distance == 0.12


def test_defense_in_depth_drops_row_without_access_marker() -> None:
    programmer = make_user("alice.programmer", "programmer", "engineering")
    leaked_row = SimpleNamespace(
        chunk_id=uuid4(),
        document_id=uuid4(),
        document_title="HR Compensation Policy",
        content="Confidential salary bands",
        page_number=1,
        section=None,
        distance=0.01,
        access_granted=False,
    )

    results = search_documents(
        "salary band", programmer, FakeSession([leaked_row]), FakeEmbedder()
    )

    assert results == []
