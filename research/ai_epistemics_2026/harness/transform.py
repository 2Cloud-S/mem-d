"""Gold-blind policies and conservative whole-group gate."""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime

import numpy as np

from .artifacts import canonical

MEMORY_FIELDS = ("id", "content", "source", "timestamp")
CONDITIONS = ("original", "exact", "semantic", "gated")


def memory_input(records: list[dict]) -> list[dict]:
    """Construct only the allowed fields; never forward metadata or the enclosing case."""
    result = [{key: deepcopy(record[key]) for key in MEMORY_FIELDS} for record in records]
    ids = [record["id"] for record in result]
    if len(set(ids)) != len(ids) or not result:
        raise ValueError("Need nonempty records with unique IDs")
    return sorted(result, key=lambda record: record["id"])


def fixed_query_time(records: list[dict]) -> str:
    return max(
        records, key=lambda m: datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00"))
    )["timestamp"]


def candidates(records: list[dict], clusters: list[dict], similarities: list[list]) -> list[dict]:
    indexes = {m["id"]: i for i, m in enumerate(records)}
    matrix = np.asarray(similarities)
    output = []
    seen: set[str] = set()
    for cluster in clusters:
        members = sorted(cluster["members"])
        if len(members) < 2 or seen.intersection(members):
            raise ValueError("Invalid or overlapping clusters")
        seen.update(members)
        scores = {
            m: float(np.mean([matrix[indexes[m], indexes[n]] for n in members if n != m]))
            for m in members
        }
        medoid = min(members, key=lambda m: (-scores[m], m))
        mean = float(
            np.mean(
                [
                    matrix[indexes[a], indexes[b]]
                    for i, a in enumerate(members)
                    for b in members[i + 1 :]
                ]
            )
        )
        output.append(
            {
                "cluster_id": cluster["clusterId"],
                "members": members,
                "medoid": medoid,
                "medoid_scores": scores,
                "mean_similarity": mean,
            }
        )
    return sorted(output, key=lambda c: (-c["mean_similarity"], tuple(c["members"])))


def gate(group: dict, recommendations: list[dict], resolutions: list[dict]) -> dict:
    """Return all observed veto reasons; no partial execution or oracle review resolution."""
    ids = set(group["members"])
    reasons: set[str] = set()
    touching = [
        r
        for r in recommendations
        if ids.intersection(m["memoryId"] for m in r["affected_memories"])
    ]
    merges = [r for r in touching if r["action"] == "merge"]
    if not merges:
        reasons.add("missing_merge_recommendation")
    if len(merges) > 1:
        reasons.add("multiple_merge_recommendations")
    if any(r["action"] != "merge" for r in touching):
        reasons.add("competing_recommendation")
    by_id = defaultdict(list)
    for resolution in resolutions:
        by_id[resolution["memoryId"]].append(resolution)
    keepers = []
    for memory_id in sorted(ids):
        values = by_id[memory_id]
        if len(values) != 1:
            reasons.add("missing_resolution" if not values else "duplicate_resolution")
            continue
        resolution = values[0]
        if resolution["resolvedAction"] != "merge":
            reasons.add(f"resolution_{resolution['resolvedAction']}")
        if resolution["conflictDetected"]:
            reasons.add("resolution_conflict")
        if resolution["role"] == "keeper":
            keepers.append(memory_id)
        if resolution["role"] not in {"keeper", "removable"}:
            reasons.add("invalid_resolution_role")
        if len(merges) == 1 and resolution["recommendationId"] != merges[0]["recommendationId"]:
            reasons.add("recommendation_reference_mismatch")
    if len(keepers) != 1:
        reasons.add("invalid_keeper_count")
    for rec in touching:
        if rec["requiresHumanApproval"]:
            reasons.add("approval_required")
        if rec["conflictDetected"]:
            reasons.add("recommendation_conflict")
    if len(merges) == 1:
        rec = merges[0]
        affected = rec["affected_memories"]
        affected_ids = [m["memoryId"] for m in affected]
        if set(affected_ids) != ids:
            reasons.add("partial_or_extra_members")
        if len(set(affected_ids)) != len(affected_ids):
            reasons.add("duplicate_affected_memory")
        if Counter(r["recommendationId"] for r in recommendations)[rec["recommendationId"]] != 1:
            reasons.add("duplicate_recommendation_id")
        roles = {m["memoryId"]: m["role"] for m in affected}
        for memory_id in ids:
            if len(by_id[memory_id]) == 1 and roles.get(memory_id) != by_id[memory_id][0]["role"]:
                reasons.add("role_mismatch")
    return {
        "allowed": not reasons,
        "veto_reasons": sorted(reasons),
        "recommended_keeper": keepers[0] if len(keepers) == 1 else None,
        "keeper_disagreement": len(keepers) == 1 and keepers[0] != group["medoid"],
    }


def exact_groups(records: list[dict]) -> list[dict]:
    buckets = defaultdict(list)
    for record in records:
        buckets[canonical({k: record[k] for k in MEMORY_FIELDS if k != "id"})].append(record["id"])
    return [
        {"members": sorted(ids), "medoid": min(ids)}
        for _, ids in sorted(buckets.items())
        if len(ids) > 1
    ]


def transform(
    records: list[dict], condition: str, groups: list[dict], decisions: list[dict], prefix: int
) -> dict:
    original = memory_input(records)
    if condition not in CONDITIONS or prefix < 0:
        raise ValueError("Unknown condition or invalid prefix")
    selected = []
    if condition == "exact":
        selected = exact_groups(original)
    elif condition in {"semantic", "gated"}:
        if len(groups) != len(decisions):
            raise ValueError("Candidate/gate length mismatch")
        selected = [
            g
            for g, d in zip(groups[:prefix], decisions[:prefix], strict=True)
            if condition == "semantic" or d["allowed"]
        ]
    removed = {m for group in selected for m in group["members"] if m != group["medoid"]}
    return {
        "memories": [deepcopy(m) for m in original if m["id"] not in removed],
        "executed_groups": deepcopy(selected),
        "removed_ids": sorted(removed),
    }
