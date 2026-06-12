from memd.contracts import CategorizedMemory, MemoryCategory, MemoryRecord
from memd.inspection import build_validation_summary
from memd.memory_evolution import audit_memory_evolution


def categories_for(records: list[MemoryRecord]) -> list[CategorizedMemory]:
    return [
        CategorizedMemory(
            memoryId=record.id,
            category=MemoryCategory.UNKNOWN,
            confidence=0.2,
        )
        for record in records
    ]


def test_memory_evolution_detects_database_contradiction() -> None:
    records = [
        MemoryRecord(id="mem_1", content="Uses PostgreSQL for billing storage"),
        MemoryRecord(id="mem_2", content="Migrated to MySQL for billing storage"),
    ]

    audit = audit_memory_evolution(records, categories_for(records))

    assert audit["contradictionCount"] >= 1
    assert audit["contradictions"][0]["confidence"] > 0
    assert len(audit["contradictions"][0]["involvedMemories"]) == 2


def test_memory_evolution_detects_preference_change() -> None:
    records = [
        MemoryRecord(id="mem_1", content="Prefers Husky for git hooks"),
        MemoryRecord(id="mem_2", content="Stopped using Husky for git hooks"),
    ]
    categories = [
        CategorizedMemory(
            memoryId="mem_1",
            category=MemoryCategory.PREFERENCE,
            confidence=0.8,
        ),
        CategorizedMemory(
            memoryId="mem_2",
            category=MemoryCategory.PREFERENCE,
            confidence=0.8,
        ),
    ]

    audit = audit_memory_evolution(records, categories)

    assert audit["preferenceChangeCount"] >= 1
    assert audit["preferenceChanges"][0]["explanation"]


def test_memory_evolution_detects_superseded_decision() -> None:
    records = [
        MemoryRecord(
            id="mem_1",
            content="Decided to use REST for billing APIs",
            timestamp="2024-01-01T00:00:00",
        ),
        MemoryRecord(
            id="mem_2",
            content="Adopted GraphQL instead of REST for billing APIs",
            timestamp="2024-06-01T00:00:00",
        ),
    ]

    audit = audit_memory_evolution(records, categories_for(records))

    assert audit["supersededMemoryCount"] >= 1
    assert audit["supersededMemories"][0]["evidence"]


def test_memory_evolution_detects_stale_temporary_memory() -> None:
    records = [
        MemoryRecord(
            id="mem_1",
            content="Temporary pilot config for billing retry experiment",
            timestamp="2020-01-01T00:00:00",
        ),
    ]
    categories = [
        CategorizedMemory(
            memoryId="mem_1",
            category=MemoryCategory.TEMPORARY,
            confidence=0.85,
        ),
    ]

    audit = audit_memory_evolution(records, categories)

    assert audit["staleMemoryCount"] >= 1
    assert audit["staleMemoryCandidates"][0]["involvedMemories"][0]["memoryId"] == "mem_1"


def test_memory_evolution_detects_status_transition() -> None:
    records = [
        MemoryRecord(id="mem_1", content="Billing retry migration is planned for Q2"),
        MemoryRecord(id="mem_2", content="Billing retry migration is in progress"),
        MemoryRecord(id="mem_3", content="Billing retry migration completed"),
    ]
    categories = [
        CategorizedMemory(memoryId="mem_1", category=MemoryCategory.GOAL, confidence=0.8),
        CategorizedMemory(memoryId="mem_2", category=MemoryCategory.TASK, confidence=0.8),
        CategorizedMemory(memoryId="mem_3", category=MemoryCategory.TASK, confidence=0.8),
    ]

    audit = audit_memory_evolution(records, categories)

    assert audit["statusTransitionCount"] >= 1
    assert audit["evolutionConfidence"] > 0


def test_memory_evolution_audit_is_attached_to_validation() -> None:
    records = [
        MemoryRecord(id="mem_1", content="Uses PostgreSQL"),
        MemoryRecord(id="mem_2", content="Migrated to MySQL"),
    ]
    categories = categories_for(records)
    evolution = audit_memory_evolution(records, categories)
    validation = build_validation_summary(
        records,
        categories,
        [],
        memory_evolution_audit=evolution,
    )

    assert validation["memoryEvolutionAudit"]["contradictionCount"] >= 1
    assert validation["memoryEvolutionAudit"]["evolutionConfidence"] > 0
