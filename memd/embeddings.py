from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence

import numpy as np

from memd.contracts import EmbeddedMemory, MemoryRecord

TOKEN_RE = re.compile(r"[a-z0-9]+")


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
    tokens = TOKEN_RE.findall(text.lower())
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]
