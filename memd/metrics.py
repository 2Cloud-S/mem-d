from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from memd.contracts import (
    AnalysisMetrics,
    CategorizedMemory,
    ClusterTrustLevel,
    DuplicateCluster,
    MemoryCategory,
    MemoryRecord,
)


def calculate_metrics(
    records: Sequence[MemoryRecord],
    categories: Sequence[CategorizedMemory],
    clusters: Sequence[DuplicateCluster],
    category_consistency: Mapping[str, object] | None = None,
) -> AnalysisMetrics:
    total = len(records)
    duplicate_members = {member for cluster in clusters for member in cluster.members}
    duplicate_count = max(0, len(duplicate_members) - len(clusters))
    trusted_duplicate_count = sum(
        max(0, len(cluster.members) - 1)
        for cluster in clusters
        if cluster.trustLevel == ClusterTrustLevel.HIGH
    )
    unverified_duplicate_count = max(0, duplicate_count - trusted_duplicate_count)
    duplicate_percentage = _percentage(duplicate_count, total)
    trusted_percentage = _percentage(trusted_duplicate_count, total)
    unverified_percentage = _percentage(unverified_duplicate_count, total)
    category_counts = Counter(category.category for category in categories)
    largest_cluster = max((len(cluster.members) for cluster in clusters), default=0)
    trusted_clusters = sum(
        1
        for cluster in clusters
        if cluster.trustLevel == ClusterTrustLevel.HIGH
    )
    compression_reasons = (
        f"{len(duplicate_members)} memories appear in duplicate clusters",
        f"{len(clusters)} duplicate clusters were detected",
        f"{trusted_clusters} clusters are high-trust automatic consolidation candidates",
        (
            f"{duplicate_count} records are estimated removable "
            "if each cluster keeps one representative"
        ),
        f"{trusted_duplicate_count} removable records are trusted",
        f"{unverified_duplicate_count} removable records require manual review",
        f"largest cluster contains {largest_cluster} records",
    )
    consistency = category_consistency or {}

    return AnalysisMetrics(
        totalMemories=total,
        duplicateCount=duplicate_count,
        duplicatePercentage=duplicate_percentage,
        compressionOpportunity=duplicate_percentage,
        trustedDuplicateCount=trusted_duplicate_count,
        unverifiedDuplicateCount=unverified_duplicate_count,
        trustedCompressionOpportunity=trusted_percentage,
        unverifiedCompressionOpportunity=unverified_percentage,
        categoryAgreementRate=number(consistency.get("categoryAgreementRate"), 100.0),
        reclassificationOpportunityCount=integer(
            consistency.get("reclassificationOpportunityCount")
        ),
        categoryBreakdown={
            category: category_counts.get(category, 0)
            for category in MemoryCategory
        },
        compressionReasons=compression_reasons,
    )


def _percentage(part: int, whole: int) -> float:
    if whole == 0:
        return 0.0
    return round((part / whole) * 100, 2)


def number(value: object, default: float = 0.0) -> float:
    if isinstance(value, int | float):
        return float(value)
    return default


def integer(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0
