from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

import numpy as np
from sklearn.cluster import DBSCAN

from memd.contracts import DuplicateCluster, EmbeddedMemory
from memd.similarity import cosine_similarity_matrix


def cluster_duplicates(
    embeddings: Sequence[EmbeddedMemory],
    threshold: float = 0.85,
    min_samples: int = 2,
) -> list[DuplicateCluster]:
    if len(embeddings) < 2:
        return []

    similarities = cosine_similarity_matrix(embeddings)
    distances = 1.0 - similarities
    labels = DBSCAN(
        eps=1.0 - threshold,
        min_samples=min_samples,
        metric="precomputed",
    ).fit_predict(distances)

    grouped: dict[int, list[int]] = defaultdict(list)
    for index, label in enumerate(labels):
        if label != -1:
            grouped[int(label)].append(index)

    clusters: list[DuplicateCluster] = []
    for cluster_index, member_indexes in enumerate(grouped.values(), start=1):
        if len(member_indexes) < 2:
            continue
        members = tuple(embeddings[index].memoryId for index in member_indexes)
        average = _average_pairwise_similarity(similarities, member_indexes)
        clusters.append(
            DuplicateCluster(
                clusterId=f"cluster_{cluster_index}",
                members=members,
                averageSimilarity=average,
            )
        )
    return clusters


def _average_pairwise_similarity(similarities: np.ndarray, indexes: list[int]) -> float:
    values: list[float] = []
    for offset, left in enumerate(indexes):
        for right in indexes[offset + 1 :]:
            values.append(float(similarities[left, right]))
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)
