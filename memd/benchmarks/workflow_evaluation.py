from __future__ import annotations

# ruff: noqa: E501
import builtins
import copy
import json
import socket
import subprocess
from collections.abc import Callable, Iterable, Mapping, MutableMapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from memd.contracts import (
    ActionPlanSummary,
    ActionPriority,
    ActionType,
    AffectedMemory,
    AnalysisMetrics,
    AnalysisReport,
    ApprovalDecision,
    ApprovalDecisionType,
    CategorizedMemory,
    ClusterTrustLevel,
    DuplicateCluster,
    GovernanceAction,
    MemoryCategory,
    MemoryRecord,
    MemoryResolution,
    OperatorItemStatus,
    PlanAggregateStatus,
    PlanningOptions,
    PolicyDecision,
    PolicyProfile,
    PolicySummary,
    Recommendation,
    RecommendationAction,
    RecommendationEvidence,
    RecommendationSummary,
    ReviewQueueId,
    ReviewSubtype,
    SimulationWarning,
    WorkflowBlockerCode,
    WorkflowStepType,
)
from memd.simulation import simulate_recommendations
from memd.workflows import (
    WORKFLOW_PLANNER_VERSION,
    WorkflowDecisionError,
    apply_workflow_decisions,
    plan_workflows,
)

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
GOLD_PATH = FIXTURES / "workflow_gold.json"
BENCHMARK_NAME = "workflow_evaluation"
GROUND_TRUTH_AUTHORITY = "tests/fixtures/workflow_gold.json"
BENCHMARK_VERSION = "0.8.0"

QUALITY_METRICS: tuple[str, ...] = (
    "overallWorkflowAccuracy",
    "itemConstructionAccuracy",
    "reviewRoutingAccuracy",
    "blockerAccuracy",
    "operationAccuracy",
    "stepOrderingAccuracy",
    "aggregateStatusAccuracy",
    "summaryConsistencyAccuracy",
    "provenanceAccuracy",
    "decisionTransitionAccuracy",
    "identityDeterminismAccuracy",
)

CHECKPOINT_TYPE_TO_METRIC: dict[str, str] = {
    "item_construction": "itemConstructionAccuracy",
    "review_routing": "reviewRoutingAccuracy",
    "blocker": "blockerAccuracy",
    "operation": "operationAccuracy",
    "step_ordering": "stepOrderingAccuracy",
    "aggregate_status": "aggregateStatusAccuracy",
    "summary_consistency": "summaryConsistencyAccuracy",
    "provenance": "provenanceAccuracy",
    "decision_transition": "decisionTransitionAccuracy",
    "identity": "identityDeterminismAccuracy",
}

SAFETY_PROPERTIES: tuple[str, ...] = (
    "source_report_immutability",
    "deterministic_planning",
    "idempotent_repeated_planning",
    "initial_never_ready",
    "zero_structural_never_ready",
    "policy_blocked_remains_blocked",
    "unresolved_policy_requires_review",
    "missing_source_action_fails_closed",
    "keep_never_removes",
    "merge_keeper_removable_safety",
    "integrity_suppresses_readiness",
    "simulation_warnings_visible_scoped",
    "structural_overlap_conflict_review",
    "blocked_decisions_atomic",
    "decision_preserves_steps_operations",
    "plan_id_stable_across_decisions",
    "cumulative_decision_fingerprint",
    "no_effects",
)

REQUIRED_AGGREGATE_STATUSES = {status.value for status in PlanAggregateStatus}
REQUIRED_BLOCKER_CODES = {code.value for code in WorkflowBlockerCode}
REQUIRED_REVIEW_SUBTYPES = {subtype.value for subtype in ReviewSubtype}
REQUIRED_PRIMARY_QUEUES = {queue.value for queue in ReviewQueueId}


@dataclass(frozen=True)
class WorkflowMetric:
    accuracy: float | None
    passed: int
    total: int


@dataclass(frozen=True)
class WorkflowEvaluationFailure:
    kind: str
    caseId: str
    checkpointId: str
    checkpointTuple: tuple[str, str, str, str] | None
    checkpointType: str
    primaryMetric: str
    phase: str
    semanticKey: str
    expected: Any
    actual: Any
    message: str


@dataclass(frozen=True)
class WorkflowCheckpoint:
    case_id: str
    phase: str
    checkpoint_type: str
    semantic_key: str
    expected: Any
    actual: Any
    passed: bool
    message: str = ""

    @property
    def checkpoint_tuple(self) -> tuple[str, str, str, str]:
        return (self.case_id, self.phase, self.checkpoint_type, self.semantic_key)

    @property
    def checkpoint_id(self) -> str:
        return "::".join(self.checkpoint_tuple)

    @property
    def primary_metric(self) -> str:
        return CHECKPOINT_TYPE_TO_METRIC[self.checkpoint_type]


@dataclass(frozen=True)
class SafetyPropertyResult:
    passed: bool
    checksPassed: int
    checksTotal: int
    failures: tuple[WorkflowEvaluationFailure, ...] = ()


@dataclass(frozen=True)
class SafetyResults:
    passed: bool
    properties: dict[str, SafetyPropertyResult]
    failures: tuple[WorkflowEvaluationFailure, ...] = ()


@dataclass(frozen=True)
class WorkflowCaseResult:
    caseId: str
    passed: bool
    checkpointsPassed: int
    checkpointsTotal: int
    initialAggregateStatus: str
    finalAggregateStatus: str


@dataclass(frozen=True)
class WorkflowEvaluationResult:
    benchmark: str
    evaluationStatus: str
    fixtureVersion: str
    plannerVersion: str
    caseCount: int
    checkpointCount: int
    qualityMetrics: dict[str, WorkflowMetric]
    diagnosticMetrics: dict[str, Any]
    safetyResults: SafetyResults
    failures: tuple[WorkflowEvaluationFailure, ...]
    gatePassed: bool
    groundTruthAuthority: str
    diagnosticOnly: bool
    cases: tuple[WorkflowCaseResult, ...] = ()
    fixturePath: Path = GOLD_PATH


@dataclass
class _MetricCounter:
    passed: int = 0
    total: int = 0


@dataclass
class _CaseRuntime:
    case: Mapping[str, Any]
    report: AnalysisReport
    initial: Any
    stages: dict[str, Any] = field(default_factory=dict)
    planning_report_unchanged: bool = True
    planning_report_before: Any = None
    planning_report_after: Any = None
    decision_plan_unchanged: dict[str, bool] = field(default_factory=dict)
    decision_errors: dict[str, bool] = field(default_factory=dict)
    decision_atomic: dict[str, bool] = field(default_factory=dict)
    decision_error_messages: dict[str, str] = field(default_factory=dict)


class WorkflowFixtureError(ValueError):
    """Raised when the workflow gold fixture is invalid before scoring."""


def _json_canonical(value: Any) -> str:
    def default(obj: Any) -> Any:
        if hasattr(obj, "model_dump"):
            return obj.model_dump(mode="json")
        if hasattr(obj, "value"):
            return obj.value
        if isinstance(obj, Path):
            return str(obj)
        return str(obj)

    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=default)


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _metric_dict_invalid() -> dict[str, WorkflowMetric]:
    return {name: WorkflowMetric(accuracy=None, passed=0, total=0) for name in QUALITY_METRICS}


def _failure(
    *,
    kind: str,
    case_id: str,
    checkpoint_type: str,
    phase: str,
    semantic_key: str,
    expected: Any,
    actual: Any,
    message: str,
) -> WorkflowEvaluationFailure:
    metric = CHECKPOINT_TYPE_TO_METRIC.get(checkpoint_type, "")
    checkpoint_tuple: tuple[str, str, str, str] | None = None
    checkpoint_id = ""
    if metric:
        checkpoint_tuple = (case_id, phase, checkpoint_type, semantic_key)
        checkpoint_id = "::".join(checkpoint_tuple)
    return WorkflowEvaluationFailure(
        kind=kind,
        caseId=case_id,
        checkpointId=checkpoint_id,
        checkpointTuple=checkpoint_tuple,
        checkpointType=checkpoint_type,
        primaryMetric=metric,
        phase=phase,
        semanticKey=semantic_key,
        expected=expected,
        actual=actual,
        message=message,
    )


def _to_failure(checkpoint: WorkflowCheckpoint) -> WorkflowEvaluationFailure:
    return WorkflowEvaluationFailure(
        kind="checkpoint_failure",
        caseId=checkpoint.case_id,
        checkpointId=checkpoint.checkpoint_id,
        checkpointTuple=checkpoint.checkpoint_tuple,
        checkpointType=checkpoint.checkpoint_type,
        primaryMetric=checkpoint.primary_metric,
        phase=checkpoint.phase,
        semanticKey=checkpoint.semantic_key,
        expected=checkpoint.expected,
        actual=checkpoint.actual,
        message=checkpoint.message,
    )


def _memory(memory_id: str, content: str | None = None) -> MemoryRecord:
    return MemoryRecord(id=memory_id, content=content or f"memory {memory_id}")


def _metrics(memory_count: int = 3) -> AnalysisMetrics:
    return AnalysisMetrics(
        totalMemories=memory_count,
        duplicateCount=0,
        duplicatePercentage=0.0,
        compressionOpportunity=0.0,
        categoryBreakdown={category: 0 for category in MemoryCategory},
    )


def _recommendation(
    rec_id: str,
    action: RecommendationAction,
    *,
    memory_ids: tuple[str, ...] = ("m1",),
    priority: ActionPriority = ActionPriority.HIGH,
    requires_human: bool = False,
    source_action_ids: tuple[str, ...] = (),
    subtype: str = "",
    conflict: bool = False,
    evidence: tuple[RecommendationEvidence, ...] = (),
) -> Recommendation:
    return Recommendation(
        recommendationId=rec_id,
        action=action,
        subtype=subtype,
        confidence=0.9,
        reason=f"Workflow evaluation recommendation {rec_id}.",
        affected_memories=tuple(
            AffectedMemory(memoryId=memory_id, role="affected") for memory_id in memory_ids
        ),
        evidence=evidence,
        priority=priority,
        requiresHumanApproval=requires_human,
        sourceActionIds=source_action_ids,
        conflictDetected=conflict,
    )


def _resolution(
    memory_id: str,
    rec_id: str,
    action: RecommendationAction,
    *,
    role: str = "",
    suppressed: tuple[RecommendationAction, ...] = (),
    conflict: bool = False,
) -> MemoryResolution:
    return MemoryResolution(
        memoryId=memory_id,
        resolvedAction=action,
        role=role,
        confidence=0.9,
        recommendationId=rec_id,
        suppressedActions=suppressed,
        conflictDetected=conflict,
    )


def _governance_action(
    action_id: str,
    decision: PolicyDecision | None = PolicyDecision.APPROVED,
) -> GovernanceAction:
    return GovernanceAction(
        actionId=action_id,
        actionType=ActionType.MERGE_CLUSTER,
        target={"clusterId": "workflow-eval"},
        title=action_id,
        rationale="workflow evaluation",
        supportingEvidence=(),
        confidence=0.9,
        estimatedImpact="low",
        requiresHumanApproval=False,
        priority=ActionPriority.MEDIUM,
        sourceSignals=("workflow-eval",),
        policyDecision=decision,
    )


def _summary_for(
    recommendations: Sequence[Recommendation],
    resolutions: Sequence[MemoryResolution],
) -> RecommendationSummary:
    counts: MutableMapping[RecommendationAction, int] = {action: 0 for action in RecommendationAction}
    for recommendation in recommendations:
        counts[recommendation.action] += 1
    return RecommendationSummary(
        totalRecommendations=len(recommendations),
        mergeCount=counts[RecommendationAction.MERGE],
        archiveCount=counts[RecommendationAction.ARCHIVE],
        reviewCount=counts[RecommendationAction.REVIEW],
        keepCount=counts[RecommendationAction.KEEP],
        deferredCount=counts[RecommendationAction.DEFER],
        memoryResolutionCount=len(resolutions),
        recommendationsByPriority={priority: 0 for priority in ActionPriority},
    )


def _base_report(
    *,
    memories: tuple[MemoryRecord, ...] | None = None,
    clusters: tuple[DuplicateCluster, ...] = (),
    recommendations: tuple[Recommendation, ...] = (),
    memory_resolutions: tuple[MemoryResolution, ...] = (),
    actions: tuple[GovernanceAction, ...] = (),
    validation: dict[str, Any] | None = None,
    categories: tuple[CategorizedMemory, ...] = (),
) -> AnalysisReport:
    source_memories = memories or (_memory("m1", "alpha"), _memory("m2", "beta"), _memory("m3", "gamma"))
    return AnalysisReport(
        metrics=_metrics(len(source_memories)),
        clusters=clusters,
        memories=source_memories,
        categories=categories,
        validation=validation or {},
        actions=actions,
        actionSummary=ActionPlanSummary(
            totalActions=len(actions),
            safeActions=0,
            reviewActions=0,
            estimatedTrustedSavings=0,
            estimatedUnverifiedSavings=0,
            actionsByPriority={priority: 0 for priority in ActionPriority},
        ),
        policySummary=PolicySummary(profile=PolicyProfile.BALANCED),
        recommendations=recommendations,
        memoryResolutions=memory_resolutions,
        recommendationSummary=_summary_for(recommendations, memory_resolutions),
    )


def _with_simulation(report: AnalysisReport) -> AnalysisReport:
    return report.model_copy(update={"simulationReport": simulate_recommendations(report)})


def _inject_warnings(report: AnalysisReport, warnings: tuple[SimulationWarning, ...]) -> AnalysisReport:
    base = _with_simulation(report) if report.simulationReport is None else report
    assert base.simulationReport is not None
    return base.model_copy(
        update={"simulationReport": base.simulationReport.model_copy(update={"simulationWarnings": warnings})}
    )


def _structural_report(kind: str = "merge") -> AnalysisReport:
    if kind == "archive":
        rec = _recommendation("rec:archive:1", RecommendationAction.ARCHIVE, source_action_ids=("act-archive",))
        return _with_simulation(
            _base_report(
                recommendations=(rec,),
                memory_resolutions=(_resolution("m1", rec.recommendationId, RecommendationAction.ARCHIVE),),
                actions=(_governance_action("act-archive", PolicyDecision.APPROVED),),
            )
        )
    rec = _recommendation(
        "rec:merge:1",
        RecommendationAction.MERGE,
        memory_ids=("m1", "m2"),
        source_action_ids=("act-merge",),
        evidence=(RecommendationEvidence(source="workflow", signal="merge", actionId="act-merge"),),
    )
    return _with_simulation(
        _base_report(
            recommendations=(rec,),
            memory_resolutions=(
                _resolution("m1", rec.recommendationId, RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", rec.recommendationId, RecommendationAction.MERGE, role="removable"),
            ),
            actions=(_governance_action("act-merge", PolicyDecision.APPROVED),),
        )
    )


def _build_report(builder: str) -> AnalysisReport:
    if builder == "empty_plan":
        return _base_report(memories=())
    if builder == "all_keep_summary_only":
        return _base_report(
            recommendations=(),
            memory_resolutions=(
                _resolution("m1", "rec:keep:m1", RecommendationAction.KEEP),
                _resolution("m2", "rec:keep:m2", RecommendationAction.KEEP),
            ),
        )
    if builder == "all_keep_items":
        return _base_report(
            recommendations=(_recommendation("rec:keep:1", RecommendationAction.KEEP),),
            memory_resolutions=(_resolution("m1", "rec:keep:1", RecommendationAction.KEEP),),
        )
    if builder == "safe_merge":
        return _structural_report("merge")
    if builder == "safe_archive":
        return _structural_report("archive")
    if builder == "structural_plus_review":
        merge = _recommendation(
            "rec:merge:1",
            RecommendationAction.MERGE,
            memory_ids=("m1", "m2"),
            source_action_ids=("act-merge",),
        )
        review = _recommendation("rec:review:1", RecommendationAction.REVIEW, memory_ids=("m3",))
        return _with_simulation(
            _base_report(
                recommendations=(merge, review),
                memory_resolutions=(
                    _resolution("m1", merge.recommendationId, RecommendationAction.MERGE, role="keeper"),
                    _resolution("m2", merge.recommendationId, RecommendationAction.MERGE, role="removable"),
                    _resolution("m3", review.recommendationId, RecommendationAction.REVIEW),
                ),
                actions=(_governance_action("act-merge", PolicyDecision.APPROVED),),
            )
        )
    if builder == "review_only":
        return _base_report(
            recommendations=(_recommendation("rec:review:1", RecommendationAction.REVIEW),),
            memory_resolutions=(_resolution("m1", "rec:review:1", RecommendationAction.REVIEW),),
        )
    if builder == "policy_requires_review":
        rec = _recommendation("rec:policy:review", RecommendationAction.MERGE, source_action_ids=("act-review",))
        return _base_report(
            recommendations=(rec,),
            actions=(_governance_action("act-review", PolicyDecision.REQUIRES_REVIEW),),
        )
    if builder == "policy_blocked":
        rec = _recommendation("rec:policy:blocked", RecommendationAction.MERGE, source_action_ids=("act-blocked",))
        return _base_report(
            recommendations=(rec,),
            actions=(_governance_action("act-blocked", PolicyDecision.BLOCKED),),
        )
    if builder == "defer_item":
        return _base_report(
            recommendations=(_recommendation("rec:defer:1", RecommendationAction.DEFER),),
            memory_resolutions=(_resolution("m1", "rec:defer:1", RecommendationAction.DEFER),),
        )
    if builder == "mixed_blocked":
        blocked = _recommendation("rec:blocked", RecommendationAction.MERGE, source_action_ids=("act-blocked",))
        defer = _recommendation("rec:defer:1", RecommendationAction.DEFER, memory_ids=("m3",))
        return _base_report(
            recommendations=(blocked, defer),
            memory_resolutions=(_resolution("m3", "rec:defer:1", RecommendationAction.DEFER),),
            actions=(_governance_action("act-blocked", PolicyDecision.BLOCKED),),
        )
    if builder == "mixed_blocked_review":
        blocked = _recommendation("rec:blocked", RecommendationAction.MERGE, source_action_ids=("act-blocked",))
        review = _recommendation("rec:review:1", RecommendationAction.REVIEW, memory_ids=("m3",))
        return _base_report(
            recommendations=(blocked, review),
            memory_resolutions=(_resolution("m3", "rec:review:1", RecommendationAction.REVIEW),),
            actions=(_governance_action("act-blocked", PolicyDecision.BLOCKED),),
        )
    if builder == "missing_source_action":
        rec = _recommendation("rec:missing-action", RecommendationAction.MERGE, source_action_ids=("missing-act",))
        return _base_report(recommendations=(rec,))
    if builder == "unresolved_policy_action":
        rec = _recommendation("rec:unresolved-action", RecommendationAction.MERGE, source_action_ids=("act-unresolved",))
        return _base_report(
            recommendations=(rec,),
            actions=(_governance_action("act-unresolved", None),),
        )
    if builder == "structural_overlap_conflict":
        archive = _recommendation("rec:archive:overlap", RecommendationAction.ARCHIVE, source_action_ids=("act-archive",))
        merge = _recommendation(
            "rec:merge:overlap",
            RecommendationAction.MERGE,
            memory_ids=("m1", "m2"),
            source_action_ids=("act-merge",),
        )
        return _with_simulation(
            _base_report(
                recommendations=(archive, merge),
                memory_resolutions=(
                    _resolution("m1", archive.recommendationId, RecommendationAction.ARCHIVE),
                    _resolution("m1", merge.recommendationId, RecommendationAction.MERGE, role="keeper"),
                    _resolution("m2", merge.recommendationId, RecommendationAction.MERGE, role="removable"),
                ),
                actions=(
                    _governance_action("act-archive", PolicyDecision.APPROVED),
                    _governance_action("act-merge", PolicyDecision.APPROVED),
                ),
            )
        )
    if builder == "scoped_warning":
        report = _with_simulation(
            _base_report(
                recommendations=(
                    _recommendation("rec:merge:warn", RecommendationAction.MERGE, memory_ids=("m1", "m2"), source_action_ids=("act-1",)),
                    _recommendation("rec:archive:ok", RecommendationAction.ARCHIVE, memory_ids=("m3",), source_action_ids=("act-2",)),
                ),
                memory_resolutions=(
                    _resolution("m1", "rec:merge:warn", RecommendationAction.MERGE, role="keeper"),
                    _resolution("m2", "rec:merge:warn", RecommendationAction.MERGE, role="removable"),
                    _resolution("m3", "rec:archive:ok", RecommendationAction.ARCHIVE),
                ),
                actions=(
                    _governance_action("act-1", PolicyDecision.APPROVED),
                    _governance_action("act-2", PolicyDecision.APPROVED),
                ),
            )
        )
        return _inject_warnings(
            report,
            (SimulationWarning(code="DUPLICATE_REMOVAL_SKIPPED", message="scoped", recommendationId="rec:merge:warn"),),
        )
    if builder == "unscoped_warning":
        report = _structural_report("merge")
        return _inject_warnings(
            report,
            (SimulationWarning(code="DUPLICATE_REMOVAL_SKIPPED", message="unscoped"),),
        )
    if builder == "duplicate_normalization":
        rec = _recommendation("rec:dup", RecommendationAction.REVIEW)
        return _base_report(recommendations=(rec, rec))
    if builder == "conflicting_duplicate_integrity":
        return _base_report(
            recommendations=(
                _recommendation("rec:dup", RecommendationAction.MERGE),
                _recommendation("rec:dup", RecommendationAction.ARCHIVE),
            )
        )
    if builder == "unknown_category_review":
        return _base_report(
            recommendations=(_recommendation("rec:unknown", RecommendationAction.REVIEW),),
            memory_resolutions=(_resolution("m1", "rec:unknown", RecommendationAction.REVIEW),),
            categories=(
                CategorizedMemory(
                    memoryId="m1",
                    category=MemoryCategory.UNKNOWN,
                    confidence=0.5,
                    reason="unknown",
                ),
            ),
            validation={"categoryQuality": {"unknownSamples": [{"memoryId": "m1"}]}},
        )
    if builder == "lifecycle_lowtrust_review":
        return _base_report(
            recommendations=(_recommendation("rec:lifecycle", RecommendationAction.REVIEW),),
            memory_resolutions=(
                MemoryResolution(
                    memoryId="m1",
                    resolvedAction=RecommendationAction.REVIEW,
                    confidence=0.9,
                    recommendationId="rec:lifecycle",
                    suppressedActions=(RecommendationAction.MERGE, RecommendationAction.ARCHIVE),
                ),
            ),
            validation={
                "memoryLifecycle": {
                    "memoryLifecycleAssignments": [
                        {
                            "memoryId": "m1",
                            "lifecycleState": "Active",
                            "alternateLifecycleSignals": ["candidate"],
                        }
                    ]
                }
            },
            clusters=(DuplicateCluster(clusterId="c1", members=("m1", "m2"), averageSimilarity=0.5, trustScore=0.1, trustLevel=ClusterTrustLevel.LOW),),
        )
    if builder == "lifecycle_plain_review":
        return _base_report(
            recommendations=(
                _recommendation(
                    "rec:lifecycle:plain",
                    RecommendationAction.REVIEW,
                    evidence=(RecommendationEvidence(source="memory_lifecycle", signal="stale"),),
                ),
            ),
            memory_resolutions=(_resolution("m1", "rec:lifecycle:plain", RecommendationAction.REVIEW),),
        )
    if builder == "orphan_merge":
        return _with_simulation(
            _base_report(
                recommendations=(_recommendation("rec:orphan", RecommendationAction.MERGE, memory_ids=("m2",)),),
                memory_resolutions=(_resolution("m2", "rec:orphan", RecommendationAction.MERGE, role="removable"),),
            )
        )
    if builder == "missing_simulation":
        rec = _recommendation("rec:merge:no-sim", RecommendationAction.MERGE, memory_ids=("m1", "m2"))
        return _base_report(
            recommendations=(rec,),
            memory_resolutions=(
                _resolution("m1", rec.recommendationId, RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", rec.recommendationId, RecommendationAction.MERGE, role="removable"),
            ),
        )
    raise WorkflowFixtureError(f"unknown workflow fixture builder: {builder}")


def _load_fixture(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise WorkflowFixtureError("workflow fixture must be a JSON object")
    if payload.get("groundTruthAuthority") != GROUND_TRUTH_AUTHORITY:
        raise WorkflowFixtureError("workflow fixture groundTruthAuthority mismatch")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise WorkflowFixtureError("workflow fixture must contain non-empty cases")
    return payload


def _canonical_checkpoint_tuple(case_id: str, phase: str, checkpoint_type: str, semantic_key: str) -> str:
    return json.dumps([case_id, phase, checkpoint_type, semantic_key], separators=(",", ":"), ensure_ascii=False)


def _validate_fixture(payload: Mapping[str, Any]) -> None:
    cases = payload["cases"]
    case_ids: set[str] = set()
    checkpoint_tuples: set[str] = set()
    checkpoint_ids: set[str] = set()
    metrics_seen: set[str] = set()
    aggregates_seen: set[str] = set()
    blockers_seen: set[str] = set()
    subtypes_seen: set[str] = set()
    queues_seen: set[str] = set()
    safety_seen: set[str] = set()
    h_seen: set[str] = set()
    ready_positive = False
    invalid_decision = False
    repeated_run = False
    multi_call = False
    required_case_tags = {
        "empty",
        "all_keep",
        "review_only",
        "all_deferred",
        "all_rejected",
        "integrity_blocked",
        "mixed_blocked",
        "mixed_blocked_review",
        "ready_for_execution",
        "missing_action",
        "unresolved_policy_action",
        "structural_overlap_conflict",
        "scoped_warning",
        "unscoped_warning",
        "duplicate_normalization",
        "conflicting_duplicate_integrity",
        "multi_call_fingerprint",
    }
    tags_seen: set[str] = set()

    for raw_case in cases:
        if not isinstance(raw_case, dict):
            raise WorkflowFixtureError("each workflow case must be an object")
        case_id = str(raw_case.get("caseId", ""))
        if not case_id or case_id in case_ids:
            raise WorkflowFixtureError(f"duplicate or missing caseId: {case_id}")
        case_ids.add(case_id)
        tags_seen.update(str(tag) for tag in raw_case.get("coverageTags", ()))
        expected = raw_case.get("expected", {})
        if not isinstance(expected, dict):
            raise WorkflowFixtureError(f"{case_id}: expected must be an object")
        if raw_case.get("builder") is None:
            raise WorkflowFixtureError(f"{case_id}: builder is required")
        for checkpoint in _expand_expected_checkpoints(raw_case):
            if checkpoint.checkpoint_type not in CHECKPOINT_TYPE_TO_METRIC:
                raise WorkflowFixtureError(f"unknown checkpoint type: {checkpoint.checkpoint_type}")
            encoded = _canonical_checkpoint_tuple(*checkpoint.checkpoint_tuple)
            if encoded in checkpoint_tuples:
                raise WorkflowFixtureError(f"duplicate checkpoint tuple: {checkpoint.checkpoint_tuple}")
            if checkpoint.checkpoint_id in checkpoint_ids:
                raise WorkflowFixtureError(f"duplicate rendered checkpoint ID: {checkpoint.checkpoint_id}")
            checkpoint_tuples.add(encoded)
            checkpoint_ids.add(checkpoint.checkpoint_id)
            metrics_seen.add(checkpoint.primary_metric)
        for status in expected.get("aggregateStatuses", ()):
            aggregates_seen.add(str(status.get("status", "")))
            if status.get("status") == PlanAggregateStatus.READY_FOR_EXECUTION.value:
                ready_positive = True
        for blocker in expected.get("blockers", ()):
            if blocker.get("present", True):
                blockers_seen.add(str(blocker.get("code", "")))
        for code in expected.get("requiredAbsentBlockerCodes", ()):
            blockers_seen.add(str(code))
        for route in expected.get("reviewRoutes", ()):
            subtypes_seen.update(str(subtype) for subtype in route.get("subtypes", ()))
            primary = route.get("primaryQueueId")
            if primary:
                queues_seen.add(str(primary))
            queues_seen.update(str(queue) for queue in route.get("queueRefs", ()))
        safety_seen.update(str(prop) for prop in expected.get("safety", ()))
        for gate in expected.get("hGates", ()):
            h_seen.add(str(gate))
        invalid_decision = invalid_decision or any(
            stage.get("expectError") for stage in expected.get("decisionStages", ())
        )
        repeated_run = repeated_run or any(
            assertion.get("relation") == "repeatedPlanEqual"
            for assertion in expected.get("identityAssertions", ())
        )
        multi_call = multi_call or any(
            assertion.get("relation") == "multiCallFingerprintChanges"
            for assertion in expected.get("identityAssertions", ())
        )

    missing_metrics = set(QUALITY_METRICS) - {"overallWorkflowAccuracy"} - metrics_seen
    if missing_metrics:
        raise WorkflowFixtureError(f"quality metric denominators missing: {sorted(missing_metrics)}")
    if not checkpoint_tuples:
        raise WorkflowFixtureError("overall checkpoint denominator is zero")
    missing_aggregates = REQUIRED_AGGREGATE_STATUSES - aggregates_seen
    if missing_aggregates:
        raise WorkflowFixtureError(f"aggregate status coverage missing: {sorted(missing_aggregates)}")
    missing_blockers = REQUIRED_BLOCKER_CODES - blockers_seen
    if missing_blockers:
        raise WorkflowFixtureError(f"blocker coverage/disposition missing: {sorted(missing_blockers)}")
    disposed_subtypes = set(
        str(subtype)
        for subtype in payload.get("reviewSubtypeDispositions", {}).get("reservedNotEmittedByPlannerVersion", ())
    )
    unknown_disposed_subtypes = disposed_subtypes - REQUIRED_REVIEW_SUBTYPES
    if unknown_disposed_subtypes:
        raise WorkflowFixtureError(f"unknown review subtype disposition: {sorted(unknown_disposed_subtypes)}")
    missing_subtypes = REQUIRED_REVIEW_SUBTYPES - disposed_subtypes - subtypes_seen
    if missing_subtypes:
        raise WorkflowFixtureError(f"review subtype coverage missing: {sorted(missing_subtypes)}")
    missing_queues = REQUIRED_PRIMARY_QUEUES - queues_seen
    if missing_queues:
        raise WorkflowFixtureError(f"review queue coverage missing: {sorted(missing_queues)}")
    missing_safety = set(SAFETY_PROPERTIES) - safety_seen
    if missing_safety:
        raise WorkflowFixtureError(f"safety coverage missing: {sorted(missing_safety)}")
    missing_h = {f"H{i}" for i in range(1, 8)} - h_seen
    if missing_h:
        raise WorkflowFixtureError(f"H-gate negative coverage missing: {sorted(missing_h)}")
    if not ready_positive:
        raise WorkflowFixtureError("ready_for_execution positive control missing")
    if not invalid_decision:
        raise WorkflowFixtureError("invalid decision atomicity case missing")
    if not repeated_run:
        raise WorkflowFixtureError("identity repeated-run case missing")
    if not multi_call:
        raise WorkflowFixtureError("multi-call decision fingerprint case missing")
    missing_tags = required_case_tags - tags_seen
    if missing_tags:
        raise WorkflowFixtureError(f"required case coverage tags missing: {sorted(missing_tags)}")


def _expand_expected_checkpoints(case: Mapping[str, Any]) -> list[WorkflowCheckpoint]:
    case_id = str(case["caseId"])
    expected = case.get("expected", {})
    checkpoints: list[WorkflowCheckpoint] = []
    for item in expected.get("items", ()):
        checkpoints.append(
            WorkflowCheckpoint(case_id, str(item.get("phase", "initial")), "item_construction", str(item["recommendationId"]), item, None, False)
        )
    for route in expected.get("reviewRoutes", ()):
        checkpoints.append(
            WorkflowCheckpoint(case_id, str(route.get("phase", "initial")), "review_routing", str(route["recommendationId"]), route, None, False)
        )
    for blocker in expected.get("blockers", ()):
        key = f"{blocker.get('code')}:{blocker.get('recommendationId', blocker.get('scope', 'plan'))}"
        checkpoints.append(
            WorkflowCheckpoint(case_id, str(blocker.get("phase", "initial")), "blocker", key, blocker, None, False)
        )
    for code in expected.get("requiredAbsentBlockerCodes", ()):
        checkpoints.append(
            WorkflowCheckpoint(case_id, "initial", "blocker", f"absent:{code}", {"code": code, "present": False}, None, False)
        )
    for operation in expected.get("operations", ()):
        checkpoints.append(
            WorkflowCheckpoint(case_id, str(operation.get("phase", "initial")), "operation", str(operation["semanticKey"]), operation, None, False)
        )
    for step in expected.get("steps", ()):
        checkpoints.append(
            WorkflowCheckpoint(case_id, str(step.get("phase", "initial")), "step_ordering", str(step["semanticKey"]), step, None, False)
        )
    for aggregate in expected.get("aggregateStatuses", ()):
        checkpoints.append(
            WorkflowCheckpoint(case_id, str(aggregate.get("phase", "initial")), "aggregate_status", "plan", aggregate, None, False)
        )
    for summary in expected.get("summaries", ()):
        checkpoints.append(
            WorkflowCheckpoint(case_id, str(summary.get("phase", "initial")), "summary_consistency", str(summary.get("semanticKey", "plan")), summary, None, False)
        )
    for provenance in expected.get("provenance", ()):
        checkpoints.append(
            WorkflowCheckpoint(case_id, str(provenance.get("phase", "initial")), "provenance", str(provenance.get("semanticKey", "plan")), provenance, None, False)
        )
    for stage in expected.get("decisionStages", ()):
        checkpoints.append(
            WorkflowCheckpoint(case_id, str(stage["stageId"]), "decision_transition", str(stage["stageId"]), stage, None, False)
        )
    for assertion in expected.get("identityAssertions", ()):
        checkpoints.append(
            WorkflowCheckpoint(case_id, str(assertion.get("phase", "initial")), "identity", str(assertion["semanticKey"]), assertion, None, False)
        )
    return checkpoints


def _options(case: Mapping[str, Any]) -> PlanningOptions:
    raw = case.get("planningOptions", {})
    if not isinstance(raw, dict):
        raw = {}
    return PlanningOptions(includeKeep=bool(raw.get("includeKeep", False)))


def _item_by_rec(plan: Any, rec_id: str) -> Any | None:
    return next((item for item in plan.items if item.recommendationId == rec_id), None)


def _blockers_for(plan: Any, *, code: str, recommendation_id: str = "", memory_id: str = "") -> list[Any]:
    return [
        blocker
        for blocker in plan.blockers
        if blocker.code.value == code
        and (not recommendation_id or blocker.recommendationId == recommendation_id)
        and (not memory_id or blocker.memoryId == memory_id)
    ]


def _plan_for_phase(runtime: _CaseRuntime, phase: str) -> Any:
    if phase == "initial":
        return runtime.initial
    return runtime.stages[phase]


def _evaluate_checkpoint(runtime: _CaseRuntime, checkpoint: WorkflowCheckpoint) -> WorkflowCheckpoint:
    expected = checkpoint.expected
    plan = _plan_for_phase(runtime, checkpoint.phase)
    ctype = checkpoint.checkpoint_type
    passed = False
    actual: Any = None
    message = ""
    if ctype == "item_construction":
        item = _item_by_rec(plan, str(expected["recommendationId"]))
        actual = None if item is None else {
            "action": item.action.value,
            "plannerItemStatus": item.plannerItemStatus.value,
            "operatorItemStatus": item.operatorItemStatus.value,
            "policyDecision": item.policyDecision.value if item.policyDecision else None,
            "requiresHumanApproval": item.requiresHumanApproval,
            "affectedMemoryIds": list(item.affectedMemoryIds),
            "conflictDetected": item.conflictDetected,
        }
        if expected.get("present", True) is False:
            passed = item is None
        elif item is not None:
            checks = []
            for field_name in (
                "action",
                "plannerItemStatus",
                "operatorItemStatus",
                "policyDecision",
                "requiresHumanApproval",
                "affectedMemoryIds",
                "conflictDetected",
            ):
                if field_name in expected:
                    checks.append(actual[field_name] == expected[field_name])
            passed = all(checks)
        message = "item expectation mismatch"
    elif ctype == "review_routing":
        item = _item_by_rec(plan, str(expected["recommendationId"]))
        if item is not None:
            actual = {
                "required": item.reviewRequirement.required,
                "subtypes": [subtype.value for subtype in item.reviewRequirement.subtypes],
                "primaryQueueId": item.reviewRequirement.primaryQueueId.value
                if item.reviewRequirement.primaryQueueId
                else None,
                "queueRefs": [queue.value for queue in item.reviewRequirement.queueRefs],
            }
            passed = (
                actual["required"] == expected.get("required")
                and set(actual["subtypes"]) == set(expected.get("subtypes", ()))
                and actual["primaryQueueId"] == expected.get("primaryQueueId")
                and set(actual["queueRefs"]) == set(expected.get("queueRefs", ()))
            )
        message = "review route mismatch"
    elif ctype == "blocker":
        present = expected.get("present", True)
        blockers = _blockers_for(
            plan,
            code=str(expected["code"]),
            recommendation_id=str(expected.get("recommendationId", "")),
            memory_id=str(expected.get("memoryId", "")),
        )
        actual = [
            {
                "code": blocker.code.value,
                "recommendationId": blocker.recommendationId,
                "memoryId": blocker.memoryId,
                "overridable": blocker.overridable,
            }
            for blocker in blockers
        ]
        if present:
            passed = bool(blockers)
            if "overridable" in expected:
                passed = passed and any(blocker.overridable == expected["overridable"] for blocker in blockers)
        else:
            passed = not blockers
        message = "blocker expectation mismatch"
    elif ctype == "operation":
        expected_type = str(expected["stepType"])
        operations = [
            step.operation
            for step in plan.steps
            if step.operation.stepType.value == expected_type
            and (
                not expected.get("recommendationIds")
                or set(step.operation.recommendationIds) == set(expected.get("recommendationIds", ()))
            )
        ]
        actual = [operation.model_dump(mode="json") for operation in operations]
        if expected.get("present", True) is False:
            passed = not operations
        else:
            passed = bool(operations)
            operation = operations[0] if operations else None
            if operation is not None:
                for field_name in ("keeperId", "removableIds", "archiveTargetIds", "reviewTargetIds"):
                    if field_name in expected:
                        value = getattr(operation, field_name)
                        passed = passed and set(value if isinstance(value, tuple) else (value,)) == set(expected[field_name])
        message = "operation expectation mismatch"
    elif ctype == "step_ordering":
        actual = [(step.sequence, step.stepType.value) for step in sorted(plan.steps, key=lambda step: step.sequence)]
        if "stepTypes" in expected:
            passed = [step_type for _sequence, step_type in actual] == expected["stepTypes"]
        else:
            passed = len(actual) == expected.get("count")
        message = "step ordering mismatch"
    elif ctype == "aggregate_status":
        actual = plan.aggregateStatus.value
        passed = actual == expected["status"]
        message = "aggregate status mismatch"
        h_gates = runtime.case.get("expected", {}).get("hGates", ())
        if h_gates:
            message = f"{','.join(str(gate) for gate in h_gates)} readiness boundary mismatch: {message}"
    elif ctype == "summary_consistency":
        actual = {
            "totalItems": plan.summary.totalItems,
            "keepCount": plan.summary.keepCount,
            "blockerCount": plan.summary.blockerCount,
            "estimatedStructuralDelta": plan.summary.estimatedStructuralDelta,
            "itemsByOperatorStatus": {
                key.value: value for key, value in plan.summary.itemsByOperatorStatus.items()
            },
        }
        passed = True
        for key, value in expected.items():
            if key in {"phase", "semanticKey"}:
                continue
            passed = passed and actual.get(key) == value
        message = "summary mismatch"
    elif ctype == "provenance":
        actual = plan.evidence.model_dump(mode="json")
        passed = True
        if expected.get("matchMode") == "complete":
            for key, value in expected.get("contains", {}).items():
                passed = passed and set(actual.get(key, ())).issuperset(set(value))
        else:
            for key, value in expected.get("contains", {}).items():
                passed = passed and set(actual.get(key, ())).issuperset(set(value))
        message = "provenance mismatch"
    elif ctype == "decision_transition":
        actual = {
            "aggregateStatus": plan.aggregateStatus.value,
            "plannerStatus": plan.plannerStatus.value,
            "decisionsFingerprint": plan.decisionsFingerprint,
            "items": {
                item.recommendationId: item.operatorItemStatus.value for item in plan.items
            },
        }
        if expected.get("expectError"):
            passed = bool(runtime.decision_errors.get(str(expected["stageId"]), False)) and bool(
                runtime.decision_atomic.get(str(expected["stageId"]), False)
            )
            actual["errorSeen"] = runtime.decision_errors.get(str(expected["stageId"]), False)
            actual["unchanged"] = runtime.decision_atomic.get(str(expected["stageId"]), False)
        else:
            passed = actual["aggregateStatus"] == expected.get("aggregateStatus")
            for rec_id, status in expected.get("operatorStatuses", {}).items():
                passed = passed and actual["items"].get(rec_id) == status
            if expected.get("fingerprintNonEmpty"):
                passed = passed and bool(actual["decisionsFingerprint"])
        message = "decision transition mismatch"
    elif ctype == "identity":
        passed, actual = _evaluate_identity(runtime, expected)
        message = "identity assertion mismatch"
    return WorkflowCheckpoint(
        checkpoint.case_id,
        checkpoint.phase,
        checkpoint.checkpoint_type,
        checkpoint.semantic_key,
        expected,
        actual,
        passed,
        "" if passed else message,
    )


def _evaluate_identity(runtime: _CaseRuntime, expected: Mapping[str, Any]) -> tuple[bool, Any]:
    relation = expected.get("relation")
    initial_dump = runtime.initial.model_dump(mode="json")
    if relation == "lowercaseSha256":
        value = runtime.initial.workflowPlanId
        return len(value) == 64 and all(char in "0123456789abcdef" for char in value), value
    if relation == "repeatedPlanEqual":
        repeated = plan_workflows(copy.deepcopy(runtime.report), options=_options(runtime.case))
        return repeated.model_dump(mode="json") == initial_dump, {
            "initial": runtime.initial.workflowPlanId,
            "repeated": repeated.workflowPlanId,
        }
    if relation == "planIdStableAcrossDecisions":
        stage = runtime.stages[str(expected["stageId"])]
        return stage.workflowPlanId == runtime.initial.workflowPlanId, {
            "initial": runtime.initial.workflowPlanId,
            "stage": stage.workflowPlanId,
        }
    if relation == "fingerprintNonEmpty":
        stage = runtime.stages[str(expected["stageId"])]
        return bool(stage.decisionsFingerprint), stage.decisionsFingerprint
    if relation == "multiCallFingerprintChanges":
        first = runtime.stages[str(expected["firstStageId"])]
        second = runtime.stages[str(expected["secondStageId"])]
        return first.decisionsFingerprint != second.decisionsFingerprint, {
            "first": first.decisionsFingerprint,
            "second": second.decisionsFingerprint,
        }
    if relation == "mutationChangesPlanId":
        mutated = runtime.report.model_copy(update={"memories": runtime.report.memories + (_memory("m-new"),)})
        repeated = plan_workflows(mutated, options=_options(runtime.case))
        return repeated.workflowPlanId != runtime.initial.workflowPlanId, {
            "initial": runtime.initial.workflowPlanId,
            "mutated": repeated.workflowPlanId,
        }
    return False, {"unknownRelation": relation}


def _decision_for(plan: Any, spec: Mapping[str, Any]) -> ApprovalDecision:
    if "targetId" in spec:
        target_id = str(spec["targetId"])
    else:
        rec_id = str(spec["recommendationId"])
        item = _item_by_rec(plan, rec_id)
        target_id = item.workflowItemId if item is not None else rec_id
    return ApprovalDecision(
        targetType="workflow_item",
        targetId=target_id,
        decision=ApprovalDecisionType(str(spec["decision"])),
    )


def _run_case(case: Mapping[str, Any]) -> _CaseRuntime:
    report = _build_report(str(case["builder"]))
    planning_before = report.model_dump(mode="json")
    initial = plan_workflows(report, options=_options(case))
    planning_after = report.model_dump(mode="json")
    runtime = _CaseRuntime(
        case=case,
        report=report,
        initial=initial,
        planning_report_unchanged=planning_after == planning_before,
        planning_report_before=planning_before,
        planning_report_after=planning_after,
    )
    current = runtime.initial
    expected = case.get("expected", {})
    for stage in expected.get("decisionStages", ()):
        stage_id = str(stage["stageId"])
        before = current.model_dump(mode="json")
        decisions = tuple(_decision_for(current, decision) for decision in stage.get("decisions", ()))
        try:
            updated = apply_workflow_decisions(current, decisions)
            runtime.decision_errors[stage_id] = False
            runtime.decision_atomic[stage_id] = False
            runtime.decision_plan_unchanged[stage_id] = current.model_dump(mode="json") == before
            current = updated
        except WorkflowDecisionError:
            runtime.decision_errors[stage_id] = True
            runtime.decision_atomic[stage_id] = current.model_dump(mode="json") == before
            runtime.decision_plan_unchanged[stage_id] = runtime.decision_atomic[stage_id]
            runtime.decision_error_messages[stage_id] = "WorkflowDecisionError"
        runtime.stages[stage_id] = current
    return runtime


@contextmanager
def _no_effects_guard() -> Iterable[None]:
    original_socket = socket.socket
    original_create_connection = socket.create_connection
    original_popen = subprocess.Popen
    original_open = builtins.open
    original_write_text = Path.write_text
    original_write_bytes = Path.write_bytes

    def blocked_socket(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("network access attempted during workflow evaluation")

    def blocked_popen(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("subprocess attempted during workflow evaluation")

    def blocked_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            raise AssertionError(f"filesystem write attempted during workflow evaluation: {file}")
        return original_open(file, mode, *args, **kwargs)

    def blocked_write_text(self: Path, *_args: Any, **_kwargs: Any) -> int:
        raise AssertionError(f"filesystem write attempted during workflow evaluation: {self}")

    def blocked_write_bytes(self: Path, *_args: Any, **_kwargs: Any) -> int:
        raise AssertionError(f"filesystem write attempted during workflow evaluation: {self}")

    socket.socket = blocked_socket  # type: ignore[assignment]
    socket.create_connection = blocked_socket  # type: ignore[assignment]
    subprocess.Popen = blocked_popen  # type: ignore[assignment]
    builtins.open = blocked_open  # type: ignore[assignment]
    Path.write_text = blocked_write_text  # type: ignore[assignment]
    Path.write_bytes = blocked_write_bytes  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket = original_socket  # type: ignore[assignment]
        socket.create_connection = original_create_connection  # type: ignore[assignment]
        subprocess.Popen = original_popen  # type: ignore[assignment]
        builtins.open = original_open  # type: ignore[assignment]
        Path.write_text = original_write_text  # type: ignore[assignment]
        Path.write_bytes = original_write_bytes  # type: ignore[assignment]


def _safety_failure(property_name: str, case_id: str, expected: Any, actual: Any, message: str) -> WorkflowEvaluationFailure:
    return _failure(
        kind="safety_failure",
        case_id=case_id,
        checkpoint_type="safety",
        phase="safety",
        semantic_key=property_name,
        expected=expected,
        actual=actual,
        message=message,
    )


def _evaluate_safety(runtimes: Sequence[_CaseRuntime]) -> SafetyResults:
    results: dict[str, SafetyPropertyResult] = {}
    failures: list[WorkflowEvaluationFailure] = []

    def record(prop: str, checks: Sequence[tuple[bool, str, Any, Any, str]]) -> None:
        prop_failures = tuple(
            _safety_failure(prop, case_id, expected, actual, message)
            for passed, case_id, expected, actual, message in checks
            if not passed
        )
        failures.extend(prop_failures)
        results[prop] = SafetyPropertyResult(
            passed=not prop_failures and len(checks) >= 1,
            checksPassed=sum(1 for passed, *_rest in checks if passed),
            checksTotal=len(checks),
            failures=prop_failures,
        )

    record(
        "source_report_immutability",
        [
            (
                runtime.planning_report_unchanged
                and all(runtime.decision_plan_unchanged.values()),
                str(runtime.case["caseId"]),
                "source report and decision input plans unchanged",
                {
                    "planningReportUnchanged": runtime.planning_report_unchanged,
                    "decisionPlanUnchanged": runtime.decision_plan_unchanged,
                },
                "source report or decision input plan mutation detected",
            )
            for runtime in runtimes
        ],
    )
    record(
        "deterministic_planning",
        [
            (
                plan_workflows(copy.deepcopy(runtime.report), options=_options(runtime.case)).model_dump(mode="json")
                == runtime.initial.model_dump(mode="json"),
                str(runtime.case["caseId"]),
                "repeated plan equal",
                runtime.initial.workflowPlanId,
                "planning is not deterministic",
            )
            for runtime in runtimes[:3]
        ],
    )
    record(
        "idempotent_repeated_planning",
        [
            (
                plan_workflows(copy.deepcopy(runtime.report), options=_options(runtime.case)).workflowPlanId
                == runtime.initial.workflowPlanId,
                str(runtime.case["caseId"]),
                runtime.initial.workflowPlanId,
                runtime.initial.workflowPlanId,
                "repeated planning changed identity",
            )
            for runtime in runtimes[-3:]
        ],
    )
    record(
        "initial_never_ready",
        [
            (
                runtime.initial.aggregateStatus != PlanAggregateStatus.READY_FOR_EXECUTION
                and runtime.initial.decisionsFingerprint == ""
                and all(item.operatorItemStatus == OperatorItemStatus.NONE for item in runtime.initial.items),
                str(runtime.case["caseId"]),
                "initial plan not ready and undecided",
                runtime.initial.aggregateStatus.value,
                "initial plan was ready or decided",
            )
            for runtime in runtimes
        ],
    )
    zero_cases = [
        runtime
        for runtime in runtimes
        if "zero_structural" in runtime.case.get("coverageTags", ())
    ]
    record(
        "zero_structural_never_ready",
        [
            (
                all(plan.aggregateStatus != PlanAggregateStatus.READY_FOR_EXECUTION for plan in (runtime.initial, *runtime.stages.values())),
                str(runtime.case["caseId"]),
                "not ready",
                [plan.aggregateStatus.value for plan in (runtime.initial, *runtime.stages.values())],
                "zero structural case became ready",
            )
            for runtime in zero_cases
        ],
    )

    def has_case(prop: str, predicate: Callable[[_CaseRuntime], bool]) -> list[tuple[bool, str, Any, Any, str]]:
        return [
            (
                predicate(runtime),
                str(runtime.case["caseId"]),
                True,
                runtime.initial.aggregateStatus.value,
                f"{prop} failed",
            )
            for runtime in runtimes
            if prop in runtime.case.get("expected", {}).get("safety", ())
        ]

    record(
        "policy_blocked_remains_blocked",
        has_case(
            "policy_blocked_remains_blocked",
            lambda runtime: any(blocker.code == WorkflowBlockerCode.POLICY_BLOCKED and not blocker.overridable for blocker in runtime.initial.blockers),
        ),
    )
    record(
        "unresolved_policy_requires_review",
        has_case(
            "unresolved_policy_requires_review",
            lambda runtime: runtime.initial.aggregateStatus == PlanAggregateStatus.REQUIRES_REVIEW,
        ),
    )
    record(
        "missing_source_action_fails_closed",
        has_case(
            "missing_source_action_fails_closed",
            lambda runtime: runtime.initial.aggregateStatus == PlanAggregateStatus.INTEGRITY_BLOCKED,
        ),
    )
    record(
        "keep_never_removes",
        has_case(
            "keep_never_removes",
            lambda runtime: not any(step.stepType in {WorkflowStepType.MERGE, WorkflowStepType.ARCHIVE} for step in runtime.initial.steps),
        ),
    )
    record(
        "merge_keeper_removable_safety",
        has_case(
            "merge_keeper_removable_safety",
            lambda runtime: any(
                step.operation.stepType == WorkflowStepType.MERGE
                and step.operation.keeperId
                and step.operation.removableIds
                and step.operation.keeperId not in step.operation.removableIds
                for step in runtime.initial.steps
            ),
        ),
    )
    record(
        "integrity_suppresses_readiness",
        has_case(
            "integrity_suppresses_readiness",
            lambda runtime: runtime.initial.aggregateStatus == PlanAggregateStatus.INTEGRITY_BLOCKED
            and not any(plan.aggregateStatus == PlanAggregateStatus.READY_FOR_EXECUTION for plan in (runtime.initial, *runtime.stages.values())),
        ),
    )
    record(
        "simulation_warnings_visible_scoped",
        has_case(
            "simulation_warnings_visible_scoped",
            lambda runtime: bool(runtime.initial.evidence.warnings)
            or runtime.initial.aggregateStatus == PlanAggregateStatus.INTEGRITY_BLOCKED,
        ),
    )
    record(
        "structural_overlap_conflict_review",
        has_case(
            "structural_overlap_conflict_review",
            lambda runtime: any(ReviewSubtype.CONFLICT in item.reviewRequirement.subtypes for item in runtime.initial.items),
        ),
    )
    record(
        "blocked_decisions_atomic",
        has_case(
            "blocked_decisions_atomic",
            lambda runtime: any(
                stage.get("expectError")
                and runtime.decision_errors.get(str(stage["stageId"]), False)
                and runtime.decision_atomic.get(str(stage["stageId"]), False)
                for stage in runtime.case.get("expected", {}).get("decisionStages", ())
            ),
        ),
    )
    record(
        "decision_preserves_steps_operations",
        has_case(
            "decision_preserves_steps_operations",
            lambda runtime: all(
                stage.steps == runtime.initial.steps
                and [step.operation for step in stage.steps] == [step.operation for step in runtime.initial.steps]
                for stage in runtime.stages.values()
            ),
        ),
    )
    record(
        "plan_id_stable_across_decisions",
        has_case(
            "plan_id_stable_across_decisions",
            lambda runtime: all(stage.workflowPlanId == runtime.initial.workflowPlanId for stage in runtime.stages.values()),
        ),
    )
    record(
        "cumulative_decision_fingerprint",
        has_case(
            "cumulative_decision_fingerprint",
            lambda runtime: len({stage.decisionsFingerprint for stage in runtime.stages.values() if stage.decisionsFingerprint}) >= 2,
        ),
    )
    no_effect_cases: list[tuple[bool, str, Any, Any, str]] = []
    for runtime in runtimes:
        try:
            with _no_effects_guard():
                plan_workflows(copy.deepcopy(runtime.report), options=_options(runtime.case))
            no_effect_cases.append((True, str(runtime.case["caseId"]), "no effect", "no effect", "effect attempted"))
        except AssertionError as exc:
            no_effect_cases.append((False, str(runtime.case["caseId"]), "no effect", str(exc), "effect attempted"))
        for stage in runtime.case.get("expected", {}).get("decisionStages", ()):
            stage_id = str(stage["stageId"])
            try:
                with _no_effects_guard():
                    decisions = tuple(_decision_for(runtime.initial, decision) for decision in stage.get("decisions", ()))
                    try:
                        apply_workflow_decisions(runtime.initial, decisions)
                    except WorkflowDecisionError:
                        pass
                no_effect_cases.append((True, str(runtime.case["caseId"]), f"no decision effect:{stage_id}", "no effect", "effect attempted"))
            except AssertionError as exc:
                no_effect_cases.append((False, str(runtime.case["caseId"]), f"no decision effect:{stage_id}", str(exc), "effect attempted"))
    record("no_effects", no_effect_cases)
    return SafetyResults(
        passed=all(result.passed and result.checksTotal >= 1 for result in results.values())
        and set(results) == set(SAFETY_PROPERTIES),
        properties=results,
        failures=tuple(failures),
    )


def _quality_metrics(checkpoints: Sequence[WorkflowCheckpoint]) -> tuple[dict[str, WorkflowMetric], tuple[WorkflowEvaluationFailure, ...]]:
    counters = {name: _MetricCounter() for name in QUALITY_METRICS}
    failures: list[WorkflowEvaluationFailure] = []
    seen: set[tuple[str, str, str, str]] = set()
    for checkpoint in checkpoints:
        if checkpoint.checkpoint_tuple in seen:
            failures.append(_to_failure(checkpoint))
            continue
        seen.add(checkpoint.checkpoint_tuple)
        counters["overallWorkflowAccuracy"].total += 1
        counters[checkpoint.primary_metric].total += 1
        if checkpoint.passed:
            counters["overallWorkflowAccuracy"].passed += 1
            counters[checkpoint.primary_metric].passed += 1
        else:
            failures.append(_to_failure(checkpoint))
    metrics: dict[str, WorkflowMetric] = {}
    for name, counter in counters.items():
        accuracy = counter.passed / counter.total if counter.total else None
        metrics[name] = WorkflowMetric(accuracy=accuracy, passed=counter.passed, total=counter.total)
    return metrics, tuple(failures)


def _diagnostics(runtimes: Sequence[_CaseRuntime]) -> dict[str, Any]:
    status_dist: MutableMapping[str, int] = {}
    queue_dist: MutableMapping[str, int] = {}
    blocker_dist: MutableMapping[str, int] = {}
    mode_dist: MutableMapping[str, int] = {}
    operation_dist: MutableMapping[str, int] = {}
    item_counts: list[int] = []
    step_counts: list[int] = []
    structural_count = 0
    review_count = 0
    integrity_count = 0
    for runtime in runtimes:
        plan = runtime.initial
        status_dist[plan.aggregateStatus.value] = status_dist.get(plan.aggregateStatus.value, 0) + 1
        mode_dist[plan.planningMode.value] = mode_dist.get(plan.planningMode.value, 0) + 1
        item_counts.append(len(plan.items))
        step_counts.append(len(plan.steps))
        if plan.aggregateStatus == PlanAggregateStatus.INTEGRITY_BLOCKED:
            integrity_count += 1
        for queue in plan.reviewQueues:
            queue_dist[queue.value] = queue_dist.get(queue.value, 0) + 1
        for blocker in plan.blockers:
            blocker_dist[blocker.code.value] = blocker_dist.get(blocker.code.value, 0) + 1
        for step in plan.steps:
            operation_dist[step.stepType.value] = operation_dist.get(step.stepType.value, 0) + 1
            if step.stepType in {WorkflowStepType.MERGE, WorkflowStepType.ARCHIVE}:
                structural_count += 1
            if step.stepType == WorkflowStepType.REVIEW:
                review_count += 1
    return {
        "diagnosticOnly": True,
        "workflowStatusDistribution": dict(sorted(status_dist.items())),
        "reviewQueueDistribution": dict(sorted(queue_dist.items())),
        "blockerDistribution": dict(sorted(blocker_dist.items())),
        "planningModeDistribution": dict(sorted(mode_dist.items())),
        "structuralOperationDistribution": dict(sorted(operation_dist.items())),
        "reviewToStructuralRatio": None if structural_count == 0 else review_count / structural_count,
        "averageWorkflowItemsPerCase": sum(item_counts) / len(item_counts) if item_counts else 0.0,
        "averageStepsPerCase": sum(step_counts) / len(step_counts) if step_counts else 0.0,
        "integrityBlockedCaseCount": integrity_count,
    }


def evaluate_workflows(gold_path: Path | None = None) -> WorkflowEvaluationResult:
    path = gold_path or GOLD_PATH
    try:
        payload = _load_fixture(path)
        _validate_fixture(payload)
    except Exception as exc:
        failure = _failure(
            kind="fixture_validation_failure",
            case_id="fixture",
            checkpoint_type="fixture",
            phase="fixture",
            semantic_key="validation",
            expected="valid workflow fixture",
            actual=type(exc).__name__,
            message=str(exc),
        )
        return WorkflowEvaluationResult(
            benchmark=BENCHMARK_NAME,
            evaluationStatus="fixture_invalid",
            fixtureVersion="",
            plannerVersion=WORKFLOW_PLANNER_VERSION,
            caseCount=0,
            checkpointCount=0,
            qualityMetrics=_metric_dict_invalid(),
            diagnosticMetrics={"diagnosticOnly": True},
            safetyResults=SafetyResults(passed=False, properties={}, failures=(failure,)),
            failures=(failure,),
            gatePassed=False,
            groundTruthAuthority=GROUND_TRUTH_AUTHORITY,
            diagnosticOnly=False,
            fixturePath=path,
        )

    try:
        runtimes = [_run_case(case) for case in payload["cases"]]
        evaluated: list[WorkflowCheckpoint] = []
        case_results: list[WorkflowCaseResult] = []
        for runtime in runtimes:
            before_count = len(evaluated)
            for checkpoint in _expand_expected_checkpoints(runtime.case):
                evaluated.append(_evaluate_checkpoint(runtime, checkpoint))
            case_checks = evaluated[before_count:]
            final_plan = next(reversed(runtime.stages.values()), runtime.initial)
            case_results.append(
                WorkflowCaseResult(
                    caseId=str(runtime.case["caseId"]),
                    passed=all(checkpoint.passed for checkpoint in case_checks),
                    checkpointsPassed=sum(1 for checkpoint in case_checks if checkpoint.passed),
                    checkpointsTotal=len(case_checks),
                    initialAggregateStatus=runtime.initial.aggregateStatus.value,
                    finalAggregateStatus=final_plan.aggregateStatus.value,
                )
            )
        metrics, checkpoint_failures = _quality_metrics(evaluated)
        safety = _evaluate_safety(runtimes)
        failures = checkpoint_failures + safety.failures
        checkpoint_count = metrics["overallWorkflowAccuracy"].total
        quality_passed = all(metric.accuracy == 1.0 and metric.total > 0 for metric in metrics.values())
        status = "scored"
        if checkpoint_failures:
            status = "scored_failure"
        if safety.failures:
            status = "safety_failure"
        gate_passed = status == "scored" and quality_passed and safety.passed and not failures
        return WorkflowEvaluationResult(
            benchmark=BENCHMARK_NAME,
            evaluationStatus=status,
            fixtureVersion=str(payload.get("fixtureVersion", "")),
            plannerVersion=WORKFLOW_PLANNER_VERSION,
            caseCount=len(runtimes),
            checkpointCount=checkpoint_count,
            qualityMetrics=metrics,
            diagnosticMetrics=_diagnostics(runtimes),
            safetyResults=safety,
            failures=failures,
            gatePassed=gate_passed,
            groundTruthAuthority=GROUND_TRUTH_AUTHORITY,
            diagnosticOnly=False,
            cases=tuple(case_results),
            fixturePath=path,
        )
    except Exception as exc:
        failure = _failure(
            kind="evaluator_error",
            case_id="evaluator",
            checkpoint_type="evaluator",
            phase="evaluator",
            semantic_key="error",
            expected="completed workflow evaluation",
            actual=type(exc).__name__,
            message=str(exc),
        )
        return WorkflowEvaluationResult(
            benchmark=BENCHMARK_NAME,
            evaluationStatus="evaluator_error",
            fixtureVersion=str(payload.get("fixtureVersion", "")),
            plannerVersion=WORKFLOW_PLANNER_VERSION,
            caseCount=len(payload.get("cases", ())),
            checkpointCount=0,
            qualityMetrics=_metric_dict_invalid(),
            diagnosticMetrics={"diagnosticOnly": True},
            safetyResults=SafetyResults(passed=False, properties={}, failures=(failure,)),
            failures=(failure,),
            gatePassed=False,
            groundTruthAuthority=GROUND_TRUTH_AUTHORITY,
            diagnosticOnly=False,
            fixturePath=path,
        )


def _failure_to_dict(failure: WorkflowEvaluationFailure) -> dict[str, Any]:
    return {
        "kind": failure.kind,
        "caseId": failure.caseId,
        "checkpointId": failure.checkpointId,
        "checkpointTuple": list(failure.checkpointTuple) if failure.checkpointTuple else None,
        "checkpointType": failure.checkpointType,
        "primaryMetric": failure.primaryMetric,
        "phase": failure.phase,
        "semanticKey": failure.semanticKey,
        "expected": failure.expected,
        "actual": failure.actual,
        "message": failure.message,
    }


def evaluation_result_to_dict(result: WorkflowEvaluationResult) -> dict[str, Any]:
    return {
        "benchmark": result.benchmark,
        "evaluationStatus": result.evaluationStatus,
        "fixtureVersion": result.fixtureVersion,
        "plannerVersion": result.plannerVersion,
        "caseCount": result.caseCount,
        "checkpointCount": result.checkpointCount,
        "qualityMetrics": {
            name: {"accuracy": metric.accuracy, "passed": metric.passed, "total": metric.total}
            for name, metric in result.qualityMetrics.items()
        },
        "diagnosticMetrics": result.diagnosticMetrics,
        "safetyResults": {
            "passed": result.safetyResults.passed,
            "properties": {
                name: {
                    "passed": prop.passed,
                    "checksPassed": prop.checksPassed,
                    "checksTotal": prop.checksTotal,
                    "failures": [_failure_to_dict(failure) for failure in prop.failures],
                }
                for name, prop in result.safetyResults.properties.items()
            },
            "failures": [_failure_to_dict(failure) for failure in result.safetyResults.failures],
        },
        "failures": [_failure_to_dict(failure) for failure in result.failures],
        "gatePassed": result.gatePassed,
        "groundTruthAuthority": result.groundTruthAuthority,
        "diagnosticOnly": result.diagnosticOnly,
        "cases": [
            {
                "caseId": case.caseId,
                "passed": case.passed,
                "checkpointsPassed": case.checkpointsPassed,
                "checkpointsTotal": case.checkpointsTotal,
                "initialAggregateStatus": case.initialAggregateStatus,
                "finalAggregateStatus": case.finalAggregateStatus,
            }
            for case in result.cases
        ],
        "reproductionCommand": "python scripts/run_workflow_evaluation.py",
        "planningOnlyDisclaimer": (
            "Workflow evaluation plans and decision transitions only; no workflow action "
            "is executed, persisted, scheduled, or externally applied."
        ),
    }


def render_markdown(result: WorkflowEvaluationResult) -> str:
    data = evaluation_result_to_dict(result)
    lines = [
        "# Workflow Evaluation Benchmark",
        "",
        "Reproducible Mem-D V0.8 workflow planning evaluation.",
        "",
        "## Ground Truth",
        "",
        f"`{data['groundTruthAuthority']}` is the sole workflow correctness authority.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Evaluation status | `{data['evaluationStatus']}` |",
        f"| Gate passed | {data['gatePassed']} |",
        f"| Fixture version | `{data['fixtureVersion']}` |",
        f"| Planner version | `{data['plannerVersion']}` |",
        f"| Cases | {data['caseCount']} |",
        f"| Checkpoints | {data['checkpointCount']} |",
        "",
        "## Quality Metrics",
        "",
        "| Metric | Accuracy | Passed | Total |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name in QUALITY_METRICS:
        metric = data["qualityMetrics"][name]
        accuracy = "null" if metric["accuracy"] is None else f"{metric['accuracy']:.4f}"
        lines.append(f"| {name} | {accuracy} | {metric['passed']} | {metric['total']} |")
    lines.extend(
        [
            "",
            "## Safety Gates",
            "",
            "| Property | Passed | Checks |",
            "| --- | --- | ---: |",
        ]
    )
    for name in SAFETY_PROPERTIES:
        prop = data["safetyResults"]["properties"].get(name, {"passed": False, "checksPassed": 0, "checksTotal": 0})
        lines.append(f"| {name} | {prop['passed']} | {prop['checksPassed']}/{prop['checksTotal']} |")
    lines.extend(
        [
            "",
            "## Diagnostic Metrics",
            "",
            "`diagnosticOnly: true`; diagnostics do not affect quality metrics or the gate.",
            "",
            "```json",
            json.dumps(data["diagnosticMetrics"], indent=2, sort_keys=True),
            "```",
            "",
            "## Case Results",
            "",
            "| Case | Passed | Checkpoints | Initial | Final |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for case in data["cases"]:
        lines.append(
            f"| {case['caseId']} | {case['passed']} | "
            f"{case['checkpointsPassed']}/{case['checkpointsTotal']} | "
            f"`{case['initialAggregateStatus']}` | `{case['finalAggregateStatus']}` |"
        )
    lines.extend(["", "## Failures", ""])
    if data["failures"]:
        for failure in data["failures"]:
            lines.append(
                f"- **{failure['caseId']}** `{failure['checkpointId']}`: {failure['message']}"
            )
    else:
        lines.append("No failures.")
    lines.extend(
        [
            "",
            "## Reproduce",
            "",
            "```bash",
            data["reproductionCommand"],
            "```",
            "",
            "## Planning-Only Disclaimer",
            "",
            data["planningOnlyDisclaimer"],
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"
