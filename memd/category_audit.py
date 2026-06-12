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

SEMANTIC_THEMES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "Architecture",
        "System structure, patterns, and design choices.",
        re.compile(
            r"\b(architecture|architectural|pattern|microservice|monolith|layered|"
            r"modular|topology|component|service mesh)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Constraint",
        "Limits, requirements, or non-negotiable boundaries.",
        re.compile(
            r"\b(must|cannot|can't|required|requirement|limit|constraint|"
            r"maximum|minimum|only|never exceed|at most|at least)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Principle",
        "Guiding standards or engineering principles.",
        re.compile(
            r"\b(principle|guideline|best practice|rule of thumb|standard practice|"
            r"engineering standard|convention)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Decision",
        "Recorded choices or adopted standards.",
        re.compile(
            r"\b(decided|decision|chose|chosen|selected|adopted|we use|"
            r"standard is|settled on|picked)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Dependency",
        "Dependencies, blockers, or prerequisite relationships.",
        re.compile(
            r"\b(depends on|blocked by|requires|prerequisite|upstream|downstream|"
            r"waiting on|contingent on)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Workflow Rule",
        "Process steps, operational workflows, or procedural rules.",
        re.compile(
            r"\b(workflow|process|procedure|before deploy|after merge|step|"
            r"pipeline stage|runbook|checklist|approval)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Context",
        "Background, situational context, or cross-memory linkage.",
        re.compile(
            r"\b(context for|background|situation|scenario|relates to|"
            r"linked to|reference for|in the context of)\b",
            re.IGNORECASE,
        ),
    ),
)

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
        enrich_semantic_diagnostic(
            unknown_diagnostic(category, records_by_id[category.memoryId])
        )
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
        "semanticThemeAnalysis": semantic_theme_analysis_report(unknown_diagnostics),
        "unknownResolutionAudit": unknown_resolution_audit_report(
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


def enrich_semantic_diagnostic(diagnostic: dict[str, object]) -> dict[str, object]:
    content = str(diagnostic.get("content", ""))
    token_count = integer(diagnostic.get("tokenCount"))
    cause = str(diagnostic.get("cause", ""))
    themes = infer_semantic_themes(content)
    is_formatting = is_formatting_issue(content, token_count, cause)
    primary_theme = themes[0]["theme"] if themes and not is_formatting else "Formatting Issue"
    return {
        **diagnostic,
        "semanticThemes": themes,
        "primarySemanticTheme": primary_theme,
        "isFormattingIssue": is_formatting,
        "groupingBasis": "formatting" if is_formatting else "semantic",
    }


def infer_semantic_themes(content: str) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for theme, description, pattern in SEMANTIC_THEMES:
        if pattern.search(content):
            matches.append(
                {
                    "theme": theme,
                    "description": description,
                    "confidence": semantic_theme_confidence(theme, content),
                }
            )
    matches.sort(key=lambda item: (-float_value(item["confidence"]), str(item["theme"])))
    return matches


def semantic_theme_confidence(theme: str, content: str) -> float:
    lowered = content.lower()
    strong_patterns = {
        "Architecture": r"\b(architecture|microservice|monolith|pattern)\b",
        "Constraint": r"\b(must|cannot|required|constraint)\b",
        "Principle": r"\b(principle|guideline|best practice)\b",
        "Decision": r"\b(decided|adopted|standard is)\b",
        "Dependency": r"\b(depends on|blocked by|requires)\b",
        "Workflow Rule": r"\b(workflow|process|before deploy|after merge)\b",
        "Context": r"\b(context for|background|relates to)\b",
    }
    pattern = strong_patterns.get(theme)
    if pattern and re.search(pattern, lowered):
        return 0.85
    return 0.65


def is_formatting_issue(content: str, token_count: int, cause: str) -> bool:
    themes = infer_semantic_themes(content)
    if themes and any(float_value(theme.get("confidence")) >= 0.8 for theme in themes):
        return False
    if cause == "terse_or_fragmented_memory":
        return True
    if token_count <= 4 and not themes:
        return True
    return bool(re.fullmatch(r"[\w\s\-./:+]{1,24}", content.strip()))


def semantic_theme_analysis_report(
    diagnostics: Sequence[dict[str, object]],
) -> dict[str, object]:
    formatting = [item for item in diagnostics if item.get("isFormattingIssue")]
    meaningful = [item for item in diagnostics if not item.get("isFormattingIssue")]
    candidate_categories = semantic_candidate_categories(meaningful)
    return {
        "summary": (
            "Semantic Theme Analysis groups Unknown memories by meaning rather than "
            "lexical shape. Formatting issues are separated from semantic concepts."
        ),
        "formattingIssues": formatting_issue_summary(formatting),
        "candidateSemanticCategories": candidate_categories,
        "recurringConcepts": [
            {
                "concept": candidate["label"],
                "evidenceCount": candidate["memoryCount"],
                "categoryPurity": candidate["categoryPurity"],
            }
            for candidate in candidate_categories[:10]
        ],
        "meaningfulUnknownCount": len(meaningful),
        "formattingIssueCount": len(formatting),
    }


def semantic_candidate_categories(
    diagnostics: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for diagnostic in diagnostics:
        theme = str(diagnostic.get("primarySemanticTheme", "Unclassified Meaning"))
        if theme != "Formatting Issue":
            grouped[theme].append(diagnostic)

    candidates = []
    for theme, items in grouped.items():
        confidences = [
            float_value(match["confidence"])
            for item in items
            for match in list_value(item.get("semanticThemes"))
            if isinstance(match, dict) and match.get("theme") == theme
        ]
        avg_confidence = round(sum(confidences) / len(confidences), 4) if confidences else 0.5
        purity = category_purity(theme, items)
        candidates.append(
            {
                "label": theme,
                "memoryCount": len(items),
                "percentageOfUnknown": percentage(len(items), len(diagnostics)),
                "categoryPurity": purity,
                "confidence": avg_confidence,
                "representativeExamples": representative_examples(items),
                "recurringConcepts": recurring_concepts_for(items),
                "suggestedMapping": semantic_mapping_suggestion(theme),
                "description": semantic_theme_description(theme),
            }
        )
    return sorted(
        candidates,
        key=lambda item: (-integer(item["memoryCount"]), -float_value(item["categoryPurity"])),
    )


def category_purity(theme: str, items: Sequence[dict[str, object]]) -> float:
    if not items:
        return 0.0
    aligned = sum(1 for item in items if item.get("primarySemanticTheme") == theme)
    strong = sum(
        1
        for item in items
        for match in list_value(item.get("semanticThemes"))
        if isinstance(match, dict)
        and match.get("theme") == theme
        and float_value(match.get("confidence")) >= 0.8
    )
    alignment = aligned / len(items)
    strength = strong / len(items)
    return round((alignment * 0.6) + (strength * 0.4), 4)


def recurring_concepts_for(items: Sequence[dict[str, object]]) -> list[str]:
    counter: Counter[str] = Counter()
    for item in items:
        for match in list_value(item.get("semanticThemes")):
            if isinstance(match, dict):
                counter[str(match.get("theme"))] += 1
    return [theme for theme, _ in counter.most_common(5)]


def formatting_issue_summary(
    diagnostics: Sequence[dict[str, object]],
) -> dict[str, object]:
    return {
        "count": len(diagnostics),
        "description": (
            "Memories that appear Unknown due to brevity or formatting rather than "
            "missing semantic category coverage."
        ),
        "representativeExamples": representative_examples(diagnostics),
        "categoryPurity": 1.0 if diagnostics else 0.0,
    }


def semantic_theme_description(theme: str) -> str:
    for label, description, _pattern in SEMANTIC_THEMES:
        if label == theme:
            return description
    return "Semantic theme inferred from Unknown memory content."


def semantic_mapping_suggestion(theme: str) -> str:
    suggestions = {
        "Architecture": "Consider Architecture as a first-class memory type.",
        "Constraint": "Consider Constraint as a first-class memory type.",
        "Principle": "Consider Principle as a first-class memory type.",
        "Decision": "Consider Decision as a first-class memory type.",
        "Dependency": "Map to Relationship or add Dependency memory type.",
        "Workflow Rule": "Consider Workflow Rule as a first-class memory type.",
        "Context": "Map to Relationship or add Context memory type.",
        "Unclassified Meaning": "Inspect examples before proposing taxonomy changes.",
    }
    return suggestions.get(theme, "Inspect semantic evidence before taxonomy changes.")


def list_value(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return []


def unknown_resolution_audit_report(
    diagnostics: Sequence[dict[str, object]],
    total_memories: int,
    unknown_count: int,
) -> dict[str, object]:
    memory_resolutions = [
        classify_unknown_resolution(diagnostic) for diagnostic in diagnostics
    ]
    classifier_failures = [
        item for item in memory_resolutions if item["resolutionType"] == "classifier_failure"
    ]
    taxonomy_gaps = [
        item for item in memory_resolutions if item["resolutionType"] == "taxonomy_gap"
    ]
    unresolved = [
        item for item in memory_resolutions if item["resolutionType"] == "unresolved"
    ]
    fixable_count = len(classifier_failures) + len(taxonomy_gaps)
    return {
        "summary": (
            "Unknown Resolution Audit estimates how much Unknown can be fixed by improving "
            "categorization versus expanding the taxonomy."
        ),
        "classifierFailureCount": len(classifier_failures),
        "taxonomyGapCount": len(taxonomy_gaps),
        "unresolvedCount": len(unresolved),
        "estimatedUnknownReduction": percentage(fixable_count, total_memories),
        "estimatedClassifierReduction": percentage(len(classifier_failures), total_memories),
        "estimatedTaxonomyGapReduction": percentage(len(taxonomy_gaps), total_memories),
        "classifierFailureRate": percentage(len(classifier_failures), unknown_count),
        "taxonomyGapRate": percentage(len(taxonomy_gaps), unknown_count),
        "unresolvedRate": percentage(len(unresolved), unknown_count),
        "topRecurringCauses": top_resolution_causes(memory_resolutions),
        "resolutionGroups": resolution_groups(memory_resolutions, unknown_count),
        "memoryResolutions": memory_resolutions,
    }


def classify_unknown_resolution(diagnostic: dict[str, object]) -> dict[str, object]:
    cause = str(diagnostic.get("cause", ""))
    metadata = cause_metadata(cause)
    mapping_confidence = float_value(diagnostic.get("mappingConfidence"))
    suggested_category = str(diagnostic.get("suggestedCategory", MemoryCategory.UNKNOWN.value))
    themes = [
        match
        for match in list_value(diagnostic.get("semanticThemes"))
        if isinstance(match, dict)
    ]
    theme_confidence = max(
        (float_value(match.get("confidence")) for match in themes),
        default=0.0,
    )
    is_formatting = bool(diagnostic.get("isFormattingIssue"))
    base_issue = metadata["issueType"]

    if (
        suggested_category != MemoryCategory.UNKNOWN.value
        and base_issue == "classifier_failure"
        and mapping_confidence >= 0.55
    ):
        resolution_type = "classifier_failure"
        confidence = round(mapping_confidence, 4)
        rationale = (
            "Likely belongs to an existing category; current heuristics did not capture "
            f"the memory shape well enough to assign {suggested_category}."
        )
    elif base_issue == "taxonomy_gap" and cause != "no_recognized_category_signal":
        resolution_type = "taxonomy_gap"
        confidence = round(max(mapping_confidence, 0.5), 4)
        rationale = metadata["description"]
    elif themes and not is_formatting:
        resolution_type = "taxonomy_gap"
        confidence = round(max(theme_confidence, mapping_confidence, 0.55), 4)
        rationale = (
            "Memory expresses a semantic concept that may require taxonomy expansion "
            f"or broader category scope ({diagnostic.get('primarySemanticTheme')})."
        )
    elif is_formatting:
        resolution_type = "taxonomy_gap"
        confidence = round(max(mapping_confidence, 0.45), 4)
        rationale = (
            "Memory appears Unknown due to brevity or formatting rather than a missing "
            "classifier rule for an existing category."
        )
    elif (
        suggested_category != MemoryCategory.UNKNOWN.value
        and mapping_confidence >= 0.55
    ):
        resolution_type = "classifier_failure"
        confidence = round(mapping_confidence, 4)
        rationale = (
            f"Diagnostic mapping suggests {suggested_category} with sufficient confidence."
        )
    elif cause == "no_recognized_category_signal" and mapping_confidence < 0.35:
        resolution_type = "unresolved"
        confidence = round(max(0.35, 1.0 - mapping_confidence), 4)
        rationale = (
            "Insufficient evidence to recommend classifier improvement or taxonomy expansion."
        )
    elif base_issue == "taxonomy_gap":
        resolution_type = "taxonomy_gap"
        confidence = round(mapping_confidence, 4)
        rationale = metadata["description"]
    else:
        resolution_type = "unresolved"
        confidence = round(max(0.3, mapping_confidence), 4)
        rationale = "Resolution path is ambiguous; inspect manually before changing taxonomy."

    return {
        "memoryId": diagnostic.get("memoryId"),
        "content": diagnostic.get("content"),
        "cause": cause,
        "causeLabel": metadata["label"],
        "resolutionType": resolution_type,
        "confidence": confidence,
        "suggestedCategory": suggested_category,
        "rationale": rationale,
    }


def top_resolution_causes(
    memory_resolutions: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for resolution in memory_resolutions:
        grouped[str(resolution.get("cause", ""))].append(resolution)

    causes = []
    for cause, items in grouped.items():
        metadata = cause_metadata(cause)
        resolution_counter = Counter(str(item.get("resolutionType", "")) for item in items)
        dominant_resolution = resolution_counter.most_common(1)[0][0]
        causes.append(
            {
                "cause": cause,
                "label": metadata["label"],
                "count": len(items),
                "percentageOfUnknown": percentage(len(items), len(memory_resolutions)),
                "dominantResolutionType": dominant_resolution,
                "resolutionBreakdown": {
                    resolution_type: resolution_counter[resolution_type]
                    for resolution_type in (
                        "classifier_failure",
                        "taxonomy_gap",
                        "unresolved",
                    )
                    if resolution_counter[resolution_type] > 0
                },
                "representativeExamples": resolution_examples(items),
            }
        )
    return sorted(
        causes,
        key=lambda item: (-integer(item["count"]), str(item["cause"])),
    )[:10]


def resolution_groups(
    memory_resolutions: Sequence[dict[str, object]],
    unknown_count: int,
) -> list[dict[str, object]]:
    grouped: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for resolution in memory_resolutions:
        grouped[str(resolution.get("resolutionType", ""))].append(resolution)

    groups = []
    labels = {
        "classifier_failure": "Classifier failure",
        "taxonomy_gap": "Taxonomy gap",
        "unresolved": "Unresolved",
    }
    descriptions = {
        "classifier_failure": (
            "Unknown memories likely fixable by improving categorization heuristics."
        ),
        "taxonomy_gap": (
            "Unknown memories likely requiring taxonomy expansion or explicit product decisions."
        ),
        "unresolved": (
            "Unknown memories without enough evidence to recommend a resolution path."
        ),
    }
    for resolution_type in ("classifier_failure", "taxonomy_gap", "unresolved"):
        items = grouped.get(resolution_type, [])
        if not items:
            continue
        cause_counter = Counter(str(item.get("cause", "")) for item in items)
        groups.append(
            {
                "resolutionType": resolution_type,
                "label": labels[resolution_type],
                "description": descriptions[resolution_type],
                "count": len(items),
                "percentageOfUnknown": percentage(len(items), unknown_count),
                "representativeExamples": resolution_examples(items),
                "topCauses": [
                    {
                        "cause": cause,
                        "label": cause_metadata(cause)["label"],
                        "count": count,
                    }
                    for cause, count in cause_counter.most_common(5)
                ],
            }
        )
    return groups


def resolution_examples(items: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    ranked = sorted(
        items,
        key=lambda item: (-float_value(item.get("confidence")), str(item.get("memoryId"))),
    )
    return [
        {
            "memoryId": item.get("memoryId"),
            "content": item.get("content"),
            "confidence": item.get("confidence"),
            "cause": item.get("cause"),
            "resolutionType": item.get("resolutionType"),
        }
        for item in ranked[:5]
    ]


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
