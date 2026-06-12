from memd.contracts import CategorizedMemory, MemoryCategory, MemoryRecord
from memd.inspection import build_validation_summary
from memd.memory_evolution import audit_memory_evolution
from memd.memory_lifecycle import infer_memory_lifecycle


def unknown_categories(records: list[MemoryRecord]) -> list[CategorizedMemory]:
    return [
        CategorizedMemory(
            memoryId=record.id,
            category=MemoryCategory.UNKNOWN,
            confidence=0.2,
        )
        for record in records
    ]


def test_lifecycle_marks_contradicted_memory_deprecated_and_newer_active() -> None:
    records = [
        MemoryRecord(id="mem_1", content="Uses PostgreSQL for billing storage"),
        MemoryRecord(id="mem_2", content="Migrated to MySQL for billing storage"),
    ]
    evolution = audit_memory_evolution(records, unknown_categories(records))
    lifecycle = infer_memory_lifecycle(evolution)

    assignments = {
        assignment["memoryId"]: assignment["lifecycleState"]
        for assignment in lifecycle["memoryLifecycleAssignments"]
    }

    assert assignments["mem_1"] == "Deprecated"
    assert assignments["mem_2"] == "Active"
    assert lifecycle["lifecycleCounts"]["Deprecated"] == 1
    assert lifecycle["lifecycleCounts"]["Active"] == 1
    assert lifecycle["lifecycleConfidence"] > 0


def test_lifecycle_marks_preference_change_deprecated_and_active() -> None:
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
    lifecycle = infer_memory_lifecycle(audit_memory_evolution(records, categories))

    assignments = {
        assignment["memoryId"]: assignment["lifecycleState"]
        for assignment in lifecycle["memoryLifecycleAssignments"]
    }

    assert assignments["mem_1"] == "Deprecated"
    assert assignments["mem_2"] == "Active"


def test_lifecycle_marks_superseded_decision() -> None:
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
    lifecycle = infer_memory_lifecycle(
        audit_memory_evolution(records, unknown_categories(records))
    )
    assignments = {
        assignment["memoryId"]: assignment["lifecycleState"]
        for assignment in lifecycle["memoryLifecycleAssignments"]
    }

    assert assignments["mem_1"] == "Superseded"
    assert assignments["mem_2"] == "Active"


def test_lifecycle_marks_stale_temporary_memory() -> None:
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
    lifecycle = infer_memory_lifecycle(audit_memory_evolution(records, categories))

    assignment = lifecycle["memoryLifecycleAssignments"][0]
    assert assignment["memoryId"] == "mem_1"
    assert assignment["lifecycleState"] == "Temporary"
    assert lifecycle["lifecycleCounts"]["Temporary"] == 1


def test_lifecycle_marks_completed_status_transition() -> None:
    records = [
        MemoryRecord(id="mem_1", content="Billing retry migration is planned for Q2"),
        MemoryRecord(id="mem_2", content="Billing retry migration completed"),
    ]
    categories = [
        CategorizedMemory(
            memoryId="mem_1",
            category=MemoryCategory.GOAL,
            confidence=0.8,
        ),
        CategorizedMemory(
            memoryId="mem_2",
            category=MemoryCategory.TASK,
            confidence=0.8,
        ),
    ]
    lifecycle = infer_memory_lifecycle(audit_memory_evolution(records, categories))
    assignments = {
        assignment["memoryId"]: assignment["lifecycleState"]
        for assignment in lifecycle["memoryLifecycleAssignments"]
    }

    assert assignments["mem_1"] == "Historical"
    assert assignments["mem_2"] == "Completed"
    assert lifecycle["lifecycleTransitions"]


def test_lifecycle_attaches_to_validation_summary() -> None:
    records = [
        MemoryRecord(id="mem_1", content="Uses PostgreSQL for billing storage"),
        MemoryRecord(id="mem_2", content="Migrated to MySQL for billing storage"),
    ]
    categories = unknown_categories(records)
    evolution = audit_memory_evolution(records, categories)
    lifecycle = infer_memory_lifecycle(evolution)
    validation = build_validation_summary(
        records,
        categories,
        [],
        memory_evolution_audit=evolution,
        memory_lifecycle=lifecycle,
    )

    assert validation["memoryLifecycle"]["lifecycleCounts"]["Deprecated"] == 1
    assert validation["memoryLifecycle"]["memoryLifecycleAssignments"]
