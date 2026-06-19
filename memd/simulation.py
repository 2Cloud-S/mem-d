from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from memd.contracts import (
    AnalysisReport,
    ClusterTrustLevel,
    DuplicateCluster,
    MemoryRecord,
    MemoryResolution,
    Recommendation,
    RecommendationAction,
    SimulatedArchiveEntry,
    SimulatedExplainability,
    SimulatedMergeGroup,
    SimulatedReviewEntry,
    SimulationMetrics,
    SimulationReport,
    SimulationWarning,
)

METRICS_DISCLAIMER = "Structural estimates only; not benchmark-equivalent compression."
ORPHAN_MERGE_CODE = "ORPHAN_MERGE_NO_KEEPER"
DUPLICATE_REMOVAL_CODE = "DUPLICATE_REMOVAL_SKIPPED"


def simulate_recommendations(report: AnalysisReport) -> SimulationReport:
    """Project hypothetical store outcomes from recommendation resolutions (read-only)."""
    simulation_mode = "full"
    s_before = {memory.id for memory in report.memories}
    active_store = {memory.id: _copy_memory(memory) for memory in report.memories}

    resolutions_by_id = {resolution.memoryId: resolution for resolution in report.memoryResolutions}
    recommendations_by_id = {
        recommendation.recommendationId: recommendation
        for recommendation in report.recommendations
    }
    lifecycle_by_id = _lifecycle_by_id(report.validation)
    cluster_by_member = _cluster_by_member(report.clusters)
    clusters_by_id = {cluster.clusterId: cluster for cluster in report.clusters}

    warnings: list[SimulationWarning] = []
    simulated_merges: list[SimulatedMergeGroup] = []
    simulated_archives: list[SimulatedArchiveEntry] = []
    review_queue: list[SimulatedReviewEntry] = []
    orphan_downgraded: set[str] = set()

    # 1. Merge removals
    merge_groups = _group_merge_resolutions(resolutions_by_id)
    for recommendation_id, group in sorted(merge_groups.items()):
        keeper_ids = [
            resolution.memoryId
            for resolution in group
            if resolution.role == "keeper" and resolution.memoryId in active_store
        ]
        removable_ids = [
            resolution.memoryId
            for resolution in group
            if resolution.role == "removable"
        ]

        if not keeper_ids:
            first_removable = removable_ids[0] if removable_ids else group[0].memoryId
            warnings.append(
                SimulationWarning(
                    code=ORPHAN_MERGE_CODE,
                    memoryId=first_removable,
                    recommendationId=recommendation_id,
                    message=(
                        "Merge simulation skipped: no keeper present in active store "
                        "for recommendation group."
                    ),
                )
            )
            for resolution in group:
                if resolution.role == "removable":
                    orphan_downgraded.add(resolution.memoryId)
                    review_queue.append(
                        _build_review_entry(
                            resolution,
                            recommendations_by_id.get(recommendation_id),
                            report,
                            lifecycle_by_id,
                            cluster_by_member,
                            orphan_merge_downgrade=True,
                        )
                    )
            continue

        keeper_id = sorted(keeper_ids)[0]
        removed: list[str] = []
        for memory_id in sorted(removable_ids):
            if memory_id not in active_store:
                continue
            if memory_id == keeper_id:
                continue
            del active_store[memory_id]
            removed.append(memory_id)

        if not removed:
            continue

        cluster_id, trust_level, trusted = _merge_trust_context(
            keeper_id, cluster_by_member, clusters_by_id
        )
        keeper_resolution = resolutions_by_id[keeper_id]
        recommendation = recommendations_by_id.get(recommendation_id)
        explainability = _build_explainability(
            keeper_resolution,
            recommendation,
            report,
            lifecycle_by_id,
            cluster_by_member,
            cluster_id=cluster_id,
        )
        simulated_merges.append(
            SimulatedMergeGroup(
                recommendationId=recommendation_id,
                keeperId=keeper_id,
                removedIds=tuple(removed),
                clusterId=cluster_id,
                trustLevel=trust_level,
                trusted=trusted,
                explainability=explainability,
            )
        )

    # 2. Archive removals
    for resolution in sorted(report.memoryResolutions, key=lambda item: item.memoryId):
        if resolution.resolvedAction != RecommendationAction.ARCHIVE:
            continue
        if simulation_mode not in {"full", "archive_only"}:
            continue
        memory_id = resolution.memoryId
        if memory_id not in active_store:
            if memory_id in s_before:
                warnings.append(
                    SimulationWarning(
                        code=DUPLICATE_REMOVAL_CODE,
                        memoryId=memory_id,
                        recommendationId=resolution.recommendationId,
                        message="Archive simulation skipped: memory already removed.",
                    )
                )
            continue

        record = active_store.pop(memory_id)
        lifecycle_state = str(lifecycle_by_id.get(memory_id, {}).get("lifecycleState", ""))
        recommendation = recommendations_by_id.get(resolution.recommendationId)
        explainability = _build_explainability(
            resolution,
            recommendation,
            report,
            lifecycle_by_id,
            cluster_by_member,
        )
        simulated_archives.append(
            SimulatedArchiveEntry(
                memoryId=memory_id,
                lifecycleState=lifecycle_state,
                recommendationId=resolution.recommendationId,
                archivedRecord=record,
                explainability=explainability,
            )
        )

    # 3. Review classification
    for resolution in sorted(report.memoryResolutions, key=lambda item: item.memoryId):
        if resolution.memoryId in orphan_downgraded:
            continue
        if resolution.resolvedAction != RecommendationAction.REVIEW:
            continue
        review_queue.append(
            _build_review_entry(
                resolution,
                recommendations_by_id.get(resolution.recommendationId),
                report,
                lifecycle_by_id,
                cluster_by_member,
            )
        )

    # 4. Keep classification — no structural change (implicit/explicit keep needs no queue entry)

    s_after = set(active_store)
    metrics = _compute_metrics(
        report=report,
        s_before=s_before,
        s_after=s_after,
        simulated_merges=simulated_merges,
        simulated_archives=simulated_archives,
        resolutions_by_id=resolutions_by_id,
        orphan_downgraded=orphan_downgraded,
        warnings=warnings,
        simulation_mode=simulation_mode,
    )

    simulated_memories = tuple(
        active_store[memory_id] for memory_id in sorted(active_store)
    )

    return SimulationReport(
        simulationId=_compute_simulation_id(report, simulation_mode),
        sourceMemoryCount=len(s_before),
        simulatedMemoryCount=len(s_after),
        simulatedMemories=simulated_memories,
        simulatedMerges=tuple(simulated_merges),
        simulatedArchives=tuple(simulated_archives),
        simulatedReviewQueue=tuple(review_queue),
        simulationWarnings=tuple(warnings),
        metrics=metrics,
        policyProfile=report.policySummary.profile.value,
        simulationMode=simulation_mode,
        metricsDisclaimer=METRICS_DISCLAIMER,
    )


def _copy_memory(record: MemoryRecord) -> MemoryRecord:
    return record.model_copy(deep=True)


def _safe_percentage(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100, 2)


def _removable_estimate(cluster: DuplicateCluster, active_ids: set[str]) -> int:
    active_members = [member for member in cluster.members if member in active_ids]
    return max(0, len(active_members) - 1)


def _trusted_removable_estimate(cluster: DuplicateCluster, active_ids: set[str]) -> int:
    if cluster.trustLevel != ClusterTrustLevel.HIGH:
        return 0
    return _removable_estimate(cluster, active_ids)


def _lifecycle_by_id(validation: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    lifecycle = validation.get("memoryLifecycle", {})
    if not isinstance(lifecycle, dict):
        return {}
    assignments = lifecycle.get("memoryLifecycleAssignments", [])
    if not isinstance(assignments, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for item in assignments:
        if isinstance(item, dict) and item.get("memoryId"):
            result[str(item["memoryId"])] = item
    return result


def _cluster_by_member(
    clusters: Sequence[DuplicateCluster],
) -> dict[str, DuplicateCluster]:
    mapping: dict[str, DuplicateCluster] = {}
    for cluster in clusters:
        for member in cluster.members:
            mapping[member] = cluster
    return mapping


def _group_merge_resolutions(
    resolutions_by_id: Mapping[str, MemoryResolution],
) -> dict[str, list[MemoryResolution]]:
    groups: dict[str, list[MemoryResolution]] = defaultdict(list)
    for resolution in resolutions_by_id.values():
        if resolution.resolvedAction != RecommendationAction.MERGE:
            continue
        groups[resolution.recommendationId].append(resolution)
    return dict(groups)


def _merge_trust_context(
    keeper_id: str,
    cluster_by_member: Mapping[str, DuplicateCluster],
    clusters_by_id: Mapping[str, DuplicateCluster],
) -> tuple[str, str, bool]:
    cluster = cluster_by_member.get(keeper_id)
    if cluster is None:
        return "", "", False
    trusted = cluster.trustLevel == ClusterTrustLevel.HIGH
    return cluster.clusterId, cluster.trustLevel.value, trusted


def _build_evidence_refs(
    resolution: MemoryResolution,
    recommendation: Recommendation | None,
    report: AnalysisReport,
    lifecycle_by_id: Mapping[str, dict[str, Any]],
    cluster_by_member: Mapping[str, DuplicateCluster],
    *,
    cluster_id: str = "",
) -> tuple[str, ...]:
    refs: list[str] = [f"resolution:{resolution.recommendationId}"]
    if recommendation is not None:
        refs.append(f"recommendation:{recommendation.recommendationId}")
        for evidence in recommendation.evidence:
            if evidence.actionId:
                refs.append(f"governance_action:{evidence.actionId}")
            if evidence.ruleId:
                refs.append(f"policy:{evidence.ruleId}")
            if evidence.caseId:
                refs.append(f"lifecycle:{evidence.caseId}")
    assignment = lifecycle_by_id.get(resolution.memoryId, {})
    if assignment:
        refs.append(f"lifecycle_assignment:{resolution.memoryId}")
        case_id = str(assignment.get("sourceCaseId", ""))
        if case_id:
            refs.append(f"lifecycle:{case_id}")
    if cluster_id:
        refs.append(f"cluster_trust:{cluster_id}")
    elif resolution.memoryId in cluster_by_member:
        refs.append(f"cluster_trust:{cluster_by_member[resolution.memoryId].clusterId}")

    for action in report.actions:
        target = action.target if isinstance(action.target, dict) else {}
        members = target.get("members", [])
        if isinstance(members, list) and resolution.memoryId in members:
            refs.append(f"governance_action:{action.actionId}")

    if recommendation is None:
        refs.extend(
            _validation_fallback_evidence_refs(
                resolution.memoryId,
                report.validation,
            )
        )

    return tuple(dict.fromkeys(refs))


def _validation_fallback_evidence_refs(
    memory_id: str,
    validation: Mapping[str, Any],
) -> list[str]:
    refs: list[str] = []

    lifecycle = validation.get("memoryLifecycle", {})
    if isinstance(lifecycle, dict):
        assignments = lifecycle.get("memoryLifecycleAssignments", [])
        if isinstance(assignments, list):
            for item in assignments:
                if isinstance(item, dict) and item.get("memoryId") == memory_id:
                    case_id = str(item.get("sourceCaseId", ""))
                    if case_id:
                        refs.append(f"lifecycle:{case_id}")

    evolution = validation.get("memoryEvolutionAudit", {})
    if isinstance(evolution, dict):
        for key in (
            "contradictions",
            "preferenceChanges",
            "supersededMemories",
            "staleMemoryCandidates",
            "statusTransitionCandidates",
        ):
            cases = evolution.get(key, [])
            if not isinstance(cases, list):
                continue
            for case in cases:
                if not isinstance(case, dict):
                    continue
                case_id = str(case.get("caseId", ""))
                if not case_id:
                    continue
                memories = case.get("involvedMemories", [])
                if not isinstance(memories, list):
                    continue
                involved_ids = {
                    str(memory.get("memoryId", ""))
                    for memory in memories
                    if isinstance(memory, dict) and memory.get("memoryId")
                }
                if memory_id in involved_ids:
                    refs.append(f"lifecycle:{case_id}")

    category_quality = validation.get("categoryQuality", {})
    if isinstance(category_quality, dict):
        unknown_samples = category_quality.get("unknownSamples", [])
        if isinstance(unknown_samples, list):
            for sample in unknown_samples:
                if isinstance(sample, dict) and sample.get("memoryId") == memory_id:
                    refs.append(f"category_quality:unknown:{memory_id}")

        consistency = category_quality.get("categoryConsistency", {})
        if isinstance(consistency, dict):
            candidates = consistency.get("reclassificationCandidates", [])
            if isinstance(candidates, list):
                for candidate in candidates:
                    if isinstance(candidate, dict) and candidate.get("memoryId") == memory_id:
                        cluster_id = str(candidate.get("clusterId", ""))
                        if cluster_id:
                            refs.append(f"category_quality:reclassification:{cluster_id}")
                        else:
                            refs.append(f"category_quality:reclassification:{memory_id}")

            conflict_clusters = consistency.get("conflictClusters", [])
            if isinstance(conflict_clusters, list):
                for cluster in conflict_clusters:
                    if not isinstance(cluster, dict):
                        continue
                    cluster_id = str(cluster.get("clusterId", ""))
                    members = cluster.get("members", [])
                    if isinstance(members, list) and memory_id in members and cluster_id:
                        refs.append(f"category_quality:conflict_cluster:{cluster_id}")

    return refs


def _fallback_reason(
    resolution: MemoryResolution,
    lifecycle_by_id: Mapping[str, dict[str, Any]],
) -> str:
    rec_id = resolution.recommendationId
    if rec_id.startswith("rec:implicit:keep:") or rec_id.startswith("rec:keep:"):
        lifecycle = lifecycle_by_id.get(resolution.memoryId, {})
        state = str(lifecycle.get("lifecycleState", ""))
        if state == "Active":
            return "Implicit retention: Active lifecycle with no remediation signal."
        return "Implicit retention: no competing remediation signal."

    if resolution.resolvedAction == RecommendationAction.REVIEW:
        suffix = _lifecycle_signal_suffix(resolution.memoryId, lifecycle_by_id)
        base = "Review required per memory resolution."
        return f"{base} {suffix}".strip() if suffix else base

    if resolution.resolvedAction == RecommendationAction.MERGE:
        return "Merge resolution applied in simulation."

    if resolution.resolvedAction == RecommendationAction.ARCHIVE:
        lifecycle = lifecycle_by_id.get(resolution.memoryId, {})
        state = str(lifecycle.get("lifecycleState", ""))
        if state:
            return f"Archive resolution applied in simulation. Lifecycle state: {state}."
        return "Archive resolution applied in simulation."

    return ""


def _lifecycle_signal_suffix(
    memory_id: str,
    lifecycle_by_id: Mapping[str, dict[str, Any]],
) -> str:
    assignment = lifecycle_by_id.get(memory_id, {})
    if not assignment:
        return ""
    state = str(assignment.get("lifecycleState", ""))
    if state:
        return f"Lifecycle signal: {state}."
    return ""


def _resolution_snapshot(resolution: MemoryResolution) -> dict[str, Any]:
    return {
        "resolvedAction": resolution.resolvedAction.value,
        "role": resolution.role,
        "confidence": resolution.confidence,
        "conflictDetected": resolution.conflictDetected,
    }


def _build_explainability(
    resolution: MemoryResolution,
    recommendation: Recommendation | None,
    report: AnalysisReport,
    lifecycle_by_id: Mapping[str, dict[str, Any]],
    cluster_by_member: Mapping[str, DuplicateCluster],
    *,
    cluster_id: str = "",
) -> SimulatedExplainability:
    if recommendation is not None:
        source = "recommendation"
        reason = recommendation.reason
    else:
        source = "resolution_fallback"
        reason = _fallback_reason(resolution, lifecycle_by_id)

    evidence_refs = _build_evidence_refs(
        resolution,
        recommendation,
        report,
        lifecycle_by_id,
        cluster_by_member,
        cluster_id=cluster_id,
    )

    return SimulatedExplainability(
        explainabilitySource=source,
        recommendationId=resolution.recommendationId,
        reason=reason,
        evidenceRefs=evidence_refs,
        resolutionSnapshot=_resolution_snapshot(resolution),
    )


def _build_review_entry(
    resolution: MemoryResolution,
    recommendation: Recommendation | None,
    report: AnalysisReport,
    lifecycle_by_id: Mapping[str, dict[str, Any]],
    cluster_by_member: Mapping[str, DuplicateCluster],
    *,
    orphan_merge_downgrade: bool = False,
) -> SimulatedReviewEntry:
    explainability = _build_explainability(
        resolution,
        recommendation,
        report,
        lifecycle_by_id,
        cluster_by_member,
    )
    reason = explainability.reason
    if orphan_merge_downgrade:
        refs = list(explainability.evidenceRefs)
        refs.append(f"warning:{ORPHAN_MERGE_CODE}")
        explainability = explainability.model_copy(
            update={
                "reason": "Orphan merge downgrade: no keeper in active store.",
                "evidenceRefs": tuple(dict.fromkeys(refs)),
            }
        )
        reason = explainability.reason

    suppressed = tuple(action.value for action in resolution.suppressedActions)
    return SimulatedReviewEntry(
        memoryId=resolution.memoryId,
        recommendationId=resolution.recommendationId,
        reason=reason,
        conflictDetected=resolution.conflictDetected,
        suppressedActions=suppressed,
        explainability=explainability,
        orphanMergeDowngrade=orphan_merge_downgrade,
    )


def _lifecycle_distribution(
    lifecycle_by_id: Mapping[str, dict[str, Any]],
    active_ids: set[str],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for memory_id in active_ids:
        assignment = lifecycle_by_id.get(memory_id, {})
        state = str(assignment.get("lifecycleState", "Unknown"))
        counts[state] += 1
    return dict(counts)


def _compute_metrics(
    *,
    report: AnalysisReport,
    s_before: set[str],
    s_after: set[str],
    simulated_merges: Sequence[SimulatedMergeGroup],
    simulated_archives: Sequence[SimulatedArchiveEntry],
    resolutions_by_id: Mapping[str, MemoryResolution],
    orphan_downgraded: set[str],
    warnings: Sequence[SimulationWarning],
    simulation_mode: str,
) -> SimulationMetrics:
    memory_count_before = len(s_before)
    memory_count_after = len(s_after)
    memory_count_delta = memory_count_after - memory_count_before
    memory_reduction_percentage = (
        _safe_percentage(abs(memory_count_delta), memory_count_before)
        if memory_count_delta < 0
        else 0.0
    )

    estimated_removable_before = sum(
        _removable_estimate(cluster, s_before) for cluster in report.clusters
    )
    estimated_removable_after = sum(
        _removable_estimate(cluster, s_after) for cluster in report.clusters
    )
    estimated_duplicate_reduction = estimated_removable_before - estimated_removable_after

    estimated_structural_before = _safe_percentage(
        estimated_removable_before, memory_count_before
    )
    estimated_structural_after = _safe_percentage(
        estimated_removable_after, memory_count_after
    )
    estimated_compression_gain = (
        estimated_structural_before - estimated_structural_after
    )

    estimated_trusted_before = sum(
        _trusted_removable_estimate(cluster, s_before) for cluster in report.clusters
    )
    estimated_trusted_after = sum(
        _trusted_removable_estimate(cluster, s_after) for cluster in report.clusters
    )
    estimated_trusted_structural_before = _safe_percentage(
        estimated_trusted_before, memory_count_before
    )
    estimated_trusted_structural_after = _safe_percentage(
        estimated_trusted_after, memory_count_after
    )
    estimated_trusted_compression_gain = (
        estimated_trusted_structural_before - estimated_trusted_structural_after
    )

    lifecycle_by_id = _lifecycle_by_id(report.validation)
    lifecycle_before = _lifecycle_distribution(lifecycle_by_id, s_before)
    lifecycle_after = _lifecycle_distribution(lifecycle_by_id, s_after)
    all_states = set(lifecycle_before) | set(lifecycle_after)
    lifecycle_change = {
        state: lifecycle_after.get(state, 0) - lifecycle_before.get(state, 0)
        for state in sorted(all_states)
    }

    archived_by_state: Counter[str] = Counter()
    for entry in simulated_archives:
        archived_by_state[entry.lifecycleState] += 1

    total_resolutions = len(report.memoryResolutions)
    resolutions_applied = sum(
        1 for memory_id in s_before if memory_id not in s_after
    )
    resolutions_no_op = total_resolutions - resolutions_applied

    eligible_actions = {RecommendationAction.MERGE, RecommendationAction.ARCHIVE}
    recommendations_eligible_set: set[str] = set()
    for resolution in report.memoryResolutions:
        if resolution.resolvedAction not in eligible_actions:
            continue
        if resolution.resolvedAction == RecommendationAction.MERGE and simulation_mode == "archive_only":
            continue
        if resolution.resolvedAction == RecommendationAction.ARCHIVE and simulation_mode == "merge_only":
            continue
        recommendations_eligible_set.add(resolution.recommendationId)

    recommendations_with_effect = {
        entry.recommendationId for entry in simulated_merges
    } | {entry.recommendationId for entry in simulated_archives}

    utilization_rate = (
        resolutions_applied / total_resolutions if total_resolutions > 0 else 0.0
    )
    outcome_rate = (
        len(recommendations_with_effect) / len(recommendations_eligible_set)
        if recommendations_eligible_set
        else 0.0
    )

    unresolved = 0
    conflict_review = 0
    for resolution in report.memoryResolutions:
        is_unresolved = (
            resolution.resolvedAction == RecommendationAction.REVIEW
            or resolution.memoryId in orphan_downgraded
            or resolution.conflictDetected
        )
        if is_unresolved:
            unresolved += 1
        if resolution.conflictDetected:
            conflict_review += 1

    suppressed_action_count = sum(
        len(resolution.suppressedActions) for resolution in report.memoryResolutions
    )

    return SimulationMetrics(
        memoryCountBefore=memory_count_before,
        memoryCountAfter=memory_count_after,
        memoryCountDelta=memory_count_delta,
        memoryReductionPercentage=memory_reduction_percentage,
        estimatedRemovableBefore=estimated_removable_before,
        estimatedRemovableAfter=estimated_removable_after,
        estimatedDuplicateReduction=estimated_duplicate_reduction,
        estimatedStructuralCompressionBefore=estimated_structural_before,
        estimatedStructuralCompressionAfter=estimated_structural_after,
        estimatedCompressionGain=estimated_compression_gain,
        estimatedTrustedRemovableBefore=estimated_trusted_before,
        estimatedTrustedRemovableAfter=estimated_trusted_after,
        estimatedTrustedStructuralCompressionBefore=estimated_trusted_structural_before,
        estimatedTrustedStructuralCompressionAfter=estimated_trusted_structural_after,
        estimatedTrustedCompressionGain=estimated_trusted_compression_gain,
        referenceCompressionOpportunity=report.metrics.compressionOpportunity,
        referenceTrustedCompressionOpportunity=report.metrics.trustedCompressionOpportunity,
        lifecycleDistributionBefore=lifecycle_before,
        lifecycleDistributionAfter=lifecycle_after,
        lifecycleDistributionChange=lifecycle_change,
        archivedByLifecycleState=dict(archived_by_state),
        totalResolutions=total_resolutions,
        resolutionsApplied=resolutions_applied,
        resolutionsNoOp=resolutions_no_op,
        mergeGroupsSimulated=len(simulated_merges),
        archivesSimulated=len(simulated_archives),
        recommendationUtilizationRate=round(utilization_rate, 4),
        recommendationsEligible=len(recommendations_eligible_set),
        recommendationsWithStructuralEffect=len(recommendations_with_effect),
        recommendationOutcomeUtilizationRate=round(outcome_rate, 4),
        unresolvedReviewCount=unresolved,
        conflictReviewCount=conflict_review,
        suppressedActionCount=suppressed_action_count,
        simulationWarningCount=len(warnings),
    )


def _compute_simulation_id(report: AnalysisReport, simulation_mode: str) -> str:
    payload = {
        "memories": sorted((memory.id, memory.content) for memory in report.memories),
        "resolutions": sorted(
            (
                resolution.memoryId,
                resolution.resolvedAction.value,
                resolution.role,
                resolution.recommendationId,
                resolution.conflictDetected,
            )
            for resolution in report.memoryResolutions
        ),
        "mode": simulation_mode,
        "policy": report.policySummary.profile.value,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
