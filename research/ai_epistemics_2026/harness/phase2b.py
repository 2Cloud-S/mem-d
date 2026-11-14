"""Replay frozen Phase 2 evidence with corpus budgets and blinded audits; never call solvers."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from ..validate_development import load_cases, validate_cases
from .artifacts import (
    RESEARCH,
    ROOT,
    THRESHOLDS,
    digest,
    freeze,
    manifest,
    read_jsonl,
    verify,
    write_json,
    write_jsonl,
)
from .backend import TokenCounter, snapshot
from .blind_audits import make_blinded_audits
from .budgets import build_points, corpus_bytes, gate_burden, payload_identity, token_match
from .transform import candidates, gate, memory_input, transform

PHASE2_COMMIT = "489e3ddeb97afa2ed250d83ba3a2a8c3adb3ef8d"


def load_frozen(source: Path, data: Path) -> tuple[list, dict, dict]:
    verify(source)
    verify(source, "audit.freeze.json")
    old = json.loads((source / "manifest.json").read_text())
    if digest(data.read_bytes()) != old["data_sha256"]:
        raise ValueError("Development data does not match frozen Phase 2 data")
    for name, expected in old["source_sha256"].items():
        content = subprocess.check_output(["git", "show", f"{PHASE2_COMMIT}:{name}"], cwd=ROOT)
        if digest(content) != expected:
            raise ValueError(f"Frozen code does not match Phase 2 commit: {name}")
    # The amendment changes PROTOCOL.md; these policy/payload functions must stay unchanged.
    for name in ("harness/transform.py", "harness/requests.py"):
        path = RESEARCH / name
        if digest(path.read_bytes()) != old["source_sha256"][str(path.relative_to(ROOT))]:
            raise ValueError("Existing gate/candidate/payload code changed")
    cases = load_cases(data)
    validate_cases(cases)
    public = {
        c["case_id"]: {
            "memories": memory_input(c["input"]["memories"]),
            **{k: c["input"][k] for k in ("question", "decision_criteria", "answer_options")},
        }
        for c in cases
    }
    source_rows = read_jsonl(source / "transformations.jsonl")
    grouped = defaultdict(list)
    for row in source_rows:
        grouped[(row["case_id"], row["threshold"])].append(row)
    expected_keys = {(cid, threshold) for cid in public for threshold in THRESHOLDS}
    if set(grouped) != expected_keys:
        raise ValueError("Missing/extra source cases or thresholds")
    rows = []
    for key, variants in sorted(grouped.items()):
        row = max(variants, key=lambda r: r["prefix"])
        for variant in variants:
            for field in ("original_records", "candidates", "gate_decisions", "memd"):
                if variant[field] != row[field]:
                    raise ValueError("Historical prefixes disagree about analysis")
        if row["original_records"] != public[row["case_id"]]["memories"]:
            raise ValueError("Frozen originals differ from input allowlist")
        recomputed = candidates(
            row["original_records"], row["memd"]["clusters"], row["memd"]["similarities"]
        )
        if recomputed != row["candidates"]:
            raise ValueError("Candidate or medoid changed")
        decisions = [
            gate(g, row["memd"]["recommendations"], row["memd"]["resolutions"]) for g in recomputed
        ]
        if decisions != row["gate_decisions"]:
            raise ValueError("Gate changed")
        for method in ("original", "exact", "semantic", "gated"):
            result = transform(
                row["original_records"], method, recomputed, decisions, len(recomputed)
            )
            if any(result[k] != row["outputs"][method][k] for k in result):
                raise ValueError(f"Historical full-prefix payload changed: {key}, {method}")
        rows.append(row)
    return rows, public, old


def summarize_point(point: dict) -> dict:
    return {k: v for k, v in point.items() if k != "outputs"} | {
        "metrics": {
            k: v
            for k, v in point["metrics"].items()
            if k not in {"token_counts", "non_exact_groups"}
        }
    }


def compare_threshold(points: list[dict], rows: list[dict], public: dict, match: dict) -> dict:
    anchors = {p["method"]: p for p in points if p["method"] != "similarity_first"}
    gated, exact = anchors["gated"], anchors["exact"]
    controls = [p for p in points if p["method"] == "similarity_first"]
    selected = next((p for p in controls if p["point_id"] == match["control"]), None)
    gm, em = gated["metrics"], exact["metrics"]
    deltas = []
    for cid in sorted(public):
        g, e = gated["outputs"][cid], exact["outputs"][cid]
        extra = sorted(set(g["removed_ids"]) - set(e["removed_ids"]))
        reinstated = sorted(set(e["removed_ids"]) - set(g["removed_ids"]))
        if extra or reinstated:
            deltas.append(
                {
                    "case_id": cid,
                    "additional_removed_ids": extra,
                    "reinstated_ids": reinstated,
                    "gated_groups": g["executed_groups"],
                }
            )
    return {
        "threshold": gated["threshold"],
        "match": match,
        "gated": summarize_point(gated),
        "exact": summarize_point(exact),
        "selected_similarity_first": summarize_point(selected) if selected else None,
        "gated_vs_exact": payload_identity(gated, exact, public),
        "gated_vs_selected_control": payload_identity(gated, selected, public)
        if selected
        else None,
        "all_similarity_prefixes_identical_to_gate": [
            p["prefix"] for p in controls if corpus_bytes(p) == corpus_bytes(gated)
        ],
        "incremental_tokens_saved_over_exact_mean_orders": (
            gm["tokens_saved_mean_orders"] - em["tokens_saved_mean_orders"]
            if gm["tokens_saved_mean_orders"] is not None
            and em["tokens_saved_mean_orders"] is not None
            else None
        ),
        "incremental_payload_changes_over_exact": deltas,
        "gate_burden": gate_burden(rows),
    }


def prepare(source: Path, data: Path, output: Path, cache: Path) -> dict:
    if output.exists():
        raise ValueError("Refusing to overwrite a Phase 2B run")
    rows, public, old = load_frozen(source, data)
    token_path, token_info = snapshot(
        old["model_lock"]["tokenizer"], cache, False, tokenizer_only=True
    )
    if token_info["files_sha256"] != old["tokenizer"]["files_sha256"]:
        raise ValueError("Pinned tokenizer asset hashes differ from frozen run")
    counter = TokenCounter(token_path, token_info)
    all_points, rankings, matches, by_threshold = [], {}, [], {}
    for threshold in THRESHOLDS:
        subset = [r for r in rows if r["threshold"] == threshold]
        points, ranking = build_points(subset, counter)
        # Check actual new tokenization against every historical full-prefix anchor.
        for method in ("original", "exact", "gated"):
            anchor = next(p for p in points if p["method"] == method)
            for count in anchor["metrics"]["token_counts"]:
                old_row = next(r for r in subset if r["case_id"] == count["case_id"])
                original_count = next(
                    v
                    for v in old_row["outputs"][method]["memory_tokens"]
                    if v["order_seed"] == count["order_seed"]
                )
                if (count["before"], count["after"]) != (
                    original_count["original"],
                    original_count["transformed"],
                ):
                    raise ValueError("Actual token counts differ from historical serialization")
        gated = next(p for p in points if p["method"] == "gated")
        match = token_match(gated, [p for p in points if p["method"] == "similarity_first"])
        all_points.extend(points)
        rankings[str(threshold)] = ranking
        matches.append(match)
        by_threshold[threshold] = (points, subset, match)
    info = manifest(data, old["model_lock"])
    rubric_path = RESEARCH / "AUDIT_RUBRIC.md"
    info.update(
        {
            "schema": "phase2b-v1",
            "purpose": "development-only budgets and pending blinded audits",
            "source_phase2_commit": PHASE2_COMMIT,
            "source_freeze_sha256": digest((source / "freeze.json").read_bytes()),
            "source_manifest_sha256": digest((source / "manifest.json").read_bytes()),
            "source_audit_freeze_sha256": digest((source / "audit.freeze.json").read_bytes()),
            "tokenizer": counter.info,
            "new_embedding_calls": 0,
            "solver_calls": 0,
            "pipeline_evidence": "reused unchanged frozen real Phase 2 recommendations",
            "audit_presentation_seed": 20262,
            "matching": {
                "same_threshold": True,
                "absolute_compression_tolerance": 0.02,
                "objective": "minimum absolute actual token gap, then shorter global prefix",
                "identity_used_for_selection": False,
                "random_budget_control": False,
            },
        }
    )
    info["source_sha256"][str(rubric_path.relative_to(ROOT))] = digest(rubric_path.read_bytes())
    output.mkdir(parents=True)
    write_json(output / "manifest.json", info)
    write_jsonl(output / "points.jsonl", all_points)
    write_json(output / "rankings.json", rankings)
    write_json(output / "matching.json", matches)
    write_json(output / "response_state.json", {"status": "not_collected", "response_count": 0})
    freeze(
        output,
        ["manifest.json", "points.jsonl", "rankings.json", "matching.json", "response_state.json"],
        "selection.freeze.json",
    )
    verify(output, "selection.freeze.json")
    # Questions enter identity checks and review content only after budget selection is frozen.
    comparisons = [
        compare_threshold(*by_threshold[t][:2], public, by_threshold[t][2]) for t in THRESHOLDS
    ]
    historical_rows = read_jsonl(source / "transformations.jsonl")
    diagnosis = [
        {
            "threshold": t,
            "historical_prefix_caps": sorted(
                {r["prefix"] for r in historical_rows if r["threshold"] == t}
            ),
            "groups_per_case_histogram": dict(
                sorted(Counter(len(r["candidates"]) for r in rows if r["threshold"] == t).items())
            ),
        }
        for t in THRESHOLDS
    ]
    write_json(
        output / "comparisons.json",
        {
            "historical_grid_diagnosis": diagnosis,
            "comparisons": comparisons,
            "human_review_status": "pending",
            "no_downstream_decision_or_safety_results": True,
        },
    )
    write_json(output / "operating-points.json", [summarize_point(p) for p in all_points])
    packets, mapping, template = make_blinded_audits(rows, public)
    reviewer, evaluator = output / "reviewer", output / "evaluator-only"
    reviewer.mkdir()
    evaluator.mkdir()
    write_json(reviewer / "packets.json", packets)
    write_json(reviewer / "response-template.json", template)
    (reviewer / "rubric.md").write_bytes(rubric_path.read_bytes())
    freeze(reviewer, ["packets.json", "response-template.json", "rubric.md"])
    write_json(evaluator / "audit-map.json", mapping)
    freeze(evaluator, ["audit-map.json"])
    write_json(
        output / "child-freezes.json",
        {
            "reviewer": digest((reviewer / "freeze.json").read_bytes()),
            "evaluator-only": digest((evaluator / "freeze.json").read_bytes()),
        },
    )
    freeze(
        output,
        ["comparisons.json", "operating-points.json", "child-freezes.json"],
        "analysis.freeze.json",
    )
    return {
        "operating_points": len(all_points),
        "unique_audit_packets": len(packets),
        "source_group_proposals": sum(len(r["candidates"]) for r in rows),
        "matched_thresholds": sum(m["status"] == "matched" for m in matches),
        "human_review_status": "pending",
        "solver_calls": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Extracted frozen Phase 2 run")
    parser.add_argument("--data", type=Path, default=RESEARCH / "development.jsonl")
    parser.add_argument(
        "--cache", type=Path, required=True, help="Pinned tokenizer cache, offline only"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.source, args.data, args.output, args.cache)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
