from math import sqrt
from pathlib import Path
from typing import NamedTuple

import pytest

from app.embeddings import LocalHashEmbeddings
from app.models import SubjectType
from app.retrieval.ingest import build_embedding_text, chunk_sections, parse_document
from app.seed import DEMO_DOCUMENTS


def dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def cosine_distance(left: list[float], right: list[float]) -> float:
    return 1.0 - dot(left, right)


def test_embedding_is_deterministic_normalized_and_configured() -> None:
    embedder = LocalHashEmbeddings(dimensions=64)

    first = embedder.embed_query("工程发布流程")
    second = embedder.embed_query("工程发布流程")

    assert first == second
    assert len(first) == 64
    assert sqrt(dot(first, first)) == pytest.approx(1.0)


def test_shared_chinese_terms_rank_above_unrelated_text() -> None:
    embedder = LocalHashEmbeddings(dimensions=256)
    query = embedder.embed_query("工程发布流程")
    related = embedder.embed_query("工程团队发布检查流程")
    unrelated = embedder.embed_query("年度休假与报销制度")

    assert dot(query, related) > dot(query, unrelated)


def test_seeded_document_composites_match_calibrated_distance() -> None:
    embedder = LocalHashEmbeddings(dimensions=1536)
    employee_query = embedder.embed_query("公司的核心协作时间是什么？")
    engineering_query = embedder.embed_query("工程发布流程是什么？")
    employee_chunk = embedder.embed_query(
        "员工手册\n工作时间\n"
        "公司采用弹性工作制，核心协作时间为工作日 10:00 至 16:00。"
    )
    engineering_chunk = embedder.embed_query(
        "工程团队指南\n发布流程\n"
        "所有生产发布必须通过持续集成检查，并至少获得一位代码所有者批准。"
        "发布完成后需要验证健康检查和关键业务指标。"
    )

    assert cosine_distance(employee_query, employee_chunk) <= 0.72
    assert cosine_distance(engineering_query, engineering_chunk) <= 0.72
    assert cosine_distance(employee_query, engineering_chunk) > 0.72
    assert cosine_distance(engineering_query, employee_chunk) > 0.72


class DemoIdentity(NamedTuple):
    department: str
    roles: frozenset[str]
    is_admin: bool = False


DEMO_IDENTITIES = {
    "alice": DemoIdentity("engineering", frozenset({"programmer"})),
    "helen": DemoIdentity("people", frozenset({"hr"})),
    "andy": DemoIdentity("operations", frozenset({"admin"}), True),
}
EXPECTED_VISIBLE_FILENAMES = {
    "alice": {
        "employee-handbook.md",
        "attendance-leave-policy.md",
        "travel-expense-policy.md",
        "information-security-policy.md",
        "remote-work-guide.md",
        "onboarding-guide.md",
        "engineering-guide.md",
        "release-change-management.md",
        "incident-response-oncall.md",
    },
    "helen": {
        "employee-handbook.md",
        "attendance-leave-policy.md",
        "travel-expense-policy.md",
        "information-security-policy.md",
        "remote-work-guide.md",
        "onboarding-guide.md",
        "hr-compensation-policy.md",
        "performance-review-policy.md",
    },
    "andy": {filename for _title, filename, _permissions in DEMO_DOCUMENTS},
}


def _is_visible(
    permissions: tuple[tuple[SubjectType, str], ...], identity: DemoIdentity
) -> bool:
    if identity.is_admin:
        return True
    return any(
        subject_type is SubjectType.AUTHENTICATED
        or (
            subject_type is SubjectType.DEPARTMENT
            and subject_id == identity.department
        )
        or (subject_type is SubjectType.ROLE and subject_id in identity.roles)
        for subject_type, subject_id in permissions
    )


def test_live_acceptance_questions_rank_acl_filtered_seed_corpus() -> None:
    documents_root = Path(__file__).parents[2] / "documents"
    embedder = LocalHashEmbeddings(dimensions=1536)
    corpus: list[tuple[str, str, tuple[tuple[SubjectType, str], ...], str, str]] = []
    for title, filename, permissions in DEMO_DOCUMENTS:
        drafts = chunk_sections(parse_document(documents_root / filename))
        for draft in drafts:
            corpus.append(
                (
                    filename,
                    title,
                    permissions,
                    draft.section or "文档",
                    build_embedding_text(title, draft),
                )
            )

    cases = (
        ("alice", "年假申请需要提前多久？", "考勤与休假制度", "年假与事假"),
        (
            "alice",
            "差旅报销应在返程后多久提交？",
            "差旅与报销制度",
            "提交时限与审批",
        ),
        ("alice", "P1 故障需要多快响应？", "故障响应与值班手册", "响应时限"),
        (
            "alice",
            "生产发布需要哪些审批和验证？",
            "发布与变更管理",
            "审批与上线前检查",
        ),
        ("helen", "薪酬复核通常在什么时候进行？", "薪酬与职级制度", "年度薪酬复核"),
        ("andy", "采购达到什么条件需要多家比价？", "采购与供应商管理制度", "比价要求"),
    )

    for identity_name, question, expected_title, expected_section in cases:
        identity = DEMO_IDENTITIES[identity_name]
        visible = [row for row in corpus if _is_visible(row[2], identity)]
        assert {row[0] for row in visible} == EXPECTED_VISIBLE_FILENAMES[
            identity_name
        ]
        query_embedding = embedder.embed_query(question)
        composite_embeddings = embedder.embed_documents([row[4] for row in visible])
        ranked = sorted(
            (
                cosine_distance(query_embedding, embedding),
                row[1],
                row[3],
            )
            for row, embedding in zip(visible, composite_embeddings, strict=True)
        )

        top_distance, top_title, top_section = ranked[0]
        assert (top_title, top_section) == (expected_title, expected_section)
        assert top_distance <= 0.72


def test_empty_text_returns_zero_vector() -> None:
    embedder = LocalHashEmbeddings(dimensions=32)

    assert embedder.embed_query("  \n") == [0.0] * 32


def test_rejects_too_few_dimensions() -> None:
    with pytest.raises(ValueError, match="at least 32"):
        LocalHashEmbeddings(dimensions=31)
