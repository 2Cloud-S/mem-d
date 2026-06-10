from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from memd.contracts import (
    AnalysisMetrics,
    CategorizedMemory,
    DuplicateCluster,
    MemoryCategory,
    MemoryRecord,
)


def calculate_metrics(
    records: Sequence[MemoryRecord],
    categories: Sequence[CategorizedMemory],
    clusters: Sequence[DuplicateCluster],
) -> AnalysisMetrics:
    total = len(records)
    duplicate_members = {member for cluster in clusters for member in cluster.members}
    duplicate_count = max(0, len(duplicate_members) - len(clusters))
    duplicate_percentage = _percentage(duplicate_count, total)
    category_counts = Counter(category.category for category in categories)
    largest_cluster = max((len(cluster.members) for cluster in clusters), default=0)
    compression_reasons = (
        f"{len(duplicate_members)} memories appear in duplicate clusters",
        f"{len(clusters)} duplicate clusters were detected",
        (
            f"{duplicate_count} records are estimated removable "
            "if each cluster keeps one representative"
        ),
        f"largest cluster contains {largest_cluster} records",
    )

    return AnalysisMetrics(
        totalMemories=total,
        duplicateCount=duplicate_count,
        duplicatePercentage=duplicate_percentage,
        compressionOpportunity=duplicate_percentage,
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
