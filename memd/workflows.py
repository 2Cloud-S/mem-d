"""Deterministic read-only workflow planner (V0.8 Phase 2 + 2.1 hardening).

``WorkflowBlockerCode.UNSUPPORTED_ACTION`` is reserved. The current closed
``RecommendationAction`` enum is fully handled by explicit planner branches.
If the contract adds a new action value, planner routing and blocker behavior
must be added in the same change — do not emit ``UNSUPPORTED_ACTION`` from
validated contracts without that branch.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from memd.contracts import (
    ActionPriority,
    AnalysisReport,
    ApprovalDecision,
    ApprovalDecisionType,
    CategorizedMemory,
    ClusterTrustLevel,
    GovernanceAction,
    MemoryCategory,
    MemoryRecord,
    MemoryResolution,
    MemoryRoleAssignment,
    OperatorItemStatus,
    PlanAggregateStatus,
    PlannerItemStatus,
    PlanningOptions,
    PolicyDecision,
    Recommendation,
    RecommendationAction,
    ReviewQueueId,
    ReviewRequirement,
    ReviewSubtype,
    SimulatedArchiveEntry,
    SimulatedMergeGroup,
    SimulatedReviewEntry,
    SimulationReport,
    SimulationWarning,
    WorkflowBlocker,
    WorkflowBlockerCode,
    WorkflowEvidence,
    WorkflowItem,
    WorkflowPlan,
    WorkflowPlannerStatus,
    WorkflowPlanningMode,
    WorkflowStep,
    WorkflowStepOperation,
    WorkflowStepType,
    WorkflowSummary,
)
from memd.simulation import (
    DUPLICATE_REMOVAL_CODE,
    ORPHAN_MERGE_CODE,
    _compute_simulation_id,
)

WORKFLOW_PLANNER_VERSION = "2"

ACTION_PRIORITY_RANK: dict[ActionPriority, int] = {
    ActionPriority.CRITICAL: 0,
    ActionPriority.HIGH: 1,
    ActionPriority.MEDIUM: 2,
    ActionPriority.LOW: 3,
    ActionPriority.DEFERRED: 4,
}

NON_OVERRIDABLE_BLOCKER_CODES: frozenset[WorkflowBlockerCode] = frozenset(
    {
        WorkflowBlockerCode.INPUT_INTEGRITY,
        WorkflowBlockerCode.POLICY_BLOCKED,
        WorkflowBlockerCode.ORPHAN_MERGE_NO_KEEPER,
        WorkflowBlockerCode.DUPLICATE_REMOVAL_SKIPPED,
        WorkflowBlockerCode.MISSING_SIMULATION,
        WorkflowBlockerCode.MISSING_KEEPER,
    }
)

PRIMARY_QUEUE_BY_SUBTYPE: tuple[tuple[ReviewSubtype, ReviewQueueId], ...] = (
    (ReviewSubtype.SIMULATION_SAFETY, ReviewQueueId.SIMULATION_SAFETY),
    (ReviewSubtype.ORPHAN_MERGE_DOWNGRADE, ReviewQueueId.SIMULATION_SAFETY),
    (ReviewSubtype.CONFLICT, ReviewQueueId.CONFLICT),
    (ReviewSubtype.POLICY, ReviewQueueId.POLICY),
    (ReviewSubtype.POLICY_BLOCKED, ReviewQueueId.POLICY),
    (ReviewSubtype.UNKNOWN_CATEGORY, ReviewQueueId.UNKNOWN_CATEGORY),
    (ReviewSubtype.LIFECYCLE, ReviewQueueId.LIFECYCLE),
    (ReviewSubtype.LIFECYCLE_ALTERNATE, ReviewQueueId.LIFECYCLE),
    (ReviewSubtype.LIFECYCLE_MIXED, ReviewQueueId.LIFECYCLE),
    (ReviewSubtype.LOW_TRUST, ReviewQueueId.LOW_TRUST),
    (ReviewSubtype.GENERAL, ReviewQueueId.GENERAL),
)

SUBTYPE_TO_QUEUE: dict[ReviewSubtype, ReviewQueueId] = dict(PRIMARY_QUEUE_BY_SUBTYPE)


class WorkflowDecisionError(ValueError):
    """Deterministic rejection of an invalid decision batch."""


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_hex(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _contract_dict(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude_none=False)


@dataclass
class AuditSets:
    unknown_memory_ids: set[str] = field(default_factory=set)
    taxonomy_conflict_memory_ids: set[str] = field(default_factory=set)
    lifecycle_alternate_memory_ids: set[str] = field(default_factory=set)
    lifecycle_mixed_memory_ids: set[str] = field(default_factory=set)
    low_trust_memory_ids: set[str] = field(default_factory=set)
    conflict_memory_ids: set[str] = field(default_factory=set)


@dataclass
class SimulationIndexes:
    merges_by_rec: dict[str, SimulatedMergeGroup] = field(default_factory=dict)
    archives_by_memory: dict[str, SimulatedArchiveEntry] = field(default_factory=dict)
    reviews_by_key: dict[tuple[str, str], SimulatedReviewEntry] = field(default_factory=dict)
    warnings_by_key: dict[tuple[str, str, str], SimulationWarning] = field(default_factory=dict)
    warnings_by_code_digest: dict[tuple[str, str], SimulationWarning] = field(default_factory=dict)


@dataclass
class BlockerDraft:
    code: WorkflowBlockerCode
    message: str
    source_layer: str
    memory_id: str = ""
    recommendation_id: str = ""
    simulation_ref: str = ""
    evidence_ref: str = ""
    integrity_cause: str = ""
    scope: str = "item"
    overridable: bool = False
    blocker_id: str = ""
    item_refs: set[str] = field(default_factory=set)


@dataclass
class ItemDraft:
    recommendation: Recommendation
    workflow_item_id: str = ""
    policy_decision: PolicyDecision | None = None
    planner_item_status: PlannerItemStatus = PlannerItemStatus.PROPOSED
    review_requirement: ReviewRequirement | None = None
    queue_rank: int = 0
    ordering_key: str = ""
    affected_memory_ids: tuple[str, ...] = ()
    roles: tuple[MemoryRoleAssignment, ...] = ()
    blocker_refs: set[str] = field(default_factory=set)
    simulation_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    conflict_detected: bool = False
    suppressed_actions: tuple[RecommendationAction, ...] = ()
    missing_action_ids: tuple[str, ...] = ()
    integrity_affected: bool = False
    r4_failed: bool = False
    structural_conflict: bool = False
    skip_structural_step: bool = False


@dataclass
class StepDraft:
    step_type: WorkflowStepType
    workflow_item_ids: tuple[str, ...]
    planner_step_status: PlannerItemStatus
    operation: WorkflowStepOperation
    depends_on_step_ids: tuple[str, ...] = ()
    step_id: str = ""
    sequence: int = 0
    description: str = ""


@dataclass
class PlanningContext:
    report: AnalysisReport
    options: PlanningOptions
    normalized_recommendations: list[Recommendation] = field(default_factory=list)
    integrity_cause_keys: list[str] = field(default_factory=list)
    conflict_integrity_cause_keys: list[str] = field(default_factory=list)
    conflicting_duplicate_variants: dict[str, list[dict[str, Any]]] = field(
        default_factory=dict
    )
    simulation_verification: dict[str, str] = field(default_factory=dict)
    source_analysis_ref: str = ""
    workflow_plan_id: str = ""
    planning_mode: WorkflowPlanningMode = WorkflowPlanningMode.FULL
    memories_by_id: dict[str, MemoryRecord] = field(default_factory=dict)
    actions_by_id: dict[str, GovernanceAction] = field(default_factory=dict)
    categories_by_id: dict[str, CategorizedMemory] = field(default_factory=dict)
    resolutions_by_rec: dict[str, list[MemoryResolution]] = field(default_factory=dict)
    simulation: SimulationReport | None = None
    simulation_indexes: SimulationIndexes = field(default_factory=SimulationIndexes)
    audit_sets: AuditSets = field(default_factory=AuditSets)
    lifecycle_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)


def _list_value(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _nested_dict(mapping: Mapping[str, object], key: str) -> dict[str, Any]:
    value = mapping.get(key, {})
    return value if isinstance(value, dict) else {}


def _memory_content_fingerprint(memory: MemoryRecord) -> str:
    return _sha256_hex(memory.content)


def _sort_recommendations(recommendations: Sequence[Recommendation]) -> list[Recommendation]:
    return sorted(
        recommendations,
        key=lambda rec: (ACTION_PRIORITY_RANK[rec.priority], rec.recommendationId),
    )


def _normalize_recommendations(
    recommendations: Sequence[Recommendation],
) -> tuple[list[Recommendation], list[str], dict[str, list[dict[str, Any]]]]:
    grouped: dict[str, list[Recommendation]] = defaultdict(list)
    for recommendation in _sort_recommendations(recommendations):
        grouped[recommendation.recommendationId].append(recommendation)

    normalized: list[Recommendation] = []
    conflict_keys: list[str] = []
    conflict_variants: dict[str, list[dict[str, Any]]] = {}

    for recommendation_id in sorted(grouped):
        variants = grouped[recommendation_id]
        canonical_variants: list[dict[str, Any]] = []
        seen: set[str] = set()
        for variant in variants:
            payload = _contract_dict(variant)
            digest = _sha256_hex(payload)
            if digest not in seen:
                seen.add(digest)
                canonical_variants.append(payload)

        if len(canonical_variants) == 1:
            normalized.append(variants[0])
            continue

        sorted_variants = sorted(canonical_variants, key=_sha256_hex)
        bundle_digest = _sha256_hex(sorted_variants)
        conflict_keys.append(f"duplicate_conflict:{recommendation_id}:{bundle_digest}")
        conflict_variants[recommendation_id] = sorted_variants
        survivor = variants[
            min(
                range(len(variants)),
                key=lambda index: _sha256_hex(_contract_dict(variants[index])),
            )
        ]
        normalized.append(survivor)

    return (
        _sort_recommendations(normalized),
        conflict_keys,
        conflict_variants,
    )


def _build_lifecycle_by_id(validation: Mapping[str, object]) -> dict[str, dict[str, Any]]:
    lifecycle = _nested_dict(validation, "memoryLifecycle")
    assignments = _list_value(lifecycle.get("memoryLifecycleAssignments"))
    mapped: dict[str, dict[str, Any]] = {}
    for assignment in assignments:
        if isinstance(assignment, dict) and isinstance(assignment.get("memoryId"), str):
            mapped[assignment["memoryId"]] = assignment
    return mapped


def _unknown_memory_ids(validation: Mapping[str, object]) -> set[str]:
    category_quality = _nested_dict(validation, "categoryQuality")
    samples = _list_value(category_quality.get("unknownSamples"))
    return {
        str(sample.get("memoryId"))
        for sample in samples
        if isinstance(sample, dict) and sample.get("memoryId")
    }


def _taxonomy_conflict_memory_ids(validation: Mapping[str, object]) -> set[str]:
    category_quality = _nested_dict(validation, "categoryQuality")
    consistency = _nested_dict(category_quality, "categoryConsistency")
    conflicts = _list_value(consistency.get("conflictClusters"))
    ids: set[str] = set()
    for conflict in conflicts:
        if not isinstance(conflict, dict):
            continue
        for candidate in _list_value(conflict.get("reclassificationCandidates")):
            if isinstance(candidate, dict) and candidate.get("memoryId"):
                ids.add(str(candidate["memoryId"]))
    return ids


def _build_audit_sets(
    report: AnalysisReport,
    lifecycle_by_id: Mapping[str, dict[str, Any]],
) -> AuditSets:
    unknown_ids = _unknown_memory_ids(report.validation)
    taxonomy_ids = _taxonomy_conflict_memory_ids(report.validation)

    lifecycle_alternate: set[str] = set()
    for memory_id, assignment in lifecycle_by_id.items():
        if assignment.get("alternateLifecycleSignals"):
            lifecycle_alternate.add(memory_id)

    lifecycle_mixed: set[str] = set()
    conflict_ids: set[str] = set()
    low_trust: set[str] = set()

    for cluster in report.clusters:
        if cluster.trustLevel == ClusterTrustLevel.LOW:
            low_trust.update(cluster.members)

    for recommendation in report.recommendations:
        if recommendation.conflictDetected:
            for affected in recommendation.affected_memories:
                conflict_ids.add(affected.memoryId)
        if recommendation.subtype == "conflict":
            for affected in recommendation.affected_memories:
                conflict_ids.add(affected.memoryId)
        if recommendation.subtype == "archive_merge_conflict":
            for affected in recommendation.affected_memories:
                lifecycle_mixed.add(affected.memoryId)
        for evidence in recommendation.evidence:
            if evidence.signal == "trustLevel=Low" or evidence.signal.endswith("=Low"):
                for affected in recommendation.affected_memories:
                    low_trust.add(affected.memoryId)

    for resolution in report.memoryResolutions:
        if resolution.conflictDetected:
            conflict_ids.add(resolution.memoryId)
        suppressed = set(resolution.suppressedActions)
        if (
            RecommendationAction.MERGE in suppressed
            and RecommendationAction.ARCHIVE in suppressed
        ):
            lifecycle_mixed.add(resolution.memoryId)

    for memory_id, category in (
        (memory.memoryId, memory) for memory in report.categories
    ):
        if category.category == MemoryCategory.UNKNOWN:
            unknown_ids.add(memory_id)

    return AuditSets(
        unknown_memory_ids=unknown_ids,
        taxonomy_conflict_memory_ids=taxonomy_ids,
        lifecycle_alternate_memory_ids=lifecycle_alternate,
        lifecycle_mixed_memory_ids=lifecycle_mixed,
        low_trust_memory_ids=low_trust,
        conflict_memory_ids=conflict_ids,
    )


def _build_simulation_indexes(simulation: SimulationReport) -> SimulationIndexes:
    indexes = SimulationIndexes()
    for merge in simulation.simulatedMerges:
        indexes.merges_by_rec[merge.recommendationId] = merge
    for archive in simulation.simulatedArchives:
        indexes.archives_by_memory[archive.memoryId] = archive
    for review in simulation.simulatedReviewQueue:
        indexes.reviews_by_key[(review.memoryId, review.recommendationId)] = review
    for warning in simulation.simulationWarnings:
        key = (warning.code, warning.memoryId, warning.recommendationId)
        indexes.warnings_by_key[key] = warning
        if not warning.memoryId:
            indexes.warnings_by_code_digest[
                (warning.code, _sha256_hex(_contract_dict(warning)))
            ] = warning
    return indexes


def _simulation_report_projection(simulation: SimulationReport | None) -> dict[str, Any] | None:
    if simulation is None:
        return None
    return {
        "simulationId": simulation.simulationId,
        "simulationMode": simulation.simulationMode,
        "analysisReportRef": simulation.analysisReportRef,
        "simulatedMerges": sorted(
            [_contract_dict(merge) for merge in simulation.simulatedMerges],
            key=lambda row: row["recommendationId"],
        ),
        "simulatedArchives": sorted(
            [_contract_dict(archive) for archive in simulation.simulatedArchives],
            key=lambda row: row["memoryId"],
        ),
        "simulatedReviewQueue": sorted(
            [_contract_dict(review) for review in simulation.simulatedReviewQueue],
            key=lambda row: (row["memoryId"], row["recommendationId"]),
        ),
        "simulationWarnings": sorted(
            [_contract_dict(warning) for warning in simulation.simulationWarnings],
            key=lambda row: (row["code"], row["memoryId"], row["recommendationId"]),
        ),
    }


def _compute_source_analysis_ref(
    report: AnalysisReport,
    normalized_recommendations: Sequence[Recommendation],
) -> str:
    fingerprint = {
        "memories": sorted(
            [
                {"id": memory.id, "contentFingerprint": _memory_content_fingerprint(memory)}
                for memory in report.memories
            ],
            key=lambda row: row["id"],
        ),
        "memoryResolutions": sorted(
            [_contract_dict(resolution) for resolution in report.memoryResolutions],
            key=lambda row: (row["memoryId"], row["recommendationId"]),
        ),
        "recommendations": sorted(
            [_contract_dict(recommendation) for recommendation in normalized_recommendations],
            key=lambda row: row["recommendationId"],
        ),
        "actions": sorted(
            [
                {
                    "actionId": action.actionId,
                    "actionType": action.actionType.value,
                    "policyDecision": (
                        action.policyDecision.value if action.policyDecision else None
                    ),
                    "policyRuleId": action.policyRuleId,
                }
                for action in report.actions
            ],
            key=lambda row: row["actionId"],
        ),
        "policyProfile": report.policySummary.profile.value,
    }
    return _sha256_hex(fingerprint)


def _verify_simulation(
    report: AnalysisReport,
    source_analysis_ref: str,
    integrity_cause_keys: list[str],
) -> dict[str, str]:
    simulation = report.simulationReport
    if simulation is None:
        return {
            "reportedSimulationId": "",
            "expectedSimulationId": "",
            "verificationStatus": "absent",
        }

    reported_id = simulation.simulationId
    expected_id = _compute_simulation_id(report, simulation.simulationMode)
    if reported_id == expected_id:
        verification_status = "matched"
    else:
        verification_status = "mismatched"
        integrity_cause_keys.append(f"simulation_id_mismatch:{reported_id}:{expected_id}")

    if simulation.analysisReportRef and simulation.analysisReportRef != source_analysis_ref:
        integrity_cause_keys.append(
            "analysis_report_ref_mismatch:"
            f"{simulation.analysisReportRef}:{source_analysis_ref}"
        )

    return {
        "reportedSimulationId": reported_id,
        "expectedSimulationId": expected_id,
        "verificationStatus": verification_status,
    }


def _compute_workflow_plan_id(
    ctx: PlanningContext,
    normalized_recommendations: Sequence[Recommendation],
) -> str:
    report = ctx.report
    audit = ctx.audit_sets
    planner_signal_inputs = {
        "plannerVersion": WORKFLOW_PLANNER_VERSION,
        "planningOptions": _contract_dict(ctx.options),
        "sourceAnalysisRef": ctx.source_analysis_ref,
        "simulationVerification": ctx.simulation_verification,
        "policyProfile": report.policySummary.profile.value,
        "memories": sorted(
            [
                {"id": memory.id, "contentFingerprint": _memory_content_fingerprint(memory)}
                for memory in report.memories
            ],
            key=lambda row: row["id"],
        ),
        "categories": sorted(
            [_contract_dict(category) for category in report.categories],
            key=lambda row: row["memoryId"],
        ),
        "validation": report.validation,
        "clusters": sorted(
            [_contract_dict(cluster) for cluster in report.clusters],
            key=lambda row: row["clusterId"],
        ),
        "actions": sorted(
            [_contract_dict(action) for action in report.actions],
            key=lambda row: row["actionId"],
        ),
        "recommendations": sorted(
            [_contract_dict(recommendation) for recommendation in normalized_recommendations],
            key=lambda row: row["recommendationId"],
        ),
        "memoryResolutions": sorted(
            [_contract_dict(resolution) for resolution in report.memoryResolutions],
            key=lambda row: (row["memoryId"], row["recommendationId"]),
        ),
        "simulationReport": _simulation_report_projection(ctx.simulation),
        "integrityCauseKeys": sorted(ctx.conflict_integrity_cause_keys),
        "auditSets": {
            "unknownMemoryIds": sorted(audit.unknown_memory_ids),
            "taxonomyConflictMemoryIds": sorted(audit.taxonomy_conflict_memory_ids),
            "lifecycleAlternateMemoryIds": sorted(audit.lifecycle_alternate_memory_ids),
            "lifecycleMixedMemoryIds": sorted(audit.lifecycle_mixed_memory_ids),
            "lowTrustMemoryIds": sorted(audit.low_trust_memory_ids),
            "conflictMemoryIds": sorted(audit.conflict_memory_ids),
        },
    }
    return _sha256_hex(planner_signal_inputs)


def _aggregate_policy(
    recommendation: Recommendation,
    actions_by_id: Mapping[str, GovernanceAction],
) -> tuple[PolicyDecision | None, tuple[str, ...]]:
    missing: list[str] = []
    if not recommendation.sourceActionIds:
        return None, tuple()

    effective: PolicyDecision | None = None
    has_unresolved = False
    for action_id in sorted(recommendation.sourceActionIds):
        action = actions_by_id.get(action_id)
        if action is None:
            missing.append(action_id)
            continue
        decision = action.policyDecision
        if decision is None:
            has_unresolved = True
            continue
        if decision == PolicyDecision.BLOCKED:
            return PolicyDecision.BLOCKED, tuple(missing)
        if decision == PolicyDecision.REQUIRES_REVIEW:
            effective = PolicyDecision.REQUIRES_REVIEW
        elif decision == PolicyDecision.APPROVED and effective is None:
            effective = PolicyDecision.APPROVED

    if missing:
        return None, tuple(sorted(missing))
    if has_unresolved:
        return PolicyDecision.REQUIRES_REVIEW, tuple()
    return effective, tuple()


def _warning_ref(warning: SimulationWarning) -> str:
    if warning.memoryId:
        return f"warning:{warning.code}:{warning.memoryId}"
    return f"warning:{warning.code}:{_sha256_hex(_contract_dict(warning))}"


def _collect_simulation_refs(
    recommendation: Recommendation,
    ctx: PlanningContext,
) -> tuple[str, ...]:
    refs: list[str] = []
    rec_id = recommendation.recommendationId
    if ctx.simulation is None:
        return tuple()

    if recommendation.action == RecommendationAction.MERGE:
        refs.append(f"merge:{rec_id}")

    for affected in recommendation.affected_memories:
        memory_id = affected.memoryId
        if recommendation.action == RecommendationAction.ARCHIVE:
            refs.append(f"archive:{memory_id}")
        review_key = (memory_id, rec_id)
        if review_key in ctx.simulation_indexes.reviews_by_key:
            refs.append(f"review:{memory_id}:{rec_id}")

    for warning in ctx.simulation.simulationWarnings:
        if warning.recommendationId == rec_id or (
            not warning.recommendationId
            and warning.code in {ORPHAN_MERGE_CODE, DUPLICATE_REMOVAL_CODE}
            and recommendation.action == RecommendationAction.MERGE
        ):
            refs.append(_warning_ref(warning))

    return tuple(dict.fromkeys(refs))


def _resolve_simulation_ref(ref: str, indexes: SimulationIndexes) -> bool:
    if ref.startswith("merge:"):
        return ref.removeprefix("merge:") in indexes.merges_by_rec
    if ref.startswith("archive:"):
        return ref.removeprefix("archive:") in indexes.archives_by_memory
    if ref.startswith("review:"):
        parts = ref.removeprefix("review:").split(":", 1)
        if len(parts) != 2:
            return False
        return (parts[0], parts[1]) in indexes.reviews_by_key
    if ref.startswith("warning:"):
        remainder = ref.removeprefix("warning:")
        parts = remainder.split(":", 1)
        if len(parts) != 2:
            return False
        code, suffix = parts
        if len(suffix) == 64 and all(char in "0123456789abcdef" for char in suffix):
            return (code, suffix) in indexes.warnings_by_code_digest
        for key, _warning in indexes.warnings_by_key.items():
            if key[0] == code and key[1] == suffix:
                return True
        return False
    return False


def _match_specific_subtypes(
    recommendation: Recommendation,
    ctx: PlanningContext,
    policy_decision: PolicyDecision | None,
) -> set[ReviewSubtype]:
    if policy_decision == PolicyDecision.BLOCKED:
        return set()

    subtypes: set[ReviewSubtype] = set()
    rec_id = recommendation.recommendationId
    indexes = ctx.simulation_indexes
    audit = ctx.audit_sets

    if ctx.simulation is not None:
        for review in ctx.simulation.simulatedReviewQueue:
            if review.recommendationId == rec_id and review.orphanMergeDowngrade:
                subtypes.add(ReviewSubtype.ORPHAN_MERGE_DOWNGRADE)
        for warning in ctx.simulation.simulationWarnings:
            if warning.code == ORPHAN_MERGE_CODE and (
                warning.recommendationId == rec_id or rec_id in indexes.merges_by_rec
            ):
                subtypes.add(ReviewSubtype.ORPHAN_MERGE_DOWNGRADE)
            if warning.code == DUPLICATE_REMOVAL_CODE and (
                warning.recommendationId == rec_id or not warning.recommendationId
            ):
                subtypes.add(ReviewSubtype.SIMULATION_SAFETY)

    if recommendation.conflictDetected or recommendation.subtype == "conflict":
        subtypes.add(ReviewSubtype.CONFLICT)
    for resolution in ctx.resolutions_by_rec.get(rec_id, ()):
        if resolution.conflictDetected:
            subtypes.add(ReviewSubtype.CONFLICT)

    if policy_decision == PolicyDecision.REQUIRES_REVIEW:
        subtypes.add(ReviewSubtype.POLICY)
    if recommendation.subtype == "policy_blocked_merge":
        subtypes.add(ReviewSubtype.POLICY)

    for affected in recommendation.affected_memories:
        memory_id = affected.memoryId
        if memory_id in audit.unknown_memory_ids:
            subtypes.add(ReviewSubtype.UNKNOWN_CATEGORY)
        category = ctx.categories_by_id.get(memory_id)
        if category and category.category == MemoryCategory.UNKNOWN:
            subtypes.add(ReviewSubtype.UNKNOWN_CATEGORY)
        if recommendation.subtype == "unknown_category":
            subtypes.add(ReviewSubtype.UNKNOWN_CATEGORY)

        lifecycle = ctx.lifecycle_by_id.get(memory_id, {})
        if lifecycle.get("alternateLifecycleSignals"):
            subtypes.add(ReviewSubtype.LIFECYCLE_ALTERNATE)
        if memory_id in audit.lifecycle_mixed_memory_ids:
            subtypes.add(ReviewSubtype.LIFECYCLE_MIXED)
        if memory_id in audit.low_trust_memory_ids:
            subtypes.add(ReviewSubtype.LOW_TRUST)

        if ctx.simulation is not None:
            merge = indexes.merges_by_rec.get(rec_id)
            if merge and merge.trustLevel == ClusterTrustLevel.LOW.value:
                subtypes.add(ReviewSubtype.LOW_TRUST)

    has_lifecycle_evidence = any(
        evidence.source == "memory_lifecycle" for evidence in recommendation.evidence
    )
    if (
        has_lifecycle_evidence
        and ReviewSubtype.LIFECYCLE_ALTERNATE not in subtypes
        and ReviewSubtype.LIFECYCLE_MIXED not in subtypes
    ):
        subtypes.add(ReviewSubtype.LIFECYCLE)

    return subtypes


def _build_review_requirement(
    recommendation: Recommendation,
    planner_item_status: PlannerItemStatus,
    policy_decision: PolicyDecision | None,
    specific_subtypes: set[ReviewSubtype],
) -> ReviewRequirement:
    if planner_item_status == PlannerItemStatus.BLOCKED:
        return ReviewRequirement(
            required=False,
            reason="",
            subtypes=(),
            primaryQueueId=None,
            queueRefs=(),
            escalationSignals=(),
        )

    independently_required = (
        recommendation.action == RecommendationAction.REVIEW
        or recommendation.requiresHumanApproval
        or policy_decision == PolicyDecision.REQUIRES_REVIEW
        or bool(specific_subtypes)
    )
    if not independently_required:
        return ReviewRequirement(
            required=False,
            reason="",
            subtypes=(),
            primaryQueueId=None,
            queueRefs=(),
            escalationSignals=(),
        )

    subtypes = set(specific_subtypes)
    if not subtypes:
        subtypes.add(ReviewSubtype.GENERAL)

    ordered_subtypes = tuple(sorted(subtypes, key=lambda subtype: subtype.value))
    queue_refs = tuple(
        sorted(
            {SUBTYPE_TO_QUEUE[subtype] for subtype in ordered_subtypes},
            key=lambda queue: queue.value,
        )
    )
    primary_queue_id: ReviewQueueId | None = None
    for subtype, queue in PRIMARY_QUEUE_BY_SUBTYPE:
        if subtype in ordered_subtypes:
            primary_queue_id = queue
            break

    reason = recommendation.reason.strip() or "Review required by workflow planner."
    return ReviewRequirement(
        required=True,
        reason=reason,
        subtypes=ordered_subtypes,
        primaryQueueId=primary_queue_id,
        queueRefs=queue_refs,
        escalationSignals=(),
    )


def _compute_queue_rank(
    recommendation: Recommendation,
    planner_item_status: PlannerItemStatus,
    review_requirement: ReviewRequirement,
    simulation_warning_count: int,
) -> int:
    rank = ACTION_PRIORITY_RANK[recommendation.priority]
    if planner_item_status == PlannerItemStatus.BLOCKED:
        rank += 100
    if recommendation.conflictDetected:
        rank -= 10
    rank -= 5 * simulation_warning_count
    if ReviewSubtype.UNKNOWN_CATEGORY in review_requirement.subtypes:
        rank -= 8
    if recommendation.action == RecommendationAction.KEEP:
        rank += 1000
    return rank


def _suppressed_actions_for_rec(
    resolutions: Sequence[MemoryResolution],
) -> tuple[RecommendationAction, ...]:
    actions: list[RecommendationAction] = []
    for resolution in resolutions:
        actions.extend(resolution.suppressedActions)
    return tuple(dict.fromkeys(actions))


def _roles_for_recommendation(
    recommendation: Recommendation,
    ctx: PlanningContext,
) -> tuple[MemoryRoleAssignment, ...]:
    roles: list[MemoryRoleAssignment] = []
    resolutions = ctx.resolutions_by_rec.get(recommendation.recommendationId, [])
    resolution_roles = {
        resolution.memoryId: resolution.role or resolution.resolvedAction.value
        for resolution in resolutions
    }
    for affected in recommendation.affected_memories:
        role = affected.role or resolution_roles.get(affected.memoryId, affected.role or "affected")
        if not role:
            role = "affected"
        roles.append(MemoryRoleAssignment(memoryId=affected.memoryId, role=role))

    if (
        recommendation.action == RecommendationAction.MERGE
        and ctx.simulation is not None
    ):
        merge = ctx.simulation_indexes.merges_by_rec.get(recommendation.recommendationId)
        if merge:
            roles = [
                MemoryRoleAssignment(memoryId=merge.keeperId, role="keeper"),
                *[
                    MemoryRoleAssignment(memoryId=memory_id, role="removable")
                    for memory_id in merge.removedIds
                ],
            ]
    return tuple(roles)


def _blocker_cause_digest(draft: BlockerDraft) -> str:
    return _sha256_hex(
        {
            "code": draft.code.value,
            "scope": draft.scope,
            "recommendationId": draft.recommendation_id or None,
            "memoryId": draft.memory_id or None,
            "sourceLayer": draft.source_layer,
            "simulationRef": draft.simulation_ref or None,
            "evidenceRef": draft.evidence_ref or None,
            "integrityCause": draft.integrity_cause or None,
        }
    )


def _blocker_id(workflow_plan_id: str, cause_digest: str) -> str:
    return _sha256_hex({"workflowPlanId": workflow_plan_id, "causeDigest": cause_digest})


def _workflow_item_id(
    workflow_plan_id: str,
    recommendation: Recommendation,
    affected_memory_ids: Sequence[str],
) -> str:
    return _sha256_hex(
        {
            "workflowPlanId": workflow_plan_id,
            "recommendationId": recommendation.recommendationId,
            "action": recommendation.action.value,
            "affectedMemoryIds": sorted(affected_memory_ids),
        }
    )


def _step_id(
    workflow_plan_id: str,
    step_type: WorkflowStepType,
    sequence: int,
    workflow_item_ids: Sequence[str],
    operation: WorkflowStepOperation,
) -> str:
    return _sha256_hex(
        {
            "workflowPlanId": workflow_plan_id,
            "stepType": step_type.value,
            "sequence": sequence,
            "workflowItemIds": sorted(workflow_item_ids),
            "operation": _contract_dict(operation),
        }
    )


def _evidence_refs_for_recommendation(recommendation: Recommendation) -> tuple[str, ...]:
    refs: list[str] = []
    for evidence in recommendation.evidence:
        if evidence.actionId:
            refs.append(f"evidence:action:{evidence.actionId}")
        elif evidence.insightId:
            refs.append(f"evidence:insight:{evidence.insightId}")
        elif evidence.caseId:
            refs.append(f"evidence:case:{evidence.caseId}")
        elif evidence.ruleId:
            refs.append(f"evidence:rule:{evidence.ruleId}")
        elif evidence.source and evidence.signal:
            refs.append(f"evidence:{evidence.source}:{_sha256_hex(evidence.signal)}")
    return tuple(dict.fromkeys(refs))


def _duplicate_variant_validation_refs(ctx: PlanningContext) -> tuple[str, ...]:
    refs: list[str] = []
    for recommendation_id in sorted(ctx.conflicting_duplicate_variants):
        for variant in ctx.conflicting_duplicate_variants[recommendation_id]:
            digest = _sha256_hex(variant)
            refs.append(f"duplicate_variant:{recommendation_id}:{digest}")
    return tuple(sorted(set(refs)))


def _planned_structural_memory_ids(
    draft: ItemDraft,
    ctx: PlanningContext,
) -> tuple[str, ...]:
    recommendation = draft.recommendation
    if ctx.simulation is None:
        return tuple()
    if recommendation.action == RecommendationAction.ARCHIVE:
        archive = ctx.simulation_indexes.archives_by_memory
        return tuple(
            sorted(
                memory_id
                for memory_id in draft.affected_memory_ids
                if memory_id in archive
            )
        )
    if recommendation.action == RecommendationAction.MERGE:
        merge = ctx.simulation_indexes.merges_by_rec.get(recommendation.recommendationId)
        if merge and merge.keeperId and merge.removedIds:
            return tuple(sorted({merge.keeperId, *merge.removedIds}))
    return tuple()


def _rebuild_item_review_state(
    draft: ItemDraft,
    ctx: PlanningContext,
    *,
    extra_subtypes: set[ReviewSubtype] | None = None,
) -> None:
    if draft.integrity_affected or draft.planner_item_status == PlannerItemStatus.DEFERRED:
        return
    specific_subtypes = _match_specific_subtypes(
        draft.recommendation, ctx, draft.policy_decision
    )
    if extra_subtypes:
        specific_subtypes |= extra_subtypes
    review_requirement = _build_review_requirement(
        draft.recommendation,
        draft.planner_item_status,
        draft.policy_decision,
        specific_subtypes,
    )
    draft.review_requirement = review_requirement
    if review_requirement.required and draft.planner_item_status != PlannerItemStatus.BLOCKED:
        draft.planner_item_status = PlannerItemStatus.REQUIRES_REVIEW
    elif draft.planner_item_status not in {
        PlannerItemStatus.BLOCKED,
        PlannerItemStatus.DEFERRED,
    }:
        draft.planner_item_status = PlannerItemStatus.PROPOSED


def _apply_structural_overlap_conflicts(
    ctx: PlanningContext,
    item_drafts: list[ItemDraft],
) -> set[str]:
    memory_kinds: dict[str, set[str]] = defaultdict(set)
    for draft in item_drafts:
        if draft.skip_structural_step or draft.planner_item_status == PlannerItemStatus.BLOCKED:
            continue
        recommendation = draft.recommendation
        if recommendation.action == RecommendationAction.ARCHIVE:
            for memory_id in _planned_structural_memory_ids(draft, ctx):
                memory_kinds[memory_id].add("archive")
        elif recommendation.action == RecommendationAction.MERGE:
            for memory_id in _planned_structural_memory_ids(draft, ctx):
                memory_kinds[memory_id].add("merge")

    conflict_memories = {
        memory_id
        for memory_id, kinds in memory_kinds.items()
        if "archive" in kinds and "merge" in kinds
    }
    if not conflict_memories:
        return set()

    for draft in item_drafts:
        if draft.integrity_affected or draft.planner_item_status == PlannerItemStatus.BLOCKED:
            continue
        structural_ids = set(_planned_structural_memory_ids(draft, ctx))
        if not structural_ids.intersection(conflict_memories):
            continue
        draft.structural_conflict = True
        draft.skip_structural_step = True
        draft.conflict_detected = True
        _rebuild_item_review_state(
            draft,
            ctx,
            extra_subtypes={ReviewSubtype.CONFLICT},
        )
        warning_count = sum(1 for ref in draft.simulation_refs if ref.startswith("warning:"))
        draft.queue_rank = _compute_queue_rank(
            draft.recommendation,
            draft.planner_item_status,
            draft.review_requirement or ReviewRequirement(required=False),
            warning_count,
        )
    return conflict_memories


def _process_duplicate_removal_warnings(
    ctx: PlanningContext,
    item_drafts: list[ItemDraft],
    blocker_drafts: list[BlockerDraft],
) -> None:
    if ctx.simulation is None:
        return
    for warning in ctx.simulation.simulationWarnings:
        if warning.code != DUPLICATE_REMOVAL_CODE:
            continue
        if warning.recommendationId:
            for draft in item_drafts:
                if draft.recommendation.recommendationId == warning.recommendationId:
                    blocker_drafts.append(
                        BlockerDraft(
                            code=WorkflowBlockerCode.DUPLICATE_REMOVAL_SKIPPED,
                            message=warning.message,
                            source_layer="simulation",
                            memory_id=warning.memoryId,
                            recommendation_id=warning.recommendationId,
                            simulation_ref=_warning_ref(warning),
                            scope="item",
                            overridable=False,
                        )
                    )
        elif warning.memoryId:
            for draft in item_drafts:
                if warning.memoryId in draft.affected_memory_ids:
                    blocker_drafts.append(
                        BlockerDraft(
                            code=WorkflowBlockerCode.DUPLICATE_REMOVAL_SKIPPED,
                            message=warning.message,
                            source_layer="simulation",
                            memory_id=warning.memoryId,
                            recommendation_id=warning.recommendationId,
                            simulation_ref=_warning_ref(warning),
                            scope="item",
                            overridable=False,
                        )
                    )
        else:
            digest = _sha256_hex(_contract_dict(warning))
            ctx.integrity_cause_keys.append(f"duplicate_removal_unscoped:{digest}")


def _integrity_blocker_message(
    unique_causes: Sequence[str],
    ctx: PlanningContext,
) -> str:
    variant_digests = sorted(
        {
            ref.rsplit(":", 1)[-1]
            for ref in _duplicate_variant_validation_refs(ctx)
        }
    )
    if variant_digests:
        return (
            "Workflow input integrity checks failed. "
            f"duplicate_variant_digests:{','.join(variant_digests)}"
        )
    return "Workflow input integrity checks failed."


def _pass_a(report: AnalysisReport, options: PlanningOptions) -> PlanningContext:
    ctx = PlanningContext(report=report, options=options)
    ctx.memories_by_id = {memory.id: memory for memory in report.memories}
    ctx.actions_by_id = {action.actionId: action for action in report.actions}
    ctx.categories_by_id = {category.memoryId: category for category in report.categories}
    ctx.resolutions_by_rec = defaultdict(list)
    for resolution in report.memoryResolutions:
        ctx.resolutions_by_rec[resolution.recommendationId].append(resolution)
    ctx.resolutions_by_rec = dict(ctx.resolutions_by_rec)

    ctx.simulation = report.simulationReport
    ctx.planning_mode = (
        WorkflowPlanningMode.FULL
        if ctx.simulation is not None
        else WorkflowPlanningMode.RECOMMENDATIONS_ONLY
    )
    if ctx.simulation is not None:
        ctx.simulation_indexes = _build_simulation_indexes(ctx.simulation)

    ctx.lifecycle_by_id = _build_lifecycle_by_id(report.validation)
    ctx.audit_sets = _build_audit_sets(report, ctx.lifecycle_by_id)

    normalized, conflict_keys, conflict_variants = _normalize_recommendations(
        report.recommendations
    )
    ctx.normalized_recommendations = normalized
    ctx.conflict_integrity_cause_keys = conflict_keys
    ctx.conflicting_duplicate_variants = conflict_variants
    ctx.integrity_cause_keys.extend(conflict_keys)

    ctx.source_analysis_ref = _compute_source_analysis_ref(report, normalized)
    ctx.simulation_verification = _verify_simulation(
        report, ctx.source_analysis_ref, ctx.integrity_cause_keys
    )
    ctx.workflow_plan_id = _compute_workflow_plan_id(ctx, normalized)
    return ctx


def _pass_b(ctx: PlanningContext) -> WorkflowPlan:
    blocker_drafts: list[BlockerDraft] = []
    item_drafts: list[ItemDraft] = []

    for recommendation in ctx.normalized_recommendations:
        if recommendation.action == RecommendationAction.KEEP and not ctx.options.includeKeep:
            continue

        affected_ids = tuple(
            sorted({affected.memoryId for affected in recommendation.affected_memories})
        )
        policy_decision, missing_action_ids = _aggregate_policy(
            recommendation, ctx.actions_by_id
        )
        draft = ItemDraft(
            recommendation=recommendation,
            affected_memory_ids=affected_ids,
            conflict_detected=recommendation.conflictDetected,
            suppressed_actions=_suppressed_actions_for_rec(
                ctx.resolutions_by_rec.get(recommendation.recommendationId, ())
            ),
            evidence_refs=_evidence_refs_for_recommendation(recommendation),
        )

        if missing_action_ids:
            for action_id in missing_action_ids:
                ctx.integrity_cause_keys.append(f"missing_source_action:{action_id}")
            draft.missing_action_ids = missing_action_ids
            draft.integrity_affected = True
            draft.policy_decision = None
            draft.planner_item_status = PlannerItemStatus.BLOCKED
            draft.skip_structural_step = True
        elif policy_decision == PolicyDecision.BLOCKED:
            draft.policy_decision = policy_decision
            draft.planner_item_status = PlannerItemStatus.BLOCKED
            blocker_drafts.append(
                BlockerDraft(
                    code=WorkflowBlockerCode.POLICY_BLOCKED,
                    message="Governance policy blocked this recommendation.",
                    source_layer="policy",
                    recommendation_id=recommendation.recommendationId,
                    scope="item",
                    overridable=False,
                )
            )
        else:
            draft.policy_decision = policy_decision

        if ctx.conflict_integrity_cause_keys and recommendation.recommendationId in (
            ctx.conflicting_duplicate_variants
        ):
            draft.integrity_affected = True
            draft.planner_item_status = PlannerItemStatus.BLOCKED
            draft.skip_structural_step = True

        if recommendation.action == RecommendationAction.DEFER and not draft.integrity_affected:
            draft.planner_item_status = PlannerItemStatus.DEFERRED

        specific_subtypes = _match_specific_subtypes(
            recommendation, ctx, draft.policy_decision
        )
        if not draft.integrity_affected and draft.planner_item_status != PlannerItemStatus.DEFERRED:
            review_requirement = _build_review_requirement(
                recommendation,
                draft.planner_item_status,
                draft.policy_decision,
                specific_subtypes,
            )
            draft.review_requirement = review_requirement
            if review_requirement.required:
                draft.planner_item_status = PlannerItemStatus.REQUIRES_REVIEW
            elif draft.planner_item_status not in {
                PlannerItemStatus.BLOCKED,
                PlannerItemStatus.DEFERRED,
            }:
                draft.planner_item_status = PlannerItemStatus.PROPOSED
        else:
            draft.review_requirement = ReviewRequirement(
                required=False,
                reason="",
                subtypes=(),
                primaryQueueId=None,
                queueRefs=(),
                escalationSignals=(),
            )

        draft.simulation_refs = _collect_simulation_refs(recommendation, ctx)

        if ctx.simulation is not None:
            for ref in draft.simulation_refs:
                if not _resolve_simulation_ref(ref, ctx.simulation_indexes):
                    ctx.integrity_cause_keys.append(f"simulation_ref_unresolved:{ref}")
                    draft.integrity_affected = True
                    draft.r4_failed = True
                    draft.planner_item_status = PlannerItemStatus.BLOCKED
                    draft.skip_structural_step = True

        if (
            ctx.planning_mode == WorkflowPlanningMode.RECOMMENDATIONS_ONLY
            and recommendation.action in {RecommendationAction.MERGE, RecommendationAction.ARCHIVE}
        ):
            blocker_drafts.append(
                BlockerDraft(
                    code=WorkflowBlockerCode.MISSING_SIMULATION,
                    message="Structural recommendation requires simulation report.",
                    source_layer="simulation",
                    recommendation_id=recommendation.recommendationId,
                    scope="item",
                    overridable=False,
                )
            )
            draft.skip_structural_step = True

        if recommendation.action == RecommendationAction.MERGE and ctx.simulation is not None:
            merge = ctx.simulation_indexes.merges_by_rec.get(recommendation.recommendationId)
            if merge is None or not merge.keeperId:
                blocker_drafts.append(
                    BlockerDraft(
                        code=WorkflowBlockerCode.MISSING_KEEPER,
                        message="Merge recommendation lacks a simulated keeper.",
                        source_layer="simulation",
                        recommendation_id=recommendation.recommendationId,
                        scope="item",
                        overridable=False,
                    )
                )
                draft.skip_structural_step = True

        for warning in (
            ctx.simulation.simulationWarnings if ctx.simulation is not None else ()
        ):
            if (
                warning.code == ORPHAN_MERGE_CODE
                and warning.recommendationId == recommendation.recommendationId
            ):
                blocker_drafts.append(
                    BlockerDraft(
                        code=WorkflowBlockerCode.ORPHAN_MERGE_NO_KEEPER,
                        message=warning.message,
                        source_layer="simulation",
                        memory_id=warning.memoryId,
                        recommendation_id=warning.recommendationId,
                        simulation_ref=_warning_ref(warning),
                        scope="item",
                        overridable=False,
                    )
                )
        warning_count = sum(
            1
            for ref in draft.simulation_refs
            if ref.startswith("warning:")
        )
        draft.queue_rank = _compute_queue_rank(
            recommendation,
            draft.planner_item_status,
            draft.review_requirement or ReviewRequirement(required=False),
            warning_count,
        )
        draft.ordering_key = (
            f"{recommendation.priority.value}:{recommendation.action.value}:"
            f"{recommendation.recommendationId}"
        )
        draft.workflow_item_id = _workflow_item_id(
            ctx.workflow_plan_id, recommendation, draft.affected_memory_ids
        )
        item_drafts.append(draft)

    _apply_structural_overlap_conflicts(ctx, item_drafts)
    _process_duplicate_removal_warnings(ctx, item_drafts, blocker_drafts)

    integrity_blocker_id = ""
    if ctx.integrity_cause_keys:
        unique_causes = sorted(set(ctx.integrity_cause_keys))
        integrity_digest = _sha256_hex(
            {
                "code": WorkflowBlockerCode.INPUT_INTEGRITY.value,
                "scope": "plan",
                "integrityCauses": unique_causes,
            }
        )
        integrity_blocker_id = _blocker_id(ctx.workflow_plan_id, integrity_digest)
        blocker_drafts.append(
            BlockerDraft(
                code=WorkflowBlockerCode.INPUT_INTEGRITY,
                message=_integrity_blocker_message(unique_causes, ctx),
                source_layer="planner",
                integrity_cause="|".join(unique_causes),
                scope="plan",
                overridable=False,
                blocker_id=integrity_blocker_id,
            )
        )

    deduped_blockers: dict[str, BlockerDraft] = {}
    for draft in blocker_drafts:
        if draft.blocker_id:
            deduped_blockers[draft.blocker_id] = draft
            continue
        cause_digest = _blocker_cause_digest(draft)
        blocker_id = _blocker_id(ctx.workflow_plan_id, cause_digest)
        draft.blocker_id = blocker_id
        if blocker_id not in deduped_blockers:
            deduped_blockers[blocker_id] = draft

    for item in item_drafts:
        if item.integrity_affected and integrity_blocker_id:
            item.blocker_refs.add(integrity_blocker_id)
        for blocker in deduped_blockers.values():
            if blocker.scope != "item":
                continue
            if (
                blocker.recommendation_id
                and blocker.recommendation_id == item.recommendation.recommendationId
            ):
                item.blocker_refs.add(blocker.blocker_id)
            elif (
                not blocker.recommendation_id
                and blocker.memory_id
                and blocker.memory_id in item.affected_memory_ids
            ):
                item.blocker_refs.add(blocker.blocker_id)

    workflow_items = tuple(
        WorkflowItem(
            workflowItemId=item.workflow_item_id,
            recommendationId=item.recommendation.recommendationId,
            action=item.recommendation.action,
            plannerItemStatus=item.planner_item_status,
            operatorItemStatus=OperatorItemStatus.NONE,
            recommendationPriority=item.recommendation.priority,
            queueRank=item.queue_rank,
            reviewRequirement=item.review_requirement
            or ReviewRequirement(required=False),
            affectedMemoryIds=item.affected_memory_ids,
            roles=_roles_for_recommendation(item.recommendation, ctx),
            policyDecision=item.policy_decision,
            requiresHumanApproval=item.recommendation.requiresHumanApproval,
            blockerRefs=tuple(sorted(item.blocker_refs)),
            simulationRefs=item.simulation_refs,
            evidenceRefs=item.evidence_refs,
            orderingKey=item.ordering_key,
            conflictDetected=item.conflict_detected,
            suppressedActions=item.suppressed_actions,
        )
        for item in item_drafts
    )

    item_by_id = {item.workflowItemId: item for item in workflow_items}
    step_drafts: list[StepDraft] = []
    memory_targets: dict[str, set[str]] = defaultdict(set)

    for item in item_drafts:
        recommendation = item.recommendation
        if item.skip_structural_step or item.planner_item_status == PlannerItemStatus.BLOCKED:
            if item.review_requirement and item.review_requirement.required:
                review_targets = tuple(sorted(item.affected_memory_ids))
                if review_targets:
                    operation = WorkflowStepOperation(
                        stepType=WorkflowStepType.REVIEW,
                        reviewTargetIds=review_targets,
                        recommendationIds=(recommendation.recommendationId,),
                    )
                    step_drafts.append(
                        StepDraft(
                            step_type=WorkflowStepType.REVIEW,
                            workflow_item_ids=(item.workflow_item_id,),
                            planner_step_status=item.planner_item_status,
                            operation=operation,
                            description=f"Review {recommendation.recommendationId}",
                        )
                    )
            continue

        if recommendation.action == RecommendationAction.REVIEW or (
            item.review_requirement and item.review_requirement.required
        ):
            review_targets = tuple(sorted(item.affected_memory_ids))
            if review_targets:
                operation = WorkflowStepOperation(
                    stepType=WorkflowStepType.REVIEW,
                    reviewTargetIds=review_targets,
                    recommendationIds=(recommendation.recommendationId,),
                )
                step_drafts.append(
                    StepDraft(
                        step_type=WorkflowStepType.REVIEW,
                        workflow_item_ids=(item.workflow_item_id,),
                        planner_step_status=item.planner_item_status,
                        operation=operation,
                        description=f"Review {recommendation.recommendationId}",
                    )
                )

        if recommendation.action == RecommendationAction.ARCHIVE and ctx.simulation is not None:
            archive = ctx.simulation_indexes.archives_by_memory
            targets = tuple(
                sorted(
                    memory_id
                    for memory_id in item.affected_memory_ids
                    if memory_id in archive
                )
            )
            for memory_id in targets:
                memory_targets[memory_id].add("archive")
            if targets:
                operation = WorkflowStepOperation(
                    stepType=WorkflowStepType.ARCHIVE,
                    archiveTargetIds=targets,
                    recommendationIds=(recommendation.recommendationId,),
                )
                step_drafts.append(
                    StepDraft(
                        step_type=WorkflowStepType.ARCHIVE,
                        workflow_item_ids=(item.workflow_item_id,),
                        planner_step_status=item.planner_item_status,
                        operation=operation,
                        description=f"Archive {recommendation.recommendationId}",
                    )
                )

        if recommendation.action == RecommendationAction.MERGE and ctx.simulation is not None:
            merge = ctx.simulation_indexes.merges_by_rec.get(recommendation.recommendationId)
            if merge and merge.keeperId and merge.removedIds:
                for memory_id in (merge.keeperId, *merge.removedIds):
                    memory_targets[memory_id].add("merge")
                operation = WorkflowStepOperation(
                    stepType=WorkflowStepType.MERGE,
                    keeperId=merge.keeperId,
                    removableIds=merge.removedIds,
                    recommendationIds=(recommendation.recommendationId,),
                )
                step_drafts.append(
                    StepDraft(
                        step_type=WorkflowStepType.MERGE,
                        workflow_item_ids=(item.workflow_item_id,),
                        planner_step_status=item.planner_item_status,
                        operation=operation,
                        description=f"Merge {recommendation.recommendationId}",
                    )
                )

        if recommendation.action == RecommendationAction.KEEP and ctx.options.includeKeep:
            operation = WorkflowStepOperation(
                stepType=WorkflowStepType.RETAIN,
                recommendationIds=(recommendation.recommendationId,),
            )
            step_drafts.append(
                StepDraft(
                    step_type=WorkflowStepType.RETAIN,
                    workflow_item_ids=(item.workflow_item_id,),
                    planner_step_status=PlannerItemStatus.PROPOSED,
                    operation=operation,
                    description=f"Retain {recommendation.recommendationId}",
                )
            )

    conflict_memories = {
        memory_id
        for memory_id, kinds in memory_targets.items()
        if "archive" in kinds and "merge" in kinds
    }
    if conflict_memories:
        step_drafts = [
            step
            for step in step_drafts
            if step.step_type not in {WorkflowStepType.ARCHIVE, WorkflowStepType.MERGE}
            or not any(
                target in conflict_memories
                for target in (
                    step.operation.archiveTargetIds
                    + step.operation.removableIds
                    + ((step.operation.keeperId,) if step.operation.keeperId else ())
                )
            )
        ]

    tier_order = {
        WorkflowStepType.REVIEW: 0,
        WorkflowStepType.ARCHIVE: 1,
        WorkflowStepType.MERGE: 2,
        WorkflowStepType.RETAIN: 3,
    }
    step_drafts.sort(
        key=lambda step: (
            tier_order[step.step_type],
            min(
                item_by_id[item_id].queueRank
                for item_id in step.workflow_item_ids
                if item_id in item_by_id
            ),
            min(
                item_by_id[item_id].orderingKey
                for item_id in step.workflow_item_ids
                if item_id in item_by_id
            ),
            min(step.workflow_item_ids),
        )
    )

    review_steps_by_memory: dict[str, list[str]] = defaultdict(list)
    workflow_steps: list[WorkflowStep] = []
    for sequence, draft in enumerate(step_drafts, start=1):
        depends_on: set[str] = set()
        if draft.step_type in {WorkflowStepType.ARCHIVE, WorkflowStepType.MERGE}:
            targets = draft.operation.archiveTargetIds + draft.operation.removableIds
            if draft.operation.keeperId:
                targets = targets + (draft.operation.keeperId,)
            for memory_id in targets:
                depends_on.update(review_steps_by_memory.get(memory_id, ()))
        step_id = _step_id(
            ctx.workflow_plan_id,
            draft.step_type,
            sequence,
            draft.workflow_item_ids,
            draft.operation,
        )
        step = WorkflowStep(
            stepId=step_id,
            sequence=sequence,
            stepType=draft.step_type,
            workflowItemIds=draft.workflow_item_ids,
            dependsOnStepIds=tuple(sorted(depends_on)),
            plannerStepStatus=draft.planner_step_status,
            operation=draft.operation,
            description=draft.description,
        )
        workflow_steps.append(step)
        if draft.step_type == WorkflowStepType.REVIEW:
            for memory_id in draft.operation.reviewTargetIds:
                review_steps_by_memory[memory_id].append(step_id)

    blockers = tuple(
        WorkflowBlocker(
            blockerId=blocker.blocker_id,
            code=blocker.code,
            message=blocker.message,
            sourceLayer=blocker.source_layer,
            memoryId=blocker.memory_id,
            recommendationId=blocker.recommendation_id,
            overridable=blocker.overridable,
        )
        for blocker in sorted(deduped_blockers.values(), key=lambda row: row.blocker_id)
    )

    keep_count = sum(
        1
        for resolution in ctx.report.memoryResolutions
        if resolution.resolvedAction == RecommendationAction.KEEP
    )
    if ctx.options.includeKeep:
        keep_count = sum(
            1 for item in workflow_items if item.action == RecommendationAction.KEEP
        )

    summary = _build_summary(workflow_items, blockers, keep_count, ctx)
    evidence = _build_evidence(workflow_items, blockers, ctx)
    aggregate_status = compute_aggregate_status(
        planning_mode=ctx.planning_mode,
        items=workflow_items,
        blockers=blockers,
        summary=summary,
    )

    review_queues = tuple(
        sorted(
            {
                queue
                for item in workflow_items
                for queue in item.reviewRequirement.queueRefs
            },
            key=lambda queue: queue.value,
        )
    )

    simulation_id = ctx.simulation.simulationId if ctx.simulation is not None else ""

    return WorkflowPlan(
        workflowPlanId=ctx.workflow_plan_id,
        sourceAnalysisRef=ctx.source_analysis_ref,
        simulationId=simulation_id,
        policyProfile=ctx.report.policySummary.profile,
        plannerStatus=WorkflowPlannerStatus.INITIAL,
        aggregateStatus=aggregate_status,
        items=workflow_items,
        steps=tuple(workflow_steps),
        summary=summary,
        reviewQueues=review_queues,
        blockers=blockers,
        evidence=evidence,
        planningMode=ctx.planning_mode,
        planningOptions=ctx.options,
        plannerVersion=WORKFLOW_PLANNER_VERSION,
        metricsDisclaimer=(
            ctx.simulation.metricsDisclaimer
            if ctx.simulation is not None
            else ""
        ),
        decisionsFingerprint="",
    )


def _build_summary(
    items: tuple[WorkflowItem, ...],
    blockers: tuple[WorkflowBlocker, ...],
    keep_count: int,
    ctx: PlanningContext,
) -> WorkflowSummary:
    items_by_action = {action: 0 for action in RecommendationAction}
    items_by_planner_status = {status: 0 for status in PlannerItemStatus}
    items_by_operator_status = {status: 0 for status in OperatorItemStatus}
    items_by_priority = {priority: 0 for priority in ActionPriority}
    review_queue_counts: dict[ReviewQueueId, int] = {}

    for item in items:
        items_by_action[item.action] += 1
        items_by_planner_status[item.plannerItemStatus] += 1
        items_by_operator_status[item.operatorItemStatus] += 1
        items_by_priority[item.recommendationPriority] += 1
        if item.reviewRequirement.required:
            for queue in item.reviewRequirement.queueRefs:
                review_queue_counts[queue] = review_queue_counts.get(queue, 0) + 1

    estimated_delta = 0
    if ctx.simulation is not None:
        estimated_delta = ctx.simulation.metrics.memoryCountDelta

    return WorkflowSummary(
        totalItems=len(items),
        itemsByAction=items_by_action,
        itemsByPlannerStatus=items_by_planner_status,
        itemsByOperatorStatus=items_by_operator_status,
        itemsByRecommendationPriority=items_by_priority,
        reviewQueueCounts=review_queue_counts,
        blockerCount=len(blockers),
        keepCount=keep_count,
        estimatedStructuralDelta=estimated_delta,
    )


def _build_evidence(
    items: tuple[WorkflowItem, ...],
    blockers: tuple[WorkflowBlocker, ...],
    ctx: PlanningContext,
) -> WorkflowEvidence:
    recommendation_ids: set[str] = set()
    memory_ids: set[str] = set()
    action_ids: set[str] = set()
    insight_ids: set[str] = set()
    simulation_event_ids: set[str] = set()
    warnings: set[str] = set()

    for item in items:
        recommendation_ids.add(item.recommendationId)
        memory_ids.update(item.affectedMemoryIds)
        simulation_event_ids.update(item.simulationRefs)
        recommendation = next(
            rec
            for rec in ctx.normalized_recommendations
            if rec.recommendationId == item.recommendationId
        )
        action_ids.update(recommendation.sourceActionIds)
        insight_ids.update(recommendation.sourceInsightIds)

    for blocker in blockers:
        if blocker.recommendationId:
            recommendation_ids.add(blocker.recommendationId)
        if blocker.memoryId:
            memory_ids.add(blocker.memoryId)
        if blocker.code in {
            WorkflowBlockerCode.ORPHAN_MERGE_NO_KEEPER,
            WorkflowBlockerCode.DUPLICATE_REMOVAL_SKIPPED,
        }:
            warnings.add(blocker.code.value)

    validation_refs: set[str] = set()
    validation_refs.update(_duplicate_variant_validation_refs(ctx))
    for item in items:
        validation_refs.update(item.evidenceRefs)
    for cause in sorted(set(ctx.integrity_cause_keys)):
        if cause.startswith("duplicate_removal_unscoped:"):
            validation_refs.add(f"integrity:{cause}")

    if ctx.integrity_cause_keys:
        for cause in sorted(set(ctx.integrity_cause_keys)):
            if cause.startswith("missing_source_action:"):
                action_ids.add(cause.split(":", 1)[1])

    return WorkflowEvidence(
        recommendationIds=tuple(sorted(recommendation_ids)),
        memoryIds=tuple(sorted(memory_ids)),
        actionIds=tuple(sorted(action_ids)),
        insightIds=tuple(sorted(insight_ids)),
        simulationEventIds=tuple(sorted(simulation_event_ids)),
        validationRefs=tuple(sorted(validation_refs)),
        warnings=tuple(sorted(warnings)),
    )


def _is_plan_level_blocker(blocker: WorkflowBlocker) -> bool:
    return blocker.code == WorkflowBlockerCode.INPUT_INTEGRITY


def _structural_eligible(item: WorkflowItem, blockers_by_id: Mapping[str, WorkflowBlocker]) -> bool:
    if item.action not in {RecommendationAction.MERGE, RecommendationAction.ARCHIVE}:
        return False
    if item.plannerItemStatus in {PlannerItemStatus.BLOCKED, PlannerItemStatus.DEFERRED}:
        return False
    if item.operatorItemStatus != OperatorItemStatus.APPROVED:
        return False
    for blocker_ref in item.blockerRefs:
        blocker = blockers_by_id.get(blocker_ref)
        if blocker is not None and not blocker.overridable:
            return False
    return True


def compute_aggregate_status(
    *,
    planning_mode: WorkflowPlanningMode,
    items: tuple[WorkflowItem, ...],
    blockers: tuple[WorkflowBlocker, ...],
    summary: WorkflowSummary,
) -> PlanAggregateStatus:
    blockers_by_id = {blocker.blockerId: blocker for blocker in blockers}
    actionable = tuple(item for item in items if item.action != RecommendationAction.KEEP)
    structural = tuple(
        item
        for item in actionable
        if item.action in {RecommendationAction.MERGE, RecommendationAction.ARCHIVE}
    )

    has_input_integrity_blocker = any(
        blocker.code == WorkflowBlockerCode.INPUT_INTEGRITY for blocker in blockers
    )
    has_plan_blocker = any(_is_plan_level_blocker(blocker) for blocker in blockers)
    any_item_blocked = any(
        item.plannerItemStatus == PlannerItemStatus.BLOCKED for item in items
    )
    all_actionable_blocked = bool(actionable) and all(
        item.plannerItemStatus == PlannerItemStatus.BLOCKED for item in actionable
    )
    any_non_blocked_actionable = any(
        item.plannerItemStatus != PlannerItemStatus.BLOCKED for item in actionable
    )
    has_mixed_blocked_items = any_item_blocked and any_non_blocked_actionable

    def is_review_item(item: WorkflowItem) -> bool:
        return (
            item.action == RecommendationAction.REVIEW
            or item.plannerItemStatus == PlannerItemStatus.REQUIRES_REVIEW
        )

    def unresolved_review(item: WorkflowItem) -> bool:
        return is_review_item(item) and item.operatorItemStatus == OperatorItemStatus.NONE

    any_unresolved_review = any(unresolved_review(item) for item in items)
    non_structural_actionable = tuple(
        item
        for item in actionable
        if item.action in {RecommendationAction.REVIEW, RecommendationAction.DEFER}
    )
    all_non_structural_resolved = all(
        item.operatorItemStatus
        in {
            OperatorItemStatus.APPROVED,
            OperatorItemStatus.REJECTED,
            OperatorItemStatus.DEFERRED,
        }
        for item in non_structural_actionable
    )
    all_structural_eligible = bool(structural) and all(
        _structural_eligible(item, blockers_by_id) for item in structural
    )
    all_actionable_rejected = bool(actionable) and all(
        item.operatorItemStatus == OperatorItemStatus.REJECTED for item in actionable
    )
    all_actionable_deferred = bool(actionable) and all(
        item.operatorItemStatus == OperatorItemStatus.DEFERRED for item in actionable
    )
    any_structural_approved = any(
        item.operatorItemStatus == OperatorItemStatus.APPROVED for item in structural
    )
    any_actionable_unresolved = any(
        item.operatorItemStatus == OperatorItemStatus.NONE for item in actionable
    )
    all_actionable_operator_resolved = bool(actionable) and all(
        item.operatorItemStatus
        in {
            OperatorItemStatus.APPROVED,
            OperatorItemStatus.REJECTED,
            OperatorItemStatus.DEFERRED,
        }
        for item in actionable
    )

    handoff_ready = (
        len(structural) >= 1
        and all_structural_eligible
        and all_non_structural_resolved
        and not any_unresolved_review
        and not any_item_blocked
        and not has_plan_blocker
        and planning_mode == WorkflowPlanningMode.FULL
    )

    if has_input_integrity_blocker:
        return PlanAggregateStatus.INTEGRITY_BLOCKED
    if summary.totalItems == 0 and summary.keepCount == 0:
        return PlanAggregateStatus.EMPTY
    if summary.totalItems == 0 and summary.keepCount > 0:
        return PlanAggregateStatus.ALL_KEEP
    if summary.totalItems > 0 and all(
        item.action == RecommendationAction.KEEP for item in items
    ):
        return PlanAggregateStatus.ALL_KEEP
    if all_actionable_blocked:
        return PlanAggregateStatus.ALL_BLOCKED
    if any_item_blocked and any_unresolved_review:
        return PlanAggregateStatus.MIXED_BLOCKED_REVIEW
    if has_mixed_blocked_items:
        return PlanAggregateStatus.MIXED_BLOCKED
    if all_actionable_rejected:
        return PlanAggregateStatus.REJECTED
    if all_actionable_deferred:
        return PlanAggregateStatus.DEFERRED
    if handoff_ready:
        return PlanAggregateStatus.READY_FOR_EXECUTION
    if any_structural_approved and any_unresolved_review:
        return PlanAggregateStatus.PARTIALLY_APPROVED
    if any_structural_approved and any_actionable_unresolved:
        return PlanAggregateStatus.PARTIALLY_APPROVED
    if any_structural_approved and not all_structural_eligible:
        return PlanAggregateStatus.PARTIALLY_APPROVED
    if all_actionable_operator_resolved and len(structural) == 0:
        return PlanAggregateStatus.APPROVED
    if (
        all_actionable_operator_resolved
        and len(structural) >= 1
        and not all_structural_eligible
    ):
        return PlanAggregateStatus.APPROVED
    if any_unresolved_review:
        return PlanAggregateStatus.REQUIRES_REVIEW
    if (
        len(structural) == 0
        and bool(actionable)
        and all(is_review_item(item) for item in actionable)
    ):
        return PlanAggregateStatus.REQUIRES_REVIEW
    return PlanAggregateStatus.PROPOSED


def plan_workflows(
    report: AnalysisReport,
    *,
    options: PlanningOptions | None = None,
) -> WorkflowPlan:
    before = report.model_dump(mode="json")
    normalized_options = options or PlanningOptions(includeKeep=False)
    ctx = _pass_a(report, normalized_options)
    plan = _pass_b(ctx)
    after = report.model_dump(mode="json")
    if before != after:
        raise RuntimeError("plan_workflows mutated the input report")
    return plan


def _operator_status_for_decision(
    decision: ApprovalDecisionType,
) -> OperatorItemStatus:
    mapping = {
        ApprovalDecisionType.APPROVED: OperatorItemStatus.APPROVED,
        ApprovalDecisionType.REJECTED: OperatorItemStatus.REJECTED,
        ApprovalDecisionType.DEFERRED: OperatorItemStatus.DEFERRED,
    }
    return mapping[decision]


def _decisions_fingerprint(items: Sequence[WorkflowItem]) -> str:
    if not items:
        return ""
    payload = sorted(
        [
            {
                "workflowItemId": item.workflowItemId,
                "operatorItemStatus": item.operatorItemStatus.value,
            }
            for item in items
        ],
        key=lambda row: row["workflowItemId"],
    )
    return _sha256_hex(payload)


def apply_workflow_decisions(
    plan: WorkflowPlan,
    decisions: tuple[ApprovalDecision, ...],
) -> WorkflowPlan:
    if not decisions:
        return plan

    before = plan.model_dump(mode="json")
    items_by_id = {item.workflowItemId: item for item in plan.items}
    blockers_by_id = {blocker.blockerId: blocker for blocker in plan.blockers}

    normalized: dict[str, ApprovalDecision] = {}
    for decision in decisions:
        if decision.targetId in normalized:
            if normalized[decision.targetId].decision != decision.decision:
                raise WorkflowDecisionError(
                    f"conflicting decisions for target {decision.targetId}"
                )
            continue
        normalized[decision.targetId] = decision

    for target_id, _decision in normalized.items():
        item = items_by_id.get(target_id)
        if item is None:
            raise WorkflowDecisionError(f"unknown workflow item target {target_id}")
        if item.action == RecommendationAction.KEEP:
            raise WorkflowDecisionError(f"cannot apply decisions to keep item {target_id}")
        if item.plannerItemStatus == PlannerItemStatus.BLOCKED:
            raise WorkflowDecisionError(f"workflow item {target_id} is blocked")
        for blocker_ref in item.blockerRefs:
            blocker = blockers_by_id.get(blocker_ref)
            if blocker is not None and not blocker.overridable:
                raise WorkflowDecisionError(
                    f"workflow item {target_id} has non-overridable blocker {blocker_ref}"
                )

    updated_items: list[WorkflowItem] = []
    for item in plan.items:
        decision = normalized.get(item.workflowItemId)
        if decision is None:
            updated_items.append(item)
            continue
        updated_items.append(
            item.model_copy(
                update={
                    "operatorItemStatus": _operator_status_for_decision(decision.decision),
                }
            )
        )

    updated_tuple = tuple(updated_items)
    summary = plan.summary.model_copy(
        update={
            "itemsByOperatorStatus": {
                status: sum(
                    1 for item in updated_tuple if item.operatorItemStatus == status
                )
                for status in OperatorItemStatus
            }
        }
    )
    aggregate_status = compute_aggregate_status(
        planning_mode=plan.planningMode,
        items=updated_tuple,
        blockers=plan.blockers,
        summary=summary,
    )
    updated_plan = plan.model_copy(
        update={
            "items": updated_tuple,
            "summary": summary,
            "aggregateStatus": aggregate_status,
            "plannerStatus": WorkflowPlannerStatus.DECIDED,
            "decisionsFingerprint": _decisions_fingerprint(updated_tuple),
        }
    )
    after = plan.model_dump(mode="json")
    if before != after:
        raise RuntimeError("apply_workflow_decisions mutated the input plan")
    return updated_plan
