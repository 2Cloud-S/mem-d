from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence

LIFECYCLE_STATES = (
    "Active",
    "Historical",
    "Superseded",
    "Deprecated",
    "Temporary",
    "Completed",
)

STATE_PRIORITY = {
    "Deprecated": 6,
    "Superseded": 5,
    "Completed": 4,
    "Temporary": 3,
    "Active": 2,
    "Historical": 1,
}

COMPLETED_SIGNAL = re.compile(
    r"\b(?:completed|done|finished|shipped|released|closed|resolved)\b",
    re.IGNORECASE,
)
TEMPORARY_SIGNAL = re.compile(
    r"\b(?:temporary|for now|during|until|interim|placeholder|short[- ]term)\b",
    re.IGNORECASE,
)


def infer_memory_lifecycle(memory_evolution_audit: dict[str, object]) -> dict[str, object]:
    assignments_by_id: dict[str, dict[str, object]] = {}
    lifecycle_transitions: list[dict[str, object]] = []

    for key in (
        "contradictions",
        "preferenceChanges",
        "supersededMemories",
        "statusTransitionCandidates",
    ):
        for case in list_value(memory_evolution_audit.get(key)):
            if not isinstance(case, dict):
                continue
            relationship = lifecycle_relationship_for_case(case)
            if relationship is None:
                continue
            lifecycle_transitions.append(relationship["transition"])
            for assignment in relationship["assignments"]:
                merge_assignment(assignments_by_id, assignment)

    for case in list_value(memory_evolution_audit.get("staleMemoryCandidates")):
        if not isinstance(case, dict):
            continue
        assignment = lifecycle_assignment_for_stale_candidate(case)
        if assignment:
            merge_assignment(assignments_by_id, assignment)
            lifecycle_transitions.append(
                {
                    "caseId": case.get("caseId"),
                    "evolutionType": "stale_memory",
                    "fromMemoryId": assignment["memoryId"],
                    "fromState": assignment["lifecycleState"],
                    "toMemoryId": None,
                    "toState": None,
                    "confidence": assignment["confidence"],
                    "explanation": "Memory is flagged as time-bound or potentially stale.",
                }
            )

    assignments = sorted(
        assignments_by_id.values(),
        key=lambda item: (
            -float_value(item.get("confidence")),
            str(item.get("memoryId")),
        ),
    )
    lifecycle_counts = {
        state: sum(1 for item in assignments if item.get("lifecycleState") == state)
        for state in LIFECYCLE_STATES
    }
    return {
        "summary": (
            "Memory Lifecycle Model infers likely lifecycle state from Memory Evolution "
            "Audit evidence only. It is diagnostic and does not modify memories."
        ),
        "lifecycleCounts": lifecycle_counts,
        "lifecycleTransitions": lifecycle_transitions,
        "lifecycleConfidence": lifecycle_confidence(assignments),
        "memoryLifecycleAssignments": assignments,
    }


def lifecycle_relationship_for_case(case: dict[str, object]) -> dict[str, object] | None:
    memories = [
        memory for memory in list_value(case.get("involvedMemories"))
        if isinstance(memory, dict)
    ]
    if len(memories) < 2:
        return None

    older = memories[0]
    newer = memories[1]
    evolution_type = str(case.get("evolutionType", ""))
    confidence = float_value(case.get("confidence"))
    explanation = str(case.get("explanation", ""))

    if evolution_type == "contradiction":
        from_state = "Deprecated"
        to_state = "Active"
        transition_explanation = (
            "Earlier memory appears contradicted by a newer memory on the same topic."
        )
    elif evolution_type == "preference_change":
        from_state = "Deprecated"
        to_state = "Active"
        transition_explanation = (
            "Earlier preference appears replaced or stopped by a newer preference signal."
        )
    elif evolution_type == "superseded_memory":
        from_state = "Superseded"
        to_state = "Active"
        transition_explanation = (
            "Earlier decision-like memory appears superseded by a newer decision."
        )
    elif evolution_type == "status_transition":
        from_state = "Historical"
        to_state = status_lifecycle_state(newer)
        transition_explanation = explanation or (
            "Earlier status memory is historical relative to a newer status signal."
        )
    else:
        return None

    return {
        "assignments": [
            build_lifecycle_assignment(
                older,
                from_state,
                confidence,
                case,
                transition_explanation,
            ),
            build_lifecycle_assignment(
                newer,
                to_state,
                confidence,
                case,
                transition_explanation,
            ),
        ],
        "transition": {
            "caseId": case.get("caseId"),
            "evolutionType": evolution_type,
            "fromMemoryId": older.get("memoryId"),
            "fromState": from_state,
            "toMemoryId": newer.get("memoryId"),
            "toState": to_state,
            "confidence": confidence,
            "explanation": transition_explanation,
        },
    }


def lifecycle_assignment_for_stale_candidate(
    case: dict[str, object],
) -> dict[str, object] | None:
    memories = [
        memory for memory in list_value(case.get("involvedMemories"))
        if isinstance(memory, dict)
    ]
    if not memories:
        return None
    memory = memories[0]
    state = stale_lifecycle_state(memory)
    return build_lifecycle_assignment(
        memory,
        state,
        float_value(case.get("confidence")),
        case,
        str(case.get("explanation", "")),
    )


def build_lifecycle_assignment(
    memory: dict[str, object],
    state: str,
    confidence: float,
    case: dict[str, object],
    explanation: str,
) -> dict[str, object]:
    return {
        "memoryId": memory.get("memoryId"),
        "content": memory.get("content"),
        "timestamp": memory.get("timestamp"),
        "category": memory.get("category"),
        "lifecycleState": state,
        "confidence": round(confidence, 4),
        "evidence": list_value(case.get("evidence")),
        "sourceCaseId": case.get("caseId"),
        "sourceEvolutionType": case.get("evolutionType", "stale_memory"),
        "explanation": explanation,
    }


def merge_assignment(
    assignments_by_id: dict[str, dict[str, object]],
    assignment: dict[str, object],
) -> None:
    memory_id = str(assignment.get("memoryId", ""))
    if not memory_id:
        return
    existing = assignments_by_id.get(memory_id)
    if existing is None:
        assignments_by_id[memory_id] = assignment
        return

    existing_state = str(existing.get("lifecycleState", "Active"))
    candidate_state = str(assignment.get("lifecycleState", "Active"))
    existing_confidence = float_value(existing.get("confidence"))
    candidate_confidence = float_value(assignment.get("confidence"))
    candidate_wins = (
        STATE_PRIORITY.get(candidate_state, 0) > STATE_PRIORITY.get(existing_state, 0)
        or (
            STATE_PRIORITY.get(candidate_state, 0) == STATE_PRIORITY.get(existing_state, 0)
            and candidate_confidence > existing_confidence
        )
    )
    if candidate_wins:
        assignment["alternateLifecycleSignals"] = [
            summarize_assignment(existing),
            *list_value(existing.get("alternateLifecycleSignals")),
        ]
        assignments_by_id[memory_id] = assignment
    else:
        alternates = list_value(existing.get("alternateLifecycleSignals"))
        existing["alternateLifecycleSignals"] = [
            *alternates,
            summarize_assignment(assignment),
        ]


def summarize_assignment(assignment: dict[str, object]) -> dict[str, object]:
    return {
        "lifecycleState": assignment.get("lifecycleState"),
        "confidence": assignment.get("confidence"),
        "sourceCaseId": assignment.get("sourceCaseId"),
        "sourceEvolutionType": assignment.get("sourceEvolutionType"),
    }


def status_lifecycle_state(memory: dict[str, object]) -> str:
    content = str(memory.get("content", ""))
    if COMPLETED_SIGNAL.search(content):
        return "Completed"
    return "Active"


def stale_lifecycle_state(memory: dict[str, object]) -> str:
    content = str(memory.get("content", ""))
    category = str(memory.get("category", ""))
    if category == "Temporary" or TEMPORARY_SIGNAL.search(content):
        return "Temporary"
    return "Historical"


def lifecycle_confidence(assignments: Sequence[dict[str, object]]) -> float:
    if not assignments:
        return 0.0
    state_counts = Counter(str(item.get("lifecycleState")) for item in assignments)
    weighted = sum(
        float_value(item.get("confidence")) * STATE_PRIORITY.get(
            str(item.get("lifecycleState")),
            1,
        )
        for item in assignments
    )
    priority_total = sum(
        STATE_PRIORITY.get(str(item.get("lifecycleState")), 1)
        for item in assignments
    )
    diversity_penalty = 0.02 * max(0, len(state_counts) - 1)
    return round(max(0.0, (weighted / priority_total) - diversity_penalty), 4)


def list_value(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return []


def float_value(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    return 0.0
