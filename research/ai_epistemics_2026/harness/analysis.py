"""Post-freeze decision scoring and paired family analysis, never a merge input."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean

import numpy as np

from .artifacts import digest, read_jsonl, verify
from .execution import parse_response


def score_frozen(
    directory, cases: list[dict], data_bytes: bytes, response_parser=parse_response
) -> list[dict]:
    import json

    verify(directory)
    verify(directory, "responses.freeze.json")
    manifest = json.loads((directory / "manifest.json").read_text())
    if digest(data_bytes) != manifest["data_sha256"]:
        raise ValueError("Scoring data differs from frozen transformation data")
    requests = read_jsonl(directory / "requests.jsonl")
    responses = read_jsonl(directory / "responses.jsonl")
    if len({r["request_id"] for r in responses}) != len(responses):
        raise ValueError("Duplicate responses")
    lookup = {r["request_id"]: r for r in responses}
    if set(lookup) != {r["request_id"] for r in requests}:
        raise ValueError("Missing or unknown responses; do not silently change pairing")
    case_map = {c["case_id"]: c for c in cases}
    excluded = {
        r["block_id"] for r in requests if lookup[r["request_id"]]["status"] == "infrastructure"
    }
    rows = []
    for request in requests:
        case = case_map[request["case_id"]]
        response = lookup[request["request_id"]]
        parsed = response_parser(response)
        error = parsed["error"]
        if parsed["label"] is not None:
            error = int(parsed["label"] not in case["evaluator_only"]["acceptable_answer_labels"])
        rows.append(
            {
                **{
                    k: request[k]
                    for k in (
                        "block_id",
                        "case_id",
                        "condition",
                        "threshold",
                        "prefix",
                        "order_seed",
                    )
                },
                "model_id": request["request"]["model"]["model_id"],
                "model_revision": request["request"]["model"]["revision"],
                "family_id": case["family_id"],
                "error": error,
                "excluded": request["block_id"] in excluded,
                "exclusion_reason": "paired_infrastructure"
                if request["block_id"] in excluded
                else None,
                "parse_reason": parsed["reason"],
                "provenance": response["provenance"],
            }
        )
    return rows


def family_metrics(rows: list[dict], condition: str) -> dict:
    """One model + operating point. Average repetitions, then cases, then families."""
    axes = {(r["model_id"], r.get("model_revision"), r["threshold"], r["prefix"]) for r in rows}
    if len(axes) > 1:
        raise ValueError("Analyze each model/revision/operating point separately")
    blocks = defaultdict(dict)
    for row in rows:
        if row["condition"] in blocks[row["block_id"]]:
            raise ValueError("Duplicate condition within paired block")
        blocks[row["block_id"]][row["condition"]] = row
    case_values = defaultdict(list)
    transition = {
        "correct_to_wrong": 0,
        "wrong_to_correct": 0,
        "correct_to_correct": 0,
        "wrong_to_wrong": 0,
    }
    excluded = 0
    for values in blocks.values():
        if "original" not in values or condition not in values:
            raise ValueError("Incomplete paired block")
        if any(r["excluded"] for r in values.values()):
            excluded += 1
            continue
        base, changed = values["original"], values[condition]
        if base["error"] not in (0, 1) or changed["error"] not in (0, 1):
            raise ValueError("Unscored error in included block")
        if (base["family_id"], base["case_id"]) != (changed["family_id"], changed["case_id"]):
            raise ValueError("Pair identity mismatch")
        case_values[(base["family_id"], base["case_id"])].append(
            (changed["error"] - base["error"], base["error"], changed["error"])
        )
        key = (
            ("correct" if base["error"] == 0 else "wrong")
            + "_to_"
            + ("correct" if changed["error"] == 0 else "wrong")
        )
        transition[key] += 1
    families = defaultdict(list)
    for (family, _), values in case_values.items():
        families[family].append([mean(v[i] for v in values) for i in range(3)])
    summaries = {
        family: [mean(v[i] for v in values) for i in range(3)]
        for family, values in sorted(families.items())
    }
    original_correct = transition["correct_to_correct"] + transition["correct_to_wrong"]
    original_wrong = transition["wrong_to_wrong"] + transition["wrong_to_correct"]
    return {
        "condition": condition,
        "paired_change": mean(v[0] for v in summaries.values()) if summaries else None,
        "original_error": mean(v[1] for v in summaries.values()) if summaries else None,
        "condition_error": mean(v[2] for v in summaries.values()) if summaries else None,
        "family_values": summaries,
        "included_families": len(summaries),
        "included_cases": len(case_values),
        "excluded_blocks": excluded,
        "transitions": transition,
        "introduced": {
            "numerator": transition["correct_to_wrong"],
            "denominator": original_correct,
        },
        "rescued": {"numerator": transition["wrong_to_correct"], "denominator": original_wrong},
    }


def bootstrap(rows: list[dict], condition: str, resamples: int = 10000, seed: int = 2026) -> dict:
    point = family_metrics(rows, condition)
    families = sorted(point["family_values"])
    if not families:
        return {
            "paired_change_95ci": None,
            "introduced_rate_95ci": None,
            "rescued_rate_95ci": None,
            "undefined_ratio_resamples": resamples,
        }
    rng = np.random.default_rng(seed)
    per_family = {}
    for family in families:
        per_family[family] = family_metrics(
            [r for r in rows if r["family_id"] == family], condition
        )
    changes, introduced, rescued = [], [], []
    for _ in range(resamples):
        sampled = rng.choice(families, size=len(families), replace=True)
        changes.append(mean(point["family_values"][f][0] for f in sampled))
        for name, destination in (("introduced", introduced), ("rescued", rescued)):
            numerator = sum(per_family[f][name]["numerator"] for f in sampled)
            denominator = sum(per_family[f][name]["denominator"] for f in sampled)
            if denominator:
                destination.append(numerator / denominator)

    def interval(values):
        return np.percentile(values, [2.5, 97.5]).tolist() if values else None

    return {
        "paired_change_95ci": interval(changes),
        "introduced_rate_95ci": interval(introduced),
        "rescued_rate_95ci": interval(rescued),
        "introduced_undefined_resamples": resamples - len(introduced),
        "rescued_undefined_resamples": resamples - len(rescued),
        "resamples": resamples,
        "seed": seed,
        "unit": "scenario_family",
    }


def compression_matches(points: list[dict], tolerance: float = 0.02) -> list[dict]:
    """Label-blind nearest compression match, before response scoring."""
    output = []
    for gated in [p for p in points if p["condition"] == "gated"]:
        choices = [
            p
            for p in points
            if p["condition"] == "semantic"
            and p["token_compression"] is not None
            and gated["token_compression"] is not None
        ]
        choices.sort(
            key=lambda p: (
                abs(p["token_compression"] - gated["token_compression"]),
                -p["threshold"],
                p["prefix"],
            )
        )
        selected = choices[0] if choices else None
        mismatch = (
            abs(selected["token_compression"] - gated["token_compression"]) if selected else None
        )
        output.append(
            {
                "gated": gated,
                "semantic": selected if mismatch is not None and mismatch <= tolerance else None,
                "mismatch": mismatch,
                "status": "matched"
                if mismatch is not None and mismatch <= tolerance
                else "unreachable_or_tokens_unavailable",
            }
        )
    return output


def gate_contrast(rows: list[dict]) -> dict:
    """Paired gated-minus-semantic error, sharing the SAME family bootstrap draws."""
    semantic = {r["block_id"]: r for r in rows if r["condition"] == "semantic"}
    paired = []
    for row in rows:
        if row["condition"] == "original":
            if row["block_id"] not in semantic:
                raise ValueError("Missing semantic contrast reference")
            paired.append({**semantic[row["block_id"]], "condition": "original"})
        elif row["condition"] == "gated":
            paired.append(row)
    return {
        "reference": "semantic",
        **family_metrics(paired, "gated"),
        **bootstrap(paired, "gated"),
    }
