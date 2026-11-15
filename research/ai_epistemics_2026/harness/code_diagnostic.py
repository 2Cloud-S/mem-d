"""One frozen neutral-code diagnostic and its eligibility-gated development comparison."""

from __future__ import annotations

import argparse
import json
import random
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .artifacts import (
    ORDER_SEEDS,
    RESEARCH,
    ROOT,
    canonical,
    digest,
    freeze,
    manifest,
    object_hash,
    read_jsonl,
    verify,
    write_json,
    write_jsonl,
)
from .backend import TokenCounter, snapshot
from .budgets import build_points, corpus_bytes, gate_burden, token_match
from .forced_choice import LABELS
from .interface_pilot import CALIBRATION, format_metrics
from .neutral_codes import (
    CODES,
    MAPPINGS,
    SYSTEM,
    NeutralCodeTransport,
    parse_code,
    render_codes,
    request_mapping,
    response_parser,
)
from .phase2b import load_frozen
from .pilot import reuse_plan
from .pilot import run as execute_run
from .pilot_analysis import CONDITIONS, analyze
from .requests import build_requests, solver_payload


def lock() -> dict:
    return json.loads((RESEARCH / "neutral-code-lock.json").read_text())


def solver(spec: dict) -> dict:
    return {
        "model_id": spec["repo_id"],
        "revision": spec["revision"],
        "temperature": 0,
        "max_output_tokens": 2,
    }


def diagnostic_requests(items: list[dict], spec: dict) -> list[dict]:
    """Only input and opaque routing ID are read. Keys do not affect schedule/prompts."""
    rows = []
    for item in sorted(items, key=lambda r: r["calibration_id"]):
        for index, mapping in enumerate(MAPPINGS):
            payload = solver_payload(item["input"], item["input"]["memories"], 2026)
            payload["answer_code_mapping"] = mapping
            request = {
                "model": {**solver(spec), "generation_seed": 2026},
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": canonical(payload)},
                ],
            }
            block = object_hash(
                ["neutral-code-diagnostic", item["calibration_id"], index, solver(spec)]
            )
            rows.append(
                {
                    "request_id": object_hash([block, "calibration", request]),
                    "block_id": block,
                    "case_id": item["calibration_id"],
                    "condition": "calibration",
                    "order_seed": 2026,
                    "threshold": None,
                    "prefix": None,
                    "mapping_index": index,
                    "request": request,
                }
            )
    random.Random(20261115).shuffle(rows)
    return [{**r, "global_execution_index": i} for i, r in enumerate(rows)]


def balanced_schedule(case_ids: list[str]) -> list[dict]:
    if len(case_ids) != len(set(case_ids)) or len(case_ids) != 20:
        raise ValueError("Development schedule requires exactly twenty case IDs")
    indices = list(range(6)) * 10
    random.Random(20261116).shuffle(indices)
    pairs = [(cid, seed) for cid in sorted(case_ids) for seed in ORDER_SEEDS]
    return [
        {"case_id": cid, "order_seed": seed, "mapping_index": index}
        for (cid, seed), index in zip(pairs, indices, strict=True)
    ]


def development_requests(public: dict, selected: dict, spec: dict) -> tuple[list, list]:
    schedule = balanced_schedule(list(public))
    mapping_index = {(r["case_id"], r["order_seed"]): r["mapping_index"] for r in schedule}
    rows = []
    for cid in sorted(public):
        outputs = {name: selected[name]["outputs"][cid] for name in CONDITIONS}
        for row in build_requests(cid, public[cid], outputs, 0.95, 3, solver(spec)):
            index = mapping_index[(cid, row["order_seed"])]
            payload = json.loads(row["request"]["messages"][1]["content"])
            payload["answer_code_mapping"] = MAPPINGS[index]
            row["request"]["messages"][0]["content"] = SYSTEM
            row["request"]["messages"][1]["content"] = canonical(payload)
            row["request"]["model"]["generation_seed"] = row["order_seed"]
            row["block_id"] = object_hash(["neutral-code-development", row["block_id"], index])
            row["request_id"] = object_hash([row["block_id"], row["condition"], row["request"]])
            row["mapping_index"] = index
            row["source_point_id"] = selected[row["condition"]]["point_id"]
            rows.append(row)
    return [{**r, "global_execution_index": i} for i, r in enumerate(rows)], schedule


def verified_eligibility(directory: Path) -> dict:
    for name in (
        "freeze.json",
        "responses.freeze.json",
        "execution.freeze.json",
        "analysis.freeze.json",
    ):
        verify(directory, name)
    info = json.loads((directory / "manifest.json").read_text())
    result = json.loads((directory / "diagnostic-analysis.json").read_text())
    if (
        info["experiment"] != "neutral-code-diagnostic"
        or not result["eligible"]
        or result.get("provenance") != "real"
    ):
        raise ValueError("Neutral-code diagnostic failed aggregate eligibility; stop inference")
    for name in (
        "neutral-code-lock.json",
        "harness/neutral_codes.py",
        "harness/code_diagnostic.py",
    ):
        relative = str((RESEARCH / name).relative_to(ROOT))
        if info["source_sha256"][relative] != digest((RESEARCH / name).read_bytes()):
            raise ValueError("Interface or analysis changed after diagnostic")
    return info


def prepare(
    kind: str,
    cache: Path,
    output: Path,
    diagnostic: Path | None = None,
    source: Path | None = None,
    source2b: Path | None = None,
) -> dict:
    if output.exists():
        raise ValueError("Refusing to overwrite a neutral-code experiment")
    if kind not in {"diagnostic", "development"}:
        raise ValueError("Unknown experiment kind")
    plan = lock()
    qualification = None
    if kind == "development":
        if diagnostic is None or source is None or source2b is None:
            raise ValueError("Development requires qualified diagnostic and both frozen sources")
        qualification = verified_eligibility(diagnostic)
    baseline = subprocess.check_output(
        [
            "git",
            "show",
            "8cd4ca705f2340aa519ebead897f484d49d450bb:research/ai_epistemics_2026/interface-calibration.jsonl",
        ],
        cwd=ROOT,
    )
    if digest(CALIBRATION.read_bytes()) != digest(baseline):
        raise ValueError("Existing calibration items or keys changed")
    path, assets = snapshot(plan["model"], cache, False)
    if "model.safetensors" not in assets["files_sha256"]:
        raise ValueError("Cached full selected checkpoint is required; no download allowed")
    if qualification and qualification["model"] != assets:
        raise ValueError("Development model differs from qualified model")
    counter = TokenCounter(path, assets)
    extra = {}
    if kind == "diagnostic":
        items = read_jsonl(CALIBRATION)
        if len(items) != 18 or len({i["calibration_id"] for i in items}) != 18:
            raise ValueError("Expected eighteen existing calibration items")
        requests = diagnostic_requests(items, plan["model"])
        if len(requests) != 108:
            raise ValueError("Incomplete item/permutation grid")
        data = CALIBRATION
        extra["calibration-keys.json"] = {i["calibration_id"]: i["evaluator_only"] for i in items}
    else:
        verify(source2b, "selection.freeze.json")
        verify(source2b, "analysis.freeze.json")
        data = RESEARCH / "development.jsonl"
        rows, public, _ = load_frozen(source, data)
        rows = [r for r in rows if r["threshold"] == 0.95]
        points, _ = build_points(rows, counter)
        previous = {p["point_id"]: p for p in read_jsonl(source2b / "points.jsonl")}
        if any(corpus_bytes(p) != corpus_bytes(previous[p["point_id"]]) for p in points):
            raise ValueError("Frozen candidate/medoid transformations changed")
        anchors = {p["method"]: p for p in points if p["method"] != "similarity_first"}
        match = token_match(
            anchors["gated"], [p for p in points if p["method"] == "similarity_first"]
        )
        if match["status"] != "matched" or match["control"] != "0.95:similarity_first:3":
            raise ValueError(
                f"Frozen similarity control is not the nearest eligible token match: {match}"
            )
        selected = {
            **anchors,
            "similarity_first": next(p for p in points if p["point_id"] == match["control"]),
        }
        requests, schedule = development_requests(public, selected, plan["model"])
        if Counter(r["condition"] for r in requests) != dict.fromkeys(CONDITIONS, 60):
            raise ValueError("Incomplete paired development denominators")
        extra.update(
            {
                "mapping-schedule.json": schedule,
                "token-matching.json": {
                    "match": match,
                    "points": [{k: v for k, v in p.items() if k != "outputs"} for p in points],
                },
                "gate-burden.json": gate_burden(rows),
            }
        )
    info = manifest(data, json.loads((RESEARCH / "model-lock.json").read_text()))
    info.update(
        {
            "experiment": f"neutral-code-{kind}",
            "purpose": "exploratory code mapping diagnostic; no explanations collected",
            "prepared_utc": datetime.now(timezone.utc).isoformat(),
            "model": assets,
            "model_cache": str(cache),
            "solver": solver(plan["model"]),
            "generation": plan["generation"],
            "limits": plan["limits"],
            "eligibility_thresholds": plan["eligibility"],
            "mappings": MAPPINGS,
            "planned_logical_requests": len(requests),
            "diagnostic_order_seed": plan["diagnostic_order_seed"],
            "development_mapping_seed": plan["development_mapping_seed"],
            "human_review_status": "pending",
            "paid_calls_authorized": False,
            "qualified_diagnostic_freeze_sha256": digest(
                (diagnostic / "analysis.freeze.json").read_bytes()
            )
            if diagnostic
            else None,
            "source_freezes": {
                "phase2": digest((source / "freeze.json").read_bytes()),
                "phase2b": digest((source2b / "selection.freeze.json").read_bytes()),
            }
            if source and source2b
            else None,
        }
    )
    for name in (
        "NEUTRAL_CODE_PLAN.md",
        "LABEL_TOKEN_INSPECTION.md",
        "neutral-code-lock.json",
        "interface-calibration.jsonl",
    ):
        info["source_sha256"][str((RESEARCH / name).relative_to(ROOT))] = digest(
            (RESEARCH / name).read_bytes()
        )
    reuse = reuse_plan(requests)
    owners = {r["owner_request_id"] for r in reuse}
    info["planned_physical_first_attempts"] = len(owners)
    rendered = [
        {
            "request_id": r["request_id"],
            **render_codes(counter.tokenizer, r["request"], info["solver"]),
        }
        for r in requests
        if r["request_id"] in owners
    ]
    output.mkdir(parents=True)
    write_json(output / "manifest.json", info)
    write_jsonl(output / "requests.jsonl", requests)
    write_json(output / "reuse-plan.json", reuse)
    write_jsonl(output / "rendered-requests.jsonl", rendered)
    for name, value in extra.items():
        write_json(output / name, value)
    freeze(
        output,
        ["manifest.json", "requests.jsonl", "reuse-plan.json", "rendered-requests.jsonl", *extra],
    )
    return {
        "run": str(output),
        "planned": len(requests),
        "physical": len(owners),
        "solver_calls": 0,
    }


def execute(directory: Path) -> dict:
    verify(directory)
    if any(
        (directory / name).exists() for name in ("responses.jsonl", "physical-submissions.jsonl")
    ):
        raise ValueError("Refusing to repeat a started experiment")
    info = json.loads((directory / "manifest.json").read_text())
    if info["experiment"] not in {"neutral-code-diagnostic", "neutral-code-development"}:
        raise ValueError("Unknown experiment")
    for name, expected in info["source_sha256"].items():
        if digest((ROOT / name).read_bytes()) != expected:
            raise ValueError(f"Source changed after preparation: {name}")
    path, assets = snapshot(info["model"], Path(info["model_cache"]), False)
    if assets != info["model"]:
        raise ValueError("Selected cached model assets changed")
    transport = NeutralCodeTransport(path, info["solver"], info["generation"], info["limits"])
    return execute_run(directory, transport)


def summarize(rows: list[dict]) -> dict:
    if len(rows) != 108 or len({(r["case_id"], r["mapping_index"]) for r in rows}) != 108:
        raise ValueError("Incomplete/duplicate diagnostic pairs")
    cases = sorted({r["case_id"] for r in rows})
    if len(cases) != 18 or Counter(r["mapping_index"] for r in rows) != dict.fromkeys(range(6), 18):
        raise ValueError("Expected every item crossed with all six mappings")
    if Counter(r["gold_label"] for r in rows) != dict.fromkeys(LABELS, 36):
        raise ValueError("Expected thirty-six planned pairs per semantic class")
    valid, correct = sum(r["valid"] for r in rows), sum(r["correct"] for r in rows)
    by_item = []
    for cid in cases:
        item = sorted([r for r in rows if r["case_id"] == cid], key=lambda r: r["mapping_index"])
        codes = {r["code"] for r in item if r["valid"]}
        labels = {r["label"] for r in item if r["valid"]}
        by_item.append(
            {
                "case_id": cid,
                "valid": sum(r["valid"] for r in item),
                "codes": [r["code"] for r in item],
                "labels": [r["label"] for r in item],
                "correct": [r["correct"] for r in item],
                "distinct_valid_codes": len(codes),
                "distinct_valid_labels": len(labels),
            }
        )

    def counts(subset):
        return {
            "planned": len(subset),
            "valid": sum(r["valid"] for r in subset),
            "correct": sum(r["correct"] for r in subset),
            "accuracy": sum(r["correct"] for r in subset) / len(subset),
        }

    return {
        "planned": 108,
        "reused_calibration_items": 18,
        "valid": valid,
        "correct": correct,
        "valid_but_wrong": valid - correct,
        "validity": valid / 108,
        "accuracy": correct / 108,
        "eligible": valid >= 103 and correct >= 87,
        "parse_reasons": dict(Counter(r["reason"] for r in rows)),
        "output_code_distribution_valid": {
            code: sum(r["code"] == code for r in rows) for code in CODES
        },
        "semantic_distribution_valid": {
            label: sum(r["label"] == label for r in rows) for label in LABELS
        },
        "by_permutation": {
            f"P{i + 1}": {
                "mapping": MAPPINGS[i],
                **counts([r for r in rows if r["mapping_index"] == i]),
            }
            for i in range(6)
        },
        "by_semantic_class": {
            label: counts([r for r in rows if r["gold_label"] == label]) for label in LABELS
        },
        "confusion": {
            gold: {
                str(pred): sum(r["gold_label"] == gold and r["label"] == pred for r in rows)
                for pred in (*LABELS, None)
            }
            for gold in LABELS
        },
        "insufficient_evidence_selection": {
            "correct": sum(r["gold_label"] == LABELS[2] and r["label"] == LABELS[2] for r in rows),
            "gold_pairs": 36,
            "predicted": sum(r["label"] == LABELS[2] for r in rows),
            "false_abstentions": sum(
                r["gold_label"] != LABELS[2] and r["label"] == LABELS[2] for r in rows
            ),
        },
        "items_with_at_least_two_valid": sum(i["valid"] >= 2 for i in by_item),
        "items_changing_semantic_answer_among_valid": sum(
            i["distinct_valid_labels"] > 1 for i in by_item
        ),
        "items_changing_code_among_valid": sum(i["distinct_valid_codes"] > 1 for i in by_item),
        "items_with_six_valid": sum(i["valid"] == 6 for i in by_item),
        "items_invariant_semantics_all_six_valid": sum(
            i["valid"] == 6 and i["distinct_valid_labels"] == 1 for i in by_item
        ),
        "items_same_code_all_six_valid": sum(
            i["valid"] == 6 and i["distinct_valid_codes"] == 1 for i in by_item
        ),
        "by_item": by_item,
        "independent_human_reviews": 0,
        "explanation_support": "not collected",
    }


def score_diagnostic(directory: Path) -> dict:
    for name in ("freeze.json", "responses.freeze.json", "execution.freeze.json"):
        verify(directory, name)
    if (directory / "analysis.freeze.json").exists():
        raise ValueError("Refusing to replace diagnostic analysis")
    info = json.loads((directory / "manifest.json").read_text())
    if info["experiment"] != "neutral-code-diagnostic":
        raise ValueError("Not the diagnostic")
    requests = read_jsonl(directory / "requests.jsonl")
    responses = read_jsonl(directory / "responses.jsonl")
    if len(responses) != 108 or len({r["request_id"] for r in responses}) != 108:
        raise ValueError("Every planned response is required")
    if any(r["provenance"] != "real" for r in responses):
        raise ValueError("Synthetic fixtures cannot qualify a solver")
    lookup = {r["request_id"]: r for r in responses}
    if set(lookup) != {r["request_id"] for r in requests}:
        raise ValueError("Response IDs differ from frozen requests")
    keys = json.loads((directory / "calibration-keys.json").read_text())
    scores = []
    for request in requests:
        result = parse_code(lookup[request["request_id"]], request_mapping(request["request"]))
        gold = keys[request["case_id"]]["answer_label"]
        scores.append(
            {
                "request_id": request["request_id"],
                "case_id": request["case_id"],
                "mapping_index": request["mapping_index"],
                "gold_label": gold,
                "code": result["code"],
                "label": result["label"],
                "reason": result["reason"],
                "valid": result["label"] is not None,
                "correct": result["label"] == gold,
            }
        )
    report = summarize(scores)
    report["provenance"] = "real"
    write_jsonl(directory / "diagnostic-scores.jsonl", scores)
    write_json(directory / "diagnostic-analysis.json", report)
    freeze(
        directory, ["diagnostic-scores.jsonl", "diagnostic-analysis.json"], "analysis.freeze.json"
    )
    return report


def score_development(directory: Path) -> dict:
    requests = read_jsonl(directory / "requests.jsonl")
    analyze(
        directory,
        RESEARCH / "development.jsonl",
        response_parser(requests),
        explanations_collected=False,
    )
    result = format_metrics(read_jsonl(directory / "scores.jsonl"))
    write_json(directory / "interface-metrics.json", result)
    freeze(directory, ["interface-metrics.json"], "interface-analysis.freeze.json")
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument(
        "command", choices=["prepare-diagnostic", "prepare-development", "run", "score"]
    )
    cli.add_argument("--run", type=Path, required=True)
    for name in ("cache", "diagnostic", "source", "source2b"):
        cli.add_argument(f"--{name}", type=Path)
    args = cli.parse_args()
    if args.command.startswith("prepare-"):
        if args.cache is None:
            cli.error("Preparation requires the existing --cache")
        result = prepare(
            args.command.removeprefix("prepare-"),
            args.cache,
            args.run,
            args.diagnostic,
            args.source,
            args.source2b,
        )
    elif args.command == "run":
        result = execute(args.run)
    else:
        info = json.loads((args.run / "manifest.json").read_text())
        result = (
            score_diagnostic(args.run)
            if info["experiment"] == "neutral-code-diagnostic"
            else score_development(args.run)
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
