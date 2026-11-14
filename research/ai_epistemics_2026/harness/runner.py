"""Development-only transformation runs, frozen requests, and compression summaries."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ..validate_development import load_cases, validate_cases
from .analysis import compression_matches
from .artifacts import (
    ORDER_SEEDS,
    THRESHOLDS,
    freeze,
    manifest,
    object_hash,
    verify,
    write_json,
    write_jsonl,
)
from .requests import build_requests, solver_payload
from .transform import CONDITIONS, candidates, gate, memory_input, transform


def build_run(cases: list[dict], adapter, counter, solver: dict) -> tuple[list, list]:
    """Evaluator data is never read here. Adapter's only input is allowlisted memories."""
    analyses = {}
    for case in cases:
        memories = memory_input(case["input"]["memories"])
        expected_embedding_hash = None
        for threshold in THRESHOLDS:
            result = adapter.analyze(memories, threshold)
            if expected_embedding_hash not in (None, result["embedding_sha256"]):
                raise ValueError("Embeddings changed across threshold conditions")
            expected_embedding_hash = result["embedding_sha256"]
            groups = candidates(memories, result["clusters"], result["similarities"])
            decisions = [gate(g, result["recommendations"], result["resolutions"]) for g in groups]
            analyses[(case["case_id"], threshold)] = (memories, result, groups, decisions)
    transformations, requests = [], []
    for threshold in THRESHOLDS:
        max_groups = max(len(analyses[(c["case_id"], threshold)][2]) for c in cases)
        for case in cases:
            memories, result, groups, decisions = analyses[(case["case_id"], threshold)]
            for prefix in range(max_groups + 1):
                outputs = {
                    name: transform(memories, name, groups, decisions, prefix)
                    for name in CONDITIONS
                }
                for name, output in outputs.items():
                    counts = []
                    for seed in ORDER_SEEDS:
                        before = solver_payload(case["input"], memories, seed)["memories"]
                        after = solver_payload(case["input"], output["memories"], seed)["memories"]
                        original_tokens, tokens = counter.count(before), counter.count(after)
                        counts.append(
                            {
                                "order_seed": seed,
                                "original": original_tokens,
                                "transformed": tokens,
                                "saved": original_tokens - tokens
                                if original_tokens is not None and tokens is not None
                                else None,
                            }
                        )
                    output["memory_tokens"] = counts
                    output["records_before"] = len(memories)
                    output["records_after"] = len(output["memories"])
                    output["condition"] = name
                transformations.append(
                    {
                        "case_id": case["case_id"],
                        "threshold": threshold,
                        "prefix": prefix,
                        "original_records": memories,
                        "original_records_sha256": object_hash(memories),
                        "candidates": groups,
                        "gate_decisions": decisions,
                        "memd": result,
                        "outputs": outputs,
                    }
                )
                requests.extend(
                    build_requests(
                        case["case_id"], case["input"], outputs, threshold, prefix, solver
                    )
                )
    return transformations, requests


def feasibility_summary(transformations: list[dict], cases: list[dict]) -> dict:
    # Called only after transformation/request freeze. Category is never a policy input.
    category = {case["case_id"]: case["category"] for case in cases}
    family = {case["case_id"]: case["family_id"] for case in cases}
    operating_points = []
    for threshold in THRESHOLDS:
        prefixes = sorted({t["prefix"] for t in transformations if t["threshold"] == threshold})
        for prefix in prefixes:
            subset = [
                t for t in transformations if t["threshold"] == threshold and t["prefix"] == prefix
            ]
            reason_counts = Counter(
                reason
                for row in subset
                for decision in row["gate_decisions"][:prefix]
                for reason in decision["veto_reasons"]
            )
            group_count = sum(len(row["candidates"][:prefix]) for row in subset)
            all_groups = sum(len(row["candidates"]) for row in subset)
            review = sum(
                any(
                    r["resolvedAction"] == "review" and r["memoryId"] in g["members"]
                    for r in row["memd"]["resolutions"]
                )
                for row in subset
                for g in row["candidates"][:prefix]
            )
            approval = sum(
                "approval_required" in d["veto_reasons"]
                for row in subset
                for d in row["gate_decisions"][:prefix]
            )
            conflicts = sum(
                any("conflict" in reason for reason in d["veto_reasons"])
                for row in subset
                for d in row["gate_decisions"][:prefix]
            )
            vetoes = sum(not d["allowed"] for row in subset for d in row["gate_decisions"][:prefix])
            for condition in CONDITIONS:
                outputs = [row["outputs"][condition] for row in subset]
                controls = [
                    row["outputs"][condition]
                    for row in subset
                    if category[row["case_id"]] == "genuine_duplicate"
                ]

                def totals(items):
                    before = sum(o["records_before"] for o in items)
                    reduction = sum(o["records_before"] - o["records_after"] for o in items)
                    token_rows = [v for o in items for v in o["memory_tokens"]]
                    available = bool(token_rows) and all(v["saved"] is not None for v in token_rows)
                    token_before = (
                        sum(v["original"] for v in token_rows) / len(ORDER_SEEDS)
                        if available
                        else None
                    )
                    saved = (
                        sum(v["saved"] for v in token_rows) / len(ORDER_SEEDS)
                        if available
                        else None
                    )
                    return {
                        "records_before": before,
                        "records_removed": reduction,
                        "record_reduction": reduction / before if before else None,
                        "memory_tokens_before_mean_orders": token_before,
                        "memory_tokens_saved_mean_orders": saved,
                        "token_compression": saved / token_before if token_before else None,
                        "executed_groups": sum(len(o["executed_groups"]) for o in items),
                    }

                value = {
                    "threshold": threshold,
                    "prefix": prefix,
                    "condition": condition,
                    **totals(outputs),
                    "genuine_duplicate_controls": totals(controls),
                }
                family_fractions = {}
                for row in subset:
                    token_rows = row["outputs"][condition]["memory_tokens"]
                    if all(v["saved"] is not None and v["original"] for v in token_rows):
                        fraction = sum(v["saved"] / v["original"] for v in token_rows) / len(
                            token_rows
                        )
                        family_fractions.setdefault(family[row["case_id"]], []).append(fraction)
                value["family_mean_token_compression"] = (
                    sum(sum(v) / len(v) for v in family_fractions.values()) / len(family_fractions)
                    if len(family_fractions) == len(set(family.values()))
                    else None
                )
                if condition in {"semantic", "gated"}:
                    value.update(
                        {"all_candidates": all_groups, "considered_candidates": group_count}
                    )
                if condition == "gated":
                    value.update(
                        {
                            "review_groups": sum(
                                any(
                                    r["resolvedAction"] == "review"
                                    and r["memoryId"] in g["members"]
                                    for r in row["memd"]["resolutions"]
                                )
                                for row in subset
                                for g in row["candidates"]
                            ),
                            "review_denominator": all_groups,
                            "considered_review_groups": review,
                            "review_memories": sum(
                                r["resolvedAction"] == "review"
                                for row in subset
                                for r in row["memd"]["resolutions"]
                            ),
                            "original_memories": sum(
                                len(row["original_records"]) for row in subset
                            ),
                            "unchanged_records": sum(len(o["memories"]) for o in outputs),
                            "approval_groups": approval,
                            "conflict_groups": conflicts,
                            "vetoed_groups": vetoes,
                            "other_veto_groups": sum(
                                not d["allowed"]
                                and not any(
                                    "review" in r or "conflict" in r or r == "approval_required"
                                    for r in d["veto_reasons"]
                                )
                                for row in subset
                                for d in row["gate_decisions"][:prefix]
                            ),
                            "veto_reason_counts_nonexclusive": dict(sorted(reason_counts.items())),
                            "keeper_disagreements": sum(
                                d["keeper_disagreement"]
                                for row in subset
                                for d in row["gate_decisions"][:prefix]
                            ),
                        }
                    )
                operating_points.append(value)
    full = [
        p
        for p in operating_points
        if p["condition"] == "gated"
        and p["prefix"]
        == max(q["prefix"] for q in operating_points if q["threshold"] == p["threshold"])
    ]
    return {
        "purpose": "development compression feasibility; no solver calls or decision outcomes",
        "operating_points": operating_points,
        "compression_matches": compression_matches(operating_points),
        "gated_any_merge": any(p["executed_groups"] for p in full),
        "gated_any_control_record_reduction": any(
            p["genuine_duplicate_controls"]["records_removed"] > 0 for p in full
        ),
        "gated_any_control_token_savings": any(
            (p["genuine_duplicate_controls"]["memory_tokens_saved_mean_orders"] or 0) > 0
            for p in full
        )
        if all(
            p["genuine_duplicate_controls"]["memory_tokens_saved_mean_orders"] is not None
            for p in full
        )
        else None,
        "detail_retention": "not independently audited; no safety or decision benefit inferred",
    }


def dry_run(
    data: Path, directory: Path, adapter, counter, lock: dict, solver_identity: dict | None = None
) -> dict:
    if directory.exists():
        raise ValueError("Output directory must be new; never overwrite a frozen run")
    cases = load_cases(data)
    validate_cases(cases)
    original_bytes = data.read_bytes()
    info = manifest(data, lock)
    if solver_identity is not None:
        if set(solver_identity) != {"model_id", "revision"} or not all(
            isinstance(v, str) and v.strip() and v != "UNASSIGNED" for v in solver_identity.values()
        ):
            raise ValueError("Provide an explicit downstream model and immutable version identity")
        info["solver"].update(solver_identity)
    info["tokenizer"] = counter.info
    transformations, requests = build_run(cases, adapter, counter, info["solver"])
    info["embedding_backend"] = {
        "class": "sentence_transformers.SentenceTransformer",
        "device": "cpu",
        "torch_threads": 1,
        "dimensions": 384,
        "hashing_fallback_detected": False,
        "verification": "parent sentence-transformer output equals vectors used by mem-d",
    }
    if data.read_bytes() != original_bytes:
        raise ValueError("Source dataset changed")
    directory.mkdir(parents=True)
    write_json(directory / "manifest.json", info)
    write_jsonl(directory / "transformations.jsonl", transformations)
    write_jsonl(directory / "requests.jsonl", requests)
    write_json(
        directory / "response_state.json",
        {"status": "not_collected", "response_count": 0, "solver_calls": 0},
    )
    freeze(
        directory,
        ["manifest.json", "transformations.jsonl", "requests.jsonl", "response_state.json"],
    )
    verify(directory)
    summary = feasibility_summary(transformations, cases)
    write_json(directory / "feasibility.json", summary)
    write_json(
        directory / "audit-template.json",
        {
            "status": "unscored",
            "request_freeze": json.loads((directory / "freeze.json").read_text()),
            "cases": [
                {"case_id": c["case_id"], "evaluator_only": c["evaluator_only"]} for c in cases
            ],
            "instructions": (
                "Audit actual outputs/candidates including vetoed groups; never infer safety "
                "from category or arbitrary-replacement gold. "
                "No responses collected; no answer audit yet."
            ),
        },
    )
    freeze(directory, ["feasibility.json", "audit-template.json"], "audit.freeze.json")
    return summary
