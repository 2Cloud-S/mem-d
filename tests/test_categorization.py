import pytest

from memd.categorization import categorize_record
from memd.contracts import MemoryCategory, MemoryRecord


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("User prefers dark mode", MemoryCategory.PREFERENCE),
        ("User works as a backend engineer", MemoryCategory.FACT),
        ("Follow up on the API review", MemoryCategory.TASK),
        ("Goal is to launch the agent memory analyzer", MemoryCategory.GOAL),
        ("Alice is the user's teammate", MemoryCategory.RELATIONSHIP),
        ("Meeting tomorrow at 10", MemoryCategory.TEMPORARY),
        ("A short note without known signals", MemoryCategory.UNKNOWN),
    ],
)
def test_categorize_record(content: str, expected: MemoryCategory) -> None:
    result = categorize_record(MemoryRecord(id="mem_1", content=content))

    assert result.category == expected
    assert 0.0 <= result.confidence <= 1.0
    assert result.reason


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("User runs Kubernetes in production.", MemoryCategory.FACT),
        ("No semicolons in TS/JS — that's the user's style.", MemoryCategory.PREFERENCE),
        (
            "The Stripe integration fact is the context for the idempotency keys task.",
            MemoryCategory.RELATIONSHIP,
        ),
        ("Fact: 14 microservices in production.", MemoryCategory.FACT),
    ],
)
def test_categorize_dataset_patterns(content: str, expected: MemoryCategory) -> None:
    result = categorize_record(MemoryRecord(id="mem_1", content=content))

    assert result.category == expected
    assert result.matchedSignals
