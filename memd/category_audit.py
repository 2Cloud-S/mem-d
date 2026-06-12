from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence

from memd.contracts import CategorizedMemory, MemoryCategory, MemoryRecord

TOKEN_RE = re.compile(r"[a-z][a-z0-9+-]{2,}", re.IGNORECASE)
STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "user",
    "users",
    "that",
    "this",
    "from",
    "into",
    "when",
    "where",
    "then",
    "than",
    "their",
    "they",
    "are",
    "has",
    "have",
    "using",
    "about",
}

CAUSE_METADATA = {
    "derived_insight_or_inference": {
        "label": "Derived Insight",
        "issueType": "taxonomy_gap",
        "suggestedMapping": "Consider a first-class Derived Insight category.",
        "description": "Memories summarize conclusions, implications, or learned facts.",
    },
    "relationship_context_without_known_entities": {
        "label": "Dependency / Context Link",
        "issueType": "taxonomy_gap",
        "suggestedMapping": "Consider a Context Link category or extend Relationship scope.",
        "description": "Memories describe dependencies or context links without people.",
    },
    "tentative_planning_language": {
        "label": "Tentative Plan",
        "issueType": "classifier_failure",
        "suggestedMapping": "Map to Goal after adding tentative planning heuristics.",
        "description": "Memories describe possible future work without explicit goal markers.",
    },
    "implicit_task_without_task_marker": {
        "label": "Implicit Task",
        "issueType": "classifier_failure",
        "suggestedMapping": "Map to Task after adding implicit review/check heuristics.",
        "description": "Memories imply work to do without todo/reminder/task wording.",
    },
    "implicit_preference_without_preference_verb": {
        "label": "Implicit Preference",
        "issueType": "classifier_failure",
        "suggestedMapping": "Map to Preference after adding preference-adjective heuristics.",
        "description": "Memories express preference through comparative or acceptability language.",
    },
    "technical_fact_without_state_verb": {
        "label": "Technical Fragment",
        "issueType": "classifier_failure",
        "suggestedMapping": "Map to Fact after adding technical noun-fragment heuristics.",
        "description": "Memories are technical fact fragments without a clear state verb.",
    },
    "time_context_without_event_marker": {
        "label": "Temporal Context",
        "issueType": "classifier_failure",
        "suggestedMapping": "Map to Temporary after adding time-context heuristics.",
        "description": "Memories include time context without an event or calendar marker.",
    },
    "terse_or_fragmented_memory": {
        "label": "Short Fragment",
        "issueType": "taxonomy_gap",
        "suggestedMapping": "Consider a Fragment/Note category or leave as Unknown.",
        "description": "Memories are too short or fragmented for current taxonomy evidence.",
    },
    "no_recognized_category_signal": {
        "label": "Unrecognized Memory Shape",
        "issueType": "taxonomy_gap",
        "suggestedMapping": "Inspect examples before creating or expanding taxonomy.",
        "description": "Memories do not match current or diagnostic category signals.",
    },
}


def audit_category_quality_v2(
    records: Sequence[MemoryRecord],
    categories: Sequence[CategorizedMemory],
) -> dict[str, object]:
    records_by_id = {record.id: record for record in records}
    unknown_categories = [
        category
        for category in categories
        if category.category == MemoryCategory.UNKNOWN
    ]
    unknown_diagnostics = [
        unknown_diagnostic(category, records_by_id[category.memoryId])
        for category in unknown_categories
        if category.memoryId in records_by_id
    ]
    unknown_clusters = group_unknowns(unknown_diagnostics)
    candidates = ranked_reclassification_candidates(unknown_diagnostics)

    return {
        "unknownRate": percentage(len(unknown_categories), len(records)),
        "highConfidenceUnknownRate": percentage(
            sum(1 for category in unknown_categories if category.confidence >= 0.7),
            len(records),
        ),
        "categoryConfidenceDistribution": confidence_distribution(categories),
        "unknownCount": len(unknown_categories),
        "topUnknownCauses": top_unknown_causes(unknown_diagnostics),
        "unknownClusters": unknown_clusters,
        "suggestedTaxonomyGaps": suggested_taxonomy_gaps(unknown_clusters),
        "reclassificationCandidates": candidates,
        "taxonomyDiscovery": taxonomy_discovery_report(
            unknown_diagnostics,
            total_memories=len(records),
            unknown_count=len(unknown_categories),
        ),
    }


def unknown_diagnostic(
    category: CategorizedMemory,
    record: MemoryRecord,
) -> dict[str, object]:
    content = record.content
    token_list = tokens(content)
    cause, suggested_category, mapping_confidence = diagnose_unknown(content, token_list)
    theme_terms = common_terms([content], limit=5)
    return {
        "memoryId": record.id,
        "content": content,
        "cause": cause,
        "themeTerms": theme_terms,
        "suggestedCategory": suggested_category.value,
        "mappingConfidence": mapping_confidence,
        "categoryConfidence": category.confidence,
        "reason": category.reason,
        "tokenCount": len(token_list),
    }


def diagnose_unknown(
    content: str,
    token_list: Sequence[str],
) -> tuple[str, MemoryCategory, float]:
    lowered = content.lower()
    if re.search(r"\b(because|therefore|means|implies|insight|learned|shows)\b", lowered):
        return "derived_insight_or_inference", MemoryCategory.RELATIONSHIP, 0.68
    if re.search(r"\b(depends on|blocked by|related|context|linked|reference)\b", lowered):
        return "relationship_context_without_known_entities", MemoryCategory.RELATIONSHIP, 0.72
    if re.search(r"\b(should consider|might|maybe|possible|candidate|option)\b", lowered):
        return "tentative_planning_language", MemoryCategory.GOAL, 0.62
    if re.search(r"\b(needs review|investigate|check|verify|decide|followup)\b", lowered):
        return "implicit_task_without_task_marker", MemoryCategory.TASK, 0.66
    if re.search(r"\b(preferable|better|worse|acceptable|unacceptable)\b", lowered):
        return "implicit_preference_without_preference_verb", MemoryCategory.PREFERENCE, 0.7
    if re.search(r"\b(api|service|database|cache|schema|token|config|pipeline)\b", lowered):
        return "technical_fact_without_state_verb", MemoryCategory.FACT, 0.58
    if re.search(r"\b(today|tomorrow|temporary|later|soon|next)\b", lowered):
        return "time_context_without_event_marker", MemoryCategory.TEMPORARY, 0.6
    if len(token_list) <= 4:
        return "terse_or_fragmented_memory", MemoryCategory.UNKNOWN, 0.35
    return "no_recognized_category_signal", MemoryCategory.UNKNOWN, 0.25


def group_unknowns(diagnostics: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    grouped: defaultdict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for diagnostic in diagnostics:
        key = (
            str(diagnostic.get("cause", "")),
            str(diagnostic.get("suggestedCategory", "")),
        )
        grouped[key].append(diagnostic)

    clusters = []
    for index, ((cause, suggested_category), items) in enumerate(
        sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0][0])),
        start=1,
    ):
        contents = [str(item.get("content", "")) for item in items]
        clusters.append(
            {
                "clusterId": f"unknown_pattern_{index}",
                "cause": cause,
                "count": len(items),
                "themeTerms": common_terms(contents, limit=8),
                "suggestedCategory": suggested_category,
                "suggestedMappingConfidence": round(
                    sum(float_value(item.get("mappingConfidence")) for item in items)
                    / len(items),
                    4,
                ),
                "representativeExamples": [
                    {
                        "memoryId": item.get("memoryId"),
                        "content": item.get("content"),
                        "mappingConfidence": item.get("mappingConfidence"),
                    }
                    for item in items[:5]
                ],
            }
        )
    return clusters


def top_unknown_causes(diagnostics: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    counter = Counter(str(item.get("cause", "")) for item in diagnostics)
    examples: dict[str, str] = {}
    for item in diagnostics:
        cause = str(item.get("cause", ""))
        examples.setdefault(cause, str(item.get("content", "")))
    return [
        {
            "cause": cause,
            "count": count,
            "percentageOfUnknown": percentage(count, len(diagnostics)),
            "example": examples.get(cause, ""),
        }
        for cause, count in counter.most_common(10)
    ]


def suggested_taxonomy_gaps(
    unknown_clusters: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    gaps = []
    for cluster in unknown_clusters:
        count = integer(cluster.get("count"))
        confidence = float_value(cluster.get("suggestedMappingConfidence"))
        cause = str(cluster.get("cause", ""))
        if count < 2 and confidence < 0.6:
            continue
        gaps.append(
            {
                "gap": taxonomy_gap_label(cause),
                "cause": cause,
                "suggestedCategory": cluster.get("suggestedCategory", "Unknown"),
                "evidenceCount": count,
                "confidence": confidence,
                "themeTerms": cluster.get("themeTerms", []),
            }
        )
    return sorted(
        gaps,
        key=lambda item: (-integer(item["evidenceCount"]), -float_value(item["confidence"])),
    )[:10]


def ranked_reclassification_candidates(
    diagnostics: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    cause_frequency = Counter(str(item.get("cause", "")) for item in diagnostics)
    candidates = [
        {
            "memoryId": item.get("memoryId"),
            "content": item.get("content"),
            "currentCategory": MemoryCategory.UNKNOWN.value,
            "suggestedCategory": item.get("suggestedCategory"),
            "confidence": item.get("mappingConfidence"),
            "frequency": cause_frequency[str(item.get("cause", ""))],
            "cause": item.get("cause"),
            "reason": (
                "Unknown memory matches a recurring diagnostic pattern; inspect before "
                "changing taxonomy rules."
            ),
        }
        for item in diagnostics
        if item.get("suggestedCategory") != MemoryCategory.UNKNOWN.value
    ]
    return sorted(
        candidates,
        key=lambda item: (-float_value(item["confidence"]), -integer(item["frequency"])),
    )[:50]


def taxonomy_discovery_report(
    diagnostics: Sequence[dict[str, object]],
    total_memories: int,
    unknown_count: int,
) -> dict[str, object]:
    candidate_categories = taxonomy_candidate_categories(
        diagnostics,
        total_memories=total_memories,
        unknown_count=unknown_count,
    )
    classifier_failures = [
        candidate
        for candidate in candidate_categories
        if candidate["issueType"] == "classifier_failure"
    ]
    taxonomy_gaps = [
        candidate
        for candidate in candidate_categories
        if candidate["issueType"] == "taxonomy_gap"
    ]
    return {
        "summary": (
            "Taxonomy Discovery groups Unknown memories into candidate semantic types. "
            "It does not create categories or change classifications."
        ),
        "candidateCategories": candidate_categories,
        "classifierFailures": classifier_failures,
        "taxonomyGaps": taxonomy_gaps,
        "estimatedResolvableUnknownCount": sum(
            integer(candidate["memoryCount"])
            for candidate in candidate_categories
            if candidate["issueType"] == "classifier_failure"
        ),
        "estimatedTaxonomyGapUnknownCount": sum(
            integer(candidate["memoryCount"])
            for candidate in taxonomy_gaps
        ),
    }


def taxonomy_candidate_categories(
    diagnostics: Sequence[dict[str, object]],
    total_memories: int,
    unknown_count: int,
) -> list[dict[str, object]]:
    grouped: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for diagnostic in diagnostics:
        grouped[str(diagnostic.get("cause", ""))].append(diagnostic)

    candidates = []
    for cause, items in grouped.items():
        metadata = cause_metadata(cause)
        count = len(items)
        confidence = round(
            sum(float_value(item.get("mappingConfidence")) for item in items) / count,
            4,
        )
        estimated_reduction = percentage(count, total_memories)
        candidates.append(
            {
                "label": metadata["label"],
                "cause": cause,
                "issueType": metadata["issueType"],
                "memoryCount": count,
                "percentageOfUnknown": percentage(count, unknown_count),
                "estimatedUnknownRateReduction": estimated_reduction,
                "estimatedRemainingUnknownRate": max(
                    0.0,
                    round(percentage(unknown_count, total_memories) - estimated_reduction, 2),
                ),
                "representativeExamples": representative_examples(items),
                "confidence": confidence,
                "suggestedMapping": metadata["suggestedMapping"],
                "description": metadata["description"],
                "themeTerms": common_terms(
                    (str(item.get("content", "")) for item in items),
                    limit=8,
                ),
            }
        )
    return sorted(
        candidates,
        key=lambda item: (
            -integer(item["memoryCount"]),
            -float_value(item["confidence"]),
            str(item["label"]),
        ),
    )


def representative_examples(items: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    ranked = sorted(
        items,
        key=lambda item: (-float_value(item.get("mappingConfidence")), str(item.get("memoryId"))),
    )
    return [
        {
            "memoryId": item.get("memoryId"),
            "content": item.get("content"),
            "confidence": item.get("mappingConfidence"),
        }
        for item in ranked[:5]
    ]


def cause_metadata(cause: str) -> dict[str, str]:
    return CAUSE_METADATA.get(
        cause,
        {
            "label": taxonomy_gap_label(cause),
            "issueType": "taxonomy_gap",
            "suggestedMapping": "Inspect examples before changing taxonomy.",
            "description": "Unknown cause does not have specific discovery metadata.",
        },
    )


def confidence_distribution(categories: Sequence[CategorizedMemory]) -> dict[str, object]:
    buckets = {
        "high": 0,
        "medium": 0,
        "low": 0,
    }
    by_category: dict[str, dict[str, int]] = {
        category.value: {"high": 0, "medium": 0, "low": 0}
        for category in MemoryCategory
    }
    for category in categories:
        bucket = confidence_bucket(category.confidence)
        buckets[bucket] += 1
        by_category[category.category.value][bucket] += 1
    return {
        "buckets": buckets,
        "byCategory": by_category,
        "averageConfidence": round(
            sum(category.confidence for category in categories) / len(categories),
            4,
        )
        if categories
        else 0.0,
    }


def confidence_bucket(confidence: float) -> str:
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.5:
        return "medium"
    return "low"


def taxonomy_gap_label(cause: str) -> str:
    labels = {
        "derived_insight_or_inference": "Derived insight memories",
        "relationship_context_without_known_entities": "Implicit relationship/context memories",
        "tentative_planning_language": "Tentative planning memories",
        "implicit_task_without_task_marker": "Implicit task memories",
        "implicit_preference_without_preference_verb": "Implicit preference memories",
        "technical_fact_without_state_verb": "Technical fact fragments",
        "time_context_without_event_marker": "Time-context memories",
        "terse_or_fragmented_memory": "Short fragmented memories",
    }
    return labels.get(cause, "Unrecognized memory shape")


def common_terms(contents: Iterable[str], limit: int = 8) -> list[str]:
    counter: Counter[str] = Counter()
    for content in contents:
        counter.update(tokens(content))
    return [term for term, _count in counter.most_common(limit)]


def tokens(content: str) -> list[str]:
    return [
        token.lower()
        for token in TOKEN_RE.findall(content)
        if token.lower() not in STOPWORDS
    ]


def percentage(part: int, whole: int) -> float:
    if whole == 0:
        return 0.0
    return round((part / whole) * 100, 2)


def float_value(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def integer(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0
