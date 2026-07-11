from __future__ import annotations

import hashlib
import math
import re
import unicodedata

from langchain_core.embeddings import Embeddings

from app.config import get_settings

LATIN_WORD_PATTERN = re.compile(r"[a-z0-9]+")
CHINESE_SEQUENCE_PATTERN = re.compile(r"[\u3400-\u9fff]+")


class LocalHashEmbeddings(Embeddings):
    """Small deterministic lexical embeddings for the dependency-free Demo."""

    def __init__(self, dimensions: int) -> None:
        if dimensions < 32:
            raise ValueError("dimensions must be at least 32")
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for feature in _features(text):
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:8], "big") % self.dimensions
            sign = 1.0 if digest[8] & 1 else -1.0
            vector[index] += sign

        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            return vector
        return [value / magnitude for value in vector]


def _features(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).lower()
    features = [f"word:{word}" for word in LATIN_WORD_PATTERN.findall(normalized)]
    for sequence in CHINESE_SEQUENCE_PATTERN.findall(normalized):
        features.extend(f"char:{character}" for character in sequence)
        features.extend(
            f"bigram:{sequence[index:index + 2]}"
            for index in range(len(sequence) - 1)
        )
    return features


def build_local_embedder() -> LocalHashEmbeddings:
    return LocalHashEmbeddings(get_settings().embedding_dimensions)
