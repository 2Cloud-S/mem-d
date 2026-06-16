from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from memd.contracts import (
    ActionPriority,
    ActionType,
    AnalysisMetrics,
    AffectedMemory,
    ClusterTrustLevel,
    DuplicateCluster,
    GovernanceAction,
    Insight,
    MemoryRecord,
    MemoryResolution,
    PolicyDecision,
    Recommendation,
    RecommendationAction,
    RecommendationEvidence,
    RecommendationSummary,
)

MERGE_MIN_CONFIDENCE = 0.80
ARCHIVE_MIN_CONFIDENCE = 0.70
KEEP_MIN_CONFIDENCE = 0.75
REVIEW_AMBIGUITY_CAP = 0.60

ARCHIVE_ELIGIBLE_STATES = frozenset(
    {"Deprecated", "Superseded", "Historical", "Temporary", "Completed"}
)

PRECEDENCE_RANK = {
    RecommendationAction.REVIEW: 0,
    RecommendationAction.ARCHIVE: 1,
    RecommendationAction.MERGE: 2,
    RecommendationAction.KEEP: 3,
    RecommendationAction.DEFER: 4,
}

SIGNAL_SEVERITY = {
    "policy.blocked": 5,
    "lifecycle.alternate": 4,
    "cluster.trust.low": 3,
    "taxonomy.conflict": 2,
    "unknown.category": 1,
}

SOURCE_PRIORITY = {
    "governance_action": 0,
    "policy": 1,
    "memory_lifecycle": 2,
    "memory_evolution": 3,
    "cluster_trust": 4,
    "cluster_audit": 5,
    "category_quality": 6,
    "compression_metrics": 7,
    "absence": 8,
    "conflict_resolution": 9,
}

MERGE_ACTION_TYPES = {ActionType.MERGE_CLUSTER, ActionType.CONSOLIDATE_PREFERENCES}
REVIEW_ACTION_TYPES = {
    ActionType.REVIEW_CLUSTER,
    ActionType.REVIEW_OVERCLUSTERED_GROUP,
    ActionType.REVIEW_CATEGORY_CONFLICT,
    ActionType.REVIEW_UNKNOWN_MEMORY,
}


@dataclass
class RecommendationCandidate:
    action: RecommendationAction
    confidence: float
    role: str = ""
    lifecycle_state: str = ""
    source: str = ""
    signal: str = ""
    severity: int = 0
    action_id: str = ""
    rule_id: str = ""
    case_id: str = ""
    cluster_id: str = ""
    subtype: str = ""
    priority: ActionPriority = ActionPriority.MEDIUM
    requires_human_approval: bool = True
    evidence: list[RecommendationEvidence] = field(default_factory=list)
    modifiers: list[str] = field(default_factory=list)
    disqualified: bool = False


def plan_recommendations(
    memories: Sequence[MemoryRecord],
    clusters: Sequence[DuplicateCluster],
    validation: Mapping[str, object],
    insights: Sequence[Insight],
    actions: Sequence[GovernanceAction],
    *,
    metrics: AnalysisMetrics | None = None,
    include_keep: bool = False,
    include_deferred: bool = False,
) -> tuple[tuple[Recommendation, ...], tuple[MemoryResolution, ...], RecommendationSummary]:
    records_by_id = {memory.id: memory for memory in memories}
    lifecycle_by_id = lifecycle_assignments_by_id(validation)
    cluster_by_member = cluster_membership_map(clusters)
    clusters_by_id = {cluster.clusterId: cluster for cluster in clusters}
    unknown_ids = unknown_memory_ids(validation)
    taxonomy_ids = taxonomy_conflict_memory_ids(validation)
    context = _RecommendationContext(
        records_by_id=records_by_id,
        lifecycle_by_id=lifecycle_by_id,
        cluster_by_member=cluster_by_member,
        clusters_by_id=clusters_by_id,
        unknown_ids=unknown_ids,
        taxonomy_ids=taxonomy_ids,
        validation=validation,
        actions=actions,
        insights=insights,
        metrics=metrics,
        include_keep=include_keep,
    )

    memory_ids = sorted(records_by_id)
    resolutions: list[MemoryResolution] = []
    for memory_id in memory_ids:
        candidates = collect_candidates(memory_id, context)
        resolution = resolve_memory_conflicts(memory_id, candidates, context)
        resolutions.append(resolution)

    recommendations = build_group_recommendations(
        resolutions,
        context,
        include_keep=include_keep,
        include_deferred=include_deferred,
    )
    recommendations = tuple(
        recommendation
        for recommendation in recommendations
        if recommendation_has_evidence(recommendation)
    )
    summary = summarize_recommendations(recommendations, resolutions)
    return tuple(recommendations), tuple(resolutions), summary


def collect_candidates(
    memory_id: str,
    context: _RecommendationContext,
) -> list[RecommendationCandidate]:
    candidates: list[RecommendationCandidate] = []
    candidates.extend(lifecycle_candidates(memory_id, context))
    candidates.extend(governance_candidates(memory_id, context))
    candidates.extend(category_candidates(memory_id, context))
    if not candidates and context.include_keep:
        candidates.extend(absence_keep_candidate(memory_id, context))
    return candidates


def resolve_memory_conflicts(
    memory_id: str,
    candidates: Sequence[RecommendationCandidate],
    context: _RecommendationContext,
) -> MemoryResolution:
    working = [candidate for candidate in candidates if not candidate.disqualified]
    apply_modifiers(memory_id, working, context)

    active = [candidate for candidate in working if not candidate.disqualified]
    if not active:
        return default_resolution(memory_id, context)

    distinct_actions = {candidate.action for candidate in active}
    suppressed: list[RecommendationAction] = []

    if len(distinct_actions) == 1:
        winner = pick_best_candidate(active)
    else:
        winner, losers = resolve_distinct_candidates(active)
        suppressed.extend(loser.action for loser in losers)

    has_archive = RecommendationAction.ARCHIVE in distinct_actions
    has_merge = RecommendationAction.MERGE in distinct_actions
    conflict_detected = False
    if has_archive and has_merge:
        winner, conflict_detected, conflict_suppressed = escalation_review_conflict(
            memory_id, active, context
        )
        suppressed.extend(conflict_suppressed)

    recommendation_id = stable_recommendation_id(winner, memory_id)
    confidence = winner.confidence
    if any(
        modifier in winner.modifiers
        for modifier in ("lifecycle.alternate", "archive_merge_conflict")
    ):
        confidence = min(confidence, REVIEW_AMBIGUITY_CAP)

    suppressed_unique = tuple(dict.fromkeys(suppressed))
    return MemoryResolution(
        memoryId=memory_id,
        resolvedAction=winner.action,
        role=winner.role,
        confidence=round(confidence, 4),
        recommendationId=recommendation_id,
        suppressedActions=suppressed_unique,
        conflictDetected=conflict_detected,
    )


def apply_modifiers(
    memory_id: str,
    candidates: list[RecommendationCandidate],
    context: _RecommendationContext,
) -> None:
    lifecycle = context.lifecycle_by_id.get(memory_id, {})
    if lifecycle.get("alternateLifecycleSignals"):
        inject_review_modifier(
            candidates,
            memory_id,
            context,
            modifier="lifecycle.alternate",
            subtype="lifecycle_ambiguity",
            severity=SIGNAL_SEVERITY["lifecycle.alternate"],
        )

    if memory_id in context.taxonomy_ids:
        inject_review_modifier(
            candidates,
            memory_id,
            context,
            modifier="taxonomy.conflict",
            subtype="taxonomy",
            severity=SIGNAL_SEVERITY["taxonomy.conflict"],
        )

    if memory_id in context.unknown_ids:
        inject_review_modifier(
            candidates,
            memory_id,
            context,
            modifier="unknown.category",
            subtype="unknown_category",
            severity=SIGNAL_SEVERITY["unknown.category"],
        )

    for candidate in list(candidates):
        if candidate.action != RecommendationAction.MERGE:
            continue
        if candidate.modifiers and "cluster.trust.low" in candidate.modifiers:
            disqualify_merge(candidate, candidates, memory_id, context, "cluster.trust.low")
        if candidate.modifiers and "policy.blocked" in candidate.modifiers:
            disqualify_merge(candidate, candidates, memory_id, context, "policy.blocked")


def resolve_distinct_candidates(
    candidates: Sequence[RecommendationCandidate],
) -> tuple[RecommendationCandidate, list[RecommendationCandidate]]:
    ranked = sorted(
        candidates,
        key=lambda item: (
            PRECEDENCE_RANK[item.action],
            -item.confidence,
            -item.severity,
            SOURCE_PRIORITY.get(item.source, 99),
            item.action_id,
        ),
    )
    top_action = ranked[0].action
    top_rank = PRECEDENCE_RANK[top_action]
    top_candidates = [item for item in ranked if PRECEDENCE_RANK[item.action] == top_rank]

    if len({item.action for item in top_candidates}) == 1:
        winner = pick_best_candidate(top_candidates)
        losers = [item for item in candidates if item is not winner]
        return winner, losers

    pair = pick_conflict_pair(top_candidates)
    if pair is None:
        winner = pick_best_candidate(top_candidates)
        losers = [item for item in candidates if item is not winner]
        return winner, losers

    resolved_action = conflict_matrix(pair[0].action, pair[1].action, pair[0], pair[1])
    if resolved_action == RecommendationAction.ARCHIVE:
        archive_candidates = [item for item in pair if item.action == RecommendationAction.ARCHIVE]
        winner = pick_best_candidate(archive_candidates or top_candidates)
    elif resolved_action == RecommendationAction.MERGE:
        merge_candidates = [item for item in pair if item.action == RecommendationAction.MERGE]
        winner = pick_best_candidate(merge_candidates or top_candidates)
    else:
        review_pool = [item for item in candidates if item.action == RecommendationAction.REVIEW]
        winner = pick_best_candidate(review_pool or top_candidates)
        if winner.action != RecommendationAction.REVIEW:
            winner = review_from_candidate(winner, subtype="conflict")

    losers = [item for item in candidates if item is not winner]
    return winner, losers


def conflict_matrix(
    action_a: RecommendationAction,
    action_b: RecommendationAction,
    candidate_a: RecommendationCandidate,
    candidate_b: RecommendationCandidate,
) -> RecommendationAction:
    pair = frozenset({action_a, action_b})

    if pair == frozenset({RecommendationAction.KEEP, RecommendationAction.REVIEW}):
        return RecommendationAction.REVIEW
    if pair == frozenset({RecommendationAction.KEEP, RecommendationAction.ARCHIVE}):
        archive_conf = max(
            candidate_a.confidence
            if candidate_a.action == RecommendationAction.ARCHIVE
            else candidate_b.confidence,
            candidate_b.confidence
            if candidate_b.action == RecommendationAction.ARCHIVE
            else candidate_a.confidence,
        )
        if archive_conf >= ARCHIVE_MIN_CONFIDENCE:
            return RecommendationAction.ARCHIVE
        return RecommendationAction.REVIEW
    if pair == frozenset({RecommendationAction.KEEP, RecommendationAction.MERGE}):
        merge_candidate = (
            candidate_a if candidate_a.action == RecommendationAction.MERGE else candidate_b
        )
        if merge_candidate.role == "keeper":
            return RecommendationAction.MERGE
        if merge_candidate.confidence >= MERGE_MIN_CONFIDENCE and not merge_candidate.modifiers:
            return RecommendationAction.MERGE
        return RecommendationAction.REVIEW
    if pair == frozenset({RecommendationAction.ARCHIVE, RecommendationAction.MERGE}):
        return RecommendationAction.REVIEW
    if pair == frozenset({RecommendationAction.MERGE, RecommendationAction.REVIEW}):
        return RecommendationAction.REVIEW
    if pair == frozenset({RecommendationAction.ARCHIVE, RecommendationAction.REVIEW}):
        return RecommendationAction.REVIEW

    return min(action_a, action_b, key=lambda action: PRECEDENCE_RANK[action])


def build_group_recommendations(
    resolutions: Sequence[MemoryResolution],
    context: _RecommendationContext,
    *,
    include_keep: bool,
    include_deferred: bool,
) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    recommendations.extend(build_merge_recommendations(resolutions, context))
    recommendations.extend(build_archive_recommendations(resolutions, context))
    recommendations.extend(build_review_recommendations(resolutions, context))
    if include_keep:
        recommendations.extend(build_keep_recommendations(resolutions, context))
    if include_deferred:
        recommendations.extend(build_deferred_recommendations(context))
    return sorted(recommendations, key=recommendation_sort_key)


def build_merge_recommendations(
    resolutions: Sequence[MemoryResolution],
    context: _RecommendationContext,
) -> list[Recommendation]:
    merge_by_cluster: dict[str, list[MemoryResolution]] = defaultdict(list)
    for resolution in resolutions:
        if resolution.resolvedAction != RecommendationAction.MERGE:
            continue
        cluster_id = context.cluster_by_member.get(resolution.memoryId, "")
        if cluster_id:
            merge_by_cluster[cluster_id].append(resolution)

    recommendations: list[Recommendation] = []
    for cluster_id in sorted(merge_by_cluster):
        cluster_resolutions = merge_by_cluster[cluster_id]
        cluster = context.clusters_by_id.get(cluster_id)
        if cluster is None:
            continue
        action = merge_action_for_cluster(cluster_id, context)
        subtype = "preference_consolidation"
        if action and action.actionType == ActionType.MERGE_CLUSTER:
            subtype = "duplicate_cluster"
        affected = tuple(
            AffectedMemory(
                memoryId=resolution.memoryId,
                role=resolution.role,
                lifecycleState=context.lifecycle_by_id.get(resolution.memoryId, {}).get(
                    "lifecycleState", ""
                ),
            )
            for resolution in sorted(cluster_resolutions, key=lambda item: item.memoryId)
        )
        confidence = min(resolution.confidence for resolution in cluster_resolutions)
        recommendations.append(
            Recommendation(
                recommendationId=f"rec:merge:{cluster_id}",
                action=RecommendationAction.MERGE,
                subtype=subtype,
                confidence=round(confidence, 4),
                reason=(
                    f"High-trust duplicate cluster {cluster_id} approved for consolidation."
                ),
                affected_memories=affected,
                evidence=merge_evidence(cluster, action),
                estimatedImpact={
                    "removableRecords": sum(
                        1 for resolution in cluster_resolutions if resolution.role == "removable"
                    ),
                    "trusted": True,
                },
                priority=action.priority if action else ActionPriority.HIGH,
                requiresHumanApproval=False,
                sourceActionIds=(action.actionId,) if action else (),
            )
        )
    return recommendations


def build_archive_recommendations(
    resolutions: Sequence[MemoryResolution],
    context: _RecommendationContext,
) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    for resolution in resolutions:
        if resolution.resolvedAction != RecommendationAction.ARCHIVE:
            continue
        lifecycle = context.lifecycle_by_id.get(resolution.memoryId, {})
        successor_id = find_successor(resolution.memoryId, context)
        affected = [
            AffectedMemory(
                memoryId=resolution.memoryId,
                role="archive_candidate",
                lifecycleState=str(lifecycle.get("lifecycleState", "")),
            )
        ]
        if successor_id:
            affected.append(
                AffectedMemory(
                    memoryId=successor_id,
                    role="successor",
                    lifecycleState=str(
                        context.lifecycle_by_id.get(successor_id, {}).get("lifecycleState", "")
                    ),
                )
            )
        recommendations.append(
            Recommendation(
                recommendationId=f"rec:archive:{resolution.memoryId}",
                action=RecommendationAction.ARCHIVE,
                confidence=resolution.confidence,
                reason=str(lifecycle.get("explanation", "Lifecycle state supports archival.")),
                affected_memories=tuple(affected),
                evidence=archive_evidence(resolution.memoryId, context),
                estimatedImpact={"archivableRecords": 1, "trusted": True},
                priority=ActionPriority.MEDIUM,
                requiresHumanApproval=True,
                suppressedCandidates=suppressed_payload(resolution),
            )
        )
    return recommendations


def build_review_recommendations(
    resolutions: Sequence[MemoryResolution],
    context: _RecommendationContext,
) -> list[Recommendation]:
    grouped: dict[str, list[MemoryResolution]] = defaultdict(list)
    for resolution in resolutions:
        if resolution.resolvedAction != RecommendationAction.REVIEW:
            continue
        subtype = review_subtype_for_memory(resolution.memoryId, context)
        if resolution.conflictDetected:
            grouped[f"conflict:{resolution.memoryId}"].append(resolution)
        else:
            grouped[f"{subtype}:{resolution.recommendationId}"].append(resolution)

    recommendations: list[Recommendation] = []
    for group_key in sorted(grouped):
        group = grouped[group_key]
        if group_key.startswith("conflict:"):
            resolution = group[0]
            recommendations.append(conflict_review_recommendation(resolution, context))
            continue

        first = group[0]
        subtype = review_subtype_for_memory(first.memoryId, context)
        rec_id = first.recommendationId
        if not rec_id.startswith("rec:"):
            rec_id = f"rec:review:{subtype}:{first.memoryId}"

        affected = tuple(
            AffectedMemory(
                memoryId=item.memoryId,
                role="review",
                lifecycleState=str(
                    context.lifecycle_by_id.get(item.memoryId, {}).get("lifecycleState", "")
                ),
            )
            for item in sorted(group, key=lambda item: item.memoryId)
        )
        recommendations.append(
            Recommendation(
                recommendationId=rec_id,
                action=RecommendationAction.REVIEW,
                subtype=subtype,
                confidence=min(item.confidence for item in group),
                reason=review_reason(subtype, group, context),
                affected_memories=affected,
                evidence=with_compression_evidence(review_evidence(group, context), context),
                estimatedImpact={"recordsAtRisk": len(group), "trusted": False},
                priority=ActionPriority.HIGH
                if subtype in {"over_clustering", "conflict", "cluster_quality"}
                else ActionPriority.MEDIUM,
                requiresHumanApproval=True,
                suppressedCandidates=suppressed_payload(group[0]),
                conflictDetected=any(item.conflictDetected for item in group),
            )
        )
    return recommendations


def build_keep_recommendations(
    resolutions: Sequence[MemoryResolution],
    context: _RecommendationContext,
) -> list[Recommendation]:
    keep_resolutions = [
        resolution
        for resolution in resolutions
        if resolution.resolvedAction == RecommendationAction.KEEP
        and resolution.confidence >= KEEP_MIN_CONFIDENCE
    ]
    if not keep_resolutions:
        return []

    recommendations: list[Recommendation] = []
    for resolution in keep_resolutions:
        lifecycle = context.lifecycle_by_id.get(resolution.memoryId, {})
        recommendations.append(
            Recommendation(
                recommendationId=f"rec:keep:{resolution.memoryId}",
                action=RecommendationAction.KEEP,
                confidence=resolution.confidence,
                reason="Active lifecycle state with no duplicate, evolution, or taxonomy conflicts.",
                affected_memories=(
                    AffectedMemory(
                        memoryId=resolution.memoryId,
                        role="retain",
                        lifecycleState=str(lifecycle.get("lifecycleState", "Active")),
                    ),
                ),
                evidence=(
                    RecommendationEvidence(
                        source="memory_lifecycle",
                        signal=f"lifecycleState={lifecycle.get('lifecycleState', 'Active')}",
                        value=lifecycle.get("confidence"),
                    ),
                    RecommendationEvidence(
                        source="absence",
                        signal="no_governance_action",
                    ),
                ),
                estimatedImpact={"retainedRecords": 1},
                priority=ActionPriority.LOW,
                requiresHumanApproval=False,
            )
        )
    return recommendations


def build_deferred_recommendations(context: _RecommendationContext) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    for action in context.actions:
        if action.actionType != ActionType.IGNORE_LOW_VALUE_ISSUE:
            continue
        insight_id = str(action.target.get("insightId", "unknown"))
        recommendations.append(
            Recommendation(
                recommendationId=f"rec:defer:{insight_id}",
                action=RecommendationAction.DEFER,
                subtype="low_priority_insight",
                confidence=action.confidence,
                reason=action.rationale,
                affected_memories=(),
                evidence=tuple(
                    RecommendationEvidence(source="governance_action", signal=line, actionId=action.actionId)
                    for line in action.supportingEvidence
                ),
                estimatedImpact={},
                priority=action.priority,
                requiresHumanApproval=False,
                sourceActionIds=(action.actionId,),
            )
        )
    return recommendations


def summarize_recommendations(
    recommendations: Sequence[Recommendation],
    resolutions: Sequence[MemoryResolution],
) -> RecommendationSummary:
    priority_counts = Counter(recommendation.priority for recommendation in recommendations)
    merge_count = sum(1 for item in recommendations if item.action == RecommendationAction.MERGE)
    archive_count = sum(1 for item in recommendations if item.action == RecommendationAction.ARCHIVE)
    review_count = sum(1 for item in recommendations if item.action == RecommendationAction.REVIEW)
    keep_count = sum(1 for item in recommendations if item.action == RecommendationAction.KEEP)
    deferred_count = sum(1 for item in recommendations if item.action == RecommendationAction.DEFER)

    trusted_removals = sum(
        integer(item.estimatedImpact.get("removableRecords"))
        for item in recommendations
        if item.action == RecommendationAction.MERGE
    )
    archivable = sum(
        integer(item.estimatedImpact.get("archivableRecords"))
        for item in recommendations
        if item.action == RecommendationAction.ARCHIVE
    )

    return RecommendationSummary(
        totalRecommendations=len(recommendations),
        mergeCount=merge_count,
        archiveCount=archive_count,
        reviewCount=review_count,
        keepCount=keep_count,
        deferredCount=deferred_count,
        memoryResolutionCount=len(resolutions),
        estimatedTrustedRemovals=trusted_removals,
        estimatedArchivableRecords=archivable,
        recommendationsByPriority={
            priority: priority_counts.get(priority, 0) for priority in ActionPriority
        },
    )


@dataclass
class _RecommendationContext:
    records_by_id: dict[str, MemoryRecord]
    lifecycle_by_id: dict[str, dict[str, object]]
    cluster_by_member: dict[str, str]
    clusters_by_id: dict[str, DuplicateCluster]
    unknown_ids: set[str]
    taxonomy_ids: set[str]
    validation: Mapping[str, object]
    actions: Sequence[GovernanceAction]
    insights: Sequence[Insight]
    metrics: AnalysisMetrics | None
    include_keep: bool


def lifecycle_candidates(
    memory_id: str,
    context: _RecommendationContext,
) -> list[RecommendationCandidate]:
    lifecycle = context.lifecycle_by_id.get(memory_id)
    if not lifecycle:
        return []

    state = str(lifecycle.get("lifecycleState", ""))
    confidence = float_value(lifecycle.get("confidence"))
    candidates: list[RecommendationCandidate] = []

    if state == "Active" and context.include_keep:
        candidates.append(
            RecommendationCandidate(
                action=RecommendationAction.KEEP,
                confidence=min(0.99, round(confidence * 0.98, 4)),
                role="retain",
                lifecycle_state=state,
                source="memory_lifecycle",
                signal=f"lifecycleState={state}",
                evidence=[
                    RecommendationEvidence(
                        source="memory_lifecycle",
                        signal=f"lifecycleState={state}",
                        value=confidence,
                    )
                ],
                priority=ActionPriority.LOW,
                requires_human_approval=False,
            )
        )
    elif state in ARCHIVE_ELIGIBLE_STATES:
        evolution_conf = evolution_confidence_for_memory(memory_id, context.validation)
        archive_conf = (
            min(confidence, evolution_conf) if evolution_conf is not None else confidence
        )
        if archive_conf >= ARCHIVE_MIN_CONFIDENCE:
            candidates.append(
                RecommendationCandidate(
                    action=RecommendationAction.ARCHIVE,
                    confidence=round(archive_conf, 4),
                    role="archive_candidate",
                    lifecycle_state=state,
                    source="memory_lifecycle",
                    signal=f"lifecycleState={state}",
                    case_id=str(lifecycle.get("sourceCaseId", "")),
                    evidence=archive_evidence_candidates(memory_id, context),
                    priority=ActionPriority.MEDIUM,
                    requires_human_approval=True,
                )
            )
        else:
            candidates.append(
                RecommendationCandidate(
                    action=RecommendationAction.REVIEW,
                    confidence=min(archive_conf, REVIEW_AMBIGUITY_CAP),
                    role="review",
                    lifecycle_state=state,
                    source="memory_lifecycle",
                    signal=f"lifecycleState={state}",
                    subtype="lifecycle_ambiguity",
                    evidence=archive_evidence_candidates(memory_id, context),
                    priority=ActionPriority.MEDIUM,
                    requires_human_approval=True,
                )
            )
    return candidates


def governance_candidates(
    memory_id: str,
    context: _RecommendationContext,
) -> list[RecommendationCandidate]:
    candidates: list[RecommendationCandidate] = []
    for action in context.actions:
        if action.actionType in MERGE_ACTION_TYPES:
            members = member_ids(action.target)
            if memory_id not in members:
                continue
            cluster_id = str(action.target.get("clusterId", ""))
            cluster = context.clusters_by_id.get(cluster_id)
            keeper_id = pick_keeper(members, context.records_by_id, context.lifecycle_by_id)
            role = "keeper" if memory_id == keeper_id else "removable"
            merge_conf = merge_confidence(action, cluster)
            candidate = RecommendationCandidate(
                action=RecommendationAction.MERGE,
                confidence=merge_conf,
                role=role,
                lifecycle_state=str(
                    context.lifecycle_by_id.get(memory_id, {}).get("lifecycleState", "")
                ),
                source="governance_action",
                signal=f"actionType={action.actionType.value}",
                action_id=action.actionId,
                rule_id=action.policyRuleId,
                cluster_id=cluster_id,
                subtype=(
                    "preference_consolidation"
                    if action.actionType == ActionType.CONSOLIDATE_PREFERENCES
                    else "duplicate_cluster"
                ),
                evidence=governance_evidence(action, cluster),
                priority=action.priority,
                requires_human_approval=action.requiresHumanApproval,
            )
            if action.policyDecision == PolicyDecision.BLOCKED:
                candidate.modifiers.append("policy.blocked")
            if action.trustLevel == ClusterTrustLevel.LOW:
                candidate.modifiers.append("cluster.trust.low")
            if action.policyDecision in {PolicyDecision.BLOCKED, PolicyDecision.REQUIRES_REVIEW}:
                review_candidate = blocked_merge_review(candidate, action)
                candidates.append(review_candidate)
            elif (
                action.policyDecision == PolicyDecision.APPROVED
                and merge_conf >= MERGE_MIN_CONFIDENCE
                and not candidate.modifiers
            ):
                candidates.append(candidate)
            else:
                candidates.append(review_from_merge(action, memory_id, role, context))
            continue

        if action.actionType not in REVIEW_ACTION_TYPES:
            continue

        target_ids = review_target_ids(action)
        if memory_id not in target_ids and action.actionType != ActionType.REVIEW_UNKNOWN_MEMORY:
            continue
        if action.actionType == ActionType.REVIEW_UNKNOWN_MEMORY and memory_id not in context.unknown_ids:
            continue

        subtype = review_subtype_for_action(action.actionType)
        candidates.append(
            RecommendationCandidate(
                action=RecommendationAction.REVIEW,
                confidence=action.confidence,
                role="review",
                lifecycle_state=str(
                    context.lifecycle_by_id.get(memory_id, {}).get("lifecycleState", "")
                ),
                source="governance_action",
                signal=f"actionType={action.actionType.value}",
                action_id=action.actionId,
                rule_id=action.policyRuleId,
                cluster_id=str(action.target.get("clusterId", "")),
                subtype=subtype,
                evidence=governance_evidence(action, context.clusters_by_id.get(
                    str(action.target.get("clusterId", "")), None
                )),
                priority=action.priority,
                requires_human_approval=True,
                severity=review_severity(action),
            )
        )
    return candidates


def category_candidates(
    memory_id: str,
    context: _RecommendationContext,
) -> list[RecommendationCandidate]:
    return []


def absence_keep_candidate(
    memory_id: str,
    context: _RecommendationContext,
) -> list[RecommendationCandidate]:
    lifecycle = context.lifecycle_by_id.get(memory_id, {})
    state = str(lifecycle.get("lifecycleState", "Active"))
    if state != "Active":
        return []
    confidence = float_value(lifecycle.get("confidence", 0.85))
    return [
        RecommendationCandidate(
            action=RecommendationAction.KEEP,
            confidence=min(0.99, round(confidence * 0.98, 4)),
            role="retain",
            lifecycle_state=state,
            source="absence",
            signal="no_governance_action",
            evidence=[
                RecommendationEvidence(source="absence", signal="no_governance_action"),
            ],
            priority=ActionPriority.LOW,
            requires_human_approval=False,
        )
    ]


def default_resolution(memory_id: str, context: _RecommendationContext) -> MemoryResolution:
    lifecycle = context.lifecycle_by_id.get(memory_id, {})
    state = str(lifecycle.get("lifecycleState", ""))
    if state == "Active":
        confidence = min(0.99, round(float_value(lifecycle.get("confidence", 0.85)) * 0.98, 4))
        action = RecommendationAction.KEEP if context.include_keep else RecommendationAction.KEEP
        return MemoryResolution(
            memoryId=memory_id,
            resolvedAction=action,
            role="retain",
            confidence=confidence,
            recommendationId=f"rec:keep:{memory_id}" if context.include_keep else f"rec:implicit:keep:{memory_id}",
        )
    return MemoryResolution(
        memoryId=memory_id,
        resolvedAction=RecommendationAction.KEEP,
        role="retain",
        confidence=0.5,
        recommendationId=f"rec:implicit:keep:{memory_id}",
    )


def inject_review_modifier(
    candidates: list[RecommendationCandidate],
    memory_id: str,
    context: _RecommendationContext,
    *,
    modifier: str,
    subtype: str,
    severity: int,
) -> None:
    existing = next((item for item in candidates if item.action == RecommendationAction.REVIEW), None)
    if existing:
        existing.modifiers.append(modifier)
        existing.severity = max(existing.severity, severity)
        return
    candidates.append(
        RecommendationCandidate(
            action=RecommendationAction.REVIEW,
            confidence=review_confidence_for_modifier(modifier),
            role="review",
            lifecycle_state=str(
                context.lifecycle_by_id.get(memory_id, {}).get("lifecycleState", "")
            ),
            source="category_quality" if modifier.startswith("unknown") or modifier.startswith("taxonomy") else "memory_lifecycle",
            signal=modifier,
            subtype=subtype,
            severity=severity,
            modifiers=[modifier],
            evidence=[
                RecommendationEvidence(source="conflict_resolution", signal=f"modifier={modifier}")
            ],
            priority=ActionPriority.MEDIUM,
            requires_human_approval=True,
        )
    )


def disqualify_merge(
    merge_candidate: RecommendationCandidate,
    candidates: list[RecommendationCandidate],
    memory_id: str,
    context: _RecommendationContext,
    modifier: str,
) -> None:
    merge_candidate.disqualified = True
    if not any(item.action == RecommendationAction.REVIEW for item in candidates):
        candidates.append(
            RecommendationCandidate(
                action=RecommendationAction.REVIEW,
                confidence=review_confidence_for_modifier(modifier),
                role="review",
                lifecycle_state=merge_candidate.lifecycle_state,
                source="policy" if modifier == "policy.blocked" else "cluster_trust",
                signal=modifier,
                subtype="over_clustering" if modifier == "cluster.trust.low" else "policy_blocked_merge",
                severity=SIGNAL_SEVERITY[modifier],
                modifiers=[modifier],
                action_id=merge_candidate.action_id,
                rule_id=merge_candidate.rule_id,
                cluster_id=merge_candidate.cluster_id,
                evidence=list(merge_candidate.evidence),
                priority=ActionPriority.HIGH,
                requires_human_approval=True,
            )
        )


def escalation_review_conflict(
    memory_id: str,
    candidates: Sequence[RecommendationCandidate],
    context: _RecommendationContext,
) -> tuple[RecommendationCandidate, bool, list[RecommendationAction]]:
    archive = next(item for item in candidates if item.action == RecommendationAction.ARCHIVE)
    merge = next(item for item in candidates if item.action == RecommendationAction.MERGE)
    suppressed = [RecommendationAction.ARCHIVE, RecommendationAction.MERGE]
    winner = RecommendationCandidate(
        action=RecommendationAction.REVIEW,
        confidence=min(REVIEW_AMBIGUITY_CAP, min(archive.confidence, merge.confidence)),
        role="review",
        lifecycle_state=archive.lifecycle_state,
        source="conflict_resolution",
        signal="suppressedCandidates=archive,merge",
        subtype="conflict",
        severity=5,
        modifiers=["archive_merge_conflict"],
        evidence=[
            *archive.evidence,
            *merge.evidence,
            RecommendationEvidence(
                source="conflict_resolution",
                signal="suppressedCandidates=archive,merge",
            ),
        ],
        priority=ActionPriority.HIGH,
        requires_human_approval=True,
    )
    return winner, True, suppressed


def conflict_review_recommendation(
    resolution: MemoryResolution,
    context: _RecommendationContext,
) -> Recommendation:
    lifecycle = context.lifecycle_by_id.get(resolution.memoryId, {})
    evidence = list(conflict_review_evidence(resolution, context))
    return Recommendation(
        recommendationId=f"rec:review:conflict:{resolution.memoryId}",
        action=RecommendationAction.REVIEW,
        subtype="conflict",
        confidence=resolution.confidence,
        reason=(
            "Competing archive and merge remediation paths detected for the same memory; "
            "manual review required."
        ),
        affected_memories=(
            AffectedMemory(
                memoryId=resolution.memoryId,
                role="review",
                lifecycleState=str(lifecycle.get("lifecycleState", "")),
            ),
        ),
        evidence=with_compression_evidence(tuple(evidence), context),
        estimatedImpact={"recordsAtRisk": 1, "trusted": False},
        priority=ActionPriority.HIGH,
        requiresHumanApproval=True,
        conflictDetected=True,
        suppressedCandidates=suppressed_payload(resolution),
    )


def conflict_review_evidence(
    resolution: MemoryResolution,
    context: _RecommendationContext,
) -> list[RecommendationEvidence]:
    evidence = list(archive_evidence_candidates(resolution.memoryId, context))
    cluster_id = context.cluster_by_member.get(resolution.memoryId, "")
    cluster = context.clusters_by_id.get(cluster_id)
    merge_action = merge_action_for_cluster(cluster_id, context) if cluster_id else None
    if merge_action:
        evidence.extend(governance_evidence(merge_action, cluster))
    if cluster is not None:
        evidence.extend(
            [
                RecommendationEvidence(
                    source="cluster_trust",
                    signal=f"trustLevel={cluster.trustLevel.value}",
                    value=cluster.trustScore,
                ),
            ]
        )
    if resolution.suppressedActions:
        evidence.append(
            RecommendationEvidence(
                source="conflict_resolution",
                signal=(
                    "suppressedCandidates="
                    + ",".join(action.value for action in resolution.suppressedActions)
                ),
            )
        )
    return evidence


def recommendation_has_evidence(recommendation: Recommendation) -> bool:
    return bool(recommendation.evidence)


def compression_metrics_evidence(context: _RecommendationContext) -> RecommendationEvidence | None:
    if context.metrics is not None:
        return RecommendationEvidence(
            source="compression_metrics",
            signal="trustedCompressionOpportunity",
            value=context.metrics.trustedCompressionOpportunity,
        )
    compression = nested_dict(context.validation, "compressionDrivers")
    trusted = compression.get("trustedRemovableRecords")
    if isinstance(trusted, int | float):
        return RecommendationEvidence(
            source="compression_metrics",
            signal="trustedRemovableRecords",
            value=float(trusted),
        )
    return None


def with_compression_evidence(
    evidence: tuple[RecommendationEvidence, ...],
    context: _RecommendationContext,
) -> tuple[RecommendationEvidence, ...]:
    items = list(evidence)
    compression = compression_metrics_evidence(context)
    if compression is not None and not any(item.source == "compression_metrics" for item in items):
        items.append(compression)
    return tuple(items) if items else (compression,) if compression else ()


def pick_best_candidate(candidates: Sequence[RecommendationCandidate]) -> RecommendationCandidate:
    return sorted(
        candidates,
        key=lambda item: (
            -item.confidence,
            -item.severity,
            SOURCE_PRIORITY.get(item.source, 99),
            item.action_id,
            item.signal,
        ),
    )[0]


def pick_conflict_pair(
    candidates: Sequence[RecommendationCandidate],
) -> tuple[RecommendationCandidate, RecommendationCandidate] | None:
    if len(candidates) < 2:
        return None
    ordered = sorted(candidates, key=lambda item: (PRECEDENCE_RANK[item.action], item.action_id))
    return ordered[0], ordered[1]


def review_from_candidate(
    candidate: RecommendationCandidate,
    *,
    subtype: str,
) -> RecommendationCandidate:
    return RecommendationCandidate(
        action=RecommendationAction.REVIEW,
        confidence=min(candidate.confidence, REVIEW_AMBIGUITY_CAP),
        role="review",
        lifecycle_state=candidate.lifecycle_state,
        source=candidate.source,
        signal=candidate.signal,
        subtype=subtype,
        severity=max(candidate.severity, 3),
        modifiers=[*candidate.modifiers, subtype],
        evidence=list(candidate.evidence),
        priority=ActionPriority.HIGH,
        requires_human_approval=True,
    )


def blocked_merge_review(
    merge_candidate: RecommendationCandidate,
    action: GovernanceAction,
) -> RecommendationCandidate:
    modifier = (
        "policy.blocked"
        if action.policyDecision == PolicyDecision.BLOCKED
        else "policy.requires_review"
    )
    return RecommendationCandidate(
        action=RecommendationAction.REVIEW,
        confidence=min(merge_candidate.confidence, 0.75),
        role="review",
        lifecycle_state=merge_candidate.lifecycle_state,
        source="policy",
        signal=modifier,
        subtype="policy_blocked_merge",
        severity=SIGNAL_SEVERITY.get("policy.blocked", 5),
        modifiers=[modifier],
        action_id=action.actionId,
        rule_id=action.policyRuleId,
        cluster_id=merge_candidate.cluster_id,
        evidence=[
            *merge_candidate.evidence,
            RecommendationEvidence(
                source="policy",
                signal=f"policyDecision={action.policyDecision.value if action.policyDecision else ''}",
                ruleId=action.policyRuleId,
            ),
        ],
        priority=ActionPriority.HIGH,
        requires_human_approval=True,
    )


def review_from_merge(
    action: GovernanceAction,
    memory_id: str,
    role: str,
    context: _RecommendationContext,
) -> RecommendationCandidate:
    return RecommendationCandidate(
        action=RecommendationAction.REVIEW,
        confidence=action.confidence,
        role="review",
        lifecycle_state=str(
            context.lifecycle_by_id.get(memory_id, {}).get("lifecycleState", "")
        ),
        source="governance_action",
        signal=f"actionType={action.actionType.value}",
        subtype="cluster_quality",
        action_id=action.actionId,
        rule_id=action.policyRuleId,
        evidence=governance_evidence(action, context.clusters_by_id.get(
            str(action.target.get("clusterId", "")), None
        )),
        priority=action.priority,
        requires_human_approval=True,
    )


def stable_recommendation_id(candidate: RecommendationCandidate, memory_id: str) -> str:
    if candidate.action == RecommendationAction.MERGE and candidate.cluster_id:
        return f"rec:merge:{candidate.cluster_id}"
    if candidate.action == RecommendationAction.ARCHIVE:
        return f"rec:archive:{memory_id}"
    if candidate.action == RecommendationAction.REVIEW and candidate.subtype == "conflict":
        return f"rec:review:conflict:{memory_id}"
    if candidate.action_id:
        return f"rec:review:{candidate.subtype}:{candidate.action_id}"
    if candidate.action == RecommendationAction.KEEP:
        return f"rec:keep:{memory_id}"
    return f"rec:{candidate.action.value}:{memory_id}"


def lifecycle_assignments_by_id(validation: Mapping[str, object]) -> dict[str, dict[str, object]]:
    lifecycle = validation.get("memoryLifecycle", {})
    if not isinstance(lifecycle, dict):
        return {}
    assignments = lifecycle.get("memoryLifecycleAssignments", [])
    if not isinstance(assignments, list):
        return {}
    mapped: dict[str, dict[str, object]] = {}
    for assignment in assignments:
        if isinstance(assignment, dict) and isinstance(assignment.get("memoryId"), str):
            mapped[assignment["memoryId"]] = assignment
    return mapped


def cluster_membership_map(clusters: Sequence[DuplicateCluster]) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for cluster in clusters:
        for member in cluster.members:
            mapped[member] = cluster.clusterId
    return mapped


def unknown_memory_ids(validation: Mapping[str, object]) -> set[str]:
    category_quality = nested_dict(validation, "categoryQuality")
    samples = list_value(category_quality.get("unknownSamples"))
    return {
        str(sample.get("memoryId"))
        for sample in samples
        if isinstance(sample, dict) and sample.get("memoryId")
    }


def taxonomy_conflict_memory_ids(validation: Mapping[str, object]) -> set[str]:
    category_quality = nested_dict(validation, "categoryQuality")
    consistency = nested_dict(category_quality, "categoryConsistency")
    conflicts = list_value(consistency.get("conflictClusters"))
    ids: set[str] = set()
    for conflict in conflicts:
        if not isinstance(conflict, dict):
            continue
        for candidate in list_value(conflict.get("reclassificationCandidates")):
            if isinstance(candidate, dict) and candidate.get("memoryId"):
                ids.add(str(candidate["memoryId"]))
    return ids


def pick_keeper(
    members: Sequence[str],
    records_by_id: Mapping[str, MemoryRecord],
    lifecycle_by_id: Mapping[str, dict[str, object]],
) -> str:
    return min(
        members,
        key=lambda memory_id: (
            0 if str(lifecycle_by_id.get(memory_id, {}).get("lifecycleState")) == "Active" else 1,
            -timestamp_sort_value(records_by_id.get(memory_id)),
            -float_value(lifecycle_by_id.get(memory_id, {}).get("confidence")),
            memory_id,
        ),
    )


def merge_confidence(action: GovernanceAction, cluster: DuplicateCluster | None) -> float:
    if cluster is None:
        return round(action.confidence, 4)
    return round(min(action.confidence, cluster.trustScore, cluster.averageSimilarity), 4)


def merge_action_for_cluster(
    cluster_id: str,
    context: _RecommendationContext,
) -> GovernanceAction | None:
    for action in context.actions:
        if action.actionType not in MERGE_ACTION_TYPES:
            continue
        if str(action.target.get("clusterId")) == cluster_id:
            return action
    return None


def merge_evidence(
    cluster: DuplicateCluster,
    action: GovernanceAction | None,
) -> tuple[RecommendationEvidence, ...]:
    evidence = [
        RecommendationEvidence(
            source="cluster_trust",
            signal=f"trustLevel={cluster.trustLevel.value}",
            value=cluster.trustScore,
        ),
        RecommendationEvidence(
            source="cluster_trust",
            signal=f"averageSimilarity={cluster.averageSimilarity}",
            value=cluster.averageSimilarity,
        ),
    ]
    if action:
        evidence.append(
            RecommendationEvidence(
                source="governance_action",
                signal=f"actionType={action.actionType.value}",
                actionId=action.actionId,
            )
        )
        if action.policyDecision:
            evidence.append(
                RecommendationEvidence(
                    source="policy",
                    signal=f"policyDecision={action.policyDecision.value}",
                    ruleId=action.policyRuleId,
                )
            )
    return tuple(evidence)


def archive_evidence(
    memory_id: str,
    context: _RecommendationContext,
) -> tuple[RecommendationEvidence, ...]:
    return tuple(archive_evidence_candidates(memory_id, context))


def archive_evidence_candidates(
    memory_id: str,
    context: _RecommendationContext,
) -> list[RecommendationEvidence]:
    lifecycle = context.lifecycle_by_id.get(memory_id, {})
    evidence = [
        RecommendationEvidence(
            source="memory_lifecycle",
            signal=f"lifecycleState={lifecycle.get('lifecycleState', '')}",
            value=lifecycle.get("confidence"),
            caseId=str(lifecycle.get("sourceCaseId", "")),
        )
    ]
    case_id = str(lifecycle.get("sourceCaseId", ""))
    evolution_type = str(lifecycle.get("sourceEvolutionType", ""))
    if evolution_type:
        evidence.append(
            RecommendationEvidence(
                source="memory_evolution",
                signal=f"evolutionType={evolution_type}",
                caseId=case_id,
            )
        )
    return evidence


def review_evidence(
    group: Sequence[MemoryResolution],
    context: _RecommendationContext,
) -> tuple[RecommendationEvidence, ...]:
    memory_id = group[0].memoryId
    subtype = review_subtype_for_memory(memory_id, context)
    evidence: list[RecommendationEvidence] = []
    for action in context.actions:
        if review_subtype_for_action(action.actionType) != subtype:
            continue
        if memory_id not in review_target_ids(action) and action.actionType != ActionType.REVIEW_UNKNOWN_MEMORY:
            continue
        evidence.extend(governance_evidence(action, context.clusters_by_id.get(
            str(action.target.get("clusterId", "")), None
        )))
    if not evidence and group[0].suppressedActions:
        evidence.append(
            RecommendationEvidence(
                source="conflict_resolution",
                signal=f"suppressedActions={','.join(action.value for action in group[0].suppressedActions)}",
            )
        )
    return tuple(evidence)


def governance_evidence(
    action: GovernanceAction,
    cluster: DuplicateCluster | None,
) -> list[RecommendationEvidence]:
    evidence = [
        RecommendationEvidence(
            source="governance_action",
            signal=f"actionType={action.actionType.value}",
            actionId=action.actionId,
        )
    ]
    if action.policyDecision:
        evidence.append(
            RecommendationEvidence(
                source="policy",
                signal=f"policyDecision={action.policyDecision.value}",
                ruleId=action.policyRuleId,
            )
        )
    if cluster is not None:
        evidence.append(
            RecommendationEvidence(
                source="cluster_trust",
                signal=f"trustLevel={cluster.trustLevel.value}",
                value=cluster.trustScore,
            )
        )
    return evidence


def review_reason(
    subtype: str,
    group: Sequence[MemoryResolution],
    context: _RecommendationContext,
) -> str:
    if subtype == "unknown_category":
        return "Unknown-category memory requires taxonomy review."
    if subtype == "taxonomy":
        return "Category disagreement inside a duplicate cluster requires review."
    if subtype == "over_clustering":
        return "Cluster may represent broad topical similarity instead of true duplicates."
    if subtype == "policy_blocked_merge":
        return "Merge recommendation blocked or requires review under selected policy."
    if subtype == "cluster_quality":
        return "Cluster quality signals require review before consolidation."
    return "Human review required before memory governance action."


def review_subtype_for_memory(memory_id: str, context: _RecommendationContext) -> str:
    if memory_id in context.unknown_ids:
        return "unknown_category"
    if memory_id in context.taxonomy_ids:
        return "taxonomy"
    for action in context.actions:
        if memory_id not in review_target_ids(action):
            continue
        return review_subtype_for_action(action.actionType)
    lifecycle = context.lifecycle_by_id.get(memory_id, {})
    if lifecycle.get("alternateLifecycleSignals"):
        return "lifecycle_ambiguity"
    return "cluster_quality"


def review_subtype_for_action(action_type: ActionType) -> str:
    mapping = {
        ActionType.REVIEW_CLUSTER: "cluster_quality",
        ActionType.REVIEW_OVERCLUSTERED_GROUP: "over_clustering",
        ActionType.REVIEW_CATEGORY_CONFLICT: "taxonomy",
        ActionType.REVIEW_UNKNOWN_MEMORY: "unknown_category",
    }
    return mapping.get(action_type, "cluster_quality")


def review_target_ids(action: GovernanceAction) -> set[str]:
    if action.actionType == ActionType.REVIEW_UNKNOWN_MEMORY:
        return {str(item) for item in list_value(action.target.get("memoryIds"))}
    if action.actionType == ActionType.REVIEW_CATEGORY_CONFLICT:
        return {str(item) for item in list_value(action.target.get("candidateMemoryIds"))}
    return set(member_ids(action.target))


def review_severity(action: GovernanceAction) -> int:
    if action.policyDecision == PolicyDecision.BLOCKED:
        return SIGNAL_SEVERITY["policy.blocked"]
    if action.trustLevel == ClusterTrustLevel.LOW:
        return SIGNAL_SEVERITY["cluster.trust.low"]
    if action.actionType == ActionType.REVIEW_CATEGORY_CONFLICT:
        return SIGNAL_SEVERITY["taxonomy.conflict"]
    if action.actionType == ActionType.REVIEW_UNKNOWN_MEMORY:
        return SIGNAL_SEVERITY["unknown.category"]
    return 0


def review_confidence_for_modifier(modifier: str) -> float:
    mapping = {
        "policy.blocked": 0.54,
        "cluster.trust.low": 0.54,
        "lifecycle.alternate": REVIEW_AMBIGUITY_CAP,
        "taxonomy.conflict": 0.88,
        "unknown.category": 0.85,
    }
    return mapping.get(modifier, 0.65)


def find_successor(memory_id: str, context: _RecommendationContext) -> str:
    lifecycle = validation_dict(context.validation, "memoryLifecycle")
    transitions = list_value(lifecycle.get("lifecycleTransitions"))
    for transition in transitions:
        if not isinstance(transition, dict):
            continue
        if transition.get("fromMemoryId") == memory_id and transition.get("toMemoryId"):
            return str(transition["toMemoryId"])
    evolution = validation_dict(context.validation, "memoryEvolutionAudit")
    for key in ("contradictions", "preferenceChanges", "supersededMemories", "statusTransitionCandidates"):
        for case in list_value(evolution.get(key)):
            if not isinstance(case, dict):
                continue
            memories = list_value(case.get("involvedMemories"))
            ids = [str(item.get("memoryId")) for item in memories if isinstance(item, dict)]
            if memory_id in ids and len(ids) >= 2:
                return ids[-1]
    return ""


def evolution_confidence_for_memory(
    memory_id: str,
    validation: Mapping[str, object],
) -> float | None:
    lifecycle = context_lifecycle_case(memory_id, validation)
    if lifecycle is None:
        return None
    case_id = str(lifecycle.get("sourceCaseId", ""))
    evolution = validation_dict(validation, "memoryEvolutionAudit")
    for key in ("contradictions", "preferenceChanges", "supersededMemories", "statusTransitionCandidates", "staleMemoryCandidates"):
        for case in list_value(evolution.get(key)):
            if isinstance(case, dict) and str(case.get("caseId")) == case_id:
                return float_value(case.get("confidence"))
    return None


def context_lifecycle_case(
    memory_id: str,
    validation: Mapping[str, object],
) -> dict[str, object] | None:
    lifecycle = validation_dict(validation, "memoryLifecycle")
    for assignment in list_value(lifecycle.get("memoryLifecycleAssignments")):
        if isinstance(assignment, dict) and assignment.get("memoryId") == memory_id:
            return assignment
    return None


def suppressed_payload(resolution: MemoryResolution) -> tuple[dict[str, Any], ...]:
    return tuple(
        {"action": action.value} for action in resolution.suppressedActions
    )


def recommendation_sort_key(recommendation: Recommendation) -> tuple[int, str]:
    priority_rank = {
        ActionPriority.CRITICAL: 0,
        ActionPriority.HIGH: 1,
        ActionPriority.MEDIUM: 2,
        ActionPriority.LOW: 3,
        ActionPriority.DEFERRED: 4,
    }
    return (priority_rank[recommendation.priority], recommendation.recommendationId)


def member_ids(target: Mapping[str, object]) -> list[str]:
    members = target.get("members")
    if isinstance(members, list):
        return [str(member) for member in members]
    return []


def nested_dict(mapping: Mapping[str, object], key: str) -> dict[str, object]:
    value = mapping.get(key)
    return value if isinstance(value, dict) else {}


def validation_dict(validation: Mapping[str, object], key: str) -> dict[str, object]:
    return nested_dict(validation, key)


def list_value(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def float_value(value: object, default: float = 0.0) -> float:
    if isinstance(value, int | float):
        return float(value)
    return default


def integer(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def timestamp_sort_value(record: MemoryRecord | None) -> int:
    if record is None or not record.timestamp:
        return 0
    normalized = record.timestamp.replace("-", "").replace(":", "").replace("T", "")
    digits = "".join(character for character in normalized if character.isdigit())
    return int(digits[:14]) if digits else 0
