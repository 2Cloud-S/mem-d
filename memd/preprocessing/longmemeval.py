from __future__ import annotations

import json
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from memd.parser.loaders import ParserError, detect_encoding

ASSISTANT_OPENER = re.compile(
    r"^(?:sure|certainly|absolutely|of course|great question|i'd be happy|"
    r"congratulations|here'?s|to solve this|to answer your question)",
    re.IGNORECASE,
)
PUZZLE = re.compile(
    r"\bpuzzle|riddle|brain teaser|fox.*chicken|help the farmer\b",
    re.IGNORECASE,
)
ROLEPLAY = re.compile(
    r"\b(?:rewrite the script|write the script|fade out|int\.|ext\.|characters:)\b",
    re.IGNORECASE,
)
CREATIVE_WRITING = re.compile(
    r"\b(?:rewrite the ending|write a story|creative writing|screenplay)\b",
    re.IGNORECASE,
)
GENERIC_FILLER = re.compile(
    r"\b(?:feel free to ask|hope this helps|let me know if|good luck|"
    r"keep up the good work|don't hesitate to reach out|thanks for sharing)\b",
    re.IGNORECASE,
)
PERSONAL_FACT = re.compile(
    r"\b(?:i am|i'm|my |i have|i bought|i got|i use|i prefer|i graduated|"
    r"i changed|i repainted|i volunteer|i spend|i created|i attend)\b",
    re.IGNORECASE,
)
QUESTION_ONLY = re.compile(
    r"^(?:can you|could you|what|how|where|when|why|do you)\b",
    re.IGNORECASE,
)

CONTENT_KEYS = ("content", "text", "memory", "message", "value")
RemovalReason = str


@dataclass(frozen=True)
class PreprocessReport:
    inputPath: str
    outputPath: str
    originalRecordCount: int
    removedAssistantTurns: int
    removedFillerRecords: int
    removedExcludedContent: int
    removedDuplicateRecords: int
    finalRecordCount: int
    retentionPercentage: float

    def to_dict(self) -> dict[str, object]:
        return {
            "inputPath": self.inputPath,
            "outputPath": self.outputPath,
            "originalRecordCount": self.originalRecordCount,
            "removedAssistantTurns": self.removedAssistantTurns,
            "removedFillerRecords": self.removedFillerRecords,
            "removedExcludedContent": self.removedExcludedContent,
            "removedDuplicateRecords": self.removedDuplicateRecords,
            "finalRecordCount": self.finalRecordCount,
            "retentionPercentage": self.retentionPercentage,
        }


def preprocess_longmemeval_jsonl(
    input_path: Path,
    output_path: Path,
) -> PreprocessReport:
    input_path = input_path.resolve()
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    kept_records: list[dict[str, Any]] = []
    seen_normalized: set[str] = set()
    stats = {
        "assistant": 0,
        "filler": 0,
        "excluded": 0,
        "duplicate": 0,
    }
    original_count = 0

    for _line_number, record in iter_jsonl_records(input_path):
        original_count += 1
        reason = removal_reason(record)
        if reason == "assistant":
            stats["assistant"] += 1
            continue
        if reason == "excluded_content":
            stats["excluded"] += 1
            continue
        if reason == "filler":
            stats["filler"] += 1
            continue

        normalized = normalize_content(extract_content(record))
        if normalized in seen_normalized:
            stats["duplicate"] += 1
            continue

        seen_normalized.add(normalized)
        kept_records.append(record)

    write_jsonl(output_path, kept_records)
    final_count = len(kept_records)
    return PreprocessReport(
        inputPath=str(input_path),
        outputPath=str(output_path),
        originalRecordCount=original_count,
        removedAssistantTurns=stats["assistant"],
        removedFillerRecords=stats["filler"],
        removedExcludedContent=stats["excluded"],
        removedDuplicateRecords=stats["duplicate"],
        finalRecordCount=final_count,
        retentionPercentage=percentage(final_count, original_count),
    )


def iter_jsonl_records(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    encoding = detect_encoding(path)
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
            content = extract_content(item)
            if not content.strip():
                continue
            yield line_number, item


def removal_reason(record: dict[str, Any]) -> RemovalReason | None:
    role = str(record.get("role", "")).strip().lower()
    content = extract_content(record)

    if role == "assistant":
        return "assistant"
    if is_excluded_content(content):
        return "excluded_content"
    if is_conversational_filler(content, role):
        return "filler"
    return None


def is_excluded_content(content: str) -> bool:
    return bool(
        PUZZLE.search(content)
        or ROLEPLAY.search(content)
        or CREATIVE_WRITING.search(content)
    )


def is_conversational_filler(content: str, role: str) -> bool:
    if GENERIC_FILLER.search(content):
        return True
    if ASSISTANT_OPENER.search(content.strip()):
        return True
    if role == "user" and QUESTION_ONLY.search(content.strip()):
        if len(content) < 180 and not PERSONAL_FACT.search(content):
            return True
    return False


def extract_content(record: dict[str, Any]) -> str:
    for key in CONTENT_KEYS:
        value = record.get(key)
        if value is not None:
            return str(value)
    return ""


def normalize_content(content: str) -> str:
    return re.sub(r"\s+", " ", content.strip().lower())


def write_jsonl(path: Path, records: Sequence[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


def write_preprocess_report(path: Path, report: PreprocessReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")


def render_preprocess_report_markdown(report: PreprocessReport) -> str:
    data = report.to_dict()
    lines = [
        "# LongMemEval Preprocessing Report",
        "",
        f"- Input: `{data['inputPath']}`",
        f"- Output: `{data['outputPath']}`",
        f"- Original record count: {data['originalRecordCount']}",
        f"- Removed assistant turns: {data['removedAssistantTurns']}",
        f"- Removed filler records: {data['removedFillerRecords']}",
        f"- Removed puzzle/roleplay/creative content: {data['removedExcludedContent']}",
        f"- Removed duplicate records: {data['removedDuplicateRecords']}",
        f"- Final record count: {data['finalRecordCount']}",
        f"- Retention percentage: {data['retentionPercentage']}%",
        "",
    ]
    return "\n".join(lines)


def percentage(part: int, whole: int) -> float:
    if whole == 0:
        return 0.0
    return round((part / whole) * 100, 2)


def default_output_paths(input_path: Path) -> tuple[Path, Path]:
    stem = input_path.stem
    parent = input_path.parent
    return (
        parent / f"{stem}.cleaned.jsonl",
        parent / f"{stem}.preprocess-report.json",
    )
