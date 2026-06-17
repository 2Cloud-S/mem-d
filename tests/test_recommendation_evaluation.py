from __future__ import annotations

import json
from pathlib import Path

from memd.benchmarks.recommendation_evaluation import (
    evaluate_recommendations,
    evaluation_result_to_dict,
)
from memd.contracts import RecommendationAction


FIXTURES = Path(__file__).parent / "fixtures"
GOLD_PATH = FIXTURES / "recommendation_gold.json"

PRIMARY_ACTIONS = {
    RecommendationAction.MERGE,
    RecommendationAction.ARCHIVE,
    RecommendationAction.REVIEW,
    RecommendationAction.KEEP,
}


def test_recommendation_gold_fixture_shape_and_actions_valid() -> None:
    payload = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    cases = payload.get("cases")
    assert isinstance(cases, list)
    assert len(cases) >= 10

    for case in cases:
        assert isinstance(case, dict)
        assert isinstance(case.get("id"), str)
        assert isinstance(case.get("memories"), list)
        assert isinstance(case.get("clusters"), list)
        assert isinstance(case.get("actions"), list)
        assert isinstance(case.get("validation"), dict)
        expected = case.get("expectedResolutions")
        assert isinstance(expected, dict)

        for memory_id, expectation in expected.items():
            assert isinstance(memory_id, str)
            assert isinstance(expectation, dict)
            assert "resolvedAction" in expectation
            resolved_action_raw = expectation.get("resolvedAction")
            action = RecommendationAction(str(resolved_action_raw))
            assert action in PRIMARY_ACTIONS

            if "role" in expectation:
                assert isinstance(expectation["role"], str)
            if "conflictDetected" in expectation:
                assert isinstance(expectation["conflictDetected"], bool)
            # Optional future field; not currently present in fixture.
            if "suppressedActions" in expectation:
                assert isinstance(expectation["suppressedActions"], list)


def test_recommendation_evaluation_metric_formulas_hold() -> None:
    result = evaluate_recommendations(GOLD_PATH)

    assert result.overall_total > 0
    assert result.overall_accuracy == result.overall_correct / result.overall_total

    for action in PRIMARY_ACTIONS:
        stats = result.per_action[action]
        assert stats.total >= 0
        if stats.total > 0:
            assert stats.accuracy == stats.correct / stats.total

    if result.conflict.total > 0:
        assert result.conflict.accuracy == result.conflict.passed / result.conflict.total


def test_recommendation_evaluation_default_path_works() -> None:
    result = evaluate_recommendations()
    assert result.case_count >= 10
    assert result.fixture_path.name == "recommendation_gold.json"
    assert result.fixture_path.exists()


def test_recommendation_evaluation_achieves_expected_accuracy() -> None:
    result = evaluate_recommendations(GOLD_PATH)
    assert result.overall_accuracy == 1.0

    for action in PRIMARY_ACTIONS:
        stats = result.per_action[action]
        assert stats.total > 0
        assert stats.correct == stats.total

    assert result.conflict.total > 0
    assert result.conflict.accuracy == 1.0


def test_recommendation_evaluation_is_deterministic() -> None:
    first = evaluation_result_to_dict(evaluate_recommendations(GOLD_PATH))
    second = evaluation_result_to_dict(evaluate_recommendations(GOLD_PATH))
    assert first == second


def test_conflict_resolution_accuracy_matches_gold_cases() -> None:
    """
    Compute conflict case pass rate directly from gold expectations, then compare.

    This ensures the conflict metric matches its intended definition.
    """
    from tests.test_recommendations import to_actions, to_clusters, to_memory_records, resolution_map

    payload = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    cases = payload["cases"]
    assert isinstance(cases, list)

    def is_conflict_case(case: dict) -> bool:
        case_id = str(case.get("id", ""))
        if case_id.startswith("conflict_"):
            return True
        expected = case.get("expectedResolutions", {})
        if isinstance(expected, dict):
            for expectation in expected.values():
                if isinstance(expectation, dict) and expectation.get("conflictDetected"):
                    return True
        return False

    total = 0
    passed = 0

    for case in cases:
        assert isinstance(case, dict)
        if not is_conflict_case(case):
            continue

        total += 1
        include_keep = bool(case.get("includeKeep", False))
        memories = to_memory_records(case)
        clusters = to_clusters(case)
        actions = to_actions(case)
        validation = dict(case.get("validation", {}))

        resolutions = resolution_map(
            memories,
            clusters,
            validation,
            actions,
            include_keep=include_keep,
        )

        expected = case.get("expectedResolutions", {})
        assert isinstance(expected, dict)

        case_passed = True
        for memory_id, expectation in expected.items():
            assert isinstance(expectation, dict)
            predicted = resolutions.get(str(memory_id))
            if predicted is None:
                case_passed = False
                continue

            expected_action = RecommendationAction(str(expectation.get("resolvedAction")))
            if predicted.resolvedAction != expected_action:
                case_passed = False

            if "role" in expectation:
                assert isinstance(expectation["role"], str)
                if predicted.role != expectation["role"]:
                    case_passed = False

            if "conflictDetected" in expectation:
                assert isinstance(expectation["conflictDetected"], bool)
                if predicted.conflictDetected != expectation["conflictDetected"]:
                    case_passed = False

            if "suppressedActions" in expectation:
                # Future: compare suppressed action sets exactly.
                expected_suppressed = expectation["suppressedActions"]
                assert isinstance(expected_suppressed, list)
                expected_set = {RecommendationAction(str(item)) for item in expected_suppressed}
                if set(predicted.suppressedActions) != expected_set:
                    case_passed = False

        if case_passed:
            passed += 1

    result = evaluate_recommendations(GOLD_PATH)
    assert total == result.conflict.total
    assert passed == result.conflict.passed
    assert result.conflict.accuracy == 1.0

