from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from memd.categorization import categorize_records
from memd.contracts import CategorizedMemory, MemoryCategory, MemoryRecord
from memd.normalization import normalize_records
from memd.parser.loaders import (
    ParserError,
    detect_encoding,
    load_csv,
    load_json,
    load_jsonl,
    load_txt,
)

ASSISTANT_OPENER = re.compile(
    r"^(?:sure|certainly|absolutely|of course|great question|i'd be happy|"
    r"congratulations|here'?s|to solve this|to answer your question)",
    re.IGNORECASE,
)
CODE_BLOCK = re.compile(r"```|<script>|import\s+\w+|def\s+\w+\(", re.IGNORECASE)
PUZZLE = re.compile(r"\bpuzzle|riddle|brain teaser|fox.*chicken|help the farmer\b", re.IGNORECASE)
ROLEPLAY = re.compile(
    r"\b(?:rewrite the script|write the script|fade out|int\.|ext\.|characters:)\b",
    re.IGNORECASE,
)
PERSONAL_FACT = re.compile(
    r"\b(?:i am|i'm|my |i have|i bought|i got|i use|i prefer|i graduated|"
    r"i changed|i repainted|i volunteer|i spend|i created|i attend)\b",
    re.IGNORECASE,
)
INSTRUCTIONAL = re.compile(
    r"\b(?:here are \d+|follow these steps|lesson plan|objectives:|materials:|procedure:)\b",
    re.IGNORECASE,
)
GENERIC_ASSISTANT = re.compile(
    r"\b(?:feel free to ask|hope this helps|let me know if|good luck|"
    r"keep up the good work|don't hesitate to reach out)\b",
    re.IGNORECASE,
)
QUESTION_ONLY = re.compile(
    r"^(?:can you|could you|what|how|where|when|why|do you)\b",
    re.IGNORECASE,
)

LOW_QUALITY_CAUSE_LABELS = {
    "assistant_turn": "Assistant conversational turn",
    "assistant_instructional_dump": "Assistant instructional or list-style response",
    "assistant_generic_filler": "Assistant generic encouragement or filler",
    "user_ephemeral_query": "Short user query without durable memory signal",
    "puzzle_or_hypothetical": "Puzzle, riddle, or hypothetical scenario",
    "roleplay_or_creative_writing": "Roleplay, script, or creative writing task",
    "code_generation": "Code generation or programming artifact",
    "terse_or_fragmented": "Terse or fragmented content",
    "unknown_category_signal": "No strong Mem-D category signal",
    "exact_duplicate_content": "Exact duplicate normalized content",
    "low_information_density": "Low information density or weak factual anchors",
}


@dataclass(frozen=True)
class DatasetQualityAudit:
    datasetPath: str
    datasetName: str
    datasetKind: str
    totalRecords: int
    estimatedMeaningfulMemories: int
    estimatedConversationalNoise: int
    estimatedMixedOrUncertain: int
    meaningfulMemoryRate: float
    conversationalNoiseRate: float
    averageMemoryLength: float
    categoryDistribution: dict[str, int]
    unknownRate: float
    duplicateRate: float
    topLowQualityCauses: list[dict[str, object]]
    benchmarkSuitability: dict[str, object]
    preprocessingRecommendations: list[str]
    roleDistribution: dict[str, int]
    sampleLowQualityRecords: list[dict[str, object]]
    sampleMeaningfulRecords: list[dict[str, object]]


def audit_external_datasets(paths: Sequence[Path]) -> dict[str, object]:
    audits = [audit_external_dataset(path) for path in paths]
    return {
        "summary": (
            "Dataset Quality Audit measures memory usefulness for external benchmark "
            "datasets. Diagnostic only; it does not modify ingestion or analysis behavior."
        ),
        "datasetCount": len(audits),
        "datasets": [audit_to_dict(audit) for audit in audits],
        "benchmarkReadiness": benchmark_readiness_summary(audits),
    }


def audit_external_dataset(path: Path) -> DatasetQualityAudit:
    path = path.resolve()
    if path.suffix.lower() == ".jsonl":
        records = load_jsonl_dataset(path)
    elif path.suffix.lower() == ".json":
        records = load_json(path)
    elif path.suffix.lower() == ".csv":
        records = load_csv(path)
    elif path.suffix.lower() == ".txt":
        records = load_txt(path)
    else:
        raise ParserError(f"Unsupported dataset format: {path.suffix or '<none>'}")

    records = normalize_records(records)
    if is_benchmark_questions_file(records):
        return audit_benchmark_questions(path, records)

    categories = categorize_records(records)
    categories_by_id = {category.memoryId: category for category in categories}
    duplicate_ids = exact_duplicate_ids(records)

    assessments = [
        assess_memory_usefulness(record, categories_by_id[record.id], duplicate_ids)
        for record in records
    ]
    cause_counter: Counter[str] = Counter()
    for assessment in assessments:
        cause_counter.update(assessment["causes"])

    meaningful = sum(1 for item in assessments if item["classification"] == "meaningful")
    noise = sum(1 for item in assessments if item["classification"] == "noise")
    mixed = len(assessments) - meaningful - noise
    total = len(records)
    category_distribution = Counter(
        categories_by_id[record.id].category.value for record in records
    )
    unknown_count = category_distribution.get(MemoryCategory.UNKNOWN.value, 0)
    duplicate_count = sum(1 for item in assessments if "exact_duplicate_content" in item["causes"])
    role_distribution = Counter(str(record.metadata.get("role", "unknown")) for record in records)
    top_causes = top_low_quality_causes(cause_counter, total)
    suitability = benchmark_suitability(
        total=total,
        meaningful=meaningful,
        noise=noise,
        unknown_rate=percentage(unknown_count, total),
        duplicate_rate=percentage(duplicate_count, total),
        top_causes=top_causes,
        role_distribution=dict(role_distribution),
    )

    return DatasetQualityAudit(
        datasetPath=str(path),
        datasetName=path.name,
        datasetKind="memory_export",
        totalRecords=total,
        estimatedMeaningfulMemories=meaningful,
        estimatedConversationalNoise=noise,
        estimatedMixedOrUncertain=mixed,
        meaningfulMemoryRate=percentage(meaningful, total),
        conversationalNoiseRate=percentage(noise, total),
        averageMemoryLength=round(
            sum(len(record.content) for record in records) / total,
            2,
        )
        if total
        else 0.0,
        categoryDistribution=dict(category_distribution),
        unknownRate=percentage(unknown_count, total),
        duplicateRate=percentage(duplicate_count, total),
        topLowQualityCauses=top_causes,
        benchmarkSuitability=suitability,
        preprocessingRecommendations=preprocessing_recommendations(top_causes, suitability),
        roleDistribution=dict(role_distribution),
        sampleLowQualityRecords=sample_records(records, assessments, "noise"),
        sampleMeaningfulRecords=sample_records(records, assessments, "meaningful"),
    )


def audit_benchmark_questions(path: Path, records: Sequence[MemoryRecord]) -> DatasetQualityAudit:
    question_types = Counter(
        str(record.metadata.get("question_type", "unknown")) for record in records
    )
    return DatasetQualityAudit(
        datasetPath=str(path.resolve()),
        datasetName=path.name,
        datasetKind="benchmark_questions",
        totalRecords=len(records),
        estimatedMeaningfulMemories=0,
        estimatedConversationalNoise=0,
        estimatedMixedOrUncertain=0,
        meaningfulMemoryRate=0.0,
        conversationalNoiseRate=0.0,
        averageMemoryLength=round(
            sum(len(record.content) for record in records) / len(records),
            2,
        )
        if records
        else 0.0,
        categoryDistribution={},
        unknownRate=0.0,
        duplicateRate=0.0,
        topLowQualityCauses=[],
        benchmarkSuitability={
            "verdict": "companion_benchmark_metadata",
            "confidence": 1.0,
            "summary": (
                "This file stores benchmark questions and answers, not memory records. "
                "Use it to evaluate retrieval against memory exports rather than as a "
                "direct Mem-D memory benchmark input."
            ),
            "questionTypeDistribution": dict(question_types),
        },
        preprocessingRecommendations=[
            "Pair question records with memory exports for end-to-end benchmark runs.",
            "Do not feed question files directly into memd analyze as memory input.",
        ],
        roleDistribution={},
        sampleLowQualityRecords=[],
        sampleMeaningfulRecords=[
            {
                "memoryId": record.id,
                "content": record.content,
                "metadata": {
                    "question_type": record.metadata.get("question_type"),
                    "answer": record.metadata.get("answer"),
                },
            }
            for record in list(records)[:5]
        ],
    )


def load_jsonl_dataset(path: Path) -> list[MemoryRecord]:
    encoding = detect_encoding(path)
    first_item = peek_jsonl_object(path, encoding)
    if first_item and "question" in first_item and "answer" in first_item:
        return load_questions_jsonl(path, encoding)
    return load_jsonl(path)


def peek_jsonl_object(path: Path, encoding: str) -> dict[str, object] | None:
    with path.open("r", encoding=encoding) as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            item = json.loads(stripped)
            if isinstance(item, dict):
                return item
            return None
    return None


def load_questions_jsonl(path: Path, encoding: str) -> list[MemoryRecord]:
    items: list[dict[str, object]] = []
    with path.open("r", encoding=encoding) as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                item = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ParserError(f"Invalid JSONL on line {line_number}: {exc}") from exc
            if not isinstance(item, dict):
                raise ParserError(f"JSONL line {line_number} must be a JSON object")
            items.append(item)
    if not items:
        raise ParserError("No records found in JSONL dataset")
    return records_from_question_items(items, source=str(path))


def records_from_question_items(
    items: Sequence[dict[str, object]],
    source: str,
) -> list[MemoryRecord]:
    records: list[MemoryRecord] = []
    for index, item in enumerate(items, start=1):
        content = str(item.get("question") or "")
        record_id = str(item.get("question_id") or f"{source}:{index}")
        metadata = {
            key: value
            for key, value in item.items()
            if key not in {"question_id", "question"}
        }
        if not content.strip():
            continue
        records.append(
            MemoryRecord(
                id=record_id,
                content=content.strip(),
                source=source,
                timestamp=str(item.get("timestamp")) if item.get("timestamp") else None,
                metadata=metadata,
            )
        )
    if not records:
        raise ParserError("No records found in JSONL dataset")
    return records


def is_benchmark_questions_file(records: Sequence[MemoryRecord]) -> bool:
    if not records:
        return False
    sample = records[0].metadata
    return "answer" in sample and "question_type" in sample


def assess_memory_usefulness(
    record: MemoryRecord,
    category: CategorizedMemory,
    duplicate_ids: set[str],
) -> dict[str, object]:
    content = record.content.strip()
    role = str(record.metadata.get("role", "")).lower()
    causes: list[str] = []
    score = 0.55

    if role == "assistant":
        score -= 0.35
        causes.append("assistant_turn")
        if INSTRUCTIONAL.search(content) or numbered_list_density(content) >= 0.2:
            score -= 0.15
            causes.append("assistant_instructional_dump")
        if GENERIC_ASSISTANT.search(content) or ASSISTANT_OPENER.search(content):
            score -= 0.1
            causes.append("assistant_generic_filler")
    elif role == "user":
        score += 0.15
        if PERSONAL_FACT.search(content):
            score += 0.2
        if QUESTION_ONLY.search(content) and len(content) < 180:
            score -= 0.15
            causes.append("user_ephemeral_query")

    if PUZZLE.search(content):
        score -= 0.25
        causes.append("puzzle_or_hypothetical")
    if ROLEPLAY.search(content):
        score -= 0.25
        causes.append("roleplay_or_creative_writing")
    if CODE_BLOCK.search(content):
        score -= 0.2
        causes.append("code_generation")
    if len(content.split()) <= 8:
        score -= 0.15
        causes.append("terse_or_fragmented")
    if category.category == MemoryCategory.UNKNOWN:
        score -= 0.1
        causes.append("unknown_category_signal")
    if record.id in duplicate_ids:
        score -= 0.2
        causes.append("exact_duplicate_content")
    if information_density(content) < 0.08:
        score -= 0.1
        causes.append("low_information_density")

    if score >= 0.65:
        classification = "meaningful"
    elif score <= 0.45:
        classification = "noise"
    else:
        classification = "mixed"

    return {
        "memoryId": record.id,
        "classification": classification,
        "usefulnessScore": round(max(0.0, min(1.0, score)), 4),
        "causes": causes,
    }


def exact_duplicate_ids(records: Sequence[MemoryRecord]) -> set[str]:
    grouped: defaultdict[str, list[str]] = defaultdict(list)
    for record in records:
        normalized = re.sub(r"\s+", " ", record.content.strip().lower())
        grouped[normalized].append(record.id)
    duplicate_ids: set[str] = set()
    for ids in grouped.values():
        if len(ids) > 1:
            duplicate_ids.update(ids)
    return duplicate_ids


def top_low_quality_causes(counter: Counter[str], total: int) -> list[dict[str, object]]:
    return [
        {
            "cause": cause,
            "label": LOW_QUALITY_CAUSE_LABELS.get(cause, cause),
            "count": count,
            "percentageOfRecords": percentage(count, total),
        }
        for cause, count in counter.most_common(10)
    ]


def benchmark_suitability(
    total: int,
    meaningful: int,
    noise: int,
    unknown_rate: float,
    duplicate_rate: float,
    top_causes: Sequence[dict[str, object]],
    role_distribution: dict[str, int],
) -> dict[str, object]:
    meaningful_rate = percentage(meaningful, total)
    noise_rate = percentage(noise, total)
    assistant_rate = percentage(role_distribution.get("assistant", 0), total)

    if meaningful_rate >= 45 and noise_rate <= 35 and unknown_rate <= 50:
        verdict = "suitable_with_filtering"
        summary = (
            "Dataset contains enough likely durable memories for Mem-D benchmarking, "
            "but preprocessing or filtering is recommended before analysis."
        )
        confidence = 0.78
    elif meaningful_rate >= 25:
        verdict = "requires_preprocessing"
        summary = (
            "Dataset has benchmark potential, but conversational noise or weak memory "
            "signals are high enough that filtering is required."
        )
        confidence = 0.66
    else:
        verdict = "poor_fit"
        summary = (
            "Dataset appears dominated by conversational turns or low-usefulness content "
            "and is a weak direct fit for Mem-D memory analysis benchmarks."
        )
        confidence = 0.72

    if assistant_rate >= 45:
        confidence = round(min(confidence, 0.7), 2)
    if duplicate_rate >= 10:
        confidence = round(min(confidence, 0.75), 2)

    return {
        "verdict": verdict,
        "confidence": confidence,
        "summary": summary,
        "meaningfulMemoryRate": meaningful_rate,
        "conversationalNoiseRate": noise_rate,
        "unknownRate": unknown_rate,
        "duplicateRate": duplicate_rate,
        "assistantTurnRate": assistant_rate,
        "dominantLowQualityCause": top_causes[0]["cause"] if top_causes else None,
    }


def preprocessing_recommendations(
    top_causes: Sequence[dict[str, object]],
    suitability: dict[str, object],
) -> list[str]:
    recommendations: list[str] = []
    cause_set = {str(item.get("cause")) for item in top_causes}

    if "assistant_turn" in cause_set:
        recommendations.append("Filter assistant turns before benchmarking durable user memory.")
    if "assistant_instructional_dump" in cause_set:
        recommendations.append("Remove long instructional assistant list responses.")
    if "user_ephemeral_query" in cause_set:
        recommendations.append("Separate ephemeral user questions from durable memory facts.")
    if "puzzle_or_hypothetical" in cause_set or "roleplay_or_creative_writing" in cause_set:
        recommendations.append("Exclude puzzle, roleplay, and creative-writing sessions.")
    if "code_generation" in cause_set:
        recommendations.append("Exclude code-generation artifacts unless testing technical memory.")
    if "exact_duplicate_content" in cause_set:
        recommendations.append("Deduplicate exact normalized content before clustering benchmarks.")
    if float(suitability.get("unknownRate", 0)) >= 35:
        recommendations.append(
            "Expect high Unknown categorization; usefulness filtering matters more "
            "than taxonomy tuning."
        )
    if not recommendations:
        recommendations.append("No major preprocessing blockers detected from usefulness signals.")
    return recommendations


def benchmark_readiness_summary(audits: Sequence[DatasetQualityAudit]) -> dict[str, object]:
    memory_audits = [audit for audit in audits if audit.datasetKind == "memory_export"]
    if not memory_audits:
        return {
            "summary": "No memory export datasets were audited.",
            "recommendedDataset": None,
        }
    ranked = sorted(
        memory_audits,
        key=lambda audit: (
            -audit.meaningfulMemoryRate,
            audit.conversationalNoiseRate,
            audit.unknownRate,
        ),
    )
    best = ranked[0]
    return {
        "summary": (
            "Compare memory exports by meaningful-memory rate, conversational noise, and "
            "Unknown rate before choosing a Mem-D benchmark dataset."
        ),
        "recommendedDataset": best.datasetName,
        "recommendedVerdict": best.benchmarkSuitability.get("verdict"),
        "datasets": [
            {
                "datasetName": audit.datasetName,
                "verdict": audit.benchmarkSuitability.get("verdict"),
                "meaningfulMemoryRate": audit.meaningfulMemoryRate,
                "conversationalNoiseRate": audit.conversationalNoiseRate,
            }
            for audit in ranked
        ],
    }


def sample_records(
    records: Sequence[MemoryRecord],
    assessments: Sequence[dict[str, object]],
    classification: str,
) -> list[dict[str, object]]:
    by_id = {record.id: record for record in records}
    selected = [
        assessment
        for assessment in assessments
        if assessment["classification"] == classification
    ]
    selected.sort(key=lambda item: float(item["usefulnessScore"]))
    samples = []
    for assessment in selected[:5]:
        record = by_id[str(assessment["memoryId"])]
        samples.append(
            {
                "memoryId": record.id,
                "content": record.content[:240],
                "role": record.metadata.get("role"),
                "usefulnessScore": assessment["usefulnessScore"],
                "causes": assessment["causes"],
            }
        )
    return samples


def numbered_list_density(content: str) -> float:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return 0.0
    numbered = sum(1 for line in lines if re.match(r"^\d+[\).]", line))
    return numbered / len(lines)


def information_density(content: str) -> float:
    tokens = re.findall(r"[a-z0-9]+", content.lower())
    if not tokens:
        return 0.0
    unique = len(set(tokens))
    return unique / len(tokens)


def percentage(part: int, whole: int) -> float:
    if whole == 0:
        return 0.0
    return round((part / whole) * 100, 2)


def audit_to_dict(audit: DatasetQualityAudit) -> dict[str, object]:
    return {
        "datasetPath": audit.datasetPath,
        "datasetName": audit.datasetName,
        "datasetKind": audit.datasetKind,
        "totalRecords": audit.totalRecords,
        "estimatedMeaningfulMemories": audit.estimatedMeaningfulMemories,
        "estimatedConversationalNoise": audit.estimatedConversationalNoise,
        "estimatedMixedOrUncertain": audit.estimatedMixedOrUncertain,
        "meaningfulMemoryRate": audit.meaningfulMemoryRate,
        "conversationalNoiseRate": audit.conversationalNoiseRate,
        "averageMemoryLength": audit.averageMemoryLength,
        "categoryDistribution": audit.categoryDistribution,
        "unknownRate": audit.unknownRate,
        "duplicateRate": audit.duplicateRate,
        "topLowQualityCauses": audit.topLowQualityCauses,
        "benchmarkSuitability": audit.benchmarkSuitability,
        "preprocessingRecommendations": audit.preprocessingRecommendations,
        "roleDistribution": audit.roleDistribution,
        "sampleLowQualityRecords": audit.sampleLowQualityRecords,
        "sampleMeaningfulRecords": audit.sampleMeaningfulRecords,
    }


def render_dataset_quality_json(report: dict[str, object]) -> str:
    return json.dumps(report, indent=2)


def render_dataset_quality_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Dataset Quality Audit",
        "",
        str(report.get("summary", "")),
        "",
    ]
    readiness = report.get("benchmarkReadiness", {})
    if isinstance(readiness, dict) and readiness.get("recommendedDataset"):
        lines.extend(
            [
                "## Benchmark Readiness",
                "",
                f"- Recommended dataset: {readiness.get('recommendedDataset')}",
                f"- Recommended verdict: {readiness.get('recommendedVerdict')}",
                "",
            ]
        )

    datasets = report.get("datasets", [])
    if isinstance(datasets, list):
        for dataset in datasets:
            if not isinstance(dataset, dict):
                continue
            lines.extend(render_dataset_section_markdown(dataset))
    return "\n".join(lines).strip() + "\n"


def render_dataset_section_markdown(dataset: dict[str, object]) -> list[str]:
    suitability = dataset.get("benchmarkSuitability", {})
    if not isinstance(suitability, dict):
        suitability = {}
    lines = [
        f"## {dataset.get('datasetName')}",
        "",
        f"- Path: `{dataset.get('datasetPath')}`",
        f"- Kind: {dataset.get('datasetKind')}",
        f"- Total records: {dataset.get('totalRecords')}",
        f"- Estimated meaningful memories: {dataset.get('estimatedMeaningfulMemories')} "
        f"({dataset.get('meaningfulMemoryRate')}%)",
        f"- Estimated conversational noise: {dataset.get('estimatedConversationalNoise')} "
        f"({dataset.get('conversationalNoiseRate')}%)",
        f"- Mixed or uncertain: {dataset.get('estimatedMixedOrUncertain')}",
        f"- Average memory length: {dataset.get('averageMemoryLength')} characters",
        f"- Unknown rate: {dataset.get('unknownRate')}%",
        f"- Duplicate rate: {dataset.get('duplicateRate')}%",
        f"- Benchmark verdict: {suitability.get('verdict')}",
        f"- Benchmark summary: {suitability.get('summary')}",
        "",
    ]

    categories = dataset.get("categoryDistribution", {})
    if isinstance(categories, dict) and categories:
        lines.append("Category distribution:")
        for label, count in sorted(categories.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {label}: {count}")
        lines.append("")

    roles = dataset.get("roleDistribution", {})
    if isinstance(roles, dict) and roles:
        lines.append("Role distribution:")
        for label, count in sorted(roles.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {label}: {count}")
        lines.append("")

    causes = dataset.get("topLowQualityCauses", [])
    if isinstance(causes, list) and causes:
        lines.extend(
            [
                "Top low-quality causes:",
                "",
                "| Cause | Count | % of records |",
                "| --- | ---: | ---: |",
            ]
        )
        for cause in causes[:10]:
            if isinstance(cause, dict):
                lines.append(
                    f"| {cause.get('label')} | {cause.get('count')} | "
                    f"{cause.get('percentageOfRecords')}% |"
                )
        lines.append("")

    recommendations = dataset.get("preprocessingRecommendations", [])
    if isinstance(recommendations, list) and recommendations:
        lines.append("Preprocessing recommendations:")
        for recommendation in recommendations:
            lines.append(f"- {recommendation}")
        lines.append("")

    return lines


def render_dataset_quality_terminal(report: dict[str, object], console) -> None:
    console.print("[bold]Dataset Quality Audit[/bold]")
    datasets = report.get("datasets", [])
    if not isinstance(datasets, list):
        return
    for dataset in datasets:
        if not isinstance(dataset, dict):
            continue
        suitability = dataset.get("benchmarkSuitability", {})
        if not isinstance(suitability, dict):
            suitability = {}
        console.print(f"[bold]{dataset.get('datasetName')}[/bold] ({dataset.get('datasetKind')})")
        console.print(f"Total records: [bold]{dataset.get('totalRecords')}[/bold]")
        console.print(
            "Meaningful memories: "
            f"[bold]{dataset.get('estimatedMeaningfulMemories')}[/bold] "
            f"({dataset.get('meaningfulMemoryRate')}%)"
        )
        console.print(
            "Conversational noise: "
            f"[bold]{dataset.get('estimatedConversationalNoise')}[/bold] "
            f"({dataset.get('conversationalNoiseRate')}%)"
        )
        console.print(f"Unknown rate: [bold]{dataset.get('unknownRate')}[/bold]%")
        console.print(f"Duplicate rate: [bold]{dataset.get('duplicateRate')}[/bold]%")
        console.print(
            "Benchmark verdict: "
            f"[bold]{suitability.get('verdict')}[/bold] — {suitability.get('summary')}"
        )
        causes = dataset.get("topLowQualityCauses", [])
        if isinstance(causes, list) and causes:
            first = causes[0] if isinstance(causes[0], dict) else {}
            console.print(
                "Top low-quality cause: "
                f"[bold]{first.get('label', '')}[/bold] ({first.get('count', 0)} records)."
            )
        console.print("")


def collect_dataset_paths(paths: Sequence[Path]) -> list[Path]:
    collected: list[Path] = []
    for path in paths:
        if path.is_dir():
            collected.extend(
                sorted(
                    candidate
                    for candidate in path.iterdir()
                    if candidate.is_file()
                    and candidate.suffix.lower() in {".json", ".jsonl", ".csv", ".txt"}
                )
            )
        else:
            collected.append(path)
    if not collected:
        raise ParserError("No dataset files found to audit")
    return collected
