"""Bounded calibration and eligibility-gated development execution. No paid backend."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .artifacts import (
    RESEARCH,
    ROOT,
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
from .budgets import build_points, corpus_bytes, token_match
from .forced_choice import SYSTEM as CHOICE_SYSTEM
from .forced_choice import ForcedChoiceTransport, parse_choice, render_choice
from .phase2b import load_frozen
from .pilot import reuse_plan
from .pilot import run as execute_run
from .pilot_analysis import CONDITIONS, analyze
from .requests import SYSTEM, build_requests, solver_payload
from .transform import memory_input

CALIBRATION = RESEARCH / "interface-calibration.jsonl"


def lock() -> dict:
    return json.loads((RESEARCH / "forced-choice-lock.json").read_text())


def model_config(spec: dict) -> dict:
    return {
        "model_id": spec["repo_id"],
        "revision": spec["revision"],
        "temperature": 0,
        "max_output_tokens": 256,
    }


def calibration_requests(items: list[dict], spec: dict) -> list[dict]:
    """Evaluator keys are deliberately not read here."""
    rows = []
    for item in items:
        public = {
            k: item["input"][k]
            for k in ("memories", "question", "decision_criteria", "answer_options")
        }
        public["memories"] = memory_input(public["memories"])
        config = {**model_config(spec), "generation_seed": 2026}
        payload = solver_payload(public, public["memories"], 2026)
        from .artifacts import canonical

        request = {
            "model": config,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": canonical(payload)},
            ],
        }
        block = object_hash(["interface-calibration", item["calibration_id"], config])
        rows.append(
            {
                "request_id": object_hash([block, "calibration", request]),
                "block_id": block,
                "case_id": item["calibration_id"],
                "condition": "calibration",
                "order_seed": 2026,
                "threshold": None,
                "prefix": None,
                "request": request,
            }
        )
    random.Random(2026).shuffle(rows)
    return rows


def eligibility(directory: Path) -> dict:
    for name in (
        "freeze.json",
        "responses.freeze.json",
        "execution.freeze.json",
        "eligibility.freeze.json",
    ):
        verify(directory, name)
    info = json.loads((directory / "manifest.json").read_text())
    report = json.loads((directory / "eligibility.json").read_text())
    if (
        info["experiment"] != "phase3b-forced-calibration"
        or report["provenance"] != "real"
        or info["constraint"] != lock()["interface"]
    ):
        raise ValueError("Eligibility requires a real frozen calibration")
    return {"manifest": info, "report": report}


def prepare(
    kind: str,
    family: str,
    cache: Path,
    output: Path,
    calibration: Path | None = None,
    source: Path | None = None,
    source2b: Path | None = None,
    prior: list[Path] | None = None,
) -> dict:
    if output.exists():
        raise ValueError("Refusing to overwrite an interface experiment")
    plan = lock()
    spec = next(m for m in plan["models"] if m["family"] == family)
    if family == "Qwen2.5-1.5B" and kind == "calibration":
        previous = [eligibility(p) for p in prior or []]
        if {p["manifest"]["model"]["family"] for p in previous} != {"Qwen2.5", "SmolLM2"}:
            raise ValueError("First test both existing models")
        if any(p["report"]["eligible"] for p in previous):
            raise ValueError("No escalation when an existing model qualifies")
    path, assets = snapshot(spec, cache, False)
    if not any(name.endswith(".safetensors") for name in assets["files_sha256"]):
        raise ValueError("Full local weights are required")
    data = CALIBRATION if kind == "calibration" else RESEARCH / "development.jsonl"
    extra = {}
    counter = TokenCounter(path, assets)
    if kind == "calibration":
        items = read_jsonl(CALIBRATION)
        assert len(items) == len({i["calibration_id"] for i in items}) == 18
        assert Counter(i["evaluator_only"]["answer_label"] for i in items) == {
            "proceed": 6,
            "do_not_proceed": 6,
            "insufficient_evidence": 6,
        }
        requests = calibration_requests(items, spec)
        extra["calibration-keys.json"] = {i["calibration_id"]: i["evaluator_only"] for i in items}
    else:
        if calibration is None or source is None or source2b is None:
            raise ValueError("Development requires eligibility and both frozen sources")
        qualified = eligibility(calibration)
        if not qualified["report"]["eligible"]:
            raise ValueError("Model failed the frozen calibration thresholds")
        if qualified["manifest"]["model"] != assets:
            raise ValueError("Calibration and development must use identical model assets")
        for name in ("forced-choice-lock.json", "harness/forced_choice.py"):
            rel = str((RESEARCH / name).relative_to(ROOT))
            if qualified["manifest"]["source_sha256"][rel] != digest(
                (RESEARCH / name).read_bytes()
            ):
                raise ValueError("Interface changed after calibration")
        verify(source2b, "selection.freeze.json")
        verify(source2b, "analysis.freeze.json")
        rows, public, _ = load_frozen(source, data)
        points, _ = build_points([r for r in rows if r["threshold"] == 0.95], counter)
        previous = {p["point_id"]: p for p in read_jsonl(source2b / "points.jsonl")}
        if any(corpus_bytes(p) != corpus_bytes(previous[p["point_id"]]) for p in points):
            raise ValueError("Frozen transformed payload changed")
        anchors = {p["method"]: p for p in points if p["method"] != "similarity_first"}
        match = token_match(
            anchors["gated"], [p for p in points if p["method"] == "similarity_first"]
        )
        if match["status"] != "matched" or match["control"] != "0.95:similarity_first:3":
            raise ValueError(f"Frozen control is not the nearest eligible tokenizer match: {match}")
        selected = {
            **anchors,
            "similarity_first": next(p for p in points if p["point_id"] == match["control"]),
        }
        requests = []
        for cid in sorted(public):
            outputs = {name: selected[name]["outputs"][cid] for name in CONDITIONS}
            for row in build_requests(cid, public[cid], outputs, 0.95, 3, model_config(spec)):
                row["request"]["model"]["generation_seed"] = row["order_seed"]
                row["request_id"] = object_hash([row["block_id"], row["condition"], row["request"]])
                row["source_point_id"] = selected[row["condition"]]["point_id"]
                requests.append(row)
        if Counter(r["condition"] for r in requests) != dict.fromkeys(CONDITIONS, 60):
            raise ValueError("Incomplete development denominators")
        extra["token-matching.json"] = {
            "match": match,
            "points": [{k: v for k, v in p.items() if k != "outputs"} for p in points],
            "selected_points": {name: selected[name]["point_id"] for name in CONDITIONS},
        }
    # Construct actual forced-choice requests before hashing/freezing. The legacy
    # public-input builders above stay unchanged, including all survivor payloads.
    for row in requests:
        row["request"]["model"]["max_output_tokens"] = 24
        row["request"]["messages"][0]["content"] = CHOICE_SYSTEM
        row["request_id"] = object_hash([row["block_id"], row["condition"], row["request"]])
    info = manifest(data, json.loads((RESEARCH / "model-lock.json").read_text()))
    info.update(
        {
            "experiment": f"phase3b-forced-{kind}",
            "purpose": "forced-choice decision accuracy; explanations not collected",
            "prepared_utc": datetime.now(timezone.utc).isoformat(),
            "model": assets,
            "model_cache": str(cache),
            "solver": {**model_config(spec), "max_output_tokens": 24},
            "generation": plan["generation"],
            "limits": {
                "model_inference_seconds": plan["limits"][
                    ("larger_" if family == "Qwen2.5-1.5B" else "")
                    + ("calibration_seconds" if kind == "calibration" else "development_seconds")
                ],
                "submission_seconds": plan["limits"]["submission_seconds"],
            },
            "constraint": plan["interface"],
            "eligibility_thresholds": plan["eligibility"],
            "planned_logical_requests": len(requests),
            "human_review_status": "pending",
            "paid_calls_authorized": False,
            "calibration_eligibility_freeze_sha256": digest(
                (calibration / "eligibility.freeze.json").read_bytes()
            )
            if calibration
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
        "PHASE3B_PLAN.md",
        "PHASE3B_FORCED_CHOICE_PLAN.md",
        "interface-lock.json",
        "forced-choice-lock.json",
        "answer-schema.json",
        "interface-calibration.jsonl",
        "requirements-phase3b.txt",
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
            **render_choice(counter.tokenizer, r["request"], info["solver"]),
        }
        for r in requests
        if r["request_id"] in owners
    ]
    output.mkdir(parents=True)
    write_json(output / "manifest.json", info)
    write_jsonl(output / "requests.jsonl", requests)
    write_json(output / "reuse-plan.json", reuse)
    write_jsonl(output / "rendered-requests.jsonl", rendered)
    for name, content in extra.items():
        write_json(output / name, content)
    freeze(
        output,
        ["manifest.json", "requests.jsonl", "reuse-plan.json", "rendered-requests.jsonl", *extra],
    )
    return {
        "run": str(output),
        "kind": kind,
        "logical": len(requests),
        "physical": len(owners),
        "solver_calls": 0,
    }


def execute(directory: Path) -> dict:
    verify(directory)
    info = json.loads((directory / "manifest.json").read_text())
    for name, expected in info["source_sha256"].items():
        if digest((ROOT / name).read_bytes()) != expected:
            raise ValueError(f"Source changed after preparation: {name}")
    path, assets = snapshot(info["model"], Path(info["model_cache"]), False)
    if assets != info["model"]:
        raise ValueError("Pinned model assets changed")
    if not info["experiment"].startswith("phase3b-forced-"):
        raise ValueError("Legacy JSON trial requires source commit 8703c6b; never rerun it")
    transport = ForcedChoiceTransport(path, info["solver"], info["generation"], info["limits"])
    return execute_run(directory, transport)


def score_calibration(directory: Path) -> dict:
    for name in ("freeze.json", "responses.freeze.json", "execution.freeze.json"):
        verify(directory, name)
    if (directory / "eligibility.freeze.json").exists():
        raise ValueError("Refusing to rescore calibration")
    info = json.loads((directory / "manifest.json").read_text())
    if info["experiment"] != "phase3b-forced-calibration":
        raise ValueError("Not a calibration run")
    keys = json.loads((directory / "calibration-keys.json").read_text())
    requests = {r["request_id"]: r for r in read_jsonl(directory / "requests.jsonl")}
    responses = read_jsonl(directory / "responses.jsonl")
    if len(responses) != 18 or {r["request_id"] for r in responses} != set(requests):
        raise ValueError("Calibration must retain all 18 planned items")
    if any(r["provenance"] != "real" for r in responses):
        raise ValueError("Synthetic test fixtures cannot qualify a real solver")
    rows = []
    for response in responses:
        cid = requests[response["request_id"]]["case_id"]
        parsed = parse_choice(response)
        rows.append(
            {
                "calibration_id": cid,
                "request_id": response["request_id"],
                "valid": parsed["label"] is not None,
                "label": parsed["label"],
                "correct": parsed["label"] == keys[cid]["answer_label"],
                "reason": parsed["reason"],
            }
        )
    valid, correct = sum(r["valid"] for r in rows), sum(r["correct"] for r in rows)
    report = {
        "planned": 18,
        "valid": valid,
        "invalid": 18 - valid,
        "correct": correct,
        "valid_but_wrong": valid - correct,
        "validity": valid / 18,
        "accuracy": correct / 18,
        "eligible": meets_thresholds(valid, correct, len(rows), info["eligibility_thresholds"]),
        "model": info["model"]["repo_id"],
        "provenance": "real",
        "independent_human_validation": False,
    }
    write_jsonl(directory / "calibration-scores.jsonl", rows)
    write_json(directory / "eligibility.json", report)
    freeze(directory, ["eligibility.json", "calibration-scores.jsonl"], "eligibility.freeze.json")
    return report


def meets_thresholds(valid: int, correct: int, planned: int, thresholds: dict) -> bool:
    return (
        planned == thresholds["planned_items"]
        and valid >= thresholds["required_valid"]
        and correct >= thresholds["required_correct"]
    )


def format_metrics(rows: list[dict]) -> dict:
    output = {}
    for condition in sorted({r["condition"] for r in rows}):
        planned = [r for r in rows if r["condition"] == condition]
        included = [r for r in planned if not r["excluded"]]
        valid = sum(r["parse_reason"] == "valid_label" for r in included)
        correct = sum(r["error"] == 0 for r in included)
        output[condition] = {
            "planned": len(planned),
            "included": len(included),
            "excluded": len(planned) - len(included),
            "valid": valid,
            "invalid_included": len(included) - valid,
            "correct": correct,
            "valid_but_wrong": valid - correct,
            "decision_accuracy_among_valid": correct / valid if valid else None,
            "planned_parse_reasons": dict(Counter(r["parse_reason"] for r in planned)),
        }
    return output


def score_development(directory: Path) -> dict:
    analyze(directory, RESEARCH / "development.jsonl", parse_choice, explanations_collected=False)
    result = format_metrics(read_jsonl(directory / "scores.jsonl"))
    write_json(directory / "interface-metrics.json", result)
    freeze(directory, ["interface-metrics.json"], "interface-analysis.freeze.json")
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument(
        "command", choices=["prepare-calibration", "prepare-development", "run", "score"]
    )
    cli.add_argument("--run", type=Path, required=True)
    cli.add_argument("--family", choices=[m["family"] for m in lock()["models"]])
    for name in ("cache", "calibration", "source", "source2b"):
        cli.add_argument(f"--{name}", type=Path)
    cli.add_argument("--prior-calibration", type=Path, action="append", default=[])
    args = cli.parse_args()
    if args.command.startswith("prepare-"):
        if not args.family or not args.cache:
            cli.error("Preparation requires --family and --cache")
        result = prepare(
            args.command.removeprefix("prepare-"),
            args.family,
            args.cache,
            args.run,
            args.calibration,
            args.source,
            args.source2b,
            args.prior_calibration,
        )
    elif args.command == "run":
        result = execute(args.run)
    else:
        info = json.loads((args.run / "manifest.json").read_text())
        result = (
            score_calibration(args.run)
            if info["experiment"] == "phase3b-forced-calibration"
            else score_development(args.run)
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
