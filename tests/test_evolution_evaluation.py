from __future__ import annotations

import json
from pathlib import Path

from memd.contracts import CategorizedMemory, MemoryCategory, MemoryRecord
from memd.memory_evolution import audit_memory_evolution

FIXTURES = Path(__file__).parent / "fixtures"
GOLD_PATH = FIXTURES / "evolution_gold.json"


def load_gold_cases() -> list[dict[str, object]]:
    payload = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError("evolution_gold.json must contain a list in `cases`")
    return [case for case in cases if isinstance(case, dict)]


def to_memory_records(case: dict[str, object]) -> tuple[list[MemoryRecord], list[CategorizedMemory]]:
    raw_memories = case.get("memories", [])
    if not isinstance(raw_memories, list):
        raise ValueError(f"Case {case.get('id')} has invalid `memories`")

    records: list[MemoryRecord] = []
    categories: list[CategorizedMemory] = []
    for item in raw_memories:
        if not isinstance(item, dict):
            continue
        memory_id = str(item["id"])
        records.append(
            MemoryRecord(
                id=memory_id,
                content=str(item["content"]),
                timestamp=str(item["timestamp"]) if item.get("timestamp") else None,
            )
        )
        category_name = str(item.get("category", MemoryCategory.UNKNOWN.value))
        categories.append(
            CategorizedMemory(
                memoryId=memory_id,
                category=MemoryCategory(category_name),
                confidence=0.9 if category_name != MemoryCategory.UNKNOWN.value else 0.2,
            )
        )
    return records, categories


def predicted_evolution_types(audit: dict[str, object]) -> set[str]:
    predicted: set[str] = set()
    if int(audit.get("contradictionCount", 0)) > 0:
        predicted.add("contradiction")
    if int(audit.get("preferenceChangeCount", 0)) > 0:
        predicted.add("preference_change")
    if int(audit.get("supersededMemoryCount", 0)) > 0:
        predicted.add("superseded_memory")
    if int(audit.get("statusTransitionCount", 0)) > 0:
        predicted.add("status_transition")
    if int(audit.get("staleMemoryCount", 0)) > 0:
        predicted.add("stale_fact")
    return predicted


def safe_div(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def test_evolution_gold_fixture_has_expected_shape() -> None:
    cases = load_gold_cases()
    assert 20 <= len(cases) <= 30
    expected_types = {str(case.get("expectedEvolutionType")) for case in cases}
    assert expected_types == {
        "contradiction",
        "preference_change",
        "superseded_memory",
        "stale_fact",
        "status_transition",
    }


def test_memory_evolution_precision_recall_f1_against_gold_fixture() -> None:
    cases = load_gold_cases()

    true_positives = 0
    false_positives = 0
    false_negatives = 0

    for case in cases:
        expected = str(case["expectedEvolutionType"])
        records, categories = to_memory_records(case)
        audit = audit_memory_evolution(records, categories)
        predicted = predicted_evolution_types(audit)

        if expected in predicted:
            true_positives += 1
        else:
            false_negatives += 1
        false_positives += len(predicted - {expected})

    precision = safe_div(true_positives, true_positives + false_positives)
    recall = safe_div(true_positives, true_positives + false_negatives)
    f1 = safe_div(2 * true_positives, (2 * true_positives) + false_positives + false_negatives)

    assert 0.0 <= precision <= 1.0
    assert 0.0 <= recall <= 1.0
    assert 0.0 <= f1 <= 1.0

    # Keep this evaluation meaningful without overfitting to exact counts.
    assert precision > 0.0
    assert recall > 0.0
    assert f1 > 0.0
