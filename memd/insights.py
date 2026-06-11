from __future__ import annotations

from collections.abc import Mapping, Sequence

from memd.contracts import (
    AnalysisMetrics,
    DuplicateCluster,
    Insight,
    InsightSeverity,
    MemoryCategory,
)

SEVERITY_RANK = {
    InsightSeverity.CRITICAL: 5,
    InsightSeverity.HIGH: 4,
    InsightSeverity.MEDIUM: 3,
    InsightSeverity.LOW: 2,
    InsightSeverity.INFO: 1,
}


def generate_analysis_insights(
    metrics: AnalysisMetrics,
    clusters: Sequence[DuplicateCluster],
    validation: Mapping[str, object],
) -> tuple[Insight, ...]:
    insights: list[Insight] = []
    insights.extend(compression_insights(metrics, clusters, validation))
    insights.extend(category_insights(metrics, validation))
    insights.extend(cluster_quality_insights(validation))
    return tuple(rank_insights(insights))


def generate_evaluation_insights(metrics: Mapping[str, object]) -> tuple[Insight, ...]:
    insights: list[Insight] = []
    precision = number(metrics.get("precision"))
    recall = number(metrics.get("recall"))
    f1 = number(metrics.get("f1"))
    purity = number(metrics.get("clusterPurity"))
    coverage = number(metrics.get("clusterCoverage"))
    false_positives = integer(metrics.get("falsePositives"))
    false_negatives = integer(metrics.get("falseNegatives"))

    if precision < 0.9 or false_positives > 0:
        insights.append(
            Insight(
                id="eval-precision-risk",
                title="Clustering precision needs attention",
                severity=InsightSeverity.HIGH,
                explanation=(
                    "The clustering evaluator found false positives or low precision. "
                    "This means unrelated memories may be grouped together."
                ),
                supportingEvidence=(
                    f"precision={precision}",
                    f"false positives={false_positives}",
                    f"cluster purity={purity}",
                ),
                confidence=0.95,
                estimatedImpact=(
                    "Reducing false positives prevents destructive cleanup recommendations."
                ),
                recommendedAction=(
                    "Inspect false-positive examples before lowering thresholds or "
                    "changing embeddings."
                ),
            )
        )
    elif recall < 0.7 or coverage < 0.8:
        insights.append(
            Insight(
                id="eval-recall-gap",
                title="Duplicate detection is still missing near-duplicates",
                severity=InsightSeverity.MEDIUM,
                explanation=(
                    "Precision is high, but recall or coverage is below target. "
                    "The engine is conservative and leaves labelled duplicates unclustered."
                ),
                supportingEvidence=(
                    f"precision={precision}",
                    f"recall={recall}",
                    f"coverage={coverage}",
                    f"false negatives={false_negatives}",
                ),
                confidence=0.9,
                estimatedImpact="Improving recall can surface more cleanup opportunities.",
                recommendedAction=(
                    "Review false-negative examples and evaluate a local embedding model "
                    "or threshold sweep."
                ),
            )
        )

    if f1 > 0:
        insights.append(
            Insight(
                id="eval-baseline-recorded",
                title="Clustering quality baseline is measurable",
                severity=InsightSeverity.INFO,
                explanation=(
                    "A labelled evaluation scorecard is available for future clustering changes."
                ),
                supportingEvidence=(
                    f"f1={f1}",
                    f"precision={precision}",
                    f"recall={recall}",
                ),
                confidence=1.0,
                estimatedImpact="Future clustering changes can be compared objectively.",
                recommendedAction="Keep this evaluation report with the threshold and model used.",
            )
        )

    return tuple(rank_insights(insights))


def compression_insights(
    metrics: AnalysisMetrics,
    clusters: Sequence[DuplicateCluster],
    validation: Mapping[str, object],
) -> list[Insight]:
    insights: list[Insight] = []
    compression = nested(validation, "compressionDrivers")
    largest_drivers = list_value(compression.get("largestClusterDrivers"))
    exact_groups = list_value(nested(validation, "clusterQuality").get("exactDuplicateGroups"))
    largest_cluster = max((len(cluster.members) for cluster in clusters), default=0)
    trusted = metrics.trustedCompressionOpportunity
    unverified = metrics.unverifiedCompressionOpportunity

    if metrics.compressionOpportunity >= 30:
        insights.append(
            Insight(
                id="compression-high",
                title="Prioritize trusted duplicate cleanup",
                severity=InsightSeverity.HIGH,
                explanation=(
                    "A large share of the memory store appears compressible, but only "
                    "high-trust clusters should be used for automatic consolidation."
                ),
                supportingEvidence=(
                    f"compression opportunity={metrics.compressionOpportunity}%",
                    f"trusted compression opportunity={trusted}%",
                    f"unverified compression opportunity={unverified}%",
                    f"duplicate count={metrics.duplicateCount}",
                    f"trusted duplicate count={metrics.trustedDuplicateCount}",
                    f"unverified duplicate count={metrics.unverifiedDuplicateCount}",
                    f"duplicate clusters={len(clusters)}",
                    *metrics.compressionReasons,
                ),
                confidence=0.9,
                estimatedImpact=(
                    f"{metrics.trustedDuplicateCount} records are high-trust consolidation "
                    "candidates; the rest require review."
                ),
                recommendedAction=(
                    "Auto-consolidate only High-trust clusters; manually review Medium and "
                    "Low-trust clusters."
                ),
            )
        )
    elif metrics.compressionOpportunity >= 10:
        insights.append(
            Insight(
                id="compression-moderate",
                title="Review duplicate clusters before cleanup",
                severity=InsightSeverity.MEDIUM,
                explanation="There is meaningful redundancy, but cleanup should be targeted.",
                supportingEvidence=(
                    f"compression opportunity={metrics.compressionOpportunity}%",
                    f"trusted compression opportunity={trusted}%",
                    f"unverified compression opportunity={unverified}%",
                    f"duplicate count={metrics.duplicateCount}",
                    f"duplicate clusters={len(clusters)}",
                ),
                confidence=0.85,
                estimatedImpact=(f"Safely reduce memory volume by up to {trusted}%."),
                recommendedAction=(
                    "Consolidate High-trust clusters first, then inspect unverified clusters."
                ),
            )
        )

    if unverified > trusted and unverified >= 10:
        insights.append(
            Insight(
                id="compression-mostly-unverified",
                title="Most compression opportunity is unverified",
                severity=InsightSeverity.HIGH,
                explanation=(
                    "The headline compression estimate depends more on Medium/Low-trust "
                    "clusters than on High-trust duplicate groups."
                ),
                supportingEvidence=(
                    f"trusted compression opportunity={trusted}%",
                    f"unverified compression opportunity={unverified}%",
                    f"trusted duplicate count={metrics.trustedDuplicateCount}",
                    f"unverified duplicate count={metrics.unverifiedDuplicateCount}",
                ),
                confidence=0.9,
                estimatedImpact="Prevents broad topical clusters from driving unsafe cleanup.",
                recommendedAction=(
                    "Treat unverified compression as a review queue, not an automatic action."
                ),
            )
        )

    if exact_groups:
        largest = exact_groups[0] if isinstance(exact_groups[0], dict) else {}
        insights.append(
            Insight(
                id="exact-duplicates",
                title="Remove exact duplicate memories first",
                severity=(
                    InsightSeverity.HIGH
                    if integer(largest.get("count")) >= 10
                    else InsightSeverity.MEDIUM
                ),
                explanation=(
                    "Exact duplicate groups are low-risk cleanup candidates because their content "
                    "matches after normalization."
                ),
                supportingEvidence=(
                    f"exact duplicate groups={len(exact_groups)}",
                    f"largest exact group size={integer(largest.get('count'))}",
                    f"sample={str(largest.get('content', ''))[:160]}",
                ),
                confidence=0.98,
                estimatedImpact=(
                    "Exact duplicates can usually be collapsed with minimal semantic risk."
                ),
                recommendedAction=(
                    "Deduplicate exact groups before reviewing semantic near-duplicates."
                ),
            )
        )

    if largest_cluster >= max(10, int(metrics.totalMemories * 0.1)):
        insights.append(
            Insight(
                id="large-cluster-driver",
                title="Investigate the largest duplicate cluster",
                severity=InsightSeverity.MEDIUM,
                explanation=(
                    "One cluster is large enough to dominate the compression estimate. "
                    "If it is correct, it is a major cleanup target; if not, it may be "
                    "over-clustering."
                ),
                supportingEvidence=(
                    f"largest cluster size={largest_cluster}",
                    f"total memories={metrics.totalMemories}",
                    *driver_evidence(largest_drivers),
                ),
                confidence=0.8,
                estimatedImpact=(
                    "Validating one large cluster can confirm or reduce the headline estimate."
                ),
                recommendedAction=(
                    "Open the largest cluster and verify all records share the same meaning."
                ),
            )
        )

    return insights


def category_insights(
    metrics: AnalysisMetrics,
    validation: Mapping[str, object],
) -> list[Insight]:
    insights: list[Insight] = []
    category_quality = nested(validation, "categoryQuality")
    consistency = nested(category_quality, "categoryConsistency")
    unknown_count = integer(category_quality.get("unknownCount"))
    unknown_percentage = number(category_quality.get("unknownPercentage"))
    total = metrics.totalMemories

    if unknown_percentage >= 15:
        severity = InsightSeverity.HIGH
    elif unknown_percentage >= 8:
        severity = InsightSeverity.MEDIUM
    else:
        severity = InsightSeverity.LOW

    if unknown_count:
        samples = list_value(category_quality.get("unknownSamples"))
        evidence = [
            f"unknown memories={unknown_count}",
            f"unknown percentage={unknown_percentage}%",
        ]
        for sample in samples[:3]:
            if isinstance(sample, dict):
                evidence.append(f"{sample.get('memoryId')}: {sample.get('content')}")
        insights.append(
            Insight(
                id="unknown-category-review",
                title="Review Unknown memories for missed patterns",
                severity=severity,
                explanation=(
                    "Unknown memories are not necessarily bad, but repeated Unknown patterns "
                    "indicate "
                    "classification blind spots or memory types that need explicit handling."
                ),
                supportingEvidence=tuple(evidence),
                confidence=0.85,
                estimatedImpact=(
                    f"Classifying {unknown_count} Unknown memories would improve "
                    "composition metrics "
                    "and downstream recommendations."
                ),
                recommendedAction=(
                    "Sample Unknown records and decide whether to add rules or leave them "
                    "as edge cases."
                ),
            )
        )

    dominant_category, dominant_count = dominant_category_count(metrics.categoryBreakdown)
    if total and dominant_count / total >= 0.5:
        insights.append(
            Insight(
                id="category-imbalance",
                title=f"Memory store is dominated by {dominant_category.value} records",
                severity=InsightSeverity.LOW,
                explanation=(
                    "A single category dominates the store. This can be legitimate, but it "
                    "may also "
                    "show that one memory type is accumulating faster than others."
                ),
                supportingEvidence=(
                    f"{dominant_category.value} count={dominant_count}",
                    f"total memories={total}",
                    f"share={round((dominant_count / total) * 100, 2)}%",
                ),
                confidence=0.75,
                estimatedImpact=(
                    "Category balance helps identify which cleanup workflow matters most."
                ),
                recommendedAction=(
                    "Review whether this category should have tighter retention or "
                    "deduplication rules."
                ),
            )
        )

    conflict_count = integer(consistency.get("conflictClusterCount"))
    reclassification_count = integer(consistency.get("reclassificationOpportunityCount"))
    agreement_rate = number_or_default(consistency.get("categoryAgreementRate"), 100.0)
    recurring = list_value(consistency.get("recurringConflicts"))
    priority = list_value(consistency.get("priorityConflicts"))
    if conflict_count:
        first_conflict = recurring[0] if recurring and isinstance(recurring[0], dict) else {}
        categories = first_conflict.get("categories", [])
        category_label = " vs ".join(str(category) for category in categories)
        severity = (
            InsightSeverity.HIGH
            if priority or agreement_rate < 80
            else InsightSeverity.MEDIUM
        )
        insights.append(
            Insight(
                id="category-consistency-conflicts",
                title="Review category disagreements inside duplicate clusters",
                severity=severity,
                explanation=(
                    "Some highly similar memories disagree on category. This suggests taxonomy "
                    "quality is less reliable than clustering evidence for those records."
                ),
                supportingEvidence=(
                    f"category agreement rate={agreement_rate}%",
                    f"conflict clusters={conflict_count}",
                    f"reclassification opportunities={reclassification_count}",
                    f"top recurring conflict={category_label}",
                    f"priority conflicts={len(priority)}",
                ),
                confidence=0.88,
                estimatedImpact=(
                    f"{reclassification_count} memories may need taxonomy review."
                ),
                recommendedAction=(
                    "Inspect reclassification candidates, especially Fact vs Preference vs "
                    "Unknown conflicts; do not change labels automatically."
                ),
            )
        )

    return insights


def cluster_quality_insights(validation: Mapping[str, object]) -> list[Insight]:
    insights: list[Insight] = []
    cluster_quality = nested(validation, "clusterQuality")
    possible_false_positives = list_value(cluster_quality.get("possibleFalsePositiveClusters"))
    over_clustering = list_value(cluster_quality.get("overClusteringCandidates"))
    contamination = list_value(cluster_quality.get("clusterContamination"))

    if possible_false_positives or over_clustering or contamination:
        candidates = possible_false_positives or over_clustering or contamination
        first = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
        insights.append(
            Insight(
                id="cluster-quality-review",
                title="Review cluster quality before trusting compression estimates",
                severity=InsightSeverity.MEDIUM,
                explanation=(
                    "Some clusters may be broad topical groups rather than true duplicate "
                    "sets. They may still be useful, but should not drive automatic cleanup."
                ),
                supportingEvidence=(
                    f"possible false-positive clusters={len(possible_false_positives)}",
                    f"over-clustering candidates={len(over_clustering)}",
                    f"contamination candidates={len(contamination)}",
                    f"first candidate={first.get('clusterId', '')}",
                    f"average similarity={first.get('averageSimilarity', '')}",
                ),
                confidence=0.8,
                estimatedImpact=(
                    "Manual review determines whether compression estimates are trustworthy."
                ),
                recommendedAction=(
                    "Audit the largest heterogeneous clusters before using them for cleanup."
                ),
            )
        )

    return insights


def rank_insights(insights: Sequence[Insight]) -> list[Insight]:
    return sorted(
        insights,
        key=lambda insight: (
            -SEVERITY_RANK[insight.severity],
            -impact_rank(insight.estimatedImpact),
            -insight.confidence,
            insight.id,
        ),
    )


def impact_rank(impact: str) -> int:
    digits = "".join(character if character.isdigit() else " " for character in impact)
    values = [int(value) for value in digits.split() if value.isdigit()]
    return max(values, default=0)


def nested(mapping: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = mapping.get(key)
    if isinstance(value, Mapping):
        return value
    return {}


def list_value(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return []


def number(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def number_or_default(value: object, default: float) -> float:
    if isinstance(value, int | float):
        return float(value)
    return default


def integer(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def dominant_category_count(
    category_breakdown: Mapping[MemoryCategory, int],
) -> tuple[MemoryCategory, int]:
    if not category_breakdown:
        return MemoryCategory.UNKNOWN, 0
    return max(category_breakdown.items(), key=lambda item: item[1])


def driver_evidence(drivers: Sequence[object]) -> tuple[str, ...]:
    if not drivers or not isinstance(drivers[0], dict):
        return ()
    driver = drivers[0]
    return (
        f"largest driver={driver.get('clusterId', '')}",
        f"driver size={driver.get('size', '')}",
        f"shared terms={', '.join(str(term) for term in driver.get('sharedTerms', []))}",
    )
