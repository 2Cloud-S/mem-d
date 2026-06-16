from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from memd.contracts import CategorizedMemory, MemoryCategory, MemoryRecord
from memd.memory_evolution import audit_memory_evolution
from memd.memory_lifecycle import infer_memory_lifecycle

FIXTURES = Path(__file__).parent / "fixtures"
GOLD_PATH = FIXTURES / "lifecycle_gold.json"
LIFECYCLE_STATES = {
    "Active",
    "Historical",
    "Superseded",
    "Deprecated",
    "Temporary",
    "Completed",
}


def load_gold_cases() -> list[dict[str, object]]:
    payload = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError("lifecycle_gold.json must contain a list in `cases`")
    return [case for case in cases if isinstance(case, dict)]


def to_records_and_categories(case: dict[str, object]) -> tuple[list[MemoryRecord], list[CategorizedMemory]]:
    raw_memories = case.get("memories", [])
    if not isinstance(raw_memories, list):
        raise ValueError(f"Case {case.get('id')} has invalid `memories`")

    records: list[MemoryRecord] = []
    categories: list[CategorizedMemory] = []
    for item in raw_memories:
        if not isinstance(item, dict):
            continue
        memory_id = str(item["id"])
        category_name = str(item.get("category", MemoryCategory.UNKNOWN.value))

        records.append(
            MemoryRecord(
                id=memory_id,
                content=str(item["content"]),
                timestamp=str(item["timestamp"]) if item.get("timestamp") else None,
            )
        )
        categories.append(
            CategorizedMemory(
                memoryId=memory_id,
                category=MemoryCategory(category_name),
                confidence=0.9 if category_name != MemoryCategory.UNKNOWN.value else 0.2,
            )
        )
    return records, categories


def lifecycle_assignment_map(lifecycle: dict[str, object]) -> dict[str, str]:
    assignments = lifecycle.get("memoryLifecycleAssignments", [])
    if not isinstance(assignments, list):
        return {}
    mapped: dict[str, str] = {}
    for assignment in assignments:
        if not isinstance(assignment, dict):
            continue
        memory_id = assignment.get("memoryId")
        state = assignment.get("lifecycleState")
        if isinstance(memory_id, str) and isinstance(state, str):
            mapped[memory_id] = state
    return mapped


def safe_div(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def test_lifecycle_gold_fixture_has_expected_shape() -> None:
    cases = load_gold_cases()
    assert len(cases) >= 10

    seen_states: set[str] = set()
    for case in cases:
        expected = case.get("expectedLifecycle")
        assert isinstance(expected, dict)
        for state in expected.values():
            assert state in LIFECYCLE_STATES
            seen_states.add(str(state))
    assert seen_states == LIFECYCLE_STATES


def test_lifecycle_overall_and_per_state_accuracy_against_gold_fixture() -> None:
    cases = load_gold_cases()

    total = 0
    correct = 0
    per_state_total: dict[str, int] = defaultdict(int)
    per_state_correct: dict[str, int] = defaultdict(int)

    for case in cases:
        expected = case.get("expectedLifecycle", {})
        if not isinstance(expected, dict):
            continue
        records, categories = to_records_and_categories(case)
        evolution = audit_memory_evolution(records, categories)
        lifecycle = infer_memory_lifecycle(evolution)
        predicted = lifecycle_assignment_map(lifecycle)

        for memory_id, expected_state in expected.items():
            if not isinstance(memory_id, str) or not isinstance(expected_state, str):
                continue
            total += 1
            per_state_total[expected_state] += 1

            if predicted.get(memory_id) == expected_state:
                correct += 1
                per_state_correct[expected_state] += 1

    overall_accuracy = safe_div(correct, total)
    per_state_accuracy = {
        state: safe_div(per_state_correct[state], per_state_total[state])
        for state in sorted(LIFECYCLE_STATES)
    }

    assert 0.0 <= overall_accuracy <= 1.0
    assert set(per_state_accuracy.keys()) == LIFECYCLE_STATES
    for value in per_state_accuracy.values():
        assert 0.0 <= value <= 1.0

    # Ensure the evaluation is informative for current heuristic behavior.
    assert overall_accuracy > 0.0
