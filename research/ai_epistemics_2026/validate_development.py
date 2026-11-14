"""Validate research data only; does not call models or execute memory policies."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

CATEGORIES = {
    "genuine_duplicate",
    "decision_changing_exception",
    "uncertainty_or_attribution",
    "unresolved_contradiction",
}
LABELS = {"proceed", "do_not_proceed", "insufficient_evidence"}
MEMORY_KEYS = {"id", "content", "source", "timestamp"}
INPUT_KEYS = {"memories", "question", "decision_criteria", "answer_options"}
CASE_KEYS = {
    "schema_version", "case_id", "family_id", "category", "split", "input", "evaluator_only"
}
GOLD_KEYS = {
    "acceptable_answer_labels", "rationale", "decisive_evidence_ids", "must_survive", "merge_safety"
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def object_keys(value: Any, keys: set[str], location: str) -> None:
    require(isinstance(value, dict), f"{location}: expected object")
    require(set(value) == keys, f"{location}: required/allowed keys are {sorted(keys)}")


def text(value: Any, location: str) -> None:
    require(isinstance(value, str) and bool(value.strip()), f"{location}: expected nonempty text")


def strings(value: Any, location: str) -> None:
    require(isinstance(value, list) and bool(value), f"{location}: expected nonempty list")
    for item in value:
        text(item, location)
    require(len(set(value)) == len(value), f"{location}: duplicate values")


def references(value: Any, ids: set[str], location: str) -> None:
    strings(value, location)
    require(set(value) <= ids, f"{location}: unknown evidence ID")


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ValueError(f"nonstandard JSON constant: {value}")


def load_cases(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    cases = []
    for line_number, line in enumerate(lines, 1):
        require(bool(line.strip()), f"line {line_number}: blank JSONL record")
        try:
            cases.append(json.loads(
                line, object_pairs_hook=unique_object, parse_constant=reject_constant
            ))
        except ValueError as error:
            raise ValueError(f"line {line_number}: {error}") from error
    return cases


def validate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    require(len(cases) == 20, "expected exactly 20 cases")
    case_ids: set[str] = set()
    memory_ids: set[str] = set()
    detail_ids: set[str] = set()
    categories: Counter[str] = Counter()
    families: Counter[str] = Counter()
    answers: Counter[str] = Counter()
    judgments: Counter[str] = Counter()
    family_categories: dict[str, set[str]] = {}

    for case in cases:
        object_keys(case, CASE_KEYS, "case")
        case_id = case["case_id"]
        text(case_id, "case_id")
        require(bool(re.fullmatch(r"dev_\d{3}", case_id)), "invalid case_id")
        require(case_id not in case_ids, f"{case_id}: duplicate case ID")
        case_ids.add(case_id)
        require(case["schema_version"] == "1.0", f"{case_id}: unsupported schema")
        require(case["split"] == "development", f"{case_id}: non-development case")
        category = case["category"]
        text(category, f"{case_id}.category")
        require(category in CATEGORIES, f"{case_id}: unknown category")
        family_id = case["family_id"]
        text(family_id, f"{case_id}.family_id")
        require(bool(re.fullmatch(r"family_\d{2}", family_id)), "invalid family_id")
        categories[category] += 1
        families[family_id] += 1
        family_categories.setdefault(family_id, set()).add(category)

        public = case["input"]
        object_keys(public, INPUT_KEYS, f"{case_id}.input")
        text(public["question"], f"{case_id}.question")
        text(public["decision_criteria"], f"{case_id}.decision_criteria")
        strings(public["answer_options"], f"{case_id}.answer_options")
        require(set(public["answer_options"]) == LABELS, "all cases must offer all three labels")
        memories = public["memories"]
        require(isinstance(memories, list) and 2 <= len(memories) <= 4,
                f"{case_id}: expected two to four memories")
        local_ids: set[str] = set()
        for memory in memories:
            # No metadata catch-all: it could accidentally contain evaluator annotations.
            object_keys(memory, MEMORY_KEYS, f"{case_id}.memory")
            for key in MEMORY_KEYS:
                text(memory[key], f"{case_id}.memory.{key}")
            memory_id = memory["id"]
            require(bool(re.fullmatch(r"m\d{3}_\d", memory_id)), "invalid memory ID")
            require(memory_id not in memory_ids, f"duplicate memory ID: {memory_id}")
            memory_ids.add(memory_id)
            local_ids.add(memory_id)
            timestamp = memory["timestamp"]
            require(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", timestamp)),
                    f"{memory_id}: expected UTC timestamp")
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        gold = case["evaluator_only"]
        object_keys(gold, GOLD_KEYS, f"{case_id}.evaluator_only")
        strings(gold["acceptable_answer_labels"], f"{case_id}.acceptable_answer_labels")
        require(set(gold["acceptable_answer_labels"]) <= LABELS, "unknown acceptable label")
        text(gold["rationale"], f"{case_id}.rationale")
        references(gold["decisive_evidence_ids"], local_ids, f"{case_id}.decisive_evidence_ids")
        details = gold["must_survive"]
        require(isinstance(details, list) and bool(details), f"{case_id}: missing required details")
        covered_ids: set[str] = set()
        for detail in details:
            object_keys(detail, {"detail_id", "description", "evidence_ids"}, "must_survive")
            text(detail["detail_id"], "detail_id")
            require(detail["detail_id"] not in detail_ids, "duplicate detail ID")
            detail_ids.add(detail["detail_id"])
            text(detail["description"], "detail description")
            references(detail["evidence_ids"], local_ids, "detail evidence")
            covered_ids.update(detail["evidence_ids"])
        require(set(gold["decisive_evidence_ids"]) <= covered_ids,
                f"{case_id}: decisive evidence has no surviving-detail annotation")

        safety = gold["merge_safety"]
        object_keys(safety, {"operation", "candidate_memory_ids", "judgment", "rationale"},
                    f"{case_id}.merge_safety")
        require(safety["operation"] == "arbitrary_single_record_replacement",
                f"{case_id}: unsupported safety-judgment scope")
        references(safety["candidate_memory_ids"], local_ids, "safety candidate IDs")
        require(len(safety["candidate_memory_ids"]) >= 2, "safety group needs two records")
        text(safety["judgment"], "safety judgment")
        require(safety["judgment"] in {"safe", "unsafe"}, "unknown safety judgment")
        text(safety["rationale"], "safety rationale")
        if category == "genuine_duplicate":
            require(safety["judgment"] == "safe", "duplicate controls must be safe")
        if category == "unresolved_contradiction":
            require(gold["acceptable_answer_labels"] == ["insufficient_evidence"],
                    "unresolved cases must accept insufficient evidence")
        answers.update(gold["acceptable_answer_labels"])
        judgments[safety["judgment"]] += 1

    require(dict(categories) == dict.fromkeys(CATEGORIES, 5), "expected five cases per category")
    require(len(families) == 10 and set(families.values()) == {2},
            "expected ten scenario families, each containing two related cases")
    pairs = [
        {"genuine_duplicate", "decision_changing_exception"},
        {"uncertainty_or_attribution", "unresolved_contradiction"},
    ]
    require(all(value in pairs for value in family_categories.values()),
            "families must retain the documented category pairing")
    return {
        "cases": len(cases), "families": len(families), "memories": len(memory_ids),
        "required_details": len(detail_ids), "categories": dict(sorted(categories.items())),
        "acceptable_labels": dict(sorted(answers.items())),
        "merge_safety_judgments": dict(sorted(judgments.items())),
        "annotation_separation": "strict input/memory key allowlists passed",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path,
                        default=Path(__file__).with_name("development.jsonl"))
    args = parser.parse_args()
    try:
        summary = validate_cases(load_cases(args.path))
    except (ValueError, OSError) as error:
        parser.exit(1, f"Validation failed: {error}\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
