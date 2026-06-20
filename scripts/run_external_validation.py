from __future__ import annotations

import json
import re
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from huggingface_hub import hf_hub_download

from memd.contracts import RecommendationAction
from memd.pipeline import analyze_file
from memd.preprocessing.longmemeval import preprocess_longmemeval_jsonl
from memd.simulation import DUPLICATE_REMOVAL_CODE, ORPHAN_MERGE_CODE

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "datasets" / "external_validation"
RESULTS_DIR = OUT_DIR / "results"
MAX_ANALYZE_RECORDS = 250  # Runtime cap; full exports retained in metadata.


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    license_note: str
    source_note: str


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return len(records)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            if isinstance(item, dict):
                records.append(item)
    return records


def _stratified_sample_records(
    records: list[dict[str, Any]],
    *,
    max_records: int,
    group_key: str,
) -> list[dict[str, Any]]:
    if len(records) <= max_records:
        return records
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        metadata = record.get("metadata", {})
        group = "default"
        if isinstance(metadata, dict) and metadata.get(group_key):
            group = str(metadata[group_key])
        grouped.setdefault(group, []).append(record)

    per_group = max(1, max_records // max(len(grouped), 1))
    sampled: list[dict[str, Any]] = []
    for group_records in grouped.values():
        sampled.extend(group_records[:per_group])
    return sampled[:max_records]


def _prepare_analysis_slice(
    source_path: Path,
    *,
    group_key: str,
    max_records: int = MAX_ANALYZE_RECORDS,
) -> tuple[Path, int, int]:
    records = _load_jsonl(source_path)
    sampled = _stratified_sample_records(records, max_records=max_records, group_key=group_key)
    slice_path = source_path.with_suffix(".analysis.jsonl")
    _write_jsonl(slice_path, sampled)
    return slice_path, len(records), len(sampled)


def _render_value(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip())
    if value is None:
        return ""
    return str(value).strip()


def convert_longmemeval_oracle(
    *,
        max_instances: int = 50,
    raw_path: Path,
    output_path: Path,
) -> tuple[int, int]:
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Expected list payload in longmemeval_oracle.json")

    records: list[dict[str, Any]] = []
    instance_count = 0
    for item in payload[:max_instances]:
        if not isinstance(item, dict):
            continue
        instance_count += 1
        question_id = str(item.get("question_id", f"instance_{instance_count}"))
        haystack_sessions = item.get("haystack_sessions", [])
        if not isinstance(haystack_sessions, list):
            continue
        turn_index = 0
        for session in haystack_sessions:
            if not isinstance(session, list):
                continue
            for turn in session:
                if not isinstance(turn, dict):
                    continue
                role = str(turn.get("role", "")).lower()
                content = str(turn.get("content", "")).strip()
                if not content:
                    continue
                turn_index += 1
                records.append(
                    {
                        "id": f"lme_{question_id}_{turn_index}",
                        "content": content,
                        "timestamp": str(item.get("question_date", "")) or None,
                        "metadata": {
                            "source": "longmemeval_oracle",
                            "question_id": question_id,
                            "role": role,
                        },
                    }
                )

    count = _write_jsonl(output_path, records)
    return instance_count, count


def convert_locomo10(source_path: Path, output_path: Path) -> tuple[int, int]:
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Expected list payload in locomo10.json")

    records: list[dict[str, Any]] = []
    session_re = re.compile(r"^session_(\d+)$")
    for sample in payload:
        if not isinstance(sample, dict):
            continue
        sample_id = str(sample.get("sample_id", "unknown"))
        conversation = sample.get("conversation", {})
        if not isinstance(conversation, dict):
            continue
        session_numbers = sorted(
            int(match.group(1))
            for key in conversation
            if (match := session_re.match(str(key)))
        )
        for session_num in session_numbers:
            timestamp = conversation.get(f"session_{session_num}_date_time")
            turns = conversation.get(f"session_{session_num}", [])
            if not isinstance(turns, list):
                continue
            for turn in turns:
                if not isinstance(turn, dict):
                    continue
                text = str(turn.get("text", "")).strip()
                if not text:
                    continue
                dia_id = str(turn.get("dia_id", f"{sample_id}_{session_num}"))
                records.append(
                    {
                        "id": f"locomo_{sample_id}_{dia_id}",
                        "content": text,
                        "timestamp": str(timestamp) if timestamp else None,
                        "metadata": {
                            "source": "locomo10",
                            "sample_id": sample_id,
                            "speaker": str(turn.get("speaker", "")),
                        },
                    }
                )

    count = _write_jsonl(output_path, records)
    return len(payload), count


def convert_personalens_users(user_ids: list[str], output_path: Path) -> tuple[int, int]:
    records: list[dict[str, Any]] = []
    for user_id in user_ids:
        profile_path = hf_hub_download(
            "AmazonScience/PersonaLens",
            f"data/profile/user{user_id}/profile.json",
            repo_type="dataset",
        )
        tasks_path = hf_hub_download(
            "AmazonScience/PersonaLens",
            f"data/profile/user{user_id}/tasks.json",
            repo_type="dataset",
        )
        profile = json.loads(Path(profile_path).read_text(encoding="utf-8"))
        tasks = json.loads(Path(tasks_path).read_text(encoding="utf-8"))
        records.extend(_personalens_profile_memories(user_id, profile))
        records.extend(_personalens_task_memories(user_id, tasks))

    count = _write_jsonl(output_path, records)
    return len(user_ids), count


def _personalens_profile_memories(user_id: str, profile: dict[str, object]) -> list[dict[str, Any]]:
    memories: list[dict[str, Any]] = []
    affinities = profile.get("affinities")
    if not isinstance(affinities, dict):
        return memories
    counter = 0
    for domain, domain_payload in sorted(affinities.items()):
        if not isinstance(domain_payload, dict):
            continue
        for field, value in sorted(domain_payload.items()):
            rendered = _render_value(value)
            if not rendered:
                continue
            counter += 1
            memories.append(
                {
                    "id": f"pl_{user_id}_affinity_{counter}",
                    "content": f"User {user_id} preference in {domain}: {field} = {rendered}.",
                    "metadata": {"source": "personalens", "user_id": user_id},
                }
            )
    return memories


def _personalens_task_memories(user_id: str, tasks: dict[str, object]) -> list[dict[str, Any]]:
    memories: list[dict[str, Any]] = []
    counter = 0
    for task_name, payload in sorted(tasks.items()):
        if not isinstance(payload, dict):
            continue
        task_id = payload.get("task_id")
        intent = payload.get("User Intent")
        goal = payload.get("Task Goal")
        if isinstance(task_id, str) and isinstance(intent, str) and intent.strip():
            counter += 1
            memories.append(
                {
                    "id": f"pl_{user_id}_intent_{counter}",
                    "content": f"PersonaLens {task_id} intent: {intent.strip()}",
                    "metadata": {"source": "personalens", "taskName": task_name},
                }
            )
        if isinstance(task_id, str) and isinstance(goal, str) and goal.strip():
            counter += 1
            memories.append(
                {
                    "id": f"pl_{user_id}_goal_{counter}",
                    "content": f"PersonaLens {task_id} goal: {goal.strip()}",
                    "metadata": {"source": "personalens", "taskName": task_name},
                }
            )
    return memories


def collect_observations(
    dataset_name: str,
    input_path: Path,
    *,
    conversation_count: int,
    preprocess: bool = False,
    group_key: str = "source",
    export_record_count: int | None = None,
) -> dict[str, Any]:
    analyze_path = input_path
    preprocess_report: dict[str, object] | None = None
    if preprocess:
        cleaned_path = analyze_path.with_name(analyze_path.name.replace(".raw.jsonl", ".cleaned.jsonl"))
        report = preprocess_longmemeval_jsonl(analyze_path, cleaned_path)
        preprocess_report = report.to_dict()
        analyze_path = cleaned_path

    slice_path, full_count, sample_count = _prepare_analysis_slice(
        analyze_path,
        group_key=group_key,
    )
    report = analyze_file(slice_path)
    resolution_counts = Counter(
        resolution.resolvedAction.value for resolution in report.memoryResolutions
    )
    conflict_count = sum(1 for resolution in report.memoryResolutions if resolution.conflictDetected)

    simulation = report.simulationReport
    warning_codes: Counter[str] = Counter()
    orphan_count = 0
    explainability_gaps = 0
    sim_metrics: dict[str, Any] = {}
    if simulation is not None:
        sim_metrics = simulation.metrics.model_dump()
        for warning in simulation.simulationWarnings:
            warning_codes[warning.code] += 1
            if warning.code == ORPHAN_MERGE_CODE:
                orphan_count += 1
        for event in (
            *simulation.simulatedMerges,
            *simulation.simulatedArchives,
            *simulation.simulatedReviewQueue,
        ):
            if not event.explainability.evidenceRefs:
                explainability_gaps += 1

    total_resolutions = len(report.memoryResolutions) or 1
    review_rate = resolution_counts.get("review", 0) / total_resolutions

    return {
        "dataset": dataset_name,
        "inputPath": str(analyze_path),
        "analysisSlicePath": str(slice_path),
        "exportRecordCount": export_record_count if export_record_count is not None else full_count,
        "analysisRecordCount": sample_count,
        "conversationOrInstanceCount": conversation_count,
        "memoryCount": len(report.memories),
        "preprocess": preprocess_report,
        "metrics": {
            "duplicatePercentage": report.metrics.duplicatePercentage,
            "compressionOpportunity": report.metrics.compressionOpportunity,
            "trustedCompressionOpportunity": report.metrics.trustedCompressionOpportunity,
            "unknownRate": _unknown_rate(report),
        },
        "recommendations": {
            "totalRecommendations": len(report.recommendations),
            "resolutionCounts": dict(resolution_counts),
            "conflictCount": conflict_count,
            "reviewRate": round(review_rate, 4),
        },
        "simulation": {
            "present": simulation is not None,
            "metrics": sim_metrics,
            "warningCodes": dict(warning_codes),
            "orphanMergeWarnings": orphan_count,
            "explainabilityGaps": explainability_gaps,
        },
        "examples": _failure_examples(report, resolution_counts, review_rate),
    }


def _unknown_rate(report: Any) -> float:
    breakdown = report.metrics.categoryBreakdown
    total = sum(breakdown.values()) or 1
    unknown = breakdown.get("Unknown", 0)
    return round(unknown / total, 4)


def _failure_examples(
    report: Any,
    resolution_counts: Counter[str],
    review_rate: float,
) -> dict[str, Any]:
    examples: dict[str, Any] = {}
    if review_rate > 0.5:
        review_ids = [
            resolution.memoryId
            for resolution in report.memoryResolutions
            if resolution.resolvedAction == RecommendationAction.REVIEW
        ][:5]
        examples["highReviewRate"] = {
            "reviewRate": review_rate,
            "sampleMemoryIds": review_ids,
        }

    unknown_samples = (
        report.validation.get("categoryQuality", {}).get("unknownSamples", [])
        if isinstance(report.validation, dict)
        else []
    )
    if isinstance(unknown_samples, list) and unknown_samples:
        examples["unknownCategorySamples"] = unknown_samples[:3]

    conflict_samples = [
        {
            "memoryId": resolution.memoryId,
            "resolvedAction": resolution.resolvedAction.value,
            "suppressedActions": [action.value for action in resolution.suppressedActions],
        }
        for resolution in report.memoryResolutions
        if resolution.conflictDetected
    ][:3]
    if conflict_samples:
        examples["conflictCases"] = conflict_samples

    if resolution_counts.get("archive", 0) > resolution_counts.get("merge", 0) * 2:
        examples["archiveDominance"] = {
            "archive": resolution_counts.get("archive", 0),
            "merge": resolution_counts.get("merge", 0),
        }

    simulation = report.simulationReport
    if simulation is not None and simulation.simulationWarnings:
        examples["simulationWarnings"] = [
            {"code": warning.code, "memoryId": warning.memoryId, "message": warning.message}
            for warning in simulation.simulationWarnings[:5]
        ]

    return examples


def ensure_locomo_download(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    url = "https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json"
    urllib.request.urlretrieve(url, path)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    oracle_path = Path(
        hf_hub_download(
            "xiaowu0162/longmemeval-cleaned",
            "longmemeval_oracle.json",
            repo_type="dataset",
        )
    )
    locomo_path = OUT_DIR / "locomo10.json"
    ensure_locomo_download(locomo_path)

    datasets = [
        DatasetSpec(
            name="longmemeval_oracle",
            license_note="MIT (LongMemEval cleaned release)",
            source_note="xiaowu0162/longmemeval-cleaned",
        ),
        DatasetSpec(
            name="locomo10",
            license_note="Research release (snap-research/locomo)",
            source_note="snap-research/locomo (GitHub raw JSON)",
        ),
        DatasetSpec(
            name="personalens_profiles",
            license_note="CDLA-Permissive-2.0",
            source_note="AmazonScience/PersonaLens (users 0-4)",
        ),
    ]

    summaries: list[dict[str, Any]] = []

    lme_raw = OUT_DIR / "longmemeval_oracle_50.raw.jsonl"
    lme_instances, lme_records = convert_longmemeval_oracle(
        max_instances=50,
        raw_path=oracle_path,
        output_path=lme_raw,
    )
    summaries.append(
        collect_observations(
            "longmemeval_oracle",
            lme_raw,
            conversation_count=lme_instances,
            preprocess=True,
            group_key="question_id",
            export_record_count=lme_records,
        )
    )

    locomo_raw = OUT_DIR / "locomo10.raw.jsonl"
    locomo_conversations, locomo_records = convert_locomo10(locomo_path, locomo_raw)
    summaries.append(
        collect_observations(
            "locomo10",
            locomo_raw,
            conversation_count=locomo_conversations,
            group_key="sample_id",
            export_record_count=locomo_records,
        )
    )

    pl_raw = OUT_DIR / "personalens.raw.jsonl"
    pl_users, pl_records = convert_personalens_users(["0", "1", "2", "3", "4"], pl_raw)
    summaries.append(
        collect_observations(
            "personalens_profiles",
            pl_raw,
            conversation_count=pl_users,
            group_key="user_id",
            export_record_count=pl_records,
        )
    )

    payload = {
        "validation": "external_pre_v0.8",
        "memdVersion": "0.7.0",
        "datasets": [
            {
                "name": spec.name,
                "license": spec.license_note,
                "source": spec.source_note,
            }
            for spec in datasets
        ],
        "downloads": {
            "longmemeval_oracle_bytes": oracle_path.stat().st_size,
            "locomo10_bytes": locomo_path.stat().st_size,
            "totalApproxMB": round(
                (oracle_path.stat().st_size + locomo_path.stat().st_size) / (1024 * 1024),
                2,
            ),
        },
        "exports": {
            "longmemeval_oracle": {"instances": lme_instances, "rawRecords": lme_records},
            "locomo10": {"conversations": locomo_conversations, "records": locomo_records},
            "personalens_profiles": {"users": pl_users, "records": pl_records},
        },
        "observations": summaries,
    }

    result_path = RESULTS_DIR / "external_validation_summary.json"
    result_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print("External validation complete")
    print(f"Summary: {result_path}")
    for item in summaries:
        print(
            f"- {item['dataset']}: memories={item['memoryCount']} "
            f"resolutions={item['recommendations']['resolutionCounts']} "
            f"reviewRate={item['recommendations']['reviewRate']}"
        )


if __name__ == "__main__":
    main()
