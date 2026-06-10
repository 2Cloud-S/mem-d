from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence

import numpy as np

from memd.contracts import EmbeddedMemory, MemoryRecord

TOKEN_RE = re.compile(r"[a-z0-9]+")
ALIASES = {
    "cert": "certificate",
    "cicd": "ci",
    "cache": "caching",
    "dev": "development",
    "env": "environment",
    "js": "javascript",
    "k8s": "kubernetes",
    "otel": "opentelemetry",
    "pkg": "package",
    "prefs": "preference",
    "repos": "repository",
    "repo": "repository",
    "ts": "typescript",
}
STEMS = (
    ("environments", "environment"),
    ("development", "develop"),
    ("projects", "project"),
    ("sessions", "session"),
    ("tracing", "trace"),
    ("collection", "collect"),
    ("caching", "cache"),
    ("renewal", "renew"),
    ("certificate", "cert"),
    ("javascript", "js"),
    ("typescript", "ts"),
)


class EmbeddingEngine:
    def __init__(self, model_name: str | None = None, dimensions: int = 384) -> None:
        self.model_name = model_name
        self.dimensions = dimensions
        self._model = None

    def embed(self, records: Sequence[MemoryRecord]) -> list[EmbeddedMemory]:
        texts = [record.content for record in records]
        vectors = self._embed_texts(texts)
        return [
            EmbeddedMemory(memoryId=record.id, embedding=tuple(float(value) for value in vector))
            for record, vector in zip(records, vectors, strict=True)
        ]

    def _embed_texts(self, texts: Sequence[str]) -> np.ndarray:
        if self.model_name:
            try:
                return self._embed_with_sentence_transformers(texts)
            except Exception:
                # The CLI must remain local and usable even if the optional model is unavailable.
                pass
        return np.array([hashing_embedding(text, self.dimensions) for text in texts], dtype=float)

    def _embed_with_sentence_transformers(self, texts: Sequence[str]) -> np.ndarray:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        vectors = self._model.encode(list(texts), normalize_embeddings=True)
        return np.asarray(vectors, dtype=float)


def hashing_embedding(text: str, dimensions: int = 384) -> list[float]:
    vector = [0.0] * dimensions
    for feature, weight in lexical_features(text):
        add_feature(vector, feature, weight)

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def lexical_features(text: str) -> list[tuple[str, float]]:
    tokens = normalize_tokens(TOKEN_RE.findall(text.lower()))
    features: list[tuple[str, float]] = []

    for token in tokens:
        features.append((f"tok:{token}", 1.0))
        for ngram in character_ngrams(token):
            features.append((f"char:{ngram}", 0.2))

    for left, right in zip(tokens, tokens[1:], strict=False):
        features.append((f"bi:{left}_{right}", 0.6))

    return features


def normalize_tokens(tokens: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    for token in tokens:
        current = ALIASES.get(token, token)
        for suffix, replacement in STEMS:
            if current == suffix:
                current = replacement
                break
        if len(current) > 4 and current.endswith("s"):
            current = current[:-1]
        normalized.append(current)
    return normalized


def character_ngrams(token: str, size: int = 4) -> list[str]:
    if len(token) <= size:
        return [token]
    return [token[index : index + size] for index in range(len(token) - size + 1)]


def add_feature(vector: list[float], feature: str, weight: float) -> None:
    digest = hashlib.sha256(feature.encode("utf-8")).digest()
    index = int.from_bytes(digest[:4], "big") % len(vector)
    sign = 1.0 if digest[4] % 2 == 0 else -1.0
    vector[index] += sign * weight
