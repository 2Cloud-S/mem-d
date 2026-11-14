"""Prepare, freeze, and execute only the bounded 0.95 development pilot."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from .artifacts import (
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
from .budgets import build_points, corpus_bytes, token_match
from .execution import execute, freeze_responses
from .local_solver import LocalTransport, render_request
from .phase2b import load_frozen
from .requests import build_requests


def reuse_plan(requests: list[dict]) -> list[dict]:
    owners = {}
    plan = []
    for row in requests:
        key = (row["block_id"], canonical(row["request"]))
        owner = owners.setdefault(key, row["request_id"])
        plan.append(
            {
                "request_id": row["request_id"],
                "owner_request_id": owner,
                "block_id": row["block_id"],
                "reused": owner != row["request_id"],
            }
        )
    return plan


def prepare(
    source: Path, source2b: Path, data: Path, cache: Path, family: str, output: Path
) -> dict:
    if output.exists():
        raise ValueError("Refusing to overwrite a pilot")
    verify(source2b, "selection.freeze.json")
    verify(source2b, "analysis.freeze.json")
    plan = json.loads((RESEARCH / "pilot-lock.json").read_text())
    spec = next(m for m in plan["models"] if m["family"] == family)
    model_path, assets = snapshot(spec, cache, False)
    if "model.safetensors" not in assets["files_sha256"]:
        raise ValueError(
            "Full selected generation weights are missing; tokenizer-only is not a solver"
        )
    rows, public, old = load_frozen(source, data)
    rows = [r for r in rows if r["threshold"] == 0.95]
    frozen = [p for p in read_jsonl(source2b / "points.jsonl") if p["threshold"] == 0.95]
    counter = TokenCounter(model_path, assets)
    points, _ = build_points(rows, counter)
    old_points = {p["point_id"]: p for p in frozen}
    for point in points:
        if corpus_bytes(point) != corpus_bytes(old_points[point["point_id"]]):
            raise ValueError("Pilot transformed payloads differ from frozen Phase 2B")
    anchors = {p["method"]: p for p in points if p["method"] != "similarity_first"}
    match = token_match(anchors["gated"], [p for p in points if p["method"] == "similarity_first"])
    control_id = "0.95:similarity_first:3"
    if match["status"] != "matched" or match["control"] != control_id:
        raise ValueError(f"Tokenizer-specific matching blocks {family}: {match}")
    control = next(p for p in points if p["point_id"] == control_id)
    selected = {
        "original": anchors["original"],
        "exact": anchors["exact"],
        "similarity_first": control,
        "gated": anchors["gated"],
    }
    solver = {
        "model_id": spec["repo_id"],
        "revision": spec["revision"],
        "temperature": 0,
        "max_output_tokens": 256,
    }
    requests = []
    for cid in sorted(public):
        outputs = {name: point["outputs"][cid] for name, point in selected.items()}
        for row in build_requests(cid, public[cid], outputs, 0.95, 3, solver):
            row["request"]["model"]["generation_seed"] = row["order_seed"]
            row["request_id"] = object_hash([row["block_id"], row["condition"], row["request"]])
            row["source_point_id"] = selected[row["condition"]]["point_id"]
            requests.append(row)
    reuse = reuse_plan(requests)
    owner_ids = {r["owner_request_id"] for r in reuse}
    rendered = [
        {"request_id": r["request_id"], **render_request(counter.tokenizer, r["request"], solver)}
        for r in requests
        if r["request_id"] in owner_ids
    ]
    info = manifest(data, old["model_lock"])
    info.update(
        {
            "schema": "phase3-pilot-v1",
            "purpose": "exploratory development solver pilot",
            "prepared_utc": datetime.now(timezone.utc).isoformat(),
            "model": assets,
            "solver": solver,
            "generation": plan["generation"],
            "limits": plan["limits"],
            "model_cache": str(cache),
            "model_path": str(model_path),
            "planned_cases": 20,
            "planned_families": 10,
            "planned_order_blocks": 60,
            "planned_logical_requests": len(requests),
            "planned_physical_first_attempts": len(owner_ids),
            "source2b_selection_freeze_sha256": digest(
                (source2b / "selection.freeze.json").read_bytes()
            ),
            "source2b_analysis_freeze_sha256": digest(
                (source2b / "analysis.freeze.json").read_bytes()
            ),
            "source_phase2_freeze_sha256": digest((source / "freeze.json").read_bytes()),
            "threshold_selection": (
                "0.95 chosen for pre-answer non-identical development transformations"
            ),
            "human_review_status": "pending",
            "independently_preregistered": False,
            "condition_point_ids": {name: p["point_id"] for name, p in selected.items()},
            "prefix_field_meaning": "paired comparison stratum 3; gate is unchanged full anchor",
            "paid_calls_authorized": False,
        }
    )
    for name in ("PILOT_PLAN.md", "pilot-lock.json"):
        info["source_sha256"][str((RESEARCH / name).relative_to(ROOT))] = digest(
            (RESEARCH / name).read_bytes()
        )
    if len(requests) != 240 or len({r["block_id"] for r in requests}) != 60:
        raise ValueError("Incomplete pilot denominators")
    output.mkdir(parents=True)
    write_json(output / "manifest.json", info)
    write_jsonl(output / "requests.jsonl", requests)
    write_json(output / "reuse-plan.json", reuse)
    write_jsonl(output / "rendered-requests.jsonl", rendered)
    write_json(
        output / "token-matching.json",
        {
            "match": match,
            "points": [{k: v for k, v in p.items() if k != "outputs"} for p in points],
            "selected_points": {name: p["point_id"] for name, p in selected.items()},
        },
    )
    freeze(
        output,
        [
            "manifest.json",
            "requests.jsonl",
            "reuse-plan.json",
            "rendered-requests.jsonl",
            "token-matching.json",
        ],
    )
    return {
        "family": family,
        "logical_requests": len(requests),
        "physical_first_attempts": len(owner_ids),
        "matching": match,
        "output": str(output),
        "solver_calls": 0,
    }


def run(directory: Path, transport=None) -> dict:
    verify(directory)
    if any(
        (directory / name).exists() for name in ("responses.jsonl", "physical-submissions.jsonl")
    ):
        raise ValueError("Refusing to rerun or overwrite a started pilot")
    info = json.loads((directory / "manifest.json").read_text())
    requests = read_jsonl(directory / "requests.jsonl")
    expected = json.loads((directory / "reuse-plan.json").read_text())
    if expected != reuse_plan(requests):
        raise ValueError("Reuse plan differs from frozen request bytes")
    if transport is None:
        path, assets = snapshot(info["model"], Path(info["model_cache"]), False)
        if assets["files_sha256"] != info["model"]["files_sha256"]:
            raise ValueError("Generation weights or tokenizer changed after pilot freeze")
        transport = LocalTransport(path, info["solver"], info["generation"], info["limits"])
    owners, responses, physical = {}, [], []
    mapping = {r["request_id"]: r for r in expected}
    log_path = directory / "physical-submissions.jsonl"
    with log_path.open("x", encoding="utf-8") as log:
        for index, row in enumerate(requests):
            record = mapping[row["request_id"]]
            owner_id = record["owner_request_id"]
            if owner_id not in owners:
                if owner_id != row["request_id"]:
                    raise ValueError("Reuse owner must precede dependent request")
                response = execute([row], transport)[0]
                owners[owner_id] = response
                for attempt_index, attempt in enumerate(response["attempts"], 1):
                    entry = {
                        "owner_request_id": owner_id,
                        "block_id": row["block_id"],
                        "attempt": attempt_index,
                        "submitted_request": row["request"],
                        "provenance": transport.provenance,
                        **attempt,
                    }
                    physical.append(entry)
                    log.write(canonical(entry) + "\n")
                    log.flush()
                print(
                    f"{index + 1}/{len(requests)} logical; "
                    f"{len(owners)} owners; status={response['status']}",
                    flush=True,
                )
            response = deepcopy(owners[owner_id])
            response["request_id"] = row["request_id"]
            if record["reused"]:
                for attempt in response["attempts"]:
                    attempt["reused_from_request_id"] = owner_id
            responses.append(response)
    freeze_responses(directory, responses)
    actual = [p for p in physical if p.get("inference_submitted", True)]
    usage = {
        key: sum((p.get("usage") or {}).get(key) or 0 for p in actual)
        for key in ("prompt_tokens", "completion_tokens")
    }
    summary = {
        "planned_logical_requests": len(requests),
        "physical_request_owners": len(owners),
        "reused_logical_requests": sum(r["reused"] for r in expected),
        "attempt_log_entries": len(physical),
        "actual_inference_attempts": len(actual),
        "actual_generated_token_usage": usage,
        "usage_missing_attempts": sum(p.get("usage") is None for p in actual),
        "physical_latency_seconds": sum(p.get("latency_seconds") or 0 for p in actual),
        "provenance": transport.provenance,
        "human_review_status": "pending",
    }
    write_json(directory / "execution-summary.json", summary)
    freeze(
        directory, ["physical-submissions.jsonl", "execution-summary.json"], "execution.freeze.json"
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    for arg in ("source", "source2b", "cache", "output"):
        p.add_argument(f"--{arg}", type=Path, required=True)
    p.add_argument("--family", choices=["Qwen2.5", "SmolLM2"], required=True)
    p.add_argument("--data", type=Path, default=RESEARCH / "development.jsonl")
    r = commands.add_parser("run")
    r.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    result = (
        prepare(args.source, args.source2b, args.data, args.cache, args.family, args.output)
        if args.command == "prepare"
        else run(args.run)
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
