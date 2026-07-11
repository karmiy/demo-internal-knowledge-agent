from math import sqrt

import pytest

from app.embeddings import LocalHashEmbeddings


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


def test_empty_text_returns_zero_vector() -> None:
    embedder = LocalHashEmbeddings(dimensions=32)

    assert embedder.embed_query("  \n") == [0.0] * 32


def test_rejects_too_few_dimensions() -> None:
    with pytest.raises(ValueError, match="at least 32"):
        LocalHashEmbeddings(dimensions=31)
