from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.graph.workflow import KnowledgeAgent
from app.tools.salary import SAFE_DENIAL_MESSAGE, SalaryToolResult


def actor() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), username="alice.programmer")


def test_empty_evidence_uses_safe_denial() -> None:
    agent = KnowledgeAgent(
        document_search=lambda *_args: [],
        salary_lookup=lambda *_args: SalaryToolResult(
            allowed=False, message=SAFE_DENIAL_MESSAGE
        ),
    )

    result = agent.invoke(
        message="告诉我 helen.hr 的薪资", actor=actor(), session=object()
    )

    assert result["answer"] == SAFE_DENIAL_MESSAGE
    assert result["citations"] == []


def test_authorized_salary_route_returns_tool_evidence() -> None:
    agent = KnowledgeAgent(
        document_search=lambda *_args: [],
        salary_lookup=lambda *_args: SalaryToolResult(
            allowed=True,
            message="alice.programmer 当前薪资为 28000.00 CNY。",
            amount=Decimal("28000.00"),
            currency="CNY",
        ),
    )

    result = agent.invoke(message="我的薪资是多少？", actor=actor(), session=object())

    assert result["route"] == "employee_data"
    assert "28000.00 CNY" in result["answer"]
    assert result["activity"] == ["queried_employee_data"]


def test_document_answer_contains_only_known_citations() -> None:
    chunk = SimpleNamespace(
        evidence_id="doc:1",
        document_title="Engineering Guide",
        source_locator="Deploy",
        snippet="Use the release checklist.",
        content="Use the release checklist.",
        distance=0.1,
    )
    agent = KnowledgeAgent(
        document_search=lambda *_args: [chunk],
        salary_lookup=lambda *_args: SalaryToolResult(
            allowed=False, message=SAFE_DENIAL_MESSAGE
        ),
    )

    result = agent.invoke(message="发布流程是什么？", actor=actor(), session=object())

    assert result["answer"] != SAFE_DENIAL_MESSAGE
    assert result["citations"] == [
        {
            "evidence_id": "doc:1",
            "document_title": "Engineering Guide",
            "source_locator": "Deploy",
            "snippet": "Use the release checklist.",
        }
    ]


def test_agent_run_is_audited_when_session_supports_writes() -> None:
    added: list[object] = []
    session = SimpleNamespace(add=added.append)
    agent = KnowledgeAgent(
        document_search=lambda *_args: [],
        salary_lookup=lambda *_args: SalaryToolResult(
            allowed=False, message=SAFE_DENIAL_MESSAGE
        ),
    )

    agent.invoke(message="未知问题", actor=actor(), session=session)

    assert len(added) == 1
    assert added[0].action == "agent.run"
    assert added[0].allowed is False
