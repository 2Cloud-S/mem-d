from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime
from itertools import combinations

from memd.contracts import CategorizedMemory, EmbeddedMemory, MemoryCategory, MemoryRecord
from memd.similarity import similarity_records

TOKEN_RE = re.compile(r"[a-z][a-z0-9+-]{2,}", re.IGNORECASE)
STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "when",
    "where",
    "than",
    "then",
    "their",
    "they",
    "are",
    "has",
    "have",
    "using",
    "about",
    "user",
    "users",
}

USAGE_AFFIRM = re.compile(
    r"\b(?:uses?|using|runs? on|built with|prefers?|preferred|standard is)\b",
    re.IGNORECASE,
)
USAGE_NEGATE = re.compile(
    r"\b(?:no longer|stopped|deprecated|removed|dropped|does not use|don't use)\b",
    re.IGNORECASE,
)
MIGRATION = re.compile(
    r"\b(?:migrated|switched|moved|replaced|transitioned)\s+(?:to|from|with)\b",
    re.IGNORECASE,
)
DECISION = re.compile(
    r"\b(?:decided|decision|adopted|chose|chosen|selected|settled on|replaced)\b",
    re.IGNORECASE,
)
PREFERENCE = re.compile(
    r"\b(?:prefers?|preferred|likes?|liked|favors?|favoured)\b",
    re.IGNORECASE,
)
STATUS_PLANNED = re.compile(
    r"\b(?:planned|planning|todo|backlog|will|should|needs? to)\b",
    re.IGNORECASE,
)
STATUS_PROGRESS = re.compile(
    r"\b(?:in progress|ongoing|started|working on|wip|underway)\b",
    re.IGNORECASE,
)
STATUS_DONE = re.compile(
    r"\b(?:completed|done|finished|shipped|released|closed|resolved)\b",
    re.IGNORECASE,
)
STALE_MARKERS = re.compile(
    r"\b(?:temporary|for now|during|until|interim|placeholder|short[- ]term)\b",
    re.IGNORECASE,
)
TECH_ANCHORS = re.compile(
    r"\b(?:postgresql|postgres|mysql|mongodb|redis|kafka|husky|eslint|prettier|"
    r"docker|kubernetes|aws|gcp|azure|python|typescript|javascript|react|vue)\b",
    re.IGNORECASE,
)
TECH_DOMAINS: tuple[tuple[str, frozenset[str]], ...] = (
    (
        "database",
        frozenset({"postgresql", "postgres", "mysql", "mongodb", "sqlite", "redis"}),
    ),
    (
        "tooling",
        frozenset({"husky", "eslint", "prettier", "docker", "kubernetes"}),
    ),
    (
        "language",
        frozenset({"python", "typescript", "javascript"}),
    ),
    (
        "frontend",
        frozenset({"react", "vue"}),
    ),
)

EVOLUTION_PAIR_THRESHOLD = 0.42


def audit_memory_evolution(
    records: Sequence[MemoryRecord],
    categories: Sequence[CategorizedMemory],
    embeddings: Sequence[EmbeddedMemory] | None = None,
) -> dict[str, object]:
    records_by_id = {record.id: record for record in records}
    categories_by_id = {category.memoryId: category for category in categories}
    pairs = candidate_evolution_pairs(records, embeddings or [])

    contradictions: list[dict[str, object]] = []
    preference_changes: list[dict[str, object]] = []
    superseded: list[dict[str, object]] = []
    status_transitions: list[dict[str, object]] = []
    assigned_pairs: set[tuple[str, str]] = set()

    for memory_a, memory_b, relation_strength in pairs:
        pair_key = tuple(sorted((memory_a, memory_b)))
        if pair_key in assigned_pairs:
            continue
        record_a = records_by_id[memory_a]
        record_b = records_by_id[memory_b]
        category_a = categories_by_id.get(memory_a)
        category_b = categories_by_id.get(memory_b)

        detection = detect_pair_evolution(
            record_a,
            record_b,
            category_a,
            category_b,
            relation_strength,
        )
        if detection is None:
            continue

        assigned_pairs.add(pair_key)
        case = build_evolution_case(
            detection["evolutionType"],
            record_a,
            record_b,
            category_a,
            category_b,
            detection["confidence"],
            detection["evidence"],
            detection["explanation"],
            relation_strength,
        )
        evolution_type = str(detection["evolutionType"])
        if evolution_type == "contradiction":
            contradictions.append(case)
        elif evolution_type == "preference_change":
            preference_changes.append(case)
        elif evolution_type == "superseded_memory":
            superseded.append(case)
        elif evolution_type == "status_transition":
            status_transitions.append(case)

    stale_candidates = detect_stale_memories(records, categories_by_id)

    all_cases = contradictions + preference_changes + superseded + status_transitions
    return {
        "summary": (
            "Memory Evolution Audit detects evidence that memories change over time. "
            "Diagnostic only; no memories are modified."
        ),
        "contradictionCount": len(contradictions),
        "preferenceChangeCount": len(preference_changes),
        "supersededMemoryCount": len(superseded),
        "staleMemoryCandidates": stale_candidates,
        "statusTransitionCandidates": status_transitions,
        "evolutionConfidence": overall_evolution_confidence(all_cases, stale_candidates),
        "contradictions": contradictions,
        "preferenceChanges": preference_changes,
        "supersededMemories": superseded,
        "staleMemoryCount": len(stale_candidates),
        "statusTransitionCount": len(status_transitions),
        "totalEvolutionSignals": (
            len(contradictions)
            + len(preference_changes)
            + len(superseded)
            + len(stale_candidates)
            + len(status_transitions)
        ),
    }


def candidate_evolution_pairs(
    records: Sequence[MemoryRecord],
    embeddings: Sequence[EmbeddedMemory],
) -> list[tuple[str, str, float]]:
    pair_scores: dict[tuple[str, str], float] = {}

    for left, right in combinations(records, 2):
        shared = set(tokens(left.content)) & set(tokens(right.content))
        if len(shared) >= 2:
            overlap = len(shared) / max(len(set(tokens(left.content))), 1)
            key = tuple(sorted((left.id, right.id)))
            pair_scores[key] = max(pair_scores.get(key, 0.0), min(0.95, 0.45 + overlap * 0.4))

        anchor_left = set(token.lower() for token in TECH_ANCHORS.findall(left.content))
        anchor_right = set(token.lower() for token in TECH_ANCHORS.findall(right.content))
        if anchor_left & anchor_right:
            key = tuple(sorted((left.id, right.id)))
            pair_scores[key] = max(pair_scores.get(key, 0.0), 0.72)
        elif shared_tech_domain(anchor_left, anchor_right):
            key = tuple(sorted((left.id, right.id)))
            pair_scores[key] = max(pair_scores.get(key, 0.0), 0.68)

    if embeddings:
        for similarity in similarity_records(embeddings, EVOLUTION_PAIR_THRESHOLD):
            key = tuple(sorted((similarity.memoryA, similarity.memoryB)))
            pair_scores[key] = max(pair_scores.get(key, 0.0), similarity.similarity)

    return [
        (memory_a, memory_b, score)
        for (memory_a, memory_b), score in sorted(
            pair_scores.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


def detect_pair_evolution(
    record_a: MemoryRecord,
    record_b: MemoryRecord,
    category_a: CategorizedMemory | None,
    category_b: CategorizedMemory | None,
    relation_strength: float,
) -> dict[str, object] | None:
    ordered = order_records(record_a, record_b)
    older, newer = ordered
    older_category = category_a if older.id == record_a.id else category_b
    newer_category = category_b if newer.id == record_b.id else category_a
    older_text = older.content
    newer_text = newer.content

    preference_change = detect_preference_change(
        older_text,
        newer_text,
        older_category,
        newer_category,
        relation_strength,
    )
    if preference_change:
        return {
            "evolutionType": "preference_change",
            **preference_change,
        }

    contradiction = detect_contradiction(older_text, newer_text, relation_strength)
    if contradiction:
        return {
            "evolutionType": "contradiction",
            **contradiction,
        }

    superseded = detect_superseded_memory(
        older,
        newer,
        older_text,
        newer_text,
        relation_strength,
    )
    if superseded:
        return {
            "evolutionType": "superseded_memory",
            **superseded,
        }

    status_transition = detect_status_transition(
        older_text,
        newer_text,
        older_category,
        newer_category,
        relation_strength,
    )
    if status_transition:
        return {
            "evolutionType": "status_transition",
            **status_transition,
        }
    return None


def shared_tech_domain(left_anchors: set[str], right_anchors: set[str]) -> bool:
    if not left_anchors or not right_anchors:
        return False
    for _domain, members in TECH_DOMAINS:
        if left_anchors & members and right_anchors & members:
            return True
    return False


def detect_contradiction(
    older_text: str,
    newer_text: str,
    relation_strength: float,
) -> dict[str, object] | None:
    evidence: list[str] = []
    confidence = 0.55

    older_anchors = set(token.lower() for token in TECH_ANCHORS.findall(older_text))
    newer_anchors = set(token.lower() for token in TECH_ANCHORS.findall(newer_text))
    shared_anchors = older_anchors & newer_anchors
    if shared_anchors:
        evidence.append(f"Shared technology anchor: {', '.join(sorted(shared_anchors))}")
        confidence += 0.1
    elif shared_tech_domain(older_anchors, newer_anchors):
        evidence.append("Memories reference technologies in the same domain.")
        confidence += 0.15

    affirm_older = bool(USAGE_AFFIRM.search(older_text))
    negate_newer = bool(USAGE_NEGATE.search(newer_text))
    migration_newer = bool(MIGRATION.search(newer_text))
    if affirm_older and (negate_newer or migration_newer):
        evidence.append("Older memory affirms usage while newer memory negates or migrates away.")
        confidence += 0.2

    older_tokens = set(tokens(older_text))
    newer_tokens = set(tokens(newer_text))
    shared = older_tokens & newer_tokens
    conflicting_usage = (
        affirm_older
        and migration_newer
        and len(shared) >= 2
    )
    if conflicting_usage:
        evidence.append("Shared topic terms with migration or replacement language.")
        confidence += 0.1

    if not evidence:
        return None

    confidence = round(min(0.95, confidence + relation_strength * 0.15), 4)
    return {
        "confidence": confidence,
        "evidence": evidence,
        "explanation": (
            "Memories appear to describe conflicting states about the same topic over time."
        ),
    }


def detect_preference_change(
    older_text: str,
    newer_text: str,
    older_category: CategorizedMemory | None,
    newer_category: CategorizedMemory | None,
    relation_strength: float,
) -> dict[str, object] | None:
    evidence: list[str] = []
    preference_categories = {
        category.category
        for category in (older_category, newer_category)
        if category is not None
    }
    if MemoryCategory.PREFERENCE in preference_categories:
        evidence.append("At least one memory is categorized as Preference.")
    if PREFERENCE.search(older_text) or PREFERENCE.search(newer_text):
        evidence.append("Preference language detected in memory content.")

    change_signal = bool(USAGE_NEGATE.search(newer_text)) or bool(MIGRATION.search(newer_text))
    if not change_signal:
        return None
    if not evidence:
        return None

    confidence = round(
        min(
            0.95,
            0.6 + (0.1 if MemoryCategory.PREFERENCE in preference_categories else 0.0)
            + relation_strength * 0.15,
        ),
        4,
    )
    return {
        "confidence": confidence,
        "evidence": evidence + ["Newer memory signals a stopped or replaced preference."],
        "explanation": (
            "Preference-related memories suggest a change in chosen tooling or behavior."
        ),
    }


def detect_superseded_memory(
    older: MemoryRecord,
    newer: MemoryRecord,
    older_text: str,
    newer_text: str,
    relation_strength: float,
) -> dict[str, object] | None:
    if not (DECISION.search(older_text) or DECISION.search(newer_text)):
        return None

    evidence = ["Decision or adoption language detected."]
    replacement = bool(MIGRATION.search(newer_text)) or bool(
        re.search(r"\b(?:instead of|replaces?|supersedes?)\b", newer_text, re.IGNORECASE)
    )
    if replacement:
        evidence.append("Newer memory includes replacement or supersession language.")

    temporal_order = parse_timestamp(older.timestamp) and parse_timestamp(newer.timestamp)
    if temporal_order and parse_timestamp(older.timestamp) != parse_timestamp(newer.timestamp):
        evidence.append("Timestamps support older-to-newer ordering.")

    if not replacement and not temporal_order:
        return None

    confidence = round(min(0.95, 0.58 + relation_strength * 0.2), 4)
    return {
        "confidence": confidence,
        "evidence": evidence,
        "explanation": "A newer decision-like memory may supersede an older one on the same topic.",
    }


def detect_status_transition(
    older_text: str,
    newer_text: str,
    older_category: CategorizedMemory | None,
    newer_category: CategorizedMemory | None,
    relation_strength: float,
) -> dict[str, object] | None:
    status_categories = {
        category.category
        for category in (older_category, newer_category)
        if category is not None
    }
    if not status_categories & {MemoryCategory.TASK, MemoryCategory.GOAL}:
        if not (STATUS_PLANNED.search(older_text) or STATUS_PROGRESS.search(newer_text)):
            return None

    older_status = status_stage(older_text)
    newer_status = status_stage(newer_text)
    if older_status is None or newer_status is None or older_status == newer_status:
        return None
    if status_rank(newer_status) <= status_rank(older_status):
        return None

    confidence = round(min(0.95, 0.62 + relation_strength * 0.15), 4)
    return {
        "confidence": confidence,
        "evidence": [
            f"Older status signal: {older_status}",
            f"Newer status signal: {newer_status}",
        ],
        "explanation": (
            f"Memories suggest a status transition from {older_status} to {newer_status}."
        ),
    }


def detect_stale_memories(
    records: Sequence[MemoryRecord],
    categories_by_id: dict[str, CategorizedMemory],
) -> list[dict[str, object]]:
    stale_candidates: list[dict[str, object]] = []
    for index, record in enumerate(records, start=1):
        category = categories_by_id.get(record.id)
        evidence: list[str] = []
        confidence = 0.45

        if category and category.category == MemoryCategory.TEMPORARY:
            evidence.append("Memory is categorized as Temporary.")
            confidence += 0.2
        if STALE_MARKERS.search(record.content):
            evidence.append("Content includes temporary or interim language.")
            confidence += 0.15
        if re.search(r"\b(?:project|phase|sprint|pilot)\b", record.content, re.IGNORECASE):
            evidence.append("Content references a bounded project or phase context.")
            confidence += 0.1

        timestamp = parse_timestamp(record.timestamp)
        if timestamp and timestamp.year < datetime.now().year:
            evidence.append("Memory timestamp appears dated relative to the current year.")
            confidence += 0.1

        if not evidence:
            continue

        stale_candidates.append(
            {
                "caseId": f"stale_memory_{index}",
                "involvedMemories": [memory_snapshot(record, category)],
                "evidence": evidence,
                "confidence": round(min(0.9, confidence), 4),
                "explanation": (
                    "Memory may represent a stale or time-bound fact that could be outdated."
                ),
            }
        )
    return stale_candidates


def build_evolution_case(
    evolution_type: str,
    record_a: MemoryRecord,
    record_b: MemoryRecord,
    category_a: CategorizedMemory | None,
    category_b: CategorizedMemory | None,
    confidence: float,
    evidence: list[str],
    explanation: str,
    relation_strength: float,
) -> dict[str, object]:
    ordered = order_records(record_a, record_b)
    older_category = category_a if ordered[0].id == record_a.id else category_b
    newer_category = category_b if ordered[1].id == record_b.id else category_a
    return {
        "caseId": f"{evolution_type}_{ordered[0].id}_{ordered[1].id}",
        "evolutionType": evolution_type,
        "involvedMemories": [
            memory_snapshot(ordered[0], older_category),
            memory_snapshot(ordered[1], newer_category),
        ],
        "evidence": evidence + [f"Relation strength: {round(relation_strength, 4)}"],
        "confidence": confidence,
        "explanation": explanation,
    }


def memory_snapshot(
    record: MemoryRecord,
    category: CategorizedMemory | None,
) -> dict[str, object]:
    return {
        "memoryId": record.id,
        "content": record.content,
        "timestamp": record.timestamp,
        "category": category.category.value if category else None,
    }


def order_records(
    record_a: MemoryRecord,
    record_b: MemoryRecord,
) -> tuple[MemoryRecord, MemoryRecord]:
    time_a = parse_timestamp(record_a.timestamp)
    time_b = parse_timestamp(record_b.timestamp)
    if time_a and time_b and time_a != time_b:
        return (record_a, record_b) if time_a < time_b else (record_b, record_a)
    return (record_a, record_b)


def status_stage(content: str) -> str | None:
    if STATUS_DONE.search(content):
        return "completed"
    if STATUS_PROGRESS.search(content):
        return "in_progress"
    if STATUS_PLANNED.search(content):
        return "planned"
    return None


def status_rank(stage: str) -> int:
    return {"planned": 1, "in_progress": 2, "completed": 3}.get(stage, 0)


def overall_evolution_confidence(
    pair_cases: Sequence[dict[str, object]],
    stale_candidates: Sequence[dict[str, object]],
) -> float:
    confidences = [
        float_value(case.get("confidence"))
        for case in [*pair_cases, *stale_candidates]
    ]
    if not confidences:
        return 0.0
    return round(sum(confidences) / len(confidences), 4)


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    candidates = (
        normalized.replace("Z", "+00:00"),
        normalized.split("T")[0],
    )
    for candidate in candidates:
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def tokens(content: str) -> list[str]:
    return [
        token.lower()
        for token in TOKEN_RE.findall(content)
        if token.lower() not in STOPWORDS
    ]


def float_value(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    return 0.0
