"""Offline corpus budgets. Labels, questions, and semantic audits never enter selection."""

from __future__ import annotations

import random
from collections import Counter
from copy import deepcopy
from fractions import Fraction

from .artifacts import ORDER_SEEDS, canonical, object_hash
from .requests import SYSTEM, solver_payload
from .transform import MEMORY_FIELDS, memory_input, transform


def global_ranking(rows: list[dict]) -> list[dict]:
    """Rank only frozen groups; case ID is routing metadata, never a sort key."""
    ranked = []
    seen: set[str] = set()
    for row in rows:
        for group in row["candidates"]:
            if seen.intersection(group["members"]):
                raise ValueError("Candidate members must be disjoint, globally unique original IDs")
            seen.update(group["members"])
            ranked.append({"case_id": row["case_id"], "group": deepcopy(group)})
    return sorted(
        ranked,
        key=lambda x: (
            -x["group"]["mean_similarity"],
            tuple(sorted(x["group"]["members"])),
            x["group"]["medoid"],
        ),
    )


def apply_groups(records: list[dict], groups: list[dict]) -> dict:
    original = memory_input(records)
    ids = {m["id"] for m in original}
    seen: set[str] = set()
    for group in groups:
        members = set(group["members"])
        if not members <= ids or group["medoid"] not in members or seen.intersection(members):
            raise ValueError("Cannot apply cross-case, overlapping, or malformed groups")
        seen.update(members)
    removed = {m for g in groups for m in g["members"] if m != g["medoid"]}
    return {
        "memories": [deepcopy(m) for m in original if m["id"] not in removed],
        "removed_ids": sorted(removed),
        "executed_groups": deepcopy(groups),
    }


def ordered_records(original: list[dict], survivors: list[dict], seed: int) -> list[dict]:
    order = [m["id"] for m in memory_input(original)]
    random.Random(seed).shuffle(order)
    rank = {key: i for i, key in enumerate(order)}
    return sorted(memory_input(survivors), key=lambda m: rank[m["id"]])


def corpus_bytes(point: dict) -> str:
    return canonical({cid: output["memories"] for cid, output in sorted(point["outputs"].items())})


def point_metrics(rows: list[dict], outputs: dict, counter) -> dict:
    counts, affected, non_exact = [], [], []
    for row in sorted(rows, key=lambda r: r["case_id"]):
        cid, original = row["case_id"], row["original_records"]
        output = outputs[cid]
        originals = {m["id"]: m for m in original}
        if any(m != originals.get(m["id"]) for m in output["memories"]):
            raise ValueError("Transformed payload was rewritten")
        if canonical(original) != canonical(output["memories"]):
            affected.append(cid)
        for group in output["executed_groups"]:
            payloads = {
                canonical({k: originals[mid][k] for k in MEMORY_FIELDS if k != "id"})
                for mid in group["members"]
            }
            if len(payloads) > 1:
                non_exact.append({"case_id": cid, "group": deepcopy(group)})
        for seed in ORDER_SEEDS:
            before = counter.count(ordered_records(original, original, seed))
            after = counter.count(ordered_records(original, output["memories"], seed))
            counts.append({"case_id": cid, "order_seed": seed, "before": before, "after": after})
    available = all(v["before"] is not None and v["after"] is not None for v in counts)
    before_sum = sum(v["before"] for v in counts) if available else None
    saved_sum = sum(v["before"] - v["after"] for v in counts) if available else None
    return {
        "records_removed": sum(len(o["removed_ids"]) for o in outputs.values()),
        "groups_executed": sum(len(o["executed_groups"]) for o in outputs.values()),
        "cases_affected": len(affected),
        "case_ids_affected": affected,
        "non_exact_groups": non_exact,
        "non_exact_group_count": len(non_exact),
        "token_counts": counts,
        "original_tokens_seed_sum": before_sum,
        "tokens_saved_seed_sum": saved_sum,
        "tokens_saved_mean_orders": saved_sum / len(ORDER_SEEDS) if available else None,
        "token_compression": saved_sum / before_sum if before_sum else None,
    }


def build_points(rows: list[dict], counter) -> tuple[list[dict], list[dict]]:
    ranking = global_ranking(rows)
    points = []
    threshold = rows[0]["threshold"]
    if any(r["threshold"] != threshold for r in rows):
        raise ValueError("Use a single threshold at a time")
    for method in ("original", "exact", "gated"):
        outputs = {
            r["case_id"]: transform(
                r["original_records"],
                method,
                r["candidates"],
                r["gate_decisions"],
                len(r["candidates"]),
            )
            for r in rows
        }
        points.append(
            {
                "point_id": f"{threshold}:{method}",
                "method": method,
                "threshold": threshold,
                "prefix": None,
                "outputs": outputs,
            }
        )
    for prefix in range(len(ranking) + 1):
        selected = ranking[:prefix]
        outputs = {
            r["case_id"]: apply_groups(
                r["original_records"],
                [g["group"] for g in selected if g["case_id"] == r["case_id"]],
            )
            for r in rows
        }
        points.append(
            {
                "point_id": f"{threshold}:similarity_first:{prefix}",
                "method": "similarity_first",
                "threshold": threshold,
                "prefix": prefix,
                "outputs": outputs,
            }
        )
    for point in points:
        point["metrics"] = point_metrics(rows, point["outputs"], counter)
        point["payload_sha256"] = object_hash(
            {cid: o["memories"] for cid, o in sorted(point["outputs"].items())}
        )
    return points, ranking


def token_match(target: dict, controls: list[dict]) -> dict:
    """Same threshold, exact integer-token sums, then shorter prefix. No identity tie-break."""
    metrics = target["metrics"]
    before, saved = metrics["original_tokens_seed_sum"], metrics["tokens_saved_seed_sum"]
    candidates = [p for p in controls if p["threshold"] == target["threshold"]]
    if (
        before is None
        or not before
        or saved is None
        or any(p["metrics"]["tokens_saved_seed_sum"] is None for p in candidates)
    ):
        return {"status": "tokens_unavailable", "target": target["point_id"], "control": None}
    if any(p["metrics"]["original_tokens_seed_sum"] != before for p in candidates):
        raise ValueError("Cannot match different original token budgets")
    candidates.sort(key=lambda p: (abs(p["metrics"]["tokens_saved_seed_sum"] - saved), p["prefix"]))
    if not candidates:
        return {"status": "unmatched", "target": target["point_id"], "control": None}
    chosen = candidates[0]
    delta = chosen["metrics"]["tokens_saved_seed_sum"] - saved
    matched = abs(delta) * 50 <= before  # inclusive 2 percentage points, no floating boundary
    return {
        "status": "matched" if matched else "unmatched",
        "target": target["point_id"],
        "control": chosen["point_id"] if matched else None,
        "nearest_control": chosen["point_id"],
        "residual_tokens_seed_sum": delta,
        "residual_tokens_mean_orders": delta / len(ORDER_SEEDS),
        "absolute_token_gap_mean_orders": abs(delta) / len(ORDER_SEEDS),
        "residual_compression_percentage_points": 100 * delta / before,
        "gap_relative_to_target_savings": abs(delta) / abs(saved) if saved else None,
        "absolute_tolerance_tokens_mean_orders": float(Fraction(before, 50 * len(ORDER_SEEDS))),
        "both_save_positive_tokens": saved > 0 and chosen["metrics"]["tokens_saved_seed_sum"] > 0,
    }


def payload_identity(a: dict, b: dict, public: dict[str, dict]) -> dict:
    """Identity is computed after matching; equal token counts are insufficient."""
    if set(a["outputs"]) != set(b["outputs"]) or set(a["outputs"]) != set(public):
        raise ValueError("Compare complete, identical case sets")
    different = [
        cid
        for cid in sorted(public)
        if canonical(a["outputs"][cid]["memories"]) != canonical(b["outputs"][cid]["memories"])
    ]
    solver_differences = []
    for cid in sorted(public):
        for seed in ORDER_SEEDS:
            messages = []
            for point in (a, b):
                payload = solver_payload(public[cid], point["outputs"][cid]["memories"], seed)
                messages.append(
                    canonical(
                        [
                            {"role": "system", "content": SYSTEM},
                            {"role": "user", "content": canonical(payload)},
                        ]
                    )
                )
            if messages[0] != messages[1]:
                solver_differences.append({"case_id": cid, "order_seed": seed})
    return {
        "left": a["point_id"],
        "right": b["point_id"],
        "byte_identical_survivor_payloads": corpus_bytes(a) == corpus_bytes(b),
        "byte_identical_solver_messages": not solver_differences,
        "differing_case_ids": different,
        "differing_solver_payloads": solver_differences,
    }


def gate_burden(rows: list[dict]) -> dict:
    return {
        "candidate_groups": sum(len(r["candidates"]) for r in rows),
        "original_memories": sum(len(r["original_records"]) for r in rows),
        "review_memories": sum(
            v["resolvedAction"] == "review" for r in rows for v in r["memd"]["resolutions"]
        ),
        "keeper_disagreements": sum(
            d["keeper_disagreement"] for r in rows for d in r["gate_decisions"]
        ),
        "review_groups": sum(
            any(
                v["resolvedAction"] == "review" and v["memoryId"] in g["members"]
                for v in r["memd"]["resolutions"]
            )
            for r in rows
            for g in r["candidates"]
        ),
        "approval_groups": sum(
            "approval_required" in d["veto_reasons"] for r in rows for d in r["gate_decisions"]
        ),
        "conflict_groups": sum(
            any("conflict" in reason for reason in d["veto_reasons"])
            for r in rows
            for d in r["gate_decisions"]
        ),
        "veto_groups": sum(not d["allowed"] for r in rows for d in r["gate_decisions"]),
        "veto_reason_counts_nonexclusive": dict(
            sorted(
                Counter(
                    reason
                    for r in rows
                    for d in r["gate_decisions"]
                    for reason in d["veto_reasons"]
                ).items()
            )
        ),
        "simple_controls_review_burden": "not_applicable; no review mechanism",
    }
