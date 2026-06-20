from __future__ import annotations

import pytest
from pydantic import ValidationError

from memd.contracts import (
    SIMULATION_REF_PREFIXES,
    ActionPriority,
    AnalysisMetrics,
    AnalysisReport,
    ApprovalDecision,
    ApprovalDecisionType,
    MemoryRecord,
    MemoryRoleAssignment,
    OperatorItemStatus,
    PlanAggregateStatus,
    PlannerItemStatus,
    PlanningOptions,
    PolicyDecision,
    PolicyProfile,
    RecommendationAction,
    ReviewQueueId,
    ReviewRequirement,
    ReviewSubtype,
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
from memd.reports import report_to_dict


def _minimal_metrics() -> AnalysisMetrics:
    return AnalysisMetrics(
        totalMemories=1,
        duplicateCount=0,
        duplicatePercentage=0.0,
        compressionOpportunity=0.0,
        categoryBreakdown={},
    )


def _minimal_review_requirement(required: bool = False) -> ReviewRequirement:
    if required:
        return ReviewRequirement(
            required=True,
            reason="Needs review",
            subtypes=(ReviewSubtype.GENERAL,),
            primaryQueueId=ReviewQueueId.GENERAL,
            queueRefs=(ReviewQueueId.GENERAL,),
            escalationSignals=(),
        )
    return ReviewRequirement(
        required=False,
        reason="",
        subtypes=(),
        primaryQueueId=None,
        queueRefs=(),
        escalationSignals=(),
    )


def _minimal_item(**overrides: object) -> WorkflowItem:
    payload = {
        "workflowItemId": "item-1",
        "recommendationId": "rec:1",
        "action": RecommendationAction.MERGE,
        "plannerItemStatus": PlannerItemStatus.PROPOSED,
        "operatorItemStatus": OperatorItemStatus.NONE,
        "recommendationPriority": ActionPriority.HIGH,
        "queueRank": 1,
        "reviewRequirement": _minimal_review_requirement(required=False),
        "affectedMemoryIds": ("m1", "m2"),
        "roles": (
            MemoryRoleAssignment(memoryId="m1", role="keeper"),
            MemoryRoleAssignment(memoryId="m2", role="removable"),
        ),
        "policyDecision": None,
        "requiresHumanApproval": False,
        "blockerRefs": (),
        "simulationRefs": ("merge:rec:1",),
        "evidenceRefs": (),
        "orderingKey": "high:merge:rec:1",
        "conflictDetected": False,
        "suppressedActions": (),
    }
    payload.update(overrides)
    return WorkflowItem(**payload)


def _minimal_step_operation(**overrides: object) -> WorkflowStepOperation:
    payload = {
        "stepType": WorkflowStepType.MERGE,
        "keeperId": "m1",
        "removableIds": ("m2",),
        "archiveTargetIds": (),
        "reviewTargetIds": (),
        "recommendationIds": ("rec:1",),
    }
    payload.update(overrides)
    return WorkflowStepOperation(**payload)


def _minimal_step(**overrides: object) -> WorkflowStep:
    payload = {
        "stepId": "step-1",
        "sequence": 1,
        "stepType": WorkflowStepType.MERGE,
        "workflowItemIds": ("item-1",),
        "dependsOnStepIds": (),
        "plannerStepStatus": PlannerItemStatus.PROPOSED,
        "operation": _minimal_step_operation(),
        "description": "merge keeper and removable",
    }
    payload.update(overrides)
    return WorkflowStep(**payload)


def _minimal_plan(**overrides: object) -> WorkflowPlan:
    payload = {
        "workflowPlanId": "a" * 64,
        "sourceAnalysisRef": "b" * 64,
        "simulationId": "c" * 64,
        "policyProfile": PolicyProfile.BALANCED,
        "plannerStatus": WorkflowPlannerStatus.INITIAL,
        "aggregateStatus": PlanAggregateStatus.PROPOSED,
        "items": (_minimal_item(),),
        "steps": (_minimal_step(),),
        "summary": WorkflowSummary(totalItems=1),
        "reviewQueues": (),
        "blockers": (),
        "evidence": WorkflowEvidence(),
        "planningMode": WorkflowPlanningMode.FULL,
        "planningOptions": PlanningOptions(),
        "plannerVersion": "1",
        "metricsDisclaimer": "",
        "decisionsFingerprint": "",
    }
    payload.update(overrides)
    return WorkflowPlan(**payload)


def _minimal_report(**overrides: object) -> AnalysisReport:
    payload = {
        "metrics": _minimal_metrics(),
        "clusters": (),
        "memories": (MemoryRecord(id="m1", content="hello"),),
    }
    payload.update(overrides)
    return AnalysisReport(**payload)


def test_planning_options_default_include_keep_false() -> None:
    assert PlanningOptions().includeKeep is False


def test_workflow_item_default_operator_status_none() -> None:
    item = _minimal_item(operatorItemStatus=OperatorItemStatus.NONE)
    assert item.operatorItemStatus == OperatorItemStatus.NONE


def test_minimal_initial_workflow_plan_is_valid() -> None:
    plan = _minimal_plan()
    assert plan.aggregateStatus == PlanAggregateStatus.PROPOSED


def test_analysis_report_without_workflow_plan_is_valid() -> None:
    report = _minimal_report()
    assert report.workflowPlan is None


def test_analysis_report_with_explicit_none_workflow_plan() -> None:
    report = _minimal_report(workflowPlan=None)
    assert report.workflowPlan is None


@pytest.mark.parametrize("value", [item.value for item in PlanAggregateStatus])
def test_plan_aggregate_status_enum_serialization(value: str) -> None:
    parsed = PlanAggregateStatus(value)
    assert parsed.value == value


def test_review_subtype_and_queue_enum_validation() -> None:
    rr = _minimal_review_requirement(required=True)
    assert rr.subtypes == (ReviewSubtype.GENERAL,)
    assert rr.primaryQueueId == ReviewQueueId.GENERAL


def test_review_requirement_required_missing_subtype_fails() -> None:
    with pytest.raises(ValidationError):
        ReviewRequirement(
            required=True,
            reason="Needs review",
            subtypes=(),
            primaryQueueId=ReviewQueueId.GENERAL,
            queueRefs=(ReviewQueueId.GENERAL,),
            escalationSignals=(),
        )


def test_review_requirement_required_missing_queue_fails() -> None:
    with pytest.raises(ValidationError):
        ReviewRequirement(
            required=True,
            reason="Needs review",
            subtypes=(ReviewSubtype.GENERAL,),
            primaryQueueId=ReviewQueueId.GENERAL,
            queueRefs=(),
            escalationSignals=(),
        )


def test_review_requirement_primary_queue_must_be_in_refs() -> None:
    with pytest.raises(ValidationError):
        ReviewRequirement(
            required=True,
            reason="Needs review",
            subtypes=(ReviewSubtype.GENERAL,),
            primaryQueueId=ReviewQueueId.GENERAL,
            queueRefs=(ReviewQueueId.POLICY,),
            escalationSignals=(),
        )


def test_review_requirement_non_required_with_queue_data_fails() -> None:
    with pytest.raises(ValidationError):
        ReviewRequirement(
            required=False,
            reason="",
            subtypes=(),
            primaryQueueId=ReviewQueueId.GENERAL,
            queueRefs=(ReviewQueueId.GENERAL,),
            escalationSignals=(),
        )


def test_review_requirement_non_required_with_escalation_signals_fails() -> None:
    with pytest.raises(ValidationError):
        ReviewRequirement(
            required=False,
            reason="",
            subtypes=(),
            primaryQueueId=None,
            queueRefs=(),
            escalationSignals=("x",),
        )


def test_valid_merge_operation() -> None:
    op = _minimal_step_operation()
    assert op.keeperId == "m1"


def test_merge_without_keeper_fails() -> None:
    with pytest.raises(ValidationError):
        _minimal_step_operation(keeperId="")


def test_merge_without_removables_fails() -> None:
    with pytest.raises(ValidationError):
        _minimal_step_operation(removableIds=())


def test_merge_keeper_inside_removables_fails() -> None:
    with pytest.raises(ValidationError):
        _minimal_step_operation(removableIds=("m1",))


def test_merge_duplicate_removables_fails() -> None:
    with pytest.raises(ValidationError):
        _minimal_step_operation(removableIds=("m2", "m2"))


def test_valid_archive_operation() -> None:
    op = WorkflowStepOperation(
        stepType=WorkflowStepType.ARCHIVE,
        archiveTargetIds=("a1",),
        recommendationIds=("rec:1",),
    )
    assert op.archiveTargetIds == ("a1",)


def test_archive_without_targets_fails() -> None:
    with pytest.raises(ValidationError):
        WorkflowStepOperation(stepType=WorkflowStepType.ARCHIVE)


def test_duplicate_archive_targets_fail() -> None:
    with pytest.raises(ValidationError):
        WorkflowStepOperation(stepType=WorkflowStepType.ARCHIVE, archiveTargetIds=("a1", "a1"))


def test_valid_review_operation() -> None:
    op = WorkflowStepOperation(
        stepType=WorkflowStepType.REVIEW,
        reviewTargetIds=("m1",),
        recommendationIds=("rec:1",),
    )
    assert op.reviewTargetIds == ("m1",)


def test_review_without_targets_fails() -> None:
    with pytest.raises(ValidationError):
        WorkflowStepOperation(stepType=WorkflowStepType.REVIEW)


def test_duplicate_review_targets_fail() -> None:
    with pytest.raises(ValidationError):
        WorkflowStepOperation(stepType=WorkflowStepType.REVIEW, reviewTargetIds=("m1", "m1"))


def test_retain_with_removal_intent_fails() -> None:
    with pytest.raises(ValidationError):
        WorkflowStepOperation(stepType=WorkflowStepType.RETAIN, removableIds=("m2",))


def test_duplicate_workflow_item_ids_fail() -> None:
    i1 = _minimal_item(workflowItemId="same", recommendationId="r1")
    i2 = _minimal_item(workflowItemId="same", recommendationId="r2")
    with pytest.raises(ValidationError):
        _minimal_plan(items=(i1, i2), steps=())


def test_duplicate_recommendation_ids_fail() -> None:
    i1 = _minimal_item(workflowItemId="i1", recommendationId="same")
    i2 = _minimal_item(workflowItemId="i2", recommendationId="same")
    with pytest.raises(ValidationError):
        _minimal_plan(items=(i1, i2), steps=())


def test_duplicate_blocker_ids_fail() -> None:
    blocker = WorkflowBlocker(
        blockerId="b1",
        code=WorkflowBlockerCode.POLICY_BLOCKED,
        message="blocked",
        sourceLayer="policy",
        overridable=False,
    )
    with pytest.raises(ValidationError):
        _minimal_plan(blockers=(blocker, blocker))


def test_duplicate_step_ids_fail() -> None:
    s1 = _minimal_step(stepId="same", sequence=1)
    s2 = _minimal_step(stepId="same", sequence=2, workflowItemIds=())
    with pytest.raises(ValidationError):
        _minimal_plan(steps=(s1, s2))


def test_gap_in_sequences_fails() -> None:
    s1 = _minimal_step(sequence=1)
    s2 = _minimal_step(stepId="step-2", sequence=3, workflowItemIds=())
    with pytest.raises(ValidationError):
        _minimal_plan(steps=(s1, s2))


def test_unknown_blocker_ref_fails() -> None:
    item = _minimal_item(blockerRefs=("missing",))
    with pytest.raises(ValidationError):
        _minimal_plan(items=(item,))


def test_initial_plan_with_decided_operator_status_fails() -> None:
    item = _minimal_item(operatorItemStatus=OperatorItemStatus.APPROVED)
    with pytest.raises(ValidationError):
        _minimal_plan(items=(item,))


def test_initial_plan_marked_ready_for_execution_fails() -> None:
    with pytest.raises(ValidationError):
        _minimal_plan(aggregateStatus=PlanAggregateStatus.READY_FOR_EXECUTION)


def test_initial_plan_with_decisions_fingerprint_fails() -> None:
    with pytest.raises(ValidationError):
        _minimal_plan(decisionsFingerprint="x")


def test_integrity_blocked_requires_integrity_blocker() -> None:
    with pytest.raises(ValidationError):
        _minimal_plan(aggregateStatus=PlanAggregateStatus.INTEGRITY_BLOCKED)


def test_invalid_workflow_plan_hash_fails() -> None:
    with pytest.raises(ValidationError):
        _minimal_plan(workflowPlanId="not-a-hash")


def test_workflow_plan_json_round_trip() -> None:
    plan = _minimal_plan()
    data = plan.model_dump(mode="json")
    reconstructed = WorkflowPlan.model_validate(data)
    assert reconstructed == plan


def test_analysis_report_json_round_trip() -> None:
    report = _minimal_report(workflowPlan=_minimal_plan())
    data = report.model_dump(mode="json")
    reconstructed = AnalysisReport.model_validate(data)
    assert reconstructed.workflowPlan is not None


def test_historical_planner_version_deserialization_allowed() -> None:
    plan = _minimal_plan(plannerVersion="0")
    dumped = plan.model_dump(mode="json")
    reloaded = WorkflowPlan.model_validate(dumped)
    assert reloaded.plannerVersion == "0"


def test_top_level_plan_mutation_rejected() -> None:
    plan = _minimal_plan()
    with pytest.raises(ValidationError):
        plan.aggregateStatus = PlanAggregateStatus.APPROVED  # type: ignore[misc]


def test_nested_frozen_model_mutation_rejected() -> None:
    item = _minimal_item()
    with pytest.raises(ValidationError):
        item.orderingKey = "changed"  # type: ignore[misc]


def test_summary_mapping_inputs_are_defensively_copied() -> None:
    source = {ReviewQueueId.GENERAL: 1}
    summary = WorkflowSummary(reviewQueueCounts=source)
    source[ReviewQueueId.GENERAL] = 99
    assert summary.reviewQueueCounts[ReviewQueueId.GENERAL] == 1


def test_nested_dictionary_mutability_limitation_documented() -> None:
    summary = WorkflowSummary(reviewQueueCounts={ReviewQueueId.GENERAL: 1})
    summary.reviewQueueCounts[ReviewQueueId.GENERAL] = 2
    assert summary.reviewQueueCounts[ReviewQueueId.GENERAL] == 2


def test_existing_analysis_report_construction_still_works() -> None:
    report = AnalysisReport(metrics=_minimal_metrics(), clusters=())
    assert report.workflowPlan is None


def test_report_output_unchanged_when_workflow_plan_none() -> None:
    payload = report_to_dict(_minimal_report(workflowPlan=None))
    assert "workflowPlan" not in payload


def test_analysis_report_model_rebuild_succeeds() -> None:
    AnalysisReport.model_rebuild()


def test_approval_decision_item_target_only() -> None:
    decision = ApprovalDecision(
        targetType="workflow_item",
        targetId="item-1",
        decision=ApprovalDecisionType.APPROVED,
        rationale="ok",
    )
    assert decision.targetType == "workflow_item"


def test_workflow_item_rejects_invalid_simulation_ref_prefix() -> None:
    with pytest.raises(ValidationError):
        _minimal_item(simulationRefs=("bad:ref",))


def test_workflow_item_rejects_duplicate_simulation_refs() -> None:
    with pytest.raises(ValidationError):
        _minimal_item(simulationRefs=("merge:rec:1", "merge:rec:1"))


def test_workflow_item_rejects_duplicate_roles() -> None:
    with pytest.raises(ValidationError):
        _minimal_item(
            roles=(
                MemoryRoleAssignment(memoryId="m1", role="keeper"),
                MemoryRoleAssignment(memoryId="m1", role="removable"),
            )
        )


def test_review_requirement_rejects_duplicate_subtypes() -> None:
    with pytest.raises(ValidationError):
        ReviewRequirement(
            required=True,
            reason="Needs review",
            subtypes=(ReviewSubtype.GENERAL, ReviewSubtype.GENERAL),
            primaryQueueId=ReviewQueueId.GENERAL,
            queueRefs=(ReviewQueueId.GENERAL,),
            escalationSignals=(),
        )


def test_review_requirement_rejects_duplicate_queue_refs() -> None:
    with pytest.raises(ValidationError):
        ReviewRequirement(
            required=True,
            reason="Needs review",
            subtypes=(ReviewSubtype.GENERAL,),
            primaryQueueId=ReviewQueueId.GENERAL,
            queueRefs=(ReviewQueueId.GENERAL, ReviewQueueId.GENERAL),
            escalationSignals=(),
        )


def test_blocker_non_overridable_codes_enforced() -> None:
    with pytest.raises(ValidationError):
        WorkflowBlocker(
            blockerId="b1",
            code=WorkflowBlockerCode.INPUT_INTEGRITY,
            message="x",
            sourceLayer="workflow",
            overridable=True,
        )


def test_simulation_ref_prefixes_constant_values() -> None:
    assert SIMULATION_REF_PREFIXES == ("merge:", "archive:", "review:", "warning:")


def _required_review() -> ReviewRequirement:
    return _minimal_review_requirement(required=True)


def test_review_action_requires_review_requirement() -> None:
    with pytest.raises(ValidationError):
        _minimal_item(
            action=RecommendationAction.REVIEW,
            reviewRequirement=_minimal_review_requirement(required=False),
        )


def test_requires_human_approval_requires_review_requirement() -> None:
    with pytest.raises(ValidationError):
        _minimal_item(
            requiresHumanApproval=True,
            reviewRequirement=_minimal_review_requirement(required=False),
        )


def test_planner_requires_review_status_requires_review_requirement() -> None:
    with pytest.raises(ValidationError):
        _minimal_item(
            plannerItemStatus=PlannerItemStatus.REQUIRES_REVIEW,
            reviewRequirement=_minimal_review_requirement(required=False),
        )


def test_policy_requires_review_requires_review_requirement() -> None:
    with pytest.raises(ValidationError):
        _minimal_item(
            policyDecision=PolicyDecision.REQUIRES_REVIEW,
            reviewRequirement=_minimal_review_requirement(required=False),
        )


def test_merge_action_with_valid_required_review_is_valid() -> None:
    item = _minimal_item(
        action=RecommendationAction.MERGE,
        reviewRequirement=_required_review(),
    )
    assert item.action == RecommendationAction.MERGE
    assert item.reviewRequirement.required is True


def test_archive_action_with_valid_required_review_is_valid() -> None:
    item = _minimal_item(
        action=RecommendationAction.ARCHIVE,
        reviewRequirement=_required_review(),
    )
    assert item.action == RecommendationAction.ARCHIVE
    assert item.reviewRequirement.required is True


def test_proposed_merge_without_review_signals_is_valid() -> None:
    item = _minimal_item(
        action=RecommendationAction.MERGE,
        plannerItemStatus=PlannerItemStatus.PROPOSED,
        requiresHumanApproval=False,
        policyDecision=None,
        reviewRequirement=_minimal_review_requirement(required=False),
    )
    assert item.reviewRequirement.required is False


def test_blocked_item_without_review_requirement_is_valid() -> None:
    item = _minimal_item(
        plannerItemStatus=PlannerItemStatus.BLOCKED,
        requiresHumanApproval=False,
        policyDecision=None,
        reviewRequirement=_minimal_review_requirement(required=False),
    )
    assert item.plannerItemStatus == PlannerItemStatus.BLOCKED


def test_merge_whitespace_only_keeper_fails() -> None:
    with pytest.raises(ValidationError):
        _minimal_step_operation(keeperId="   ")


def test_merge_whitespace_only_removable_fails() -> None:
    with pytest.raises(ValidationError):
        _minimal_step_operation(removableIds=("   ",))


def test_archive_whitespace_only_target_fails() -> None:
    with pytest.raises(ValidationError):
        WorkflowStepOperation(
            stepType=WorkflowStepType.ARCHIVE,
            archiveTargetIds=("   ",),
        )


def test_review_whitespace_only_target_fails() -> None:
    with pytest.raises(ValidationError):
        WorkflowStepOperation(
            stepType=WorkflowStepType.REVIEW,
            reviewTargetIds=("   ",),
        )


def test_operation_ids_duplicate_after_trimming_fails() -> None:
    with pytest.raises(ValidationError):
        _minimal_step_operation(removableIds=("m2", " m2 "))


def test_operation_ids_normalize_whitespace() -> None:
    op = _minimal_step_operation(keeperId=" m1 ", removableIds=(" m2 ",))
    assert op.keeperId == "m1"
    assert op.removableIds == ("m2",)


def _minimal_item_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "workflowItemId": "item-1",
        "recommendationId": "rec:1",
        "action": RecommendationAction.MERGE.value,
        "plannerItemStatus": PlannerItemStatus.PROPOSED.value,
        "operatorItemStatus": OperatorItemStatus.NONE.value,
        "recommendationPriority": ActionPriority.HIGH.value,
        "queueRank": 1,
        "reviewRequirement": {
            "required": False,
            "reason": "",
            "subtypes": [],
            "primaryQueueId": None,
            "queueRefs": [],
            "escalationSignals": [],
        },
        "requiresHumanApproval": False,
        "orderingKey": "high:merge:rec:1",
    }
    payload.update(overrides)
    return payload


def _minimal_plan_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "workflowPlanId": "a" * 64,
        "sourceAnalysisRef": "b" * 64,
        "policyProfile": PolicyProfile.BALANCED.value,
        "plannerStatus": WorkflowPlannerStatus.INITIAL.value,
        "aggregateStatus": PlanAggregateStatus.PROPOSED.value,
        "items": [],
        "steps": [],
        "summary": {"totalItems": 0},
        "evidence": {},
        "planningMode": WorkflowPlanningMode.FULL.value,
        "plannerVersion": "1",
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        pytest.param(
            WorkflowItem,
            _minimal_item_payload(plannerItemStatus="not_a_status"),
            id="planner-item-status",
        ),
        pytest.param(
            WorkflowItem,
            _minimal_item_payload(operatorItemStatus="not_a_status"),
            id="operator-item-status",
        ),
        pytest.param(
            WorkflowItem,
            _minimal_item_payload(action="not_an_action"),
            id="recommendation-action",
        ),
        pytest.param(
            WorkflowItem,
            _minimal_item_payload(recommendationPriority="not_a_priority"),
            id="action-priority",
        ),
        pytest.param(
            WorkflowItem,
            _minimal_item_payload(policyDecision="not_a_decision"),
            id="policy-decision",
        ),
        pytest.param(
            WorkflowPlan,
            _minimal_plan_payload(aggregateStatus="not_a_status"),
            id="aggregate-plan-status",
        ),
        pytest.param(
            WorkflowPlan,
            _minimal_plan_payload(plannerStatus="not_a_status"),
            id="planner-status",
        ),
        pytest.param(
            WorkflowPlan,
            _minimal_plan_payload(planningMode="not_a_mode"),
            id="planning-mode",
        ),
        pytest.param(
            WorkflowStep,
            {
                "stepId": "step-1",
                "sequence": 1,
                "stepType": WorkflowStepType.MERGE.value,
                "plannerStepStatus": "not_a_status",
                "operation": {
                    "stepType": WorkflowStepType.MERGE.value,
                    "keeperId": "m1",
                    "removableIds": ["m2"],
                },
            },
            id="planner-step-status",
        ),
        pytest.param(
            WorkflowStep,
            {
                "stepId": "step-1",
                "sequence": 1,
                "stepType": "not_a_step_type",
                "plannerStepStatus": PlannerItemStatus.PROPOSED.value,
                "operation": {
                    "stepType": WorkflowStepType.MERGE.value,
                    "keeperId": "m1",
                    "removableIds": ["m2"],
                },
            },
            id="workflow-step-type",
        ),
        pytest.param(
            WorkflowStepOperation,
            {"stepType": "not_a_step_type", "keeperId": "m1", "removableIds": ["m2"]},
            id="operation-step-type",
        ),
        pytest.param(
            WorkflowBlocker,
            {
                "blockerId": "b1",
                "code": "NOT_A_CODE",
                "message": "blocked",
                "sourceLayer": "policy",
                "overridable": False,
            },
            id="blocker-code",
        ),
        pytest.param(
            ReviewRequirement,
            {
                "required": True,
                "reason": "Needs review",
                "subtypes": ["not_a_subtype"],
                "primaryQueueId": ReviewQueueId.GENERAL.value,
                "queueRefs": [ReviewQueueId.GENERAL.value],
            },
            id="review-subtype",
        ),
        pytest.param(
            ReviewRequirement,
            {
                "required": True,
                "reason": "Needs review",
                "subtypes": [ReviewSubtype.GENERAL.value],
                "primaryQueueId": "review:not_a_queue",
                "queueRefs": ["review:not_a_queue"],
            },
            id="review-queue-id",
        ),
        pytest.param(
            ApprovalDecision,
            {
                "targetType": "workflow_item",
                "targetId": "item-1",
                "decision": "not_a_decision",
            },
            id="approval-decision-type",
        ),
    ],
)
def test_invalid_enum_values_rejected(model: type, payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)
