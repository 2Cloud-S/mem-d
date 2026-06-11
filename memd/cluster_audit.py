from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

import numpy as np

from memd.contracts import CategorizedMemory, DuplicateCluster, EmbeddedMemory, MemoryRecord
from memd.inspection import common_terms
from memd.similarity import cosine_similarity_matrix


def audit_largest_clusters(
    records: Sequence[MemoryRecord],
    categories: Sequence[CategorizedMemory],
    clusters: Sequence[DuplicateCluster],
    embeddings: Sequence[EmbeddedMemory],
    limit: int = 10,
) -> dict[str, object]:
    records_by_id = {record.id: record for record in records}
    categories_by_id = {category.memoryId: category for category in categories}
    similarity_lookup = cluster_similarity_lookup(embeddings)
    all_audits = [
        audit_cluster(cluster, records_by_id, categories_by_id, similarity_lookup)
        for cluster in clusters
    ]
    audits = sorted(all_audits, key=lambda item: int(item["size"]), reverse=True)[:limit]
    over_clustering = [audit for audit in all_audits if audit["appearsHeterogeneous"]]
    contamination = [
        {
            "clusterId": audit["clusterId"],
            "outliers": audit["outlierMemories"],
            "contaminationScore": audit["contaminationScore"],
        }
        for audit in all_audits
        if audit["outlierMemories"]
    ]
    return {
        "allClusterAudits": all_audits,
        "auditedClusterCount": len(audits),
        "largestClusterAudits": audits,
        "overClusteringCandidates": over_clustering,
        "clusterContamination": contamination,
    }


def audit_cluster(
    cluster: DuplicateCluster,
    records_by_id: dict[str, MemoryRecord],
    categories_by_id: dict[str, CategorizedMemory],
    similarity_lookup: dict[tuple[str, str], float],
) -> dict[str, object]:
    members = [member for member in cluster.members if member in records_by_id]
    pairwise = pairwise_similarities(members, similarity_lookup)
    distribution = similarity_distribution(pairwise)
    category_mix = Counter(
        categories_by_id[member].category.value
        for member in members
        if member in categories_by_id
    )
    member_profiles = member_similarity_profiles(members, similarity_lookup)
    representative_ids = [
        item["memoryId"]
        for item in sorted(
            member_profiles,
            key=lambda profile: profile["averageSimilarityToCluster"],
            reverse=True,
        )[:3]
    ]
    outliers = [
        profile
        for profile in member_profiles
        if profile["averageSimilarityToCluster"] < 0.45
    ][:5]
    themes = common_terms((records_by_id[member].content for member in members), limit=10)
    heterogeneity_reasons = heterogeneity_reasons_for(
        cluster_size=len(members),
        distribution=distribution,
        category_mix=category_mix,
        themes=themes,
        outliers=outliers,
    )
    appears_heterogeneous = bool(heterogeneity_reasons)

    return {
        "clusterId": cluster.clusterId,
        "size": len(members),
        "averageSimilarity": cluster.averageSimilarity,
        "similarityDistribution": distribution,
        "dominantThemes": themes,
        "categoryMix": dict(category_mix),
        "representativeMemories": [
            {"id": member, "content": records_by_id[member].content}
            for member in representative_ids
        ],
        "outlierMemories": [
            {
                "id": profile["memoryId"],
                "content": records_by_id[profile["memoryId"]].content,
                "averageSimilarityToCluster": profile["averageSimilarityToCluster"],
            }
            for profile in outliers
        ],
        "conceptAssessment": "multiple-concepts" if appears_heterogeneous else "single-concept",
        "appearsHeterogeneous": appears_heterogeneous,
        "heterogeneityReasons": heterogeneity_reasons,
        "contaminationScore": round(len(outliers) / len(members), 4) if members else 0.0,
    }


def cluster_similarity_lookup(
    embeddings: Sequence[EmbeddedMemory],
) -> dict[tuple[str, str], float]:
    similarities = cosine_similarity_matrix(embeddings)
    lookup: dict[tuple[str, str], float] = {}
    for row in range(len(embeddings)):
        for column in range(row + 1, len(embeddings)):
            lookup[normalize_pair(embeddings[row].memoryId, embeddings[column].memoryId)] = round(
                float(similarities[row, column]),
                4,
            )
    return lookup


def pairwise_similarities(
    members: Sequence[str],
    similarity_lookup: dict[tuple[str, str], float],
) -> list[float]:
    values: list[float] = []
    for index, left in enumerate(members):
        for right in members[index + 1 :]:
            values.append(similarity_lookup.get(normalize_pair(left, right), 0.0))
    return values


def similarity_distribution(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {
            "min": 0.0,
            "p25": 0.0,
            "median": 0.0,
            "p75": 0.0,
            "max": 0.0,
            "spread": 0.0,
        }
    array = np.asarray(values, dtype=float)
    minimum = float(np.min(array))
    maximum = float(np.max(array))
    return {
        "min": round(minimum, 4),
        "p25": round(float(np.percentile(array, 25)), 4),
        "median": round(float(np.percentile(array, 50)), 4),
        "p75": round(float(np.percentile(array, 75)), 4),
        "max": round(maximum, 4),
        "spread": round(maximum - minimum, 4),
    }


def member_similarity_profiles(
    members: Sequence[str],
    similarity_lookup: dict[tuple[str, str], float],
) -> list[dict[str, object]]:
    profiles: list[dict[str, object]] = []
    for member in members:
        similarities = [
            similarity_lookup.get(normalize_pair(member, other), 0.0)
            for other in members
            if other != member
        ]
        average = round(sum(similarities) / len(similarities), 4) if similarities else 0.0
        profiles.append(
            {
                "memoryId": member,
                "averageSimilarityToCluster": average,
            }
        )
    return profiles


def heterogeneity_reasons_for(
    cluster_size: int,
    distribution: dict[str, float],
    category_mix: Counter[str],
    themes: Sequence[str],
    outliers: Sequence[dict[str, object]],
) -> list[str]:
    reasons: list[str] = []
    if cluster_size >= 10 and distribution["median"] < 0.55:
        reasons.append("large cluster has low median pairwise similarity")
    if distribution["spread"] >= 0.45:
        reasons.append("wide similarity spread suggests chained topical grouping")
    if len(category_mix) > 2:
        reasons.append("cluster mixes more than two memory categories")
    if category_mix:
        dominant_count = category_mix.most_common(1)[0][1]
        if dominant_count / cluster_size < 0.75:
            reasons.append("no dominant category covers at least 75% of the cluster")
    if cluster_size >= 5 and len(themes) < 2:
        reasons.append("few shared terms across a large cluster")
    if outliers:
        reasons.append("one or more memories have low average similarity to the cluster")
    return reasons


def normalize_pair(left: str, right: str) -> tuple[str, str]:
    return tuple(sorted((left, right)))
