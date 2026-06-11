from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from memd.contracts import CategorizedMemory, DuplicateCluster, MemoryCategory, MemoryRecord

PRIORITY_CONFLICTS = {
    frozenset((MemoryCategory.FACT, MemoryCategory.PREFERENCE)),
    frozenset((MemoryCategory.FACT, MemoryCategory.UNKNOWN)),
    frozenset((MemoryCategory.PREFERENCE, MemoryCategory.UNKNOWN)),
}


def audit_category_consistency(
    records: Sequence[MemoryRecord],
    categories: Sequence[CategorizedMemory],
    clusters: Sequence[DuplicateCluster],
) -> dict[str, object]:
    records_by_id = {record.id: record for record in records}
    categories_by_id = {category.memoryId: category for category in categories}
    cluster_audits = [
        audit_cluster_categories(cluster, records_by_id, categories_by_id)
        for cluster in clusters
    ]
    conflicts = [audit for audit in cluster_audits if audit["hasCategoryConflict"]]
    candidates = [
        candidate
        for audit in conflicts
        for candidate in audit["reclassificationCandidates"]
        if isinstance(candidate, dict)
    ]
    agreement_rate = category_agreement_rate(cluster_audits)

    return {
        "categoryAgreementRate": agreement_rate,
        "clustersAnalyzed": len(cluster_audits),
        "conflictClusterCount": len(conflicts),
        "reclassificationOpportunityCount": len(candidates),
        "conflictRate": percentage(len(conflicts), len(cluster_audits)),
        "conflictClusters": conflicts[:20],
        "reclassificationCandidates": candidates[:50],
        "recurringConflicts": recurring_conflicts(conflicts),
        "priorityConflicts": [
            conflict
            for conflict in recurring_conflicts(conflicts)
            if conflict.get("isPriorityConflict")
        ],
    }


def audit_cluster_categories(
    cluster: DuplicateCluster,
    records_by_id: dict[str, MemoryRecord],
    categories_by_id: dict[str, CategorizedMemory],
) -> dict[str, object]:
    member_categories = [
        categories_by_id[member]
        for member in cluster.members
        if member in categories_by_id
    ]
    category_mix = Counter(category.category for category in member_categories)
    dominant_category, dominant_count = dominant_category_for(category_mix)
    minority_categories = [
        {
            "category": category.value,
            "count": count,
        }
        for category, count in category_mix.most_common()
        if category != dominant_category
    ]
    candidates = reclassification_candidates(
        cluster=cluster,
        records_by_id=records_by_id,
        categories_by_id=categories_by_id,
        dominant_category=dominant_category,
    )

    return {
        "clusterId": cluster.clusterId,
        "size": len(cluster.members),
        "averageSimilarity": cluster.averageSimilarity,
        "trustLevel": cluster.trustLevel.value,
        "categoryAgreementRate": percentage(dominant_count, len(member_categories)),
        "dominantCategory": dominant_category.value if dominant_category else "",
        "dominantCategoryCount": dominant_count,
        "minorityCategories": minority_categories,
        "categoryMix": {
            category.value: count
            for category, count in category_mix.items()
        },
        "hasCategoryConflict": len(category_mix) > 1,
        "conflictPairs": conflict_pairs(category_mix),
        "reclassificationCandidates": candidates,
    }


def reclassification_candidates(
    cluster: DuplicateCluster,
    records_by_id: dict[str, MemoryRecord],
    categories_by_id: dict[str, CategorizedMemory],
    dominant_category: MemoryCategory | None,
) -> list[dict[str, object]]:
    if dominant_category is None:
        return []

    candidates: list[dict[str, object]] = []
    for member in cluster.members:
        category = categories_by_id.get(member)
        record = records_by_id.get(member)
        if category is None or record is None or category.category == dominant_category:
            continue
        candidates.append(
            {
                "clusterId": cluster.clusterId,
                "memoryId": member,
                "content": record.content,
                "currentCategory": category.category.value,
                "suggestedCategory": dominant_category.value,
                "categoryConfidence": category.confidence,
                "categoryReason": category.reason,
                "clusterAverageSimilarity": cluster.averageSimilarity,
                "clusterTrustLevel": cluster.trustLevel.value,
                "reason": (
                    "Memory is in a duplicate cluster whose dominant category is "
                    f"{dominant_category.value}."
                ),
            }
        )
    return candidates


def category_agreement_rate(cluster_audits: Sequence[dict[str, object]]) -> float:
    total_members = sum(int_value(audit.get("size")) for audit in cluster_audits)
    agreed_members = sum(
        int_value(audit.get("dominantCategoryCount"))
        for audit in cluster_audits
    )
    return percentage(agreed_members, total_members)


def conflict_pairs(category_mix: Counter[MemoryCategory]) -> list[dict[str, object]]:
    categories = list(category_mix)
    pairs: list[dict[str, object]] = []
    for index, left in enumerate(categories):
        for right in categories[index + 1 :]:
            pair = frozenset((left, right))
            pairs.append(
                {
                    "categories": [left.value, right.value],
                    "isPriorityConflict": pair in PRIORITY_CONFLICTS,
                }
            )
    return pairs


def recurring_conflicts(conflicts: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    counter: Counter[tuple[str, str]] = Counter()
    priority: dict[tuple[str, str], bool] = {}
    for conflict in conflicts:
        for pair in conflict.get("conflictPairs", []):
            if not isinstance(pair, dict):
                continue
            categories = pair.get("categories", [])
            if not isinstance(categories, list) or len(categories) != 2:
                continue
            key = tuple(sorted(str(category) for category in categories))
            counter[key] += 1
            priority[key] = bool(pair.get("isPriorityConflict"))
    return [
        {
            "categories": list(categories),
            "clusterCount": count,
            "isPriorityConflict": priority.get(categories, False),
        }
        for categories, count in counter.most_common(10)
    ]


def dominant_category_for(
    category_mix: Counter[MemoryCategory],
) -> tuple[MemoryCategory | None, int]:
    if not category_mix:
        return None, 0
    return category_mix.most_common(1)[0]


def percentage(part: int, whole: int) -> float:
    if whole == 0:
        return 0.0
    return round((part / whole) * 100, 2)


def int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0
