from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import memd.benchmarks.workflow_evaluation as workflow_eval
from memd.benchmarks.workflow_evaluation import (
    CHECKPOINT_TYPE_TO_METRIC,
    GOLD_PATH,
    QUALITY_METRICS,
    SAFETY_PROPERTIES,
    _evaluate_safety,
    _load_fixture,
    _no_effects_guard,
    _run_case,
    evaluate_workflows,
    evaluation_result_to_dict,
    render_markdown,
)


def _write_fixture(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "workflow_gold.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _fixture_payload() -> dict:
    return json.loads(GOLD_PATH.read_text(encoding="utf-8"))


def test_workflow_evaluation_gate_passes() -> None:
    result = evaluate_workflows()
    assert result.evaluationStatus == "scored"
    assert result.gatePassed is True
    assert result.failures == ()
    assert result.checkpointCount > 0
    assert result.qualityMetrics["overallWorkflowAccuracy"].total == result.checkpointCount


def test_all_quality_metrics_are_present_and_perfect() -> None:
    result = evaluate_workflows()
    assert tuple(result.qualityMetrics) == QUALITY_METRICS
    for metric in result.qualityMetrics.values():
        assert metric.total > 0
        assert metric.accuracy == 1.0
        assert metric.passed == metric.total


def test_safety_gates_are_present_non_vacuous_and_passing() -> None:
    result = evaluate_workflows()
    assert result.safetyResults.passed is True
    assert set(result.safetyResults.properties) == set(SAFETY_PROPERTIES)
    for prop in result.safetyResults.properties.values():
        assert prop.passed is True
        assert prop.checksTotal >= 1
        assert prop.checksPassed == prop.checksTotal


def test_diagnostics_are_non_gating() -> None:
    result = evaluate_workflows()
    diagnostics = result.diagnosticMetrics
    assert diagnostics["diagnosticOnly"] is True
    assert "workflowStatusDistribution" in diagnostics
    assert "reviewQueueDistribution" in diagnostics
    assert "blockerDistribution" in diagnostics


def test_fixture_invalid_state_is_distinct(tmp_path) -> None:
    invalid = tmp_path / "workflow_gold.json"
    invalid.write_text(
        json.dumps(
            {
                "fixtureVersion": "0.8.0",
                "plannerVersion": "2",
                "groundTruthAuthority": "tests/fixtures/workflow_gold.json",
                "cases": [],
            }
        ),
        encoding="utf-8",
    )
    result = evaluate_workflows(invalid)
    assert result.evaluationStatus == "fixture_invalid"
    assert result.gatePassed is False
    assert result.failures
    for metric in result.qualityMetrics.values():
        assert metric.accuracy is None
        assert metric.passed == 0
        assert metric.total == 0


def test_duplicate_checkpoint_rejection_is_fixture_invalid(tmp_path) -> None:
    payload = _fixture_payload()
    payload["cases"][0]["expected"]["aggregateStatuses"].append({"status": "empty"})
    result = evaluate_workflows(_write_fixture(tmp_path, payload))
    assert result.evaluationStatus == "fixture_invalid"
    assert result.checkpointCount == 0
    assert "duplicate checkpoint tuple" in result.failures[0].message


def test_checkpoint_rendered_id_collision_is_fixture_invalid(tmp_path) -> None:
    payload = _fixture_payload()
    payload["cases"].extend(
        [
            {
                "caseId": "rendered::collision",
                "builder": "empty_plan",
                "expected": {"aggregateStatuses": [{"phase": "a", "status": "empty"}]},
            },
            {
                "caseId": "rendered",
                "builder": "empty_plan",
                "expected": {"aggregateStatuses": [{"phase": "collision::a", "status": "empty"}]},
            },
        ]
    )
    result = evaluate_workflows(_write_fixture(tmp_path, payload))
    assert result.evaluationStatus == "fixture_invalid"
    assert result.checkpointCount == 0
    assert "duplicate rendered checkpoint ID" in result.failures[0].message


def test_review_subtype_metadata_only_does_not_satisfy_non_vacuity(tmp_path) -> None:
    payload = _fixture_payload()
    payload["reviewSubtypeDispositions"] = {"reservedNotEmittedByPlannerVersion": []}
    policy_case = next(case for case in payload["cases"] if case["caseId"] == "policy_blocked")
    policy_route = policy_case["expected"]["reviewRoutes"][0]
    policy_route["coverageSubtypes"] = ["policy_blocked"]
    result = evaluate_workflows(_write_fixture(tmp_path, payload))
    assert result.evaluationStatus == "fixture_invalid"
    assert "review subtype coverage missing" in result.failures[0].message
    assert "policy_blocked" in result.failures[0].message


def test_missing_scored_review_subtype_is_fixture_invalid(tmp_path) -> None:
    payload = _fixture_payload()
    payload["cases"] = [
        case
        for case in payload["cases"]
        if case["caseId"] != "review_subtype_matrix_lifecycle_plain"
    ]
    result = evaluate_workflows(_write_fixture(tmp_path, payload))
    assert result.evaluationStatus == "fixture_invalid"
    assert "review subtype coverage missing" in result.failures[0].message
    assert "lifecycle" in result.failures[0].message


def test_checkpoint_primary_metric_mapping_complete() -> None:
    assert CHECKPOINT_TYPE_TO_METRIC == {
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


def test_h1_h7_boundary_cases_are_present() -> None:
    result = evaluate_workflows()
    case_ids = {case.caseId for case in result.cases}
    for gate in ("h1", "h2", "h3", "h4", "h5", "h6", "h7"):
        assert any(case_id.startswith(gate) for case_id in case_ids)
    assert "ready_for_execution_positive" in case_ids or "safe_merge" in case_ids


def test_h_gate_failure_message_names_gate(tmp_path) -> None:
    payload = _fixture_payload()
    for case in payload["cases"]:
        if case["caseId"] == "h2_unapproved_structural_negative":
            case["expected"]["aggregateStatuses"][0]["status"] = "ready_for_execution"
            break
    result = evaluate_workflows(_write_fixture(tmp_path, payload))
    assert result.evaluationStatus == "scored_failure"
    assert any("H2 readiness boundary mismatch" in failure.message for failure in result.failures)


def test_decision_application_cases_are_present() -> None:
    result = evaluate_workflows()
    case_ids = {case.caseId for case in result.cases}
    assert "invalid_decision_atomicity" in case_ids
    assert "multi_call_decision_fingerprint" in case_ids
    assert "orphan_merge_missing_keeper" in case_ids
    assert any(case.finalAggregateStatus == "ready_for_execution" for case in result.cases)
    assert any(case.finalAggregateStatus == "rejected" for case in result.cases)
    assert any(case.finalAggregateStatus == "deferred" for case in result.cases)
    orphan = next(case for case in result.cases if case.caseId == "orphan_merge_missing_keeper")
    assert orphan.passed is True


def test_result_serialization_and_markdown_are_deterministic() -> None:
    first = evaluate_workflows()
    second = evaluate_workflows()
    assert evaluation_result_to_dict(first) == evaluation_result_to_dict(second)
    assert render_markdown(first) == render_markdown(second)
    payload = evaluation_result_to_dict(first)
    assert payload["groundTruthAuthority"] == "tests/fixtures/workflow_gold.json"
    assert payload["diagnosticMetrics"]["diagnosticOnly"] is True
    assert "planningOnlyDisclaimer" in payload


def test_runner_writes_outputs(tmp_path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_workflow_evaluation.py",
            "--output-dir",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Workflow evaluation complete" in completed.stdout
    assert (tmp_path / "workflow_evaluation.json").exists()
    assert (tmp_path / "workflow_evaluation.md").exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "workflow_evaluation.json",
        "workflow_evaluation.md",
    ]
    payload = json.loads((tmp_path / "workflow_evaluation.json").read_text(encoding="utf-8"))
    assert payload["gatePassed"] is True


def test_source_report_mutation_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = workflow_eval.plan_workflows

    def mutating_plan(report, *, options=None):
        report.validation["mutationSentinel"] = "changed"
        return original(report, options=options)

    monkeypatch.setattr(workflow_eval, "plan_workflows", mutating_plan)
    payload = _load_fixture(GOLD_PATH)
    runtime = _run_case(payload["cases"][0])
    safety = _evaluate_safety((runtime,))
    prop = safety.properties["source_report_immutability"]
    assert prop.passed is False
    assert "mutation detected" in prop.failures[0].message


def test_decision_input_plan_mutation_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = workflow_eval.apply_workflow_decisions

    def mutating_decision(plan, decisions):
        plan.summary.itemsByOperatorStatus.clear()
        return original(plan, decisions)

    monkeypatch.setattr(workflow_eval, "apply_workflow_decisions", mutating_decision)
    payload = _load_fixture(GOLD_PATH)
    case = next(case for case in payload["cases"] if case["caseId"] == "safe_merge")
    runtime = _run_case(case)
    safety = _evaluate_safety((runtime,))
    prop = safety.properties["source_report_immutability"]
    assert prop.passed is False
    assert "mutation detected" in prop.failures[0].message


def test_no_effects_guard_blocks_ci_observable_effects(tmp_path) -> None:
    with pytest.raises(AssertionError, match="filesystem write attempted"):
        with _no_effects_guard():
            (tmp_path / "blocked.txt").write_text("blocked", encoding="utf-8")
    with pytest.raises(AssertionError, match="filesystem write attempted"):
        with _no_effects_guard():
            with open(tmp_path / "blocked.txt", "w", encoding="utf-8"):
                pass


def test_no_network_or_external_dependency_assumption() -> None:
    result = evaluate_workflows()
    assert result.groundTruthAuthority == "tests/fixtures/workflow_gold.json"
    assert result.diagnosticOnly is False
    payload = evaluation_result_to_dict(result)
    assert payload["groundTruthAuthority"] == "tests/fixtures/workflow_gold.json"
    assert payload["diagnosticMetrics"]["diagnosticOnly"] is True
