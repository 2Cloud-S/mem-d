from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from memd.contracts import EmbeddedMemory, SimilarityRecord


def embedding_matrix(embeddings: Sequence[EmbeddedMemory]) -> np.ndarray:
    if not embeddings:
        return np.empty((0, 0), dtype=float)
    return np.asarray([embedding.embedding for embedding in embeddings], dtype=float)


def cosine_similarity_matrix(embeddings: Sequence[EmbeddedMemory]) -> np.ndarray:
    matrix = embedding_matrix(embeddings)
    if matrix.size == 0:
        return np.empty((0, 0), dtype=float)

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized = matrix / norms
    similarities = normalized @ normalized.T
    return np.clip(similarities, 0.0, 1.0)


def similarity_records(
    embeddings: Sequence[EmbeddedMemory],
    threshold: float,
) -> list[SimilarityRecord]:
    similarities = cosine_similarity_matrix(embeddings)
    records: list[SimilarityRecord] = []

    for row in range(len(embeddings)):
        for column in range(row + 1, len(embeddings)):
            score = float(similarities[row, column])
            if score >= threshold:
                records.append(
                    SimilarityRecord(
                        memoryA=embeddings[row].memoryId,
                        memoryB=embeddings[column].memoryId,
                        similarity=score,
                    )
                )
    return records
