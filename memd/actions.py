from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from memd.contracts import (
    ActionPlanSummary,
    ActionPriority,
    ActionType,
    CategorizedMemory,
    ClusterTrustLevel,
    DuplicateCluster,
    GovernanceAction,
    Insight,
    InsightSeverity,
    MemoryCategory,
)

INSIGHT_PRIORITY = {
    InsightSeverity.CRITICAL: ActionPriority.CRITICAL,
    InsightSeverity.HIGH: ActionPriority.HIGH,
    InsightSeverity.MEDIUM: ActionPriority.MEDIUM,
    InsightSeverity.LOW: ActionPriority.LOW,
    InsightSeverity.INFO: ActionPriority.DEFERRED,
}


def plan_governance_actions(
    clusters: Sequence[DuplicateCluster],
    categories: Sequence[CategorizedMemory],
    validation: Mapping[str, object],
    insights: Sequence[Insight],
) -> tuple[tuple[GovernanceAction, ...], ActionPlanSummary]:
    insights_by_id = {insight.id: insight for insight in insights}
    categories_by_id = {category.memoryId: category for category in categories}
    cluster_quality = nested(validation, "clusterQuality")
    category_quality = nested(validation, "categoryQuality")
    consistency = nested(category_quality, "categoryConsistency")
    contaminated = keyed_by_cluster_id(list_value(cluster_quality.get("clusterContamination")))
    overclustered = keyed_by_cluster_id(list_value(cluster_quality.get("overClusteringCandidates")))

    actions: list[GovernanceAction] = []
    for cluster in clusters:
        if cluster.trustLevel == ClusterTrustLevel.HIGH:
            actions.append(
                merge_action(
                    cluster,
                    categories_by_id,
                    insights_by_id,
                )
            )
        if cluster.clusterId in overclustered:
            actions.append(
                overclustered_action(cluster, overclustered[cluster.clusterId], insights_by_id)
            )
        elif cluster.trustLevel != ClusterTrustLevel.HIGH or cluster.clusterId in contaminated:
            actions.append(
                review_cluster_action(
                    cluster,
                    contaminated.get(cluster.clusterId, {}),
                    insights_by_id,
                )
            )

    for conflict in list_value(consistency.get("conflictClusters")):
        if isinstance(conflict, dict):
            actions.append(category_conflict_action(conflict, insights_by_id))

    unknown_samples = list_value(category_quality.get("unknownSamples"))
    if unknown_samples:
        actions.append(unknown_memory_action(category_quality, insights_by_id))

    for insight in insights:
        if insight.severity in {InsightSeverity.LOW, InsightSeverity.INFO}:
            actions.append(ignore_low_value_action(insight))

    ranked = tuple(sorted(actions, key=action_sort_key))
    return ranked, summarize_actions(ranked)


def merge_action(
    cluster: DuplicateCluster,
    categories_by_id: Mapping[str, CategorizedMemory],
    insights_by_id: Mapping[str, Insight],
) -> GovernanceAction:
    category = dominant_category(cluster, categories_by_id)
    action_type = (
        ActionType.CONSOLIDATE_PREFERENCES
        if category == MemoryCategory.PREFERENCE
        else ActionType.MERGE_CLUSTER
    )
    priority = priority_from_insight(
        insights_by_id,
        "compression-high",
        default=ActionPriority.HIGH if cluster.trustScore >= 0.9 else ActionPriority.MEDIUM,
    )
    return GovernanceAction(
        actionId=stable_action_id(action_type, cluster.clusterId),
        actionType=action_type,
        target={
            "clusterId": cluster.clusterId,
            "members": list(cluster.members),
            "removableRecords": removable_records(cluster),
        },
        title=f"Consolidate high-trust duplicate cluster {cluster.clusterId}",
        rationale=(
            "The cluster is High trust and can be treated as a consolidation candidate "
            "without changing clustering or category assignments."
        ),
        supportingEvidence=(
            f"trust level={cluster.trustLevel.value}",
            f"trust score={cluster.trustScore}",
            f"average similarity={cluster.averageSimilarity}",
            f"members={len(cluster.members)}",
            *cluster.trustReasons,
        ),
        trustLevel=cluster.trustLevel,
        confidence=cluster.trustScore,
        estimatedImpact=f"May safely remove {removable_records(cluster)} duplicate records.",
        requiresHumanApproval=False,
        priority=priority,
        sourceSignals=(
            "cluster_trust",
            "duplicate_cluster",
            "insights.compression",
        ),
    )


def review_cluster_action(
    cluster: DuplicateCluster,
    contamination: Mapping[str, object],
    insights_by_id: Mapping[str, Insight],
) -> GovernanceAction:
    contamination_score = number(contamination.get("contaminationScore"))
    priority = (
        ActionPriority.HIGH
        if cluster.trustLevel == ClusterTrustLevel.LOW or contamination_score >= 0.15
        else priority_from_insight(insights_by_id, "cluster-quality-review")
    )
    evidence = [
        f"trust level={cluster.trustLevel.value}",
        f"trust score={cluster.trustScore}",
        f"average similarity={cluster.averageSimilarity}",
        f"members={len(cluster.members)}",
        *cluster.trustReasons,
    ]
    if contamination:
        evidence.append(f"contamination score={contamination_score}")
    return GovernanceAction(
        actionId=stable_action_id(ActionType.REVIEW_CLUSTER, cluster.clusterId),
        actionType=ActionType.REVIEW_CLUSTER,
        target={
            "clusterId": cluster.clusterId,
            "members": list(cluster.members),
            "removableRecords": removable_records(cluster),
        },
        title=f"Review duplicate cluster {cluster.clusterId} before consolidation",
        rationale=(
            "The cluster is not safe enough for automatic consolidation or contains "
            "contamination signals."
        ),
        supportingEvidence=tuple(evidence),
        trustLevel=cluster.trustLevel,
        confidence=max(0.0, round(cluster.trustScore - contamination_score, 4)),
        estimatedImpact=(
            f"Could save {removable_records(cluster)} records if validated, but remains "
            "unverified."
        ),
        requiresHumanApproval=True,
        priority=priority,
        sourceSignals=(
            "cluster_trust",
            "cluster_audit.contamination",
            "insights.cluster_quality",
        ),
    )


def overclustered_action(
    cluster: DuplicateCluster,
    audit: Mapping[str, object],
    insights_by_id: Mapping[str, Insight],
) -> GovernanceAction:
    reasons = list_value(audit.get("heterogeneityReasons"))
    priority = priority_from_insight(insights_by_id, "cluster-quality-review")
    return GovernanceAction(
        actionId=stable_action_id(ActionType.REVIEW_OVERCLUSTERED_GROUP, cluster.clusterId),
        actionType=ActionType.REVIEW_OVERCLUSTERED_GROUP,
        target={
            "clusterId": cluster.clusterId,
            "members": list(cluster.members),
            "removableRecords": removable_records(cluster),
        },
        title=f"Review possible over-clustered group {cluster.clusterId}",
        rationale=(
            "The cluster audit suggests this group may represent broad topical similarity "
            "instead of one duplicate concept."
        ),
        supportingEvidence=(
            f"concept assessment={audit.get('conceptAssessment', '')}",
            f"contamination score={audit.get('contaminationScore', 0)}",
            f"trust level={cluster.trustLevel.value}",
            *[str(reason) for reason in reasons],
        ),
        trustLevel=cluster.trustLevel,
        confidence=cluster.trustScore,
        estimatedImpact=(
            f"Prevents unsafe consolidation of {removable_records(cluster)} possible records."
        ),
        requiresHumanApproval=True,
        priority=priority,
        sourceSignals=(
            "cluster_audit.over_clustering",
            "cluster_trust",
            "insights.cluster_quality",
        ),
    )


def category_conflict_action(
    conflict: Mapping[str, object],
    insights_by_id: Mapping[str, Insight],
) -> GovernanceAction:
    candidates = list_value(conflict.get("reclassificationCandidates"))
    priority = priority_from_insight(insights_by_id, "category-consistency-conflicts")
    return GovernanceAction(
        actionId=stable_action_id(
            ActionType.REVIEW_CATEGORY_CONFLICT,
            str(conflict.get("clusterId", "unknown")),
        ),
        actionType=ActionType.REVIEW_CATEGORY_CONFLICT,
        target={
            "clusterId": conflict.get("clusterId", ""),
            "dominantCategory": conflict.get("dominantCategory", ""),
            "minorityCategories": conflict.get("minorityCategories", []),
            "candidateMemoryIds": [
                candidate.get("memoryId")
                for candidate in candidates
                if isinstance(candidate, dict)
            ],
        },
        title=f"Review category disagreement in {conflict.get('clusterId', '')}",
        rationale=(
            "Highly similar memories in the same duplicate cluster disagree on category, "
            "which indicates a taxonomy reliability issue."
        ),
        supportingEvidence=(
            f"dominant category={conflict.get('dominantCategory', '')}",
            f"category agreement rate={conflict.get('categoryAgreementRate', 0)}%",
            f"category mix={conflict.get('categoryMix', {})}",
            f"reclassification candidates={len(candidates)}",
        ),
        trustLevel=None,
        confidence=0.88,
        estimatedImpact=f"Review {len(candidates)} possible category corrections.",
        requiresHumanApproval=True,
        priority=priority,
        sourceSignals=(
            "category_consistency",
            "duplicate_cluster",
            "insights.category_consistency",
        ),
    )


def unknown_memory_action(
    category_quality: Mapping[str, object],
    insights_by_id: Mapping[str, Insight],
) -> GovernanceAction:
    samples = [
        sample
        for sample in list_value(category_quality.get("unknownSamples"))
        if isinstance(sample, dict)
    ]
    unknown_count = integer(category_quality.get("unknownCount"))
    priority = priority_from_insight(insights_by_id, "unknown-category-review")
    return GovernanceAction(
        actionId=stable_action_id(ActionType.REVIEW_UNKNOWN_MEMORY, "unknown-category-samples"),
        actionType=ActionType.REVIEW_UNKNOWN_MEMORY,
        target={
            "memoryIds": [sample.get("memoryId") for sample in samples[:20]],
            "sampleCount": len(samples[:20]),
            "unknownCount": unknown_count,
        },
        title="Review Unknown-category memories",
        rationale=(
            "Unknown categories indicate records that did not match current V1 taxonomy "
            "heuristics and may need classification review."
        ),
        supportingEvidence=(
            f"unknown memories={unknown_count}",
            f"unknown percentage={category_quality.get('unknownPercentage', 0)}%",
            *[
                f"{sample.get('memoryId')}: {sample.get('content', '')}"
                for sample in samples[:3]
            ],
        ),
        trustLevel=None,
        confidence=0.85,
        estimatedImpact=f"Review {unknown_count} uncategorized memories.",
        requiresHumanApproval=True,
        priority=priority,
        sourceSignals=(
            "category_quality.unknown",
            "insights.unknown_category",
        ),
    )


def ignore_low_value_action(insight: Insight) -> GovernanceAction:
    return GovernanceAction(
        actionId=stable_action_id(ActionType.IGNORE_LOW_VALUE_ISSUE, insight.id),
        actionType=ActionType.IGNORE_LOW_VALUE_ISSUE,
        target={"insightId": insight.id},
        title=f"Defer low-priority issue: {insight.title}",
        rationale=(
            "The issue is informational or low severity and does not need immediate "
            "governance action."
        ),
        supportingEvidence=insight.supportingEvidence,
        trustLevel=None,
        confidence=insight.confidence,
        estimatedImpact=insight.estimatedImpact,
        requiresHumanApproval=False,
        priority=INSIGHT_PRIORITY[insight.severity],
        sourceSignals=("insights.low_priority",),
    )


def summarize_actions(actions: Sequence[GovernanceAction]) -> ActionPlanSummary:
    priority_counts = Counter(action.priority for action in actions)
    trusted_savings = sum(
        integer(action.target.get("removableRecords"))
        for action in actions
        if not action.requiresHumanApproval
        and action.actionType
        in {ActionType.MERGE_CLUSTER, ActionType.CONSOLIDATE_PREFERENCES}
    )
    unverified_savings = sum(
        integer(action.target.get("removableRecords"))
        for action in actions
        if action.requiresHumanApproval
    )
    return ActionPlanSummary(
        totalActions=len(actions),
        safeActions=sum(1 for action in actions if not action.requiresHumanApproval),
        reviewActions=sum(1 for action in actions if action.requiresHumanApproval),
        estimatedTrustedSavings=trusted_savings,
        estimatedUnverifiedSavings=unverified_savings,
        actionsByPriority={
            priority: priority_counts.get(priority, 0)
            for priority in ActionPriority
        },
    )


def dominant_category(
    cluster: DuplicateCluster,
    categories_by_id: Mapping[str, CategorizedMemory],
) -> MemoryCategory | None:
    counter = Counter(
        categories_by_id[member].category
        for member in cluster.members
        if member in categories_by_id
    )
    if not counter:
        return None
    return counter.most_common(1)[0][0]


def stable_action_id(action_type: ActionType, target_id: str) -> str:
    safe_target = target_id.lower().replace(" ", "-").replace("_", "-")
    return f"{action_type.value}:{safe_target}"


def removable_records(cluster: DuplicateCluster) -> int:
    return max(0, len(cluster.members) - 1)


def priority_from_insight(
    insights_by_id: Mapping[str, Insight],
    insight_id: str,
    default: ActionPriority = ActionPriority.MEDIUM,
) -> ActionPriority:
    insight = insights_by_id.get(insight_id)
    if insight is None:
        return default
    return INSIGHT_PRIORITY[insight.severity]


def action_sort_key(action: GovernanceAction) -> tuple[int, bool, str]:
    return (
        priority_rank(action.priority),
        action.requiresHumanApproval,
        action.actionId,
    )


def priority_rank(priority: ActionPriority) -> int:
    ranks = {
        ActionPriority.CRITICAL: 0,
        ActionPriority.HIGH: 1,
        ActionPriority.MEDIUM: 2,
        ActionPriority.LOW: 3,
        ActionPriority.DEFERRED: 4,
    }
    return ranks[priority]


def keyed_by_cluster_id(items: Sequence[object]) -> dict[str, Mapping[str, object]]:
    keyed: dict[str, Mapping[str, object]] = {}
    for item in items:
        if isinstance(item, Mapping):
            cluster_id = item.get("clusterId")
            if isinstance(cluster_id, str):
                keyed[cluster_id] = item
    return keyed


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


def integer(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0
