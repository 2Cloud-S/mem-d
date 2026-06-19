from __future__ import annotations

import json
from pathlib import Path

import pytest

from memd.benchmarks.simulation_evaluation import (
    DIAGNOSTIC_EXPECTED_FIELDS,
    GATING_EXPECTED_FIELDS,
    GOLD_PATH,
    PERCENT_TOLERANCE,
    RATE_TOLERANCE,
    RECOGNIZED_EXPECTED_FIELDS,
    build_report_from_case,
    evaluate_simulations,
    evaluation_result_to_dict,
    render_markdown,
)
from memd.simulation import simulate_recommendations


FIXTURES = Path(__file__).parent / "fixtures"
SIMULATION_GOLD_PATH = FIXTURES / "simulation_gold.json"


def test_simulation_gold_fixture_shape_and_fields_valid() -> None:
    payload = json.loads(SIMULATION_GOLD_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    cases = payload.get("cases")
    assert isinstance(cases, list)
    assert len(cases) >= 9

    case_ids: set[str] = set()
    for case in cases:
        assert isinstance(case, dict)
        case_id = case.get("id")
        assert isinstance(case_id, str)
        case_ids.add(case_id)
        assert isinstance(case.get("memories"), list)
        expected = case.get("expected")
        assert isinstance(expected, dict)
        for field_name in expected:
            assert field_name in RECOGNIZED_EXPECTED_FIELDS

    assert len(case_ids) == len(cases)


def test_simulation_gold_unique_case_ids() -> None:
    payload = json.loads(SIMULATION_GOLD_PATH.read_text(encoding="utf-8"))
    cases = payload["cases"]
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))


def test_simulation_evaluation_metric_formulas_hold() -> None:
    result = evaluate_simulations(SIMULATION_GOLD_PATH)

    assert result.total_checkpoints > 0
    assert result.overall_structural_accuracy == (
        result.passed_checkpoints / result.total_checkpoints
    )

    for stats in (
        result.merge,
        result.archive,
        result.review,
        result.warning,
        result.orphan,
        result.explainability,
        result.metric_consistency,
    ):
        if stats.total > 0:
            assert stats.accuracy == stats.passed / stats.total


def test_simulation_evaluation_default_path_works() -> None:
    result = evaluate_simulations()
    assert result.case_count >= 9
    assert result.fixture_path.name == "simulation_gold.json"
    assert result.fixture_path.exists()


def test_evaluate_simulations_overall_accuracy() -> None:
    result = evaluate_simulations(SIMULATION_GOLD_PATH)
    assert result.overall_structural_accuracy == 1.0
    assert result.passed_checkpoints == result.total_checkpoints
    assert not result.failures


def test_evaluate_simulations_orphan_accuracy() -> None:
    result = evaluate_simulations(SIMULATION_GOLD_PATH)
    assert result.orphan_merge_accuracy == 1.0
    assert result.orphan.passed == result.orphan.total
    assert result.orphan.total > 0


def test_evaluate_simulations_metric_consistency() -> None:
    result = evaluate_simulations(SIMULATION_GOLD_PATH)
    assert result.metric_consistency_accuracy == 1.0


def test_evaluate_simulations_is_deterministic() -> None:
    first = evaluation_result_to_dict(evaluate_simulations(SIMULATION_GOLD_PATH))
    second = evaluation_result_to_dict(evaluate_simulations(SIMULATION_GOLD_PATH))
    first.pop("metadata")
    second.pop("metadata")
    assert first == second


def test_evaluate_simulations_safety_gate() -> None:
    result = evaluate_simulations(SIMULATION_GOLD_PATH)
    assert result.safety.passed
    assert all(result.safety.properties.values())


def test_diagnostic_metrics_do_not_affect_gate() -> None:
    result = evaluate_simulations(SIMULATION_GOLD_PATH)
    assert result.diagnostic["diagnosticOnly"] is True
    assert result.gate_passed
    diagnostic = result.diagnostic
    assert "recommendationUtilizationDistribution" in diagnostic
    assert "warningDistribution" in diagnostic
    assert "projectedReductionDistribution" in diagnostic


def test_float_tolerance_constants_match_plan() -> None:
    assert PERCENT_TOLERANCE == 0.01
    assert RATE_TOLERANCE == 0.0001


def test_gating_vs_diagnostic_expected_fields() -> None:
    payload = json.loads(SIMULATION_GOLD_PATH.read_text(encoding="utf-8"))
    for case in payload["cases"]:
        expected = case.get("expected", {})
        for field_name in expected:
            if field_name in DIAGNOSTIC_EXPECTED_FIELDS:
                assert field_name not in GATING_EXPECTED_FIELDS


def test_evaluate_simulations_reports_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    from memd.benchmarks import simulation_evaluation as module

    original = module._evaluate_expected_fields

    def _broken(*args, **kwargs):
        acc = args[3]
        acc.failures.append(
            module.SimulationEvaluationFailure(
                case_id="synthetic",
                checkpoint="memoryCountAfter",
                expected=1,
                actual=2,
                category="overall",
            )
        )
        acc.overall.total += 1
        return 0, 1

    monkeypatch.setattr(module, "_evaluate_expected_fields", _broken)
    result = evaluate_simulations(SIMULATION_GOLD_PATH)
    assert result.overall_structural_accuracy < 1.0
    assert any(failure.case_id == "synthetic" for failure in result.failures)

    monkeypatch.setattr(module, "_evaluate_expected_fields", original)


def test_regression_guard_expectations() -> None:
    result = evaluate_simulations(SIMULATION_GOLD_PATH)
    guards = result.regression_guards
    assert guards["diagnosticOnly"] is True
    assert guards["longmemeval"]["passed"] is None
    assert guards["perma"]["passed"] is None


def test_benchmark_artifact_generation(tmp_path: Path) -> None:
    result = evaluate_simulations(SIMULATION_GOLD_PATH)
    payload = evaluation_result_to_dict(result)
    markdown = render_markdown(result)

    json_path = tmp_path / "simulation_evaluation.json"
    md_path = tmp_path / "simulation_evaluation.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")

    assert json_path.exists()
    assert md_path.exists()
    assert payload["benchmark"] == "simulation_evaluation"
    assert "overallStructuralAccuracy" in payload
    assert "Simulation Evaluation Benchmark" in markdown


def test_per_category_accuracy_calculations() -> None:
    result = evaluate_simulations(SIMULATION_GOLD_PATH)
    assert result.merge_projection_accuracy == 1.0
    assert result.archive_projection_accuracy == 1.0
    assert result.review_preservation_accuracy == 1.0
    assert result.warning_accuracy == 1.0
    assert result.explainability_accuracy == 1.0


def test_build_report_from_case_runs_simulation() -> None:
    payload = json.loads(SIMULATION_GOLD_PATH.read_text(encoding="utf-8"))
    case = next(item for item in payload["cases"] if item["id"] == "sim_merge_1")
    report = build_report_from_case(case)
    simulation = simulate_recommendations(report)
    assert simulation.metrics.memoryCountAfter == 1
