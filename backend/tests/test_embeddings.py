from math import sqrt

import pytest

from app.embeddings import LocalHashEmbeddings


def dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


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


def test_empty_text_returns_zero_vector() -> None:
    embedder = LocalHashEmbeddings(dimensions=32)

    assert embedder.embed_query("  \n") == [0.0] * 32


def test_rejects_too_few_dimensions() -> None:
    with pytest.raises(ValueError, match="at least 32"):
        LocalHashEmbeddings(dimensions=31)
