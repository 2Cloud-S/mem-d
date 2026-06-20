"""V0.8 Phase 2 workflow planner tests."""

from __future__ import annotations

import json

import pytest

from memd.contracts import (
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
    PlannerItemStatus,
    PlanningOptions,
    PolicyDecision,
    PolicyProfile,
    PolicySummary,
    Recommendation,
    RecommendationAction,
    RecommendationEvidence,
    ReviewQueueId,
    ReviewSubtype,
    SimulatedExplainability,
    SimulationMetrics,
    SimulationWarning,
    WorkflowBlocker,
    WorkflowBlockerCode,
    WorkflowItem,
    WorkflowPlannerStatus,
    WorkflowPlanningMode,
    WorkflowStepType,
    WorkflowSummary,
)
from memd.metrics import calculate_metrics
from memd.simulation import (
    simulate_recommendations,
)
from memd.workflows import (
    WORKFLOW_PLANNER_VERSION,
    WorkflowDecisionError,
    apply_workflow_decisions,
    compute_aggregate_status,
    plan_workflows,
)
from tests.test_recommendations import to_memory_records


def _metrics(memories: int = 2) -> AnalysisMetrics:
    return AnalysisMetrics(
        totalMemories=memories,
        duplicateCount=0,
        duplicatePercentage=0.0,
        compressionOpportunity=0.0,
        categoryBreakdown={category: 0 for category in MemoryCategory},
    )


def _explainability(rec_id: str = "rec:1") -> SimulatedExplainability:
    return SimulatedExplainability(
        explainabilitySource="test",
        recommendationId=rec_id,
        reason="test",
    )


def _simulation_metrics() -> SimulationMetrics:
    return SimulationMetrics()


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
        reason="Planner test recommendation.",
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
) -> MemoryResolution:
    return MemoryResolution(
        memoryId=memory_id,
        resolvedAction=action,
        role=role,
        confidence=0.9,
        recommendationId=rec_id,
    )


def _governance_action(
    action_id: str,
    decision: PolicyDecision | None = PolicyDecision.APPROVED,
) -> GovernanceAction:
    return GovernanceAction(
        actionId=action_id,
        actionType=ActionType.MERGE_CLUSTER,
        target={"clusterId": "c1"},
        title=action_id,
        rationale="test",
        supportingEvidence=(),
        confidence=0.9,
        estimatedImpact="low",
        requiresHumanApproval=False,
        priority=ActionPriority.MEDIUM,
        sourceSignals=("test",),
        policyDecision=decision,
    )


def _base_report(**overrides: object) -> AnalysisReport:
    payload: dict[str, object] = {
        "metrics": _metrics(),
        "clusters": (),
        "memories": (MemoryRecord(id="m1", content="alpha"), MemoryRecord(id="m2", content="beta")),
        "validation": {},
        "actions": (),
        "policySummary": PolicySummary(profile=PolicyProfile.BALANCED),
        "recommendations": (),
        "memoryResolutions": (),
    }
    payload.update(overrides)
    return AnalysisReport(**payload)


def _with_simulation(report: AnalysisReport) -> AnalysisReport:
    simulation = simulate_recommendations(report)
    return report.model_copy(update={"simulationReport": simulation})


def _inject_simulation_warnings(
    report: AnalysisReport,
    warnings: tuple[SimulationWarning, ...],
) -> AnalysisReport:
    base = _with_simulation(report) if report.simulationReport is None else report
    assert base.simulationReport is not None
    return base.model_copy(
        update={
            "simulationReport": base.simulationReport.model_copy(
                update={"simulationWarnings": warnings}
            )
        }
    )


def _structural_overlap_report(*, archive_first: bool) -> AnalysisReport:
    archive = _recommendation("rec:archive:1", RecommendationAction.ARCHIVE)
    merge = _recommendation(
        "rec:merge:1",
        RecommendationAction.MERGE,
        memory_ids=("m1", "m2"),
        source_action_ids=("act-1",),
    )
    recommendations = (archive, merge) if archive_first else (merge, archive)
    return _with_simulation(
        _base_report(
            recommendations=recommendations,
            memoryResolutions=(
                _resolution("m1", "rec:archive:1", RecommendationAction.ARCHIVE),
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
            actions=(_governance_action("act-1", PolicyDecision.APPROVED),),
        )
    )


def _plan_dump(plan) -> str:
    return json.dumps(plan.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


# T01
def test_t01_empty_report() -> None:
    plan = plan_workflows(_base_report(recommendations=(), memories=()))
    assert plan.aggregateStatus == PlanAggregateStatus.EMPTY
    assert plan.summary.totalItems == 0


# T02
def test_t02_all_keep_summary_only() -> None:
    report = _base_report(
        memoryResolutions=(
            _resolution("m1", "rec:keep:m1", RecommendationAction.KEEP),
            _resolution("m2", "rec:keep:m2", RecommendationAction.KEEP),
        ),
        recommendations=(),
    )
    plan = plan_workflows(report)
    assert plan.aggregateStatus == PlanAggregateStatus.ALL_KEEP
    assert plan.summary.totalItems == 0
    assert plan.summary.keepCount == 2


# T03
def test_t03_review_only_recommendations() -> None:
    report = _base_report(
        recommendations=(
            _recommendation("rec:review:1", RecommendationAction.REVIEW),
        ),
        memoryResolutions=(
            _resolution("m1", "rec:review:1", RecommendationAction.REVIEW),
        ),
    )
    plan = plan_workflows(report)
    item = plan.items[0]
    assert item.action == RecommendationAction.REVIEW
    assert item.plannerItemStatus == PlannerItemStatus.REQUIRES_REVIEW


# T04
def test_t04_merge_with_simulated_group() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation(
                    "rec:merge:1",
                    RecommendationAction.MERGE,
                    memory_ids=("m1", "m2"),
                    source_action_ids=("act-1",),
                ),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
            actions=(_governance_action("act-1", PolicyDecision.APPROVED),),
        )
    )
    plan = plan_workflows(report)
    assert any(step.stepType == WorkflowStepType.MERGE for step in plan.steps)
    assert "merge:rec:merge:1" in plan.items[0].simulationRefs


# T05
def test_t05_archive_with_simulated_entry() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation("rec:archive:1", RecommendationAction.ARCHIVE),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:archive:1", RecommendationAction.ARCHIVE),
            ),
        )
    )
    plan = plan_workflows(report)
    assert any(step.stepType == WorkflowStepType.ARCHIVE for step in plan.steps)


# T06
def test_t06_defer_action() -> None:
    report = _base_report(
        recommendations=(_recommendation("rec:defer:1", RecommendationAction.DEFER),),
        memoryResolutions=(_resolution("m1", "rec:defer:1", RecommendationAction.DEFER),),
    )
    plan = plan_workflows(report)
    assert plan.items[0].plannerItemStatus == PlannerItemStatus.DEFERRED


# T07
def test_t07_missing_simulation_recommendations_only() -> None:
    report = _base_report(
        recommendations=(
            _recommendation("rec:merge:1", RecommendationAction.MERGE, memory_ids=("m1", "m2")),
        ),
        memoryResolutions=(
            _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
            _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
        ),
    )
    plan = plan_workflows(report)
    assert plan.planningMode == WorkflowPlanningMode.RECOMMENDATIONS_ONLY
    assert any(blocker.code == WorkflowBlockerCode.MISSING_SIMULATION for blocker in plan.blockers)


# T08
def test_t08_simulation_id_match() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation("rec:merge:1", RecommendationAction.MERGE, memory_ids=("m1", "m2")),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
        )
    )
    plan = plan_workflows(report)
    assert plan.simulationId == report.simulationReport.simulationId
    assert plan.aggregateStatus != PlanAggregateStatus.INTEGRITY_BLOCKED


# T09
def test_t09_simulation_id_mismatch_integrity_blocked() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation("rec:merge:1", RecommendationAction.MERGE, memory_ids=("m1", "m2")),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
        )
    )
    bad = report.simulationReport.model_copy(update={"simulationId": "0" * 64})
    report = report.model_copy(update={"simulationReport": bad})
    plan = plan_workflows(report)
    assert plan.aggregateStatus == PlanAggregateStatus.INTEGRITY_BLOCKED
    assert any(blocker.code == WorkflowBlockerCode.INPUT_INTEGRITY for blocker in plan.blockers)


# T10
def test_t10_analysis_report_ref_match_and_mismatch() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation("rec:merge:1", RecommendationAction.MERGE, memory_ids=("m1", "m2")),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
        )
    )
    good = plan_workflows(report)
    assert good.aggregateStatus != PlanAggregateStatus.INTEGRITY_BLOCKED

    bad_sim = report.simulationReport.model_copy(update={"analysisReportRef": "bad"})
    bad_report = report.model_copy(update={"simulationReport": bad_sim})
    bad_plan = plan_workflows(bad_report)
    assert bad_plan.aggregateStatus == PlanAggregateStatus.INTEGRITY_BLOCKED


# T11
def test_t11_byte_equivalent_duplicate_recommendations() -> None:
    rec = _recommendation("rec:dup", RecommendationAction.REVIEW)
    report = _base_report(recommendations=(rec, rec))
    plan = plan_workflows(report)
    assert len(plan.items) == 1


# T12
def test_t12_conflicting_duplicate_recommendations() -> None:
    first = _recommendation("rec:dup", RecommendationAction.MERGE)
    second = _recommendation("rec:dup", RecommendationAction.ARCHIVE)
    plan = plan_workflows(_base_report(recommendations=(first, second)))
    assert plan.aggregateStatus == PlanAggregateStatus.INTEGRITY_BLOCKED


# T13
def test_t13_unknown_category_routing() -> None:
    report = _base_report(
        categories=(
            CategorizedMemory(
                memoryId="m1",
                category=MemoryCategory.UNKNOWN,
                confidence=0.5,
                reason="unknown",
            ),
        ),
        recommendations=(_recommendation("rec:review:1", RecommendationAction.REVIEW),),
        memoryResolutions=(_resolution("m1", "rec:review:1", RecommendationAction.REVIEW),),
        validation={
            "categoryQuality": {
                "unknownSamples": [{"memoryId": "m1"}],
            }
        },
    )
    plan = plan_workflows(report)
    assert ReviewSubtype.UNKNOWN_CATEGORY in plan.items[0].reviewRequirement.subtypes


# T14
def test_t14_lifecycle_subtypes() -> None:
    report = _base_report(
        recommendations=(_recommendation("rec:review:1", RecommendationAction.REVIEW),),
        memoryResolutions=(_resolution("m1", "rec:review:1", RecommendationAction.REVIEW),),
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
    )
    plan = plan_workflows(report)
    assert ReviewSubtype.LIFECYCLE_ALTERNATE in plan.items[0].reviewRequirement.subtypes


# T15
def test_t15_policy_review_and_blocked() -> None:
    review_report = _base_report(
        recommendations=(
            _recommendation(
                "rec:merge:1",
                RecommendationAction.MERGE,
                source_action_ids=("act-review",),
            ),
        ),
        actions=(_governance_action("act-review", PolicyDecision.REQUIRES_REVIEW),),
    )
    review_plan = plan_workflows(review_report)
    assert review_plan.items[0].policyDecision == PolicyDecision.REQUIRES_REVIEW

    blocked_report = _base_report(
        recommendations=(
            _recommendation(
                "rec:merge:2",
                RecommendationAction.MERGE,
                source_action_ids=("act-blocked",),
            ),
        ),
        actions=(_governance_action("act-blocked", PolicyDecision.BLOCKED),),
    )
    blocked_plan = plan_workflows(blocked_report)
    assert blocked_plan.items[0].plannerItemStatus == PlannerItemStatus.BLOCKED


# T16
def test_t16_conflict_routing() -> None:
    report = _base_report(
        recommendations=(
            _recommendation(
                "rec:review:1",
                RecommendationAction.REVIEW,
                conflict=True,
                subtype="conflict",
            ),
        ),
        memoryResolutions=(
            MemoryResolution(
                memoryId="m1",
                resolvedAction=RecommendationAction.REVIEW,
                confidence=0.9,
                recommendationId="rec:review:1",
                conflictDetected=True,
            ),
        ),
    )
    plan = plan_workflows(report)
    assert ReviewSubtype.CONFLICT in plan.items[0].reviewRequirement.subtypes


# T17
def test_t17_orphan_warning_blocker() -> None:
    case = {
        "memories": [
            {"id": "m1", "content": "a"},
            {"id": "m2", "content": "b"},
        ],
        "clusters": [],
        "validation": {},
        "actions": [],
        "useExplicitResolutions": True,
        "memoryResolutions": [
            {
                "memoryId": "m2",
                "resolvedAction": "merge",
                "role": "removable",
                "confidence": 0.9,
                "recommendationId": "rec:merge:orphan",
            }
        ],
    }
    memories = to_memory_records(case)
    metrics = calculate_metrics(memories, [], [], {})
    report = AnalysisReport(
        metrics=metrics,
        clusters=(),
        memories=tuple(memories),
        recommendations=(
            _recommendation("rec:merge:orphan", RecommendationAction.MERGE, memory_ids=("m2",)),
        ),
        memoryResolutions=(
            _resolution("m2", "rec:merge:orphan", RecommendationAction.MERGE, role="removable"),
        ),
    )
    report = _with_simulation(report)
    plan = plan_workflows(report)
    assert any(
        blocker.code == WorkflowBlockerCode.ORPHAN_MERGE_NO_KEEPER for blocker in plan.blockers
    )


# M1 — every closed RecommendationAction enum member has an explicit planner path.
@pytest.mark.parametrize("action", list(RecommendationAction))
def test_m1_all_recommendation_actions_have_explicit_planner_path(
    action: RecommendationAction,
) -> None:
    memory_ids = ("m1", "m2") if action == RecommendationAction.MERGE else ("m1",)
    rec = _recommendation(f"rec:{action.value}", action, memory_ids=memory_ids)
    resolutions = tuple(
        _resolution(
            memory_id,
            rec.recommendationId,
            action,
            role="keeper" if index == 0 else "removable",
        )
        for index, memory_id in enumerate(memory_ids)
    )
    report = _base_report(recommendations=(rec,), memoryResolutions=resolutions)
    if action in {RecommendationAction.MERGE, RecommendationAction.ARCHIVE}:
        report = _with_simulation(report)
    options = PlanningOptions(includeKeep=True) if action == RecommendationAction.KEEP else None
    plan = plan_workflows(report, options=options) if options else plan_workflows(report)
    assert plan.plannerVersion == WORKFLOW_PLANNER_VERSION
    assert not any(
        blocker.code == WorkflowBlockerCode.UNSUPPORTED_ACTION for blocker in plan.blockers
    )
    if action != RecommendationAction.KEEP:
        assert any(item.action == action for item in plan.items)


# T19
def test_t19_two_pass_deterministic_ids() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation("rec:merge:1", RecommendationAction.MERGE, memory_ids=("m1", "m2")),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
        )
    )
    plan = plan_workflows(report)
    for item in plan.items:
        assert item.workflowItemId
        assert item.workflowItemId != plan.workflowPlanId


# T20
def test_t20_repeated_plan_workflows_byte_identical() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation("rec:merge:1", RecommendationAction.MERGE, memory_ids=("m1", "m2")),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
        )
    )
    first = _plan_dump(plan_workflows(report))
    second = _plan_dump(plan_workflows(report))
    assert first == second


# T21
def test_t21_report_immutability() -> None:
    report = _base_report(
        recommendations=(_recommendation("rec:review:1", RecommendationAction.REVIEW),),
    )
    before = report.model_dump(mode="json")
    plan_workflows(report)
    assert report.model_dump(mode="json") == before


# T22
def test_t22_plan_immutability_for_decisions() -> None:
    report = _base_report(
        recommendations=(_recommendation("rec:review:1", RecommendationAction.REVIEW),),
        memoryResolutions=(_resolution("m1", "rec:review:1", RecommendationAction.REVIEW),),
    )
    plan = plan_workflows(report)
    before = plan.model_dump(mode="json")
    item_id = plan.items[0].workflowItemId
    apply_workflow_decisions(
        plan,
        (
            ApprovalDecision(
                targetType="workflow_item",
                targetId=item_id,
                decision=ApprovalDecisionType.APPROVED,
            ),
        ),
    )
    assert plan.model_dump(mode="json") == before


# T23
def test_t23_include_keep_true_vs_false() -> None:
    report = _base_report(
        recommendations=(_recommendation("rec:keep:1", RecommendationAction.KEEP),),
        memoryResolutions=(_resolution("m1", "rec:keep:1", RecommendationAction.KEEP),),
    )
    without = plan_workflows(report)
    with_keep = plan_workflows(report, options=PlanningOptions(includeKeep=True))
    assert without.summary.totalItems == 0
    assert with_keep.summary.totalItems == 1
    assert any(step.stepType == WorkflowStepType.RETAIN for step in with_keep.steps)


# T24
def test_t24_step_tiers_gap_free_sequences() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation("rec:review:1", RecommendationAction.REVIEW),
                _recommendation(
                    "rec:merge:1",
                    RecommendationAction.MERGE,
                    memory_ids=("m1", "m2"),
                    source_action_ids=("act-1",),
                ),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:review:1", RecommendationAction.REVIEW),
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
            actions=(_governance_action("act-1", PolicyDecision.APPROVED),),
        )
    )
    plan = plan_workflows(report)
    sequences = [step.sequence for step in plan.steps]
    assert sequences == list(range(1, len(sequences) + 1))
    review_index = next(
        i for i, step in enumerate(plan.steps) if step.stepType == WorkflowStepType.REVIEW
    )
    merge_index = next(
        i for i, step in enumerate(plan.steps) if step.stepType == WorkflowStepType.MERGE
    )
    assert review_index < merge_index


# T25
def test_t25_evidence_closure() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation(
                    "rec:merge:1",
                    RecommendationAction.MERGE,
                    memory_ids=("m1", "m2"),
                    source_action_ids=("act-1",),
                ),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
            actions=(_governance_action("act-1", PolicyDecision.APPROVED),),
        )
    )
    plan = plan_workflows(report)
    for item in plan.items:
        assert item.recommendationId in plan.evidence.recommendationIds


# T26
def test_t26_safe_proposed_merge_no_review() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation(
                    "rec:merge:1",
                    RecommendationAction.MERGE,
                    memory_ids=("m1", "m2"),
                    source_action_ids=("act-1",),
                ),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
            actions=(_governance_action("act-1", PolicyDecision.APPROVED),),
        )
    )
    plan = plan_workflows(report)
    item = next(item for item in plan.items if item.action == RecommendationAction.MERGE)
    assert item.plannerItemStatus == PlannerItemStatus.PROPOSED
    assert not item.reviewRequirement.required


# T27
def test_t27_safe_proposed_archive_no_review() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation(
                    "rec:archive:1",
                    RecommendationAction.ARCHIVE,
                    source_action_ids=("act-1",),
                ),
            ),
            memoryResolutions=(_resolution("m1", "rec:archive:1", RecommendationAction.ARCHIVE),),
            actions=(_governance_action("act-1", PolicyDecision.APPROVED),),
        )
    )
    plan = plan_workflows(report)
    item = plan.items[0]
    assert item.plannerItemStatus == PlannerItemStatus.PROPOSED
    assert not item.reviewRequirement.required


# T28
def test_t28_review_action_general_subtype() -> None:
    report = _base_report(
        recommendations=(_recommendation("rec:review:1", RecommendationAction.REVIEW),),
        memoryResolutions=(_resolution("m1", "rec:review:1", RecommendationAction.REVIEW),),
    )
    plan = plan_workflows(report)
    assert ReviewSubtype.GENERAL in plan.items[0].reviewRequirement.subtypes


# T29
def test_t29_human_approval_general_subtype() -> None:
    report = _base_report(
        recommendations=(
            _recommendation(
                "rec:merge:1",
                RecommendationAction.MERGE,
                requires_human=True,
            ),
        ),
    )
    plan = plan_workflows(report)
    assert plan.items[0].reviewRequirement.required
    assert ReviewSubtype.GENERAL in plan.items[0].reviewRequirement.subtypes


# T30
def test_t30_policy_aggregation_order_independent() -> None:
    rec = _recommendation(
        "rec:merge:1",
        RecommendationAction.MERGE,
        source_action_ids=("act-a", "act-b"),
    )
    actions = (
        _governance_action("act-a", PolicyDecision.REQUIRES_REVIEW),
        _governance_action("act-b", PolicyDecision.APPROVED),
    )
    forward = plan_workflows(_base_report(recommendations=(rec,), actions=actions))
    reverse_rec = rec.model_copy(update={"sourceActionIds": ("act-b", "act-a")})
    reverse = plan_workflows(_base_report(recommendations=(reverse_rec,), actions=actions))
    assert forward.items[0].policyDecision == reverse.items[0].policyDecision


# T31 / T32
def test_t31_t32_blocker_id_collision_and_dedup() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation(
                    "rec:merge:1",
                    RecommendationAction.MERGE,
                    memory_ids=("m1", "m2"),
                    source_action_ids=("act-1",),
                ),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
            actions=(_governance_action("act-1", PolicyDecision.BLOCKED),),
        )
    )
    plan = plan_workflows(report)
    blocker_ids = [blocker.blockerId for blocker in plan.blockers]
    assert len(blocker_ids) == len(set(blocker_ids))


# T33
def test_t33_plan_level_integrity_aggregates_causes() -> None:
    first = _recommendation("rec:dup", RecommendationAction.MERGE)
    second = _recommendation("rec:dup", RecommendationAction.ARCHIVE)
    plan = plan_workflows(_base_report(recommendations=(first, second)))
    integrity = next(
        blocker for blocker in plan.blockers if blocker.code == WorkflowBlockerCode.INPUT_INTEGRITY
    )
    assert integrity.blockerId in plan.items[0].blockerRefs


# T34
def test_t34_cumulative_decisions_fingerprint() -> None:
    report = _base_report(
        recommendations=(
            _recommendation("rec:review:1", RecommendationAction.REVIEW),
            _recommendation("rec:review:2", RecommendationAction.REVIEW, memory_ids=("m2",)),
        ),
        memoryResolutions=(
            _resolution("m1", "rec:review:1", RecommendationAction.REVIEW),
            _resolution("m2", "rec:review:2", RecommendationAction.REVIEW),
        ),
    )
    plan = plan_workflows(report)
    decided = apply_workflow_decisions(
        plan,
        (
            ApprovalDecision(
                targetType="workflow_item",
                targetId=plan.items[0].workflowItemId,
                decision=ApprovalDecisionType.APPROVED,
            ),
        ),
    )
    assert decided.decisionsFingerprint
    assert decided.plannerStatus == WorkflowPlannerStatus.DECIDED


# T35 / T36
def test_t35_t36_multi_call_and_idempotent() -> None:
    report = _base_report(
        recommendations=(
            _recommendation("rec:review:1", RecommendationAction.REVIEW),
            _recommendation("rec:review:2", RecommendationAction.REVIEW, memory_ids=("m2",)),
        ),
        memoryResolutions=(
            _resolution("m1", "rec:review:1", RecommendationAction.REVIEW),
            _resolution("m2", "rec:review:2", RecommendationAction.REVIEW),
        ),
    )
    plan = plan_workflows(report)
    first = apply_workflow_decisions(
        plan,
        (
            ApprovalDecision(
                targetType="workflow_item",
                targetId=plan.items[0].workflowItemId,
                decision=ApprovalDecisionType.APPROVED,
            ),
        ),
    )
    second = apply_workflow_decisions(
        first,
        (
            ApprovalDecision(
                targetType="workflow_item",
                targetId=first.items[1].workflowItemId,
                decision=ApprovalDecisionType.APPROVED,
            ),
        ),
    )
    assert second.items[0].operatorItemStatus == OperatorItemStatus.APPROVED
    third = apply_workflow_decisions(
        second,
        (
            ApprovalDecision(
                targetType="workflow_item",
                targetId=second.items[1].workflowItemId,
                decision=ApprovalDecisionType.APPROVED,
            ),
        ),
    )
    assert _plan_dump(second) == _plan_dump(third)


# T37
def test_t37_aggregate_helper_without_completed_plan() -> None:
    items = (
        WorkflowItem(
            workflowItemId="a" * 64,
            recommendationId="rec:1",
            action=RecommendationAction.REVIEW,
            plannerItemStatus=PlannerItemStatus.REQUIRES_REVIEW,
            operatorItemStatus=OperatorItemStatus.NONE,
            recommendationPriority=ActionPriority.HIGH,
            queueRank=1,
            reviewRequirement=plan_workflows(
                _base_report(
                    recommendations=(_recommendation("rec:1", RecommendationAction.REVIEW),),
                )
            ).items[0].reviewRequirement,
            requiresHumanApproval=False,
            orderingKey="high:review:rec:1",
        ),
    )
    summary = WorkflowSummary(totalItems=1)
    status = compute_aggregate_status(
        planning_mode=WorkflowPlanningMode.RECOMMENDATIONS_ONLY,
        items=items,
        blockers=(),
        summary=summary,
    )
    assert status == PlanAggregateStatus.REQUIRES_REVIEW


# T38 / T39
def test_t38_t39_canonical_floats_alter_plan_id() -> None:
    rec = _recommendation("rec:1", RecommendationAction.REVIEW)
    base = plan_workflows(_base_report(recommendations=(rec,)))
    changed = rec.model_copy(update={"confidence": 0.91})
    other = plan_workflows(_base_report(recommendations=(changed,)))
    assert base.workflowPlanId != other.workflowPlanId


# T40
def test_t40_attached_workflow_plan_excluded_from_identity() -> None:
    report = _base_report(
        recommendations=(_recommendation("rec:1", RecommendationAction.REVIEW),),
    )
    first = plan_workflows(report)
    attached = report.model_copy(update={"workflowPlan": first})
    second = plan_workflows(attached)
    assert first.workflowPlanId == second.workflowPlanId


# T41
def test_t41_no_handoff_steps() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation("rec:merge:1", RecommendationAction.MERGE, memory_ids=("m1", "m2")),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
        )
    )
    plan = plan_workflows(report)
    assert all(step.stepType != WorkflowStepType.HANDOFF for step in plan.steps)


# T58
def test_t58_no_execution_persistence_or_file_io() -> None:
    report = _base_report(
        recommendations=(_recommendation("rec:1", RecommendationAction.REVIEW),),
    )
    plan = plan_workflows(report)
    assert plan.plannerStatus == WorkflowPlannerStatus.INITIAL


# T59
def test_t59_exact_simulation_report_field_usage() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation("rec:merge:1", RecommendationAction.MERGE, memory_ids=("m1", "m2")),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
        )
    )
    plan = plan_workflows(report)
    assert any(ref.startswith("merge:") for ref in plan.items[0].simulationRefs)


# T60
def test_t60_category_change_alters_workflow_plan_id() -> None:
    base = _base_report(
        recommendations=(_recommendation("rec:1", RecommendationAction.REVIEW),),
        categories=(
            CategorizedMemory(
                memoryId="m1",
                category=MemoryCategory.FACT,
                confidence=0.9,
            ),
        ),
    )
    changed = base.model_copy(
        update={
            "categories": (
                CategorizedMemory(
                    memoryId="m1",
                    category=MemoryCategory.UNKNOWN,
                    confidence=0.5,
                ),
            ),
            "validation": {"categoryQuality": {"unknownSamples": [{"memoryId": "m1"}]}},
        }
    )
    assert plan_workflows(base).workflowPlanId != plan_workflows(changed).workflowPlanId


# T61
def test_t61_lifecycle_signal_change_alters_workflow_plan_id() -> None:
    base = _base_report(
        recommendations=(_recommendation("rec:1", RecommendationAction.REVIEW),),
    )
    changed = base.model_copy(
        update={
            "validation": {
                "memoryLifecycle": {
                    "memoryLifecycleAssignments": [
                        {"memoryId": "m1", "alternateLifecycleSignals": ["x"]}
                    ]
                }
            }
        }
    )
    assert plan_workflows(base).workflowPlanId != plan_workflows(changed).workflowPlanId


# T62
def test_t62_policy_decision_change_alters_workflow_plan_id() -> None:
    rec = _recommendation("rec:1", RecommendationAction.MERGE, source_action_ids=("act-1",))
    approved = _base_report(
        recommendations=(rec,),
        actions=(_governance_action("act-1", PolicyDecision.APPROVED),),
    )
    blocked = approved.model_copy(
        update={"actions": (_governance_action("act-1", PolicyDecision.BLOCKED),)}
    )
    assert plan_workflows(approved).workflowPlanId != plan_workflows(blocked).workflowPlanId


# T63
def test_t63_trust_signal_change_alters_workflow_plan_id() -> None:
    base = _base_report(
        clusters=(
            DuplicateCluster(
                clusterId="c1",
                members=("m1", "m2"),
                averageSimilarity=0.9,
                trustLevel=ClusterTrustLevel.HIGH,
            ),
        ),
        recommendations=(_recommendation("rec:1", RecommendationAction.REVIEW),),
    )
    changed = base.model_copy(
        update={
            "clusters": (
                DuplicateCluster(
                    clusterId="c1",
                    members=("m1", "m2"),
                    averageSimilarity=0.9,
                    trustLevel=ClusterTrustLevel.LOW,
                ),
            )
        }
    )
    assert plan_workflows(base).workflowPlanId != plan_workflows(changed).workflowPlanId


# T64
def test_t64_simulation_warnings_change_alters_workflow_plan_id() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation("rec:merge:1", RecommendationAction.MERGE, memory_ids=("m1", "m2")),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
        )
    )
    base_plan = plan_workflows(report)
    extra_warning = report.simulationReport.simulationWarnings + (
        SimulationWarning(code="EXTRA", message="extra"),
    )
    changed = report.model_copy(
        update={
            "simulationReport": report.simulationReport.model_copy(
                update={"simulationWarnings": extra_warning}
            )
        }
    )
    assert base_plan.workflowPlanId != plan_workflows(changed).workflowPlanId


# T65 / T66 / T67
def test_t65_t66_t67_duplicate_identity_properties() -> None:
    first = _recommendation("rec:dup", RecommendationAction.MERGE)
    second = _recommendation("rec:dup", RecommendationAction.ARCHIVE)
    conflict_a = plan_workflows(_base_report(recommendations=(first, second)))
    conflict_b = plan_workflows(_base_report(recommendations=(second, first)))
    assert conflict_a.workflowPlanId == conflict_b.workflowPlanId

    dup = _recommendation("rec:dup", RecommendationAction.MERGE)
    single = plan_workflows(_base_report(recommendations=(dup,)))
    multi = plan_workflows(_base_report(recommendations=(dup, dup)))
    assert single.workflowPlanId == multi.workflowPlanId
    assert conflict_a.workflowPlanId != single.workflowPlanId


# T68 / T69
def test_t68_t69_reported_and_expected_simulation_id_alter_plan_id() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation("rec:merge:1", RecommendationAction.MERGE, memory_ids=("m1", "m2")),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
        )
    )
    base = plan_workflows(report)
    changed_reported = report.model_copy(
        update={
            "simulationReport": report.simulationReport.model_copy(
                update={"simulationId": "f" * 64}
            )
        }
    )
    assert base.workflowPlanId != plan_workflows(changed_reported).workflowPlanId

    changed_expected = report.model_copy(
        update={"memories": report.memories + (MemoryRecord(id="m3", content="gamma"),)}
    )
    changed_expected = _with_simulation(changed_expected)
    assert base.workflowPlanId != plan_workflows(changed_expected).workflowPlanId


# T70
def test_t70_r2_explicit_comparison_without_assert() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation("rec:merge:1", RecommendationAction.MERGE, memory_ids=("m1", "m2")),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
        )
    )
    bad = report.simulationReport.model_copy(update={"simulationId": "bad"})
    plan = plan_workflows(report.model_copy(update={"simulationReport": bad}))
    assert plan.aggregateStatus == PlanAggregateStatus.INTEGRITY_BLOCKED


# T71
def test_t71_r4_failure_in_pass_b() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation("rec:merge:1", RecommendationAction.MERGE, memory_ids=("m1", "m2")),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
        )
    )
    manual_report = report.model_copy(
        update={
            "simulationReport": report.simulationReport.model_copy(
                update={"simulatedMerges": ()}
            ),
        }
    )
    plan = plan_workflows(manual_report)
    assert plan.aggregateStatus == PlanAggregateStatus.INTEGRITY_BLOCKED
    assert not any(step.stepType == WorkflowStepType.MERGE for step in plan.steps)


# T72 / T73 / T74
def test_t72_t73_t74_missing_source_action_ids() -> None:
    one = plan_workflows(
        _base_report(
            recommendations=(
                _recommendation(
                    "rec:1",
                    RecommendationAction.MERGE,
                    source_action_ids=("missing-1",),
                ),
            ),
        )
    )
    assert one.aggregateStatus == PlanAggregateStatus.INTEGRITY_BLOCKED
    assert "missing-1" in one.evidence.actionIds

    two = plan_workflows(
        _base_report(
            recommendations=(
                _recommendation(
                    "rec:1",
                    RecommendationAction.MERGE,
                    source_action_ids=("missing-b", "missing-a"),
                ),
            ),
        )
    )
    reverse = plan_workflows(
        _base_report(
            recommendations=(
                _recommendation(
                    "rec:1",
                    RecommendationAction.MERGE,
                    source_action_ids=("missing-a", "missing-b"),
                ),
            ),
        )
    )
    assert two.evidence.actionIds == reverse.evidence.actionIds


# T75
def test_t75_integrity_causes_accumulated_across_passes() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation(
                    "rec:merge:1",
                    RecommendationAction.MERGE,
                    memory_ids=("m1", "m2"),
                    source_action_ids=("missing-act",),
                ),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
        )
    )
    bad = report.simulationReport.model_copy(update={"simulationId": "bad"})
    plan = plan_workflows(report.model_copy(update={"simulationReport": bad}))
    integrity = next(
        blocker for blocker in plan.blockers if blocker.code == WorkflowBlockerCode.INPUT_INTEGRITY
    )
    assert integrity
    assert "missing-act" in plan.evidence.actionIds


def test_empty_decisions_return_same_plan() -> None:
    plan = plan_workflows(
        _base_report(recommendations=(_recommendation("rec:1", RecommendationAction.REVIEW),))
    )
    assert apply_workflow_decisions(plan, ()) is plan


def test_decision_errors() -> None:
    plan = plan_workflows(
        _base_report(
            recommendations=(_recommendation("rec:1", RecommendationAction.REVIEW),),
            memoryResolutions=(_resolution("m1", "rec:1", RecommendationAction.REVIEW),),
        )
    )
    with pytest.raises(WorkflowDecisionError):
        apply_workflow_decisions(
            plan,
            (
                ApprovalDecision(
                    targetType="workflow_item",
                    targetId="missing",
                    decision=ApprovalDecisionType.APPROVED,
                ),
            ),
        )


# T42 (extended by M2 hardening tests below)
def test_t42_structural_conflict_withholds_archive_and_merge() -> None:
    plan = plan_workflows(_structural_overlap_report(archive_first=True))
    assert not any(step.stepType == WorkflowStepType.ARCHIVE for step in plan.steps)
    assert not any(step.stepType == WorkflowStepType.MERGE for step in plan.steps)


def test_m2_structural_overlap_routes_both_items_to_conflict_review() -> None:
    plan = plan_workflows(_structural_overlap_report(archive_first=True))
    archive_item = next(item for item in plan.items if item.action == RecommendationAction.ARCHIVE)
    merge_item = next(item for item in plan.items if item.action == RecommendationAction.MERGE)
    for item in (archive_item, merge_item):
        assert item.conflictDetected
        assert item.plannerItemStatus == PlannerItemStatus.REQUIRES_REVIEW
        assert item.reviewRequirement.required
        assert ReviewSubtype.CONFLICT in item.reviewRequirement.subtypes
        assert item.reviewRequirement.primaryQueueId == ReviewQueueId.CONFLICT


def test_m2_structural_overlap_unrelated_items_unaffected() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation("rec:archive:1", RecommendationAction.ARCHIVE),
                _recommendation(
                    "rec:merge:1",
                    RecommendationAction.MERGE,
                    memory_ids=("m1", "m2"),
                    source_action_ids=("act-1",),
                ),
                _recommendation(
                    "rec:archive:2",
                    RecommendationAction.ARCHIVE,
                    memory_ids=("m2",),
                    source_action_ids=("act-2",),
                ),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:archive:1", RecommendationAction.ARCHIVE),
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
                _resolution("m2", "rec:archive:2", RecommendationAction.ARCHIVE),
            ),
            actions=(
                _governance_action("act-1", PolicyDecision.APPROVED),
                _governance_action("act-2", PolicyDecision.APPROVED),
            ),
        )
    )
    plan = plan_workflows(report)
    archive_two = next(item for item in plan.items if item.recommendationId == "rec:archive:2")
    assert archive_two.plannerItemStatus == PlannerItemStatus.PROPOSED
    assert ReviewSubtype.CONFLICT not in archive_two.reviewRequirement.subtypes
    assert any(step.stepType == WorkflowStepType.ARCHIVE for step in plan.steps)


def test_m2_structural_overlap_order_independent() -> None:
    forward = _plan_dump(plan_workflows(_structural_overlap_report(archive_first=True)))
    reverse = _plan_dump(plan_workflows(_structural_overlap_report(archive_first=False)))
    assert forward == reverse


# T43
def test_t43_review_step_precedes_structural_for_same_memory() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation("rec:review:1", RecommendationAction.REVIEW),
                _recommendation(
                    "rec:archive:1",
                    RecommendationAction.ARCHIVE,
                    source_action_ids=("act-1",),
                ),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:review:1", RecommendationAction.REVIEW),
                _resolution("m1", "rec:archive:1", RecommendationAction.ARCHIVE),
            ),
            actions=(_governance_action("act-1", PolicyDecision.APPROVED),),
        )
    )
    plan = plan_workflows(report)
    review_steps = [step for step in plan.steps if step.stepType == WorkflowStepType.REVIEW]
    archive_steps = [step for step in plan.steps if step.stepType == WorkflowStepType.ARCHIVE]
    if review_steps and archive_steps:
        assert review_steps[0].sequence < archive_steps[0].sequence
        assert archive_steps[0].dependsOnStepIds


# T44
def test_t44_blocked_item_excluded_from_structural_steps() -> None:
    report = _base_report(
        recommendations=(
            _recommendation(
                "rec:merge:1",
                RecommendationAction.MERGE,
                source_action_ids=("act-1",),
            ),
        ),
        actions=(_governance_action("act-1", PolicyDecision.BLOCKED),),
    )
    plan = plan_workflows(report)
    assert not any(
        step.stepType in {WorkflowStepType.MERGE, WorkflowStepType.ARCHIVE} for step in plan.steps
    )


def _review_required_item(item_id: str, rec_id: str = "rec:review:1") -> WorkflowItem:
    plan = plan_workflows(
        _base_report(
            recommendations=(_recommendation(rec_id, RecommendationAction.REVIEW),),
            memoryResolutions=(_resolution("m1", rec_id, RecommendationAction.REVIEW),),
        )
    )
    return plan.items[0].model_copy(update={"workflowItemId": item_id})


def _merge_item(item_id: str, rec_id: str = "rec:merge:1") -> WorkflowItem:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation(
                    rec_id,
                    RecommendationAction.MERGE,
                    memory_ids=("m1", "m2"),
                    source_action_ids=("act-1",),
                ),
            ),
            memoryResolutions=(
                _resolution("m1", rec_id, RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", rec_id, RecommendationAction.MERGE, role="removable"),
            ),
            actions=(_governance_action("act-1", PolicyDecision.APPROVED),),
        )
    )
    plan = plan_workflows(report)
    return plan.items[0].model_copy(update={"workflowItemId": item_id})


def _integrity_blocker(blocker_id: str = "i" * 64) -> WorkflowBlocker:
    return WorkflowBlocker(
        blockerId=blocker_id,
        code=WorkflowBlockerCode.INPUT_INTEGRITY,
        message="integrity",
        sourceLayer="planner",
        overridable=False,
    )


@pytest.mark.parametrize(
    ("items", "blockers", "summary", "planning_mode", "expected"),
    [
        (
            (),
            (_integrity_blocker(),),
            WorkflowSummary(totalItems=0, keepCount=0),
            WorkflowPlanningMode.FULL,
            PlanAggregateStatus.INTEGRITY_BLOCKED,
        ),
        (
            (),
            (),
            WorkflowSummary(totalItems=0, keepCount=0),
            WorkflowPlanningMode.FULL,
            PlanAggregateStatus.EMPTY,
        ),
        (
            (),
            (),
            WorkflowSummary(totalItems=0, keepCount=2),
            WorkflowPlanningMode.FULL,
            PlanAggregateStatus.ALL_KEEP,
        ),
    ],
    ids=["t45-integrity", "t46-empty", "t47-all-keep-summary"],
)
def test_t45_t57_aggregate_status_parametrized(
    items: tuple[WorkflowItem, ...],
    blockers: tuple[WorkflowBlocker, ...],
    summary: WorkflowSummary,
    planning_mode: WorkflowPlanningMode,
    expected: PlanAggregateStatus,
) -> None:
    assert (
        compute_aggregate_status(
            planning_mode=planning_mode,
            items=items,
            blockers=blockers,
            summary=summary,
        )
        == expected
    )


def test_t48_all_blocked_aggregate() -> None:
    item = _review_required_item("a" * 64).model_copy(
        update={"plannerItemStatus": PlannerItemStatus.BLOCKED}
    )
    summary = WorkflowSummary(totalItems=1)
    assert (
        compute_aggregate_status(
            planning_mode=WorkflowPlanningMode.FULL,
            items=(item,),
            blockers=(),
            summary=summary,
        )
        == PlanAggregateStatus.ALL_BLOCKED
    )


def test_t49_mixed_blocked_review() -> None:
    blocked = _review_required_item("a" * 64).model_copy(
        update={"plannerItemStatus": PlannerItemStatus.BLOCKED}
    )
    review = _review_required_item("b" * 64, "rec:review:2")
    summary = WorkflowSummary(totalItems=2)
    assert (
        compute_aggregate_status(
            planning_mode=WorkflowPlanningMode.FULL,
            items=(blocked, review),
            blockers=(),
            summary=summary,
        )
        == PlanAggregateStatus.MIXED_BLOCKED_REVIEW
    )


def test_t50_mixed_blocked() -> None:
    blocked = _merge_item("a" * 64).model_copy(
        update={"plannerItemStatus": PlannerItemStatus.BLOCKED}
    )
    proposed = _merge_item("b" * 64, "rec:merge:2")
    summary = WorkflowSummary(totalItems=2)
    assert (
        compute_aggregate_status(
            planning_mode=WorkflowPlanningMode.FULL,
            items=(blocked, proposed),
            blockers=(),
            summary=summary,
        )
        == PlanAggregateStatus.MIXED_BLOCKED
    )


def test_t51_rejected_aggregate() -> None:
    item = _review_required_item("a" * 64).model_copy(
        update={"operatorItemStatus": OperatorItemStatus.REJECTED}
    )
    summary = WorkflowSummary(totalItems=1)
    assert (
        compute_aggregate_status(
            planning_mode=WorkflowPlanningMode.FULL,
            items=(item,),
            blockers=(),
            summary=summary,
        )
        == PlanAggregateStatus.REJECTED
    )


def test_t52_deferred_aggregate() -> None:
    item = _review_required_item("a" * 64).model_copy(
        update={"operatorItemStatus": OperatorItemStatus.DEFERRED}
    )
    summary = WorkflowSummary(totalItems=1)
    assert (
        compute_aggregate_status(
            planning_mode=WorkflowPlanningMode.FULL,
            items=(item,),
            blockers=(),
            summary=summary,
        )
        == PlanAggregateStatus.DEFERRED
    )


def test_t53_initial_plan_never_ready_for_execution() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation(
                    "rec:merge:1",
                    RecommendationAction.MERGE,
                    memory_ids=("m1", "m2"),
                    source_action_ids=("act-1",),
                ),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
            actions=(_governance_action("act-1", PolicyDecision.APPROVED),),
        )
    )
    plan = plan_workflows(report)
    assert plan.aggregateStatus != PlanAggregateStatus.READY_FOR_EXECUTION


def test_t54_handoff_ready_after_decisions() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation(
                    "rec:merge:1",
                    RecommendationAction.MERGE,
                    memory_ids=("m1", "m2"),
                    source_action_ids=("act-1",),
                ),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
            actions=(_governance_action("act-1", PolicyDecision.APPROVED),),
        )
    )
    plan = plan_workflows(report)
    decided = apply_workflow_decisions(
        plan,
        (
            ApprovalDecision(
                targetType="workflow_item",
                targetId=plan.items[0].workflowItemId,
                decision=ApprovalDecisionType.APPROVED,
            ),
        ),
    )
    assert decided.aggregateStatus == PlanAggregateStatus.READY_FOR_EXECUTION


def test_t55_partially_approved_with_unresolved_review() -> None:
    merge = _merge_item("a" * 64).model_copy(
        update={"operatorItemStatus": OperatorItemStatus.APPROVED}
    )
    review = _review_required_item("b" * 64, "rec:review:2")
    summary = WorkflowSummary(totalItems=2)
    assert (
        compute_aggregate_status(
            planning_mode=WorkflowPlanningMode.FULL,
            items=(merge, review),
            blockers=(),
            summary=summary,
        )
        == PlanAggregateStatus.PARTIALLY_APPROVED
    )


def test_t56_approved_review_only_no_structural() -> None:
    item = _review_required_item("a" * 64).model_copy(
        update={"operatorItemStatus": OperatorItemStatus.APPROVED}
    )
    summary = WorkflowSummary(totalItems=1)
    assert (
        compute_aggregate_status(
            planning_mode=WorkflowPlanningMode.FULL,
            items=(item,),
            blockers=(),
            summary=summary,
        )
        == PlanAggregateStatus.APPROVED
    )


def test_t57_proposed_default() -> None:
    item = _merge_item("a" * 64)
    summary = WorkflowSummary(totalItems=1)
    assert (
        compute_aggregate_status(
            planning_mode=WorkflowPlanningMode.FULL,
            items=(item,),
            blockers=(),
            summary=summary,
        )
        == PlanAggregateStatus.PROPOSED
    )


def test_aggregate_requires_review_initial() -> None:
    plan = plan_workflows(
        _base_report(
            recommendations=(_recommendation("rec:1", RecommendationAction.REVIEW),),
            memoryResolutions=(_resolution("m1", "rec:1", RecommendationAction.REVIEW),),
        )
    )
    assert plan.aggregateStatus == PlanAggregateStatus.REQUIRES_REVIEW


def test_handoff_h7_recommendations_only() -> None:
    report = _base_report(
        recommendations=(
            _recommendation(
                "rec:merge:1",
                RecommendationAction.MERGE,
                source_action_ids=("act-1",),
            ),
        ),
        actions=(_governance_action("act-1", PolicyDecision.APPROVED),),
    )
    plan = plan_workflows(report)
    assert plan.planningMode == WorkflowPlanningMode.RECOMMENDATIONS_ONLY
    assert plan.aggregateStatus != PlanAggregateStatus.READY_FOR_EXECUTION


def test_workflow_planner_version_constant() -> None:
    from memd.workflows import ACTION_PRIORITY_RANK, WORKFLOW_PLANNER_VERSION

    assert WORKFLOW_PLANNER_VERSION == "2"
    assert ACTION_PRIORITY_RANK[ActionPriority.CRITICAL] == 0


def test_m3_approved_plus_unresolved_requires_review() -> None:
    rec = _recommendation(
        "rec:merge:1",
        RecommendationAction.MERGE,
        source_action_ids=("act-approved", "act-unresolved"),
    )
    actions = (
        _governance_action("act-approved", PolicyDecision.APPROVED),
        _governance_action("act-unresolved", None),
    )
    plan = plan_workflows(_base_report(recommendations=(rec,), actions=actions))
    assert plan.items[0].policyDecision == PolicyDecision.REQUIRES_REVIEW


def test_m3_unresolved_only_requires_review() -> None:
    rec = _recommendation(
        "rec:merge:1",
        RecommendationAction.MERGE,
        source_action_ids=("act-unresolved",),
    )
    plan = plan_workflows(
        _base_report(
            recommendations=(rec,),
            actions=(_governance_action("act-unresolved", None),),
        )
    )
    assert plan.items[0].policyDecision == PolicyDecision.REQUIRES_REVIEW
    assert plan.items[0].plannerItemStatus == PlannerItemStatus.REQUIRES_REVIEW


def test_m3_approved_only_approved() -> None:
    rec = _recommendation(
        "rec:merge:1",
        RecommendationAction.MERGE,
        source_action_ids=("act-approved",),
    )
    plan = plan_workflows(
        _base_report(
            recommendations=(rec,),
            actions=(_governance_action("act-approved", PolicyDecision.APPROVED),),
        )
    )
    assert plan.items[0].policyDecision == PolicyDecision.APPROVED


def test_m3_blocked_plus_unresolved_blocked() -> None:
    rec = _recommendation(
        "rec:merge:1",
        RecommendationAction.MERGE,
        source_action_ids=("act-blocked", "act-unresolved"),
    )
    actions = (
        _governance_action("act-blocked", PolicyDecision.BLOCKED),
        _governance_action("act-unresolved", None),
    )
    plan = plan_workflows(_base_report(recommendations=(rec,), actions=actions))
    assert plan.items[0].policyDecision == PolicyDecision.BLOCKED
    assert plan.items[0].plannerItemStatus == PlannerItemStatus.BLOCKED


def test_m3_requires_review_plus_unresolved_requires_review() -> None:
    rec = _recommendation(
        "rec:merge:1",
        RecommendationAction.MERGE,
        source_action_ids=("act-review", "act-unresolved"),
    )
    actions = (
        _governance_action("act-review", PolicyDecision.REQUIRES_REVIEW),
        _governance_action("act-unresolved", None),
    )
    plan = plan_workflows(_base_report(recommendations=(rec,), actions=actions))
    assert plan.items[0].policyDecision == PolicyDecision.REQUIRES_REVIEW


def test_m3_unresolved_not_same_as_missing_action() -> None:
    unresolved = plan_workflows(
        _base_report(
            recommendations=(
                _recommendation(
                    "rec:merge:1",
                    RecommendationAction.MERGE,
                    source_action_ids=("act-unresolved",),
                ),
            ),
            actions=(_governance_action("act-unresolved", None),),
        )
    )
    missing = plan_workflows(
        _base_report(
            recommendations=(
                _recommendation(
                    "rec:merge:2",
                    RecommendationAction.MERGE,
                    source_action_ids=("missing-act",),
                ),
            ),
        )
    )
    assert unresolved.aggregateStatus != PlanAggregateStatus.INTEGRITY_BLOCKED
    assert missing.aggregateStatus == PlanAggregateStatus.INTEGRITY_BLOCKED


def test_m3_policy_source_action_order_independent() -> None:
    rec = _recommendation(
        "rec:merge:1",
        RecommendationAction.MERGE,
        source_action_ids=("act-approved", "act-unresolved"),
    )
    actions = (
        _governance_action("act-approved", PolicyDecision.APPROVED),
        _governance_action("act-unresolved", None),
    )
    forward = plan_workflows(_base_report(recommendations=(rec,), actions=actions))
    reverse_rec = rec.model_copy(update={"sourceActionIds": ("act-unresolved", "act-approved")})
    reverse = plan_workflows(_base_report(recommendations=(reverse_rec,), actions=actions))
    assert forward.items[0].policyDecision == reverse.items[0].policyDecision


def test_m4_lifecycle_mixed_from_suppressed_actions_positive() -> None:
    report = _base_report(
        recommendations=(_recommendation("rec:review:1", RecommendationAction.REVIEW),),
        memoryResolutions=(
            MemoryResolution(
                memoryId="m1",
                resolvedAction=RecommendationAction.REVIEW,
                confidence=0.9,
                recommendationId="rec:review:1",
                suppressedActions=(
                    RecommendationAction.MERGE,
                    RecommendationAction.ARCHIVE,
                ),
            ),
        ),
    )
    plan = plan_workflows(report)
    item = plan.items[0]
    assert ReviewSubtype.LIFECYCLE_MIXED in item.reviewRequirement.subtypes
    assert item.reviewRequirement.primaryQueueId == ReviewQueueId.LIFECYCLE


def test_m4_lifecycle_mixed_from_suppressed_actions_negative() -> None:
    report = _base_report(
        recommendations=(_recommendation("rec:review:1", RecommendationAction.REVIEW),),
        memoryResolutions=(
            MemoryResolution(
                memoryId="m1",
                resolvedAction=RecommendationAction.REVIEW,
                confidence=0.9,
                recommendationId="rec:review:1",
                suppressedActions=(RecommendationAction.MERGE,),
            ),
        ),
    )
    plan = plan_workflows(report)
    assert ReviewSubtype.LIFECYCLE_MIXED not in plan.items[0].reviewRequirement.subtypes


def test_m5_duplicate_removal_warning_scoped_by_recommendation_id() -> None:
    report = _inject_simulation_warnings(
        _with_simulation(
            _base_report(
                recommendations=(
                    _recommendation(
                        "rec:merge:1",
                        RecommendationAction.MERGE,
                        memory_ids=("m1", "m2"),
                        source_action_ids=("act-1",),
                    ),
                    _recommendation(
                        "rec:merge:2",
                        RecommendationAction.MERGE,
                        memory_ids=("m1", "m2"),
                        source_action_ids=("act-2",),
                    ),
                ),
                memoryResolutions=(
                    _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                    _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
                    _resolution("m1", "rec:merge:2", RecommendationAction.MERGE, role="keeper"),
                    _resolution("m2", "rec:merge:2", RecommendationAction.MERGE, role="removable"),
                ),
                actions=(
                    _governance_action("act-1", PolicyDecision.APPROVED),
                    _governance_action("act-2", PolicyDecision.APPROVED),
                ),
            )
        ),
        (
            SimulationWarning(
                code="DUPLICATE_REMOVAL_SKIPPED",
                message="duplicate removal skipped",
                recommendationId="rec:merge:1",
            ),
        ),
    )
    plan = plan_workflows(report)
    targeted = next(item for item in plan.items if item.recommendationId == "rec:merge:1")
    other = next(item for item in plan.items if item.recommendationId == "rec:merge:2")
    duplicate_blockers = [
        blocker
        for blocker in plan.blockers
        if blocker.code == WorkflowBlockerCode.DUPLICATE_REMOVAL_SKIPPED
    ]
    assert duplicate_blockers
    assert duplicate_blockers[0].blockerId in targeted.blockerRefs
    assert duplicate_blockers[0].blockerId not in other.blockerRefs


def test_m5_duplicate_removal_warning_scoped_by_memory_id() -> None:
    report = _inject_simulation_warnings(
        _with_simulation(
            _base_report(
                recommendations=(
                    _recommendation(
                        "rec:merge:1",
                        RecommendationAction.MERGE,
                        memory_ids=("m1", "m2"),
                        source_action_ids=("act-1",),
                    ),
                    _recommendation(
                        "rec:archive:1",
                        RecommendationAction.ARCHIVE,
                        memory_ids=("m2",),
                        source_action_ids=("act-2",),
                    ),
                ),
                memoryResolutions=(
                    _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                    _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
                    _resolution("m2", "rec:archive:1", RecommendationAction.ARCHIVE),
                ),
                actions=(
                    _governance_action("act-1", PolicyDecision.APPROVED),
                    _governance_action("act-2", PolicyDecision.APPROVED),
                ),
            )
        ),
        (
            SimulationWarning(
                code="DUPLICATE_REMOVAL_SKIPPED",
                message="duplicate removal skipped",
                memoryId="m1",
            ),
        ),
    )
    plan = plan_workflows(report)
    merge_item = next(item for item in plan.items if item.recommendationId == "rec:merge:1")
    archive_item = next(item for item in plan.items if item.recommendationId == "rec:archive:1")
    duplicate_blockers = [
        blocker
        for blocker in plan.blockers
        if blocker.code == WorkflowBlockerCode.DUPLICATE_REMOVAL_SKIPPED
    ]
    assert duplicate_blockers
    assert duplicate_blockers[0].blockerId in merge_item.blockerRefs
    assert duplicate_blockers[0].blockerId not in archive_item.blockerRefs


def test_m5_duplicate_removal_unscoped_warning_integrity_blocked() -> None:
    report = _inject_simulation_warnings(
        _with_simulation(
            _base_report(
                recommendations=(
                    _recommendation(
                        "rec:merge:1",
                        RecommendationAction.MERGE,
                        memory_ids=("m1", "m2"),
                        source_action_ids=("act-1",),
                    ),
                ),
                memoryResolutions=(
                    _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                    _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
                ),
                actions=(_governance_action("act-1", PolicyDecision.APPROVED),),
            )
        ),
        (
            SimulationWarning(
                code="DUPLICATE_REMOVAL_SKIPPED",
                message="duplicate removal skipped",
            ),
        ),
    )
    plan = plan_workflows(report)
    assert plan.aggregateStatus == PlanAggregateStatus.INTEGRITY_BLOCKED
    duplicate_blockers = [
        blocker
        for blocker in plan.blockers
        if blocker.code == WorkflowBlockerCode.DUPLICATE_REMOVAL_SKIPPED
    ]
    assert not duplicate_blockers
    assert any(
        ref.startswith("integrity:duplicate_removal_unscoped:")
        for ref in plan.evidence.validationRefs
    )
    assert not plan.items[0].blockerRefs


def test_m7_conflicting_duplicate_variants_in_validation_refs() -> None:
    first = _recommendation("rec:dup", RecommendationAction.MERGE)
    second = _recommendation("rec:dup", RecommendationAction.ARCHIVE)
    plan = plan_workflows(_base_report(recommendations=(first, second)))
    variant_refs = [
        ref for ref in plan.evidence.validationRefs if ref.startswith("duplicate_variant:")
    ]
    assert len(variant_refs) == 2
    assert variant_refs == sorted(variant_refs)
    integrity = next(
        blocker for blocker in plan.blockers if blocker.code == WorkflowBlockerCode.INPUT_INTEGRITY
    )
    assert "duplicate_variant_digests:" in integrity.message


def test_m7_conflicting_duplicate_variant_coverage_order_independent() -> None:
    first = _recommendation("rec:dup", RecommendationAction.MERGE)
    second = _recommendation("rec:dup", RecommendationAction.ARCHIVE)
    forward = plan_workflows(_base_report(recommendations=(first, second)))
    reverse = plan_workflows(_base_report(recommendations=(second, first)))
    assert forward.evidence.validationRefs == reverse.evidence.validationRefs


def test_l1_evidence_refs_populated_from_recommendation_evidence() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation(
                    "rec:merge:1",
                    RecommendationAction.MERGE,
                    memory_ids=("m1", "m2"),
                    source_action_ids=("act-1",),
                    evidence=(
                        RecommendationEvidence(
                            source="governance",
                            signal="merge_cluster",
                            actionId="act-evidence-1",
                        ),
                    ),
                ),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
            actions=(_governance_action("act-1", PolicyDecision.APPROVED),),
        )
    )
    plan = plan_workflows(report)
    assert "evidence:action:act-evidence-1" in plan.items[0].evidenceRefs
    assert "evidence:action:act-evidence-1" in plan.evidence.validationRefs


def test_l5_decision_on_non_overridable_blocker_rejected() -> None:
    report = _base_report(
        recommendations=(
            _recommendation("rec:merge:1", RecommendationAction.MERGE, memory_ids=("m1", "m2")),
        ),
        memoryResolutions=(
            _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
            _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
        ),
    )
    plan = plan_workflows(report)
    before = plan.model_dump(mode="json")
    fingerprint_before = plan.decisionsFingerprint
    with pytest.raises(WorkflowDecisionError):
        apply_workflow_decisions(
            plan,
            (
                ApprovalDecision(
                    targetType="workflow_item",
                    targetId=plan.items[0].workflowItemId,
                    decision=ApprovalDecisionType.APPROVED,
                ),
            ),
        )
    assert plan.model_dump(mode="json") == before
    assert plan.decisionsFingerprint == fingerprint_before


def test_l6_repeated_identical_decision_full_plan_idempotent() -> None:
    report = _base_report(
        recommendations=(_recommendation("rec:1", RecommendationAction.REVIEW),),
        memoryResolutions=(_resolution("m1", "rec:1", RecommendationAction.REVIEW),),
    )
    plan = plan_workflows(report)
    decision = ApprovalDecision(
        targetType="workflow_item",
        targetId=plan.items[0].workflowItemId,
        decision=ApprovalDecisionType.APPROVED,
    )
    first = apply_workflow_decisions(plan, (decision,))
    second = apply_workflow_decisions(first, (decision,))
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_l6_duplicate_identical_decisions_in_one_batch_idempotent() -> None:
    report = _base_report(
        recommendations=(_recommendation("rec:1", RecommendationAction.REVIEW),),
        memoryResolutions=(_resolution("m1", "rec:1", RecommendationAction.REVIEW),),
    )
    plan = plan_workflows(report)
    decision = ApprovalDecision(
        targetType="workflow_item",
        targetId=plan.items[0].workflowItemId,
        decision=ApprovalDecisionType.APPROVED,
    )
    once = apply_workflow_decisions(plan, (decision,))
    twice = apply_workflow_decisions(plan, (decision, decision))
    assert once.model_dump(mode="json") == twice.model_dump(mode="json")


def test_l6_multi_call_cumulative_decisions_full_plan_idempotent() -> None:
    report = _base_report(
        recommendations=(
            _recommendation("rec:review:1", RecommendationAction.REVIEW),
            _recommendation("rec:review:2", RecommendationAction.REVIEW, memory_ids=("m2",)),
        ),
        memoryResolutions=(
            _resolution("m1", "rec:review:1", RecommendationAction.REVIEW),
            _resolution("m2", "rec:review:2", RecommendationAction.REVIEW),
        ),
    )
    plan = plan_workflows(report)
    first = apply_workflow_decisions(
        plan,
        (
            ApprovalDecision(
                targetType="workflow_item",
                targetId=plan.items[0].workflowItemId,
                decision=ApprovalDecisionType.APPROVED,
            ),
        ),
    )
    second = apply_workflow_decisions(
        first,
        (
            ApprovalDecision(
                targetType="workflow_item",
                targetId=first.items[1].workflowItemId,
                decision=ApprovalDecisionType.APPROVED,
            ),
        ),
    )
    third = apply_workflow_decisions(
        second,
        (
            ApprovalDecision(
                targetType="workflow_item",
                targetId=second.items[1].workflowItemId,
                decision=ApprovalDecisionType.APPROVED,
            ),
        ),
    )
    assert second.model_dump(mode="json") == third.model_dump(mode="json")


def test_decisions_fingerprint_stable_on_repeat() -> None:
    report = _base_report(
        recommendations=(_recommendation("rec:1", RecommendationAction.REVIEW),),
        memoryResolutions=(_resolution("m1", "rec:1", RecommendationAction.REVIEW),),
    )
    plan = plan_workflows(report)
    decision = ApprovalDecision(
        targetType="workflow_item",
        targetId=plan.items[0].workflowItemId,
        decision=ApprovalDecisionType.APPROVED,
    )
    first = apply_workflow_decisions(plan, (decision,))
    second = apply_workflow_decisions(first, (decision,))
    assert first.decisionsFingerprint == second.decisionsFingerprint
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_initial_plan_never_ready_rule() -> None:
    report = _with_simulation(
        _base_report(
            recommendations=(
                _recommendation(
                    "rec:merge:1",
                    RecommendationAction.MERGE,
                    memory_ids=("m1", "m2"),
                    source_action_ids=("act-1",),
                ),
            ),
            memoryResolutions=(
                _resolution("m1", "rec:merge:1", RecommendationAction.MERGE, role="keeper"),
                _resolution("m2", "rec:merge:1", RecommendationAction.MERGE, role="removable"),
            ),
            actions=(_governance_action("act-1", PolicyDecision.APPROVED),),
        )
    )
    plan = plan_workflows(report)
    assert plan.aggregateStatus == PlanAggregateStatus.PROPOSED


def test_blocked_decision_on_keep_rejected() -> None:
    report = _base_report(
        recommendations=(_recommendation("rec:keep:1", RecommendationAction.KEEP),),
        memoryResolutions=(_resolution("m1", "rec:keep:1", RecommendationAction.KEEP),),
    )
    plan = plan_workflows(report, options=PlanningOptions(includeKeep=True))
    with pytest.raises(WorkflowDecisionError):
        apply_workflow_decisions(
            plan,
            (
                ApprovalDecision(
                    targetType="workflow_item",
                    targetId=plan.items[0].workflowItemId,
                    decision=ApprovalDecisionType.APPROVED,
                ),
            ),
        )
