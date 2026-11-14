"""Post-response-freeze development analysis; explanation support remains an audit outcome."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from ..validate_development import load_cases
from .analysis import bootstrap, family_metrics, score_frozen
from .artifacts import RESEARCH, freeze, read_jsonl, verify, write_json, write_jsonl
from .execution import parse_response

CONDITIONS = ("original", "exact", "similarity_first", "gated")


def contrast(rows: list[dict], target: str, reference: str) -> dict:
    paired = [
        {**r, "condition": "original" if r["condition"] == reference else target}
        for r in rows
        if r["condition"] in {target, reference}
    ]
    return {
        "target": target,
        "reference": reference,
        **family_metrics(paired, target),
        **bootstrap(paired, target),
    }


def analyze(directory: Path, data: Path) -> dict:
    verify(directory)
    verify(directory, "responses.freeze.json")
    verify(directory, "execution.freeze.json")
    if (directory / "analysis.freeze.json").exists():
        raise ValueError("Refusing to overwrite pilot analysis")
    cases = load_cases(data)
    rows = score_frozen(directory, cases, data.read_bytes())
    if any(r["provenance"] != "real" for r in rows):
        raise ValueError("Synthetic fixtures are not empirical pilot results")
    requests = {r["request_id"]: r for r in read_jsonl(directory / "requests.jsonl")}
    responses = read_jsonl(directory / "responses.jsonl")
    per_condition = {}
    for condition in CONDITIONS:
        subset = [r for r in rows if r["condition"] == condition]
        included = [r for r in subset if not r["excluded"]]
        metrics = family_metrics(rows, condition)
        per_condition[condition] = {
            **metrics,
            **bootstrap(rows, condition),
            "planned_observations": len(subset),
            "included_observations": len(included),
            "excluded_observations": len(subset) - len(included),
            "error_count": sum(r["error"] for r in included),
            "correct_count": sum(r["error"] == 0 for r in included),
            "family_weighted_accuracy": 1 - metrics["condition_error"]
            if metrics["condition_error"] is not None
            else None,
            "parse_reason_counts_planned": dict(Counter(r["parse_reason"] for r in subset)),
        }
    case_results = []
    for case in cases:
        selected = [r for r in rows if r["case_id"] == case["case_id"]]
        case_results.append(
            {
                "case_id": case["case_id"],
                "family_id": case["family_id"],
                "condition_errors": {
                    c: [
                        r["error"] if not r["excluded"] else None
                        for r in selected
                        if r["condition"] == c
                    ]
                    for c in CONDITIONS
                },
            }
        )
    report = {
        "purpose": "exploratory development pilot, not confirmatory",
        "conditions": per_condition,
        "gate_vs_exact": contrast(rows, "gated", "exact"),
        "gate_vs_similarity_first": contrast(rows, "gated", "similarity_first"),
        "case_results": case_results,
        "human_review_status": "pending",
        "explanation_support_status": "unscored; label correctness is a separate metric",
    }
    case_map = {c["case_id"]: c for c in cases}
    explanation_audit = []
    for response in responses:
        request = requests[response["request_id"]]
        case = case_map[request["case_id"]]
        explanation_audit.append(
            {
                "request_id": response["request_id"],
                "case_id": case["case_id"],
                "order_seed": request["order_seed"],
                "condition": request["condition"],
                "response": response["text"],
                "parsed": parse_response(response),
                "acceptable_labels": case["evaluator_only"]["acceptable_answer_labels"],
                "explanation_supported": None,
                "reviewer_provenance": None,
            }
        )
    write_jsonl(directory / "scores.jsonl", rows)
    write_json(directory / "analysis.json", report)
    write_json(directory / "explanation-audit.json", explanation_audit)
    freeze(
        directory,
        ["scores.jsonl", "analysis.json", "explanation-audit.json"],
        "analysis.freeze.json",
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=RESEARCH / "development.jsonl")
    args = parser.parse_args()
    report = analyze(args.run, args.data)
    print(
        json.dumps(
            {
                c: {
                    k: v
                    for k, v in values.items()
                    if k
                    in {
                        "planned_observations",
                        "included_observations",
                        "excluded_observations",
                        "correct_count",
                        "error_count",
                        "paired_change",
                    }
                }
                for c, values in report["conditions"].items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
