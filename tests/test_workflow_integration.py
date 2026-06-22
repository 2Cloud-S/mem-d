"""V0.8 Phase 3 workflow pipeline and reporting integration tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from memd.contracts import (
    ActionPriority,
    AnalysisMetrics,
    AnalysisReport,
    MemoryCategory,
    MemoryRecord,
    OperatorItemStatus,
    PlanAggregateStatus,
    PlannerItemStatus,
    PlanningOptions,
    PolicyProfile,
    RecommendationAction,
    ReviewRequirement,
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
from memd.pipeline import analyze_file
from memd.reports import (
    render_json,
    render_markdown,
    render_terminal,
    render_workflow_terminal,
    report_to_dict,
    workflow_plan_to_dict,
)

FIXTURES = Path(__file__).parent / "fixtures"
MEMORIES_JSON = FIXTURES / "memories.json"


def _minimal_metrics() -> AnalysisMetrics:
    return AnalysisMetrics(
        totalMemories=1,
        duplicateCount=0,
        duplicatePercentage=0.0,
        compressionOpportunity=0.0,
        categoryBreakdown={category: 0 for category in MemoryCategory},
    )


def _minimal_report(*, workflow_plan: WorkflowPlan | None = None) -> AnalysisReport:
    return AnalysisReport(
        metrics=_minimal_metrics(),
        clusters=(),
        memories=(MemoryRecord(id="m1", content="hello"),),
        workflowPlan=workflow_plan,
    )


def _minimal_item(index: int = 1) -> WorkflowItem:
    return WorkflowItem(
        workflowItemId=f"{index:064x}",
        recommendationId=f"rec:{index}",
        action=RecommendationAction.MERGE,
        plannerItemStatus=PlannerItemStatus.PROPOSED,
        operatorItemStatus=OperatorItemStatus.NONE,
        recommendationPriority=ActionPriority.HIGH,
        queueRank=index,
        reviewRequirement=ReviewRequirement(required=False),
        affectedMemoryIds=(f"m{index}",),
        requiresHumanApproval=False,
        orderingKey=f"high:merge:rec:{index}",
    )


def _minimal_plan(**overrides: object) -> WorkflowPlan:
    payload = {
        "workflowPlanId": "a" * 64,
        "sourceAnalysisRef": "b" * 64,
        "simulationId": "c" * 64,
        "policyProfile": PolicyProfile.BALANCED,
        "plannerStatus": WorkflowPlannerStatus.INITIAL,
        "aggregateStatus": PlanAggregateStatus.PROPOSED,
        "items": (),
        "steps": (),
        "summary": WorkflowSummary(totalItems=0),
        "reviewQueues": (),
        "blockers": (),
        "evidence": WorkflowEvidence(),
        "planningMode": WorkflowPlanningMode.FULL,
        "planningOptions": PlanningOptions(),
        "plannerVersion": "2",
        "metricsDisclaimer": "",
        "decisionsFingerprint": "",
    }
    payload.update(overrides)
    return WorkflowPlan(**payload)


def _plan_report(plan: WorkflowPlan) -> AnalysisReport:
    return _minimal_report(workflow_plan=plan)


def _integrity_blocked_plan():
    blocker = WorkflowBlocker(
        blockerId="d" * 64,
        code=WorkflowBlockerCode.INPUT_INTEGRITY,
        message="Workflow input integrity checks failed.",
        sourceLayer="planner",
        overridable=False,
    )
    return _minimal_plan(
        plannerVersion="2",
        aggregateStatus=PlanAggregateStatus.INTEGRITY_BLOCKED,
        blockers=(blocker,),
        items=(),
        steps=(),
        summary=WorkflowSummary(totalItems=0, blockerCount=1),
    )


def test_analyze_file_attaches_workflow_plan() -> None:
    report = analyze_file(MEMORIES_JSON)
    assert report.workflowPlan is not None
    assert report.workflowPlan.plannerVersion == "2"


def test_plan_workflows_spy_receives_simulation_without_existing_plan() -> None:
    captured: dict[str, object] = {}
    sentinel = _minimal_plan(plannerVersion="2", items=(), steps=())

    def spy(report, *, options=None):
        captured["report"] = report
        captured["dump"] = report.model_dump(mode="json")
        return sentinel

    with patch("memd.pipeline.plan_workflows", side_effect=spy):
        result = analyze_file(MEMORIES_JSON)

    report = captured["report"]
    assert report.simulationReport is not None
    assert report.workflowPlan is None
    assert result.workflowPlan is sentinel
    assert captured["dump"] == report.model_dump(mode="json")


def test_plan_workflows_spy_called_exactly_once() -> None:
    sentinel = _minimal_plan(plannerVersion="2")
    with patch("memd.pipeline.plan_workflows", return_value=sentinel) as spy:
        analyze_file(MEMORIES_JSON)
    assert spy.call_count == 1


def test_plan_workflows_input_immutable_during_call() -> None:
    snapshots: list[dict[str, object]] = []

    def spy(report, *, options=None):
        snapshots.append(report.model_dump(mode="json"))
        return _minimal_plan(plannerVersion="2", items=(), steps=())

    with patch("memd.pipeline.plan_workflows", side_effect=spy):
        analyze_file(MEMORIES_JSON)

    assert len(snapshots) == 1


def test_apply_workflow_decisions_not_called_from_pipeline() -> None:
    with patch("memd.workflows.apply_workflow_decisions") as spy:
        analyze_file(MEMORIES_JSON)
    spy.assert_not_called()


def test_planner_exception_propagates_from_pipeline() -> None:
    with patch("memd.pipeline.plan_workflows", side_effect=RuntimeError("planner failed")):
        with pytest.raises(RuntimeError, match="planner failed"):
            analyze_file(MEMORIES_JSON)


def test_integrity_blocked_plan_attached_without_exception() -> None:
    blocked = _integrity_blocked_plan()
    with patch("memd.pipeline.plan_workflows", return_value=blocked):
        report = analyze_file(MEMORIES_JSON)
    assert report.workflowPlan is blocked
    assert report.workflowPlan.aggregateStatus == PlanAggregateStatus.INTEGRITY_BLOCKED


def test_initial_planner_and_operator_statuses() -> None:
    report = analyze_file(MEMORIES_JSON)
    plan = report.workflowPlan
    assert plan is not None
    assert plan.plannerStatus == WorkflowPlannerStatus.INITIAL
    assert plan.planningOptions.includeKeep is False
    assert all(item.operatorItemStatus.value == "none" for item in plan.items)
    assert plan.decisionsFingerprint == ""


def test_repeated_analyze_file_identical_workflow_plan() -> None:
    first = analyze_file(MEMORIES_JSON)
    second = analyze_file(MEMORIES_JSON)
    assert first.workflowPlan is not None
    assert second.workflowPlan is not None
    assert first.workflowPlan.model_dump(mode="json") == second.workflowPlan.model_dump(
        mode="json"
    )


def test_analyze_file_does_not_modify_source_file() -> None:
    before = MEMORIES_JSON.read_bytes()
    analyze_file(MEMORIES_JSON)
    assert MEMORIES_JSON.read_bytes() == before


def test_workflow_plan_to_dict_equals_model_dump() -> None:
    report = analyze_file(MEMORIES_JSON)
    assert report.workflowPlan is not None
    plan = report.workflowPlan
    assert workflow_plan_to_dict(plan) == plan.model_dump(mode="json", exclude_none=False)


def test_json_includes_workflow_plan_when_present() -> None:
    payload = json.loads(render_json(analyze_file(MEMORIES_JSON)))
    assert "workflowPlan" in payload
    assert payload["workflowPlan"]["plannerVersion"] == "2"


def test_json_omits_workflow_plan_when_none() -> None:
    payload = report_to_dict(_minimal_report(workflow_plan=None))
    assert "workflowPlan" not in payload


def test_json_workflow_plan_includes_contract_fields() -> None:
    plan = analyze_file(MEMORIES_JSON).workflowPlan
    assert plan is not None
    payload = workflow_plan_to_dict(plan)
    expected_keys = {
        "workflowPlanId",
        "sourceAnalysisRef",
        "simulationId",
        "policyProfile",
        "plannerStatus",
        "aggregateStatus",
        "items",
        "steps",
        "summary",
        "reviewQueues",
        "blockers",
        "evidence",
        "planningMode",
        "planningOptions",
        "plannerVersion",
        "metricsDisclaimer",
        "decisionsFingerprint",
    }
    assert expected_keys <= set(payload.keys())
    assert "plannerSignalInputs" not in payload


def _workflow_step(
    sequence: int,
    step_type: WorkflowStepType,
    operation: WorkflowStepOperation,
) -> WorkflowStep:
    return WorkflowStep(
        stepId=f"step-{sequence}",
        sequence=sequence,
        stepType=step_type,
        plannerStepStatus=PlannerItemStatus.PROPOSED,
        operation=operation,
    )


def test_json_structured_operations_preserved() -> None:
    steps = (
        _workflow_step(
            1,
            WorkflowStepType.MERGE,
            WorkflowStepOperation(
                stepType=WorkflowStepType.MERGE,
                keeperId="m1",
                removableIds=("m2", "m3"),
                recommendationIds=("rec:merge",),
            ),
        ),
        _workflow_step(
            2,
            WorkflowStepType.ARCHIVE,
            WorkflowStepOperation(
                stepType=WorkflowStepType.ARCHIVE,
                archiveTargetIds=("m4",),
                recommendationIds=("rec:archive",),
            ),
        ),
        _workflow_step(
            3,
            WorkflowStepType.REVIEW,
            WorkflowStepOperation(
                stepType=WorkflowStepType.REVIEW,
                reviewTargetIds=("m5",),
                recommendationIds=("rec:review",),
            ),
        ),
        _workflow_step(
            4,
            WorkflowStepType.RETAIN,
            WorkflowStepOperation(
                stepType=WorkflowStepType.RETAIN,
                recommendationIds=("rec:retain",),
            ),
        ),
    )
    plan = _minimal_plan(steps=steps)
    payload = workflow_plan_to_dict(plan)

    assert payload == plan.model_dump(mode="json", exclude_none=False)
    operations = {step["stepType"]: step["operation"] for step in payload["steps"]}

    merge = operations["merge"]
    assert merge["stepType"] == "merge"
    assert merge["keeperId"] == "m1"
    assert merge["removableIds"] == ["m2", "m3"]
    assert merge["recommendationIds"] == ["rec:merge"]
    assert merge["archiveTargetIds"] == []
    assert merge["reviewTargetIds"] == []

    archive = operations["archive"]
    assert archive["stepType"] == "archive"
    assert archive["archiveTargetIds"] == ["m4"]
    assert archive["keeperId"] == ""
    assert archive["removableIds"] == []
    assert archive["reviewTargetIds"] == []

    review = operations["review"]
    assert review["stepType"] == "review"
    assert review["reviewTargetIds"] == ["m5"]
    assert review["keeperId"] == ""
    assert review["removableIds"] == []
    assert review["archiveTargetIds"] == []

    retain = operations["retain"]
    assert retain["stepType"] == "retain"
    assert retain["keeperId"] == ""
    assert retain["removableIds"] == []
    assert retain["archiveTargetIds"] == []
    assert retain["reviewTargetIds"] == []


def test_json_rendering_deterministic() -> None:
    report = analyze_file(MEMORIES_JSON)
    first = render_json(report)
    second = render_json(report)
    assert first == second


def test_markdown_heading_order_simulation_before_workflow_before_compression() -> None:
    markdown = render_markdown(analyze_file(MEMORIES_JSON))
    sim = markdown.index("## Simulation Summary")
    workflow = markdown.index("## Workflow Plan")
    compression = markdown.index("## Compression Explanation")
    assert sim < workflow < compression


def test_markdown_simulation_is_h2_not_h1() -> None:
    markdown = render_markdown(analyze_file(MEMORIES_JSON))
    assert "## Simulation Summary" in markdown
    assert "\n# Simulation Summary\n" not in markdown


def test_markdown_workflow_planning_disclaimer() -> None:
    markdown = render_markdown(analyze_file(MEMORIES_JSON))
    assert "Planning only — no memory changes performed." in markdown
    assert "Operator decisions are not applied" in markdown


def test_markdown_workflow_summary_fields() -> None:
    markdown = render_markdown(analyze_file(MEMORIES_JSON))
    assert "- Planner version: 2" in markdown
    assert "- Planning mode:" in markdown
    assert "- Aggregate status:" in markdown


def test_markdown_integrity_blocked_prominent() -> None:
    report = analyze_file(MEMORIES_JSON).model_copy(
        update={"workflowPlan": _integrity_blocked_plan()}
    )
    markdown = render_markdown(report)
    assert "Workflow integrity blocked" in markdown
    assert "INPUT_INTEGRITY" in markdown


@pytest.mark.parametrize("count", [19, 20, 21])
def test_markdown_item_truncation_boundaries(count: int) -> None:
    items = tuple(_minimal_item(index) for index in range(1, count + 1))
    plan = _minimal_plan(
        items=items,
        summary=WorkflowSummary(totalItems=count),
    )
    markdown = render_markdown(_plan_report(plan))

    visible_count = min(count, 20)
    for index in range(1, visible_count + 1):
        assert f"#### `rec:{index}`" in markdown
    if count <= 20:
        assert "additional entries omitted" not in markdown
    else:
        assert "#### `rec:21`" not in markdown
        assert (
            "... 1 additional entries omitted; use JSON output for the complete plan."
            in markdown
        )
    assert len(workflow_plan_to_dict(plan)["items"]) == count


@pytest.mark.parametrize("count", [19, 20, 21])
def test_markdown_step_truncation_boundaries(count: int) -> None:
    steps = tuple(
        _workflow_step(
            index,
            WorkflowStepType.REVIEW,
            WorkflowStepOperation(
                stepType=WorkflowStepType.REVIEW,
                reviewTargetIds=(f"m{index}",),
            ),
        )
        for index in range(1, count + 1)
    )
    plan = _minimal_plan(steps=steps)
    markdown = render_markdown(_plan_report(plan))

    visible_count = min(count, 20)
    for index in range(1, visible_count + 1):
        assert f"#### Step {index}: review" in markdown
    if count <= 20:
        assert "additional entries omitted" not in markdown
    else:
        assert "#### Step 21: review" not in markdown
        assert (
            "... 1 additional entries omitted; use JSON output for the complete plan."
            in markdown
        )
    assert len(workflow_plan_to_dict(plan)["steps"]) == count


def _overridable_blocker(index: int) -> WorkflowBlocker:
    return WorkflowBlocker(
        blockerId=f"{index:064x}",
        code=WorkflowBlockerCode.MISSING_KEEPER,
        message=f"overridable blocker {index}",
        sourceLayer="simulation",
        overridable=True,
    )


def _non_overridable_blocker(index: int) -> WorkflowBlocker:
    return WorkflowBlocker(
        blockerId=f"{index:064x}",
        code=WorkflowBlockerCode.MISSING_KEEPER,
        message=f"non-overridable blocker {index}",
        sourceLayer="simulation",
        overridable=False,
    )


@pytest.mark.parametrize("count", [19, 20, 21])
def test_markdown_overridable_blocker_truncation_boundaries(count: int) -> None:
    blockers = tuple(_overridable_blocker(index) for index in range(1, count + 1))
    plan = _minimal_plan(
        blockers=blockers,
        summary=WorkflowSummary(totalItems=0, blockerCount=count),
    )
    markdown = render_markdown(_plan_report(plan))

    visible_count = min(count, 20)
    for index in range(1, visible_count + 1):
        assert f"overridable blocker {index}" in markdown
    if count <= 20:
        assert "additional entries omitted" not in markdown
    else:
        assert "overridable blocker 21" not in markdown
        assert (
            "... 1 additional entries omitted; use JSON output for the complete plan."
            in markdown
        )
    assert len(workflow_plan_to_dict(plan)["blockers"]) == count


def test_markdown_non_overridable_blockers_never_truncated() -> None:
    blockers = tuple(_non_overridable_blocker(index) for index in range(1, 22))
    plan = _minimal_plan(
        blockers=blockers,
        summary=WorkflowSummary(totalItems=0, blockerCount=len(blockers)),
    )
    markdown = render_markdown(_plan_report(plan))

    for index in range(1, 22):
        assert f"non-overridable blocker {index}" in markdown
    assert "additional entries omitted" not in markdown


@pytest.mark.parametrize("count", [19, 20, 21])
def test_markdown_evidence_ref_truncation_boundaries(count: int) -> None:
    refs = tuple(f"evidence:test:{index:02d}" for index in range(1, count + 1))
    plan = _minimal_plan(evidence=WorkflowEvidence(validationRefs=refs))
    markdown = render_markdown(_plan_report(plan))

    visible_count = min(count, 20)
    for index in range(1, visible_count + 1):
        assert f"`evidence:test:{index:02d}`" in markdown
    if count <= 20:
        assert "additional entries omitted" not in markdown
    else:
        assert "`evidence:test:21`" not in markdown
        assert (
            "... 1 additional entries omitted; use JSON output for the complete plan."
            in markdown
        )
    assert len(workflow_plan_to_dict(plan)["evidence"]["validationRefs"]) == count


def test_markdown_integrity_refs_never_truncated() -> None:
    refs = tuple(f"integrity:cause:{index:02d}" for index in range(1, 22))
    blocker = WorkflowBlocker(
        blockerId="f" * 64,
        code=WorkflowBlockerCode.INPUT_INTEGRITY,
        message="integrity",
        sourceLayer="planner",
        overridable=False,
    )
    plan = _minimal_plan(
        aggregateStatus=PlanAggregateStatus.INTEGRITY_BLOCKED,
        blockers=(blocker,),
        evidence=WorkflowEvidence(validationRefs=refs),
        summary=WorkflowSummary(totalItems=0, blockerCount=1),
    )
    markdown = render_markdown(_plan_report(plan))

    for index in range(1, 22):
        assert f"`integrity:cause:{index:02d}`" in markdown
    assert "additional entries omitted" not in markdown


def test_markdown_no_execution_language() -> None:
    markdown = render_markdown(analyze_file(MEMORIES_JSON))
    lowered = markdown.lower()
    assert "executed" not in lowered
    assert "will merge" not in lowered


def _workflow_terminal_output(report) -> str:
    console = Console(record=True, width=120)
    render_workflow_terminal(report, console)
    return console.export_text()


def test_terminal_workflow_summary_and_notice() -> None:
    output = _workflow_terminal_output(analyze_file(MEMORIES_JSON))
    assert "Workflow Plan:" in output
    assert "Planner state: initial" in output
    assert "Planning only — operator decisions have not been applied." in output


def test_terminal_no_ready_for_execution_count() -> None:
    output = _workflow_terminal_output(analyze_file(MEMORIES_JSON)).lower()
    assert "ready_for_execution" not in output
    assert "ready for execution" not in output


def test_terminal_integrity_blocked_first() -> None:
    report = analyze_file(MEMORIES_JSON).model_copy(
        update={"workflowPlan": _integrity_blocked_plan()}
    )
    output = _workflow_terminal_output(report)
    assert "Workflow integrity blocked" in output
    assert "INPUT_INTEGRITY" in output


def test_terminal_no_item_dump() -> None:
    report = analyze_file(MEMORIES_JSON)
    output = _workflow_terminal_output(report)
    assert "recommendationId" not in output
    assert "workflowItemId" not in output
    assert output.count("\n") < 15


def test_terminal_no_interactive_controls() -> None:
    output = _workflow_terminal_output(analyze_file(MEMORIES_JSON)).lower()
    assert "approve item" not in output
    assert "prompt" not in output


def test_report_to_dict_does_not_mutate_report_or_plan() -> None:
    report = analyze_file(MEMORIES_JSON)
    assert report.workflowPlan is not None
    before_report = report.model_dump(mode="json")
    before_plan = report.workflowPlan.model_dump(mode="json")
    report_to_dict(report)
    assert report.model_dump(mode="json") == before_report
    assert report.workflowPlan.model_dump(mode="json") == before_plan


def test_render_markdown_does_not_mutate_report_or_plan() -> None:
    report = analyze_file(MEMORIES_JSON)
    assert report.workflowPlan is not None
    before_report = report.model_dump(mode="json")
    before_plan = report.workflowPlan.model_dump(mode="json")
    render_markdown(report)
    assert report.model_dump(mode="json") == before_report
    assert report.workflowPlan.model_dump(mode="json") == before_plan


def test_render_terminal_does_not_mutate_report_or_plan() -> None:
    report = analyze_file(MEMORIES_JSON)
    assert report.workflowPlan is not None
    before_report = report.model_dump(mode="json")
    before_plan = report.workflowPlan.model_dump(mode="json")
    console = Console(record=True, width=120)
    render_terminal(report, console=console)
    assert report.model_dump(mode="json") == before_report
    assert report.workflowPlan.model_dump(mode="json") == before_plan


def test_benchmark_json_parse_smoke() -> None:
    payload = json.loads(render_json(analyze_file(MEMORIES_JSON)))
    assert isinstance(payload, dict)
    assert "metrics" in payload
    assert "workflowPlan" in payload


def test_integrity_blocked_renders_in_json_markdown_terminal() -> None:
    report = analyze_file(MEMORIES_JSON).model_copy(
        update={"workflowPlan": _integrity_blocked_plan()}
    )
    payload = json.loads(render_json(report))
    assert payload["workflowPlan"]["aggregateStatus"] == "integrity_blocked"
    markdown = render_markdown(report)
    assert "Workflow integrity blocked" in markdown
    console = Console(record=True, width=120)
    render_terminal(report, console=console)
    assert "Workflow integrity blocked" in console.export_text()
