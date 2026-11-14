"""Content-only fixed-medoid packets; keep the provenance mapping away from reviewers."""

from __future__ import annotations

import random
from copy import deepcopy

from .artifacts import canonical, object_hash
from .budgets import apply_groups
from .transform import fixed_query_time, memory_input

PRESENTATION_SEED = 20262
PACKET_FIELDS = {
    "audit_id",
    "original_records",
    "proposed_survivor_records",
    "question",
    "decision_criteria",
    "query_time",
}
RECORD_FIELDS = {"id", "content", "source", "timestamp"}
JUDGMENTS = (
    "decision_relevant_information_lost",
    "scope_changed",
    "negation_changed",
    "certainty_changed",
    "attribution_changed",
    "time_changed",
    "justified_decision_changed",
    "original_justified_decision",
    "proposed_justified_decision",
    "ambiguous",
    "unscorable",
    "rationale",
)


def make_blinded_audits(rows: list[dict], public: dict[str, dict]) -> tuple[list, dict, dict]:
    unique: dict[str, dict] = {}
    mappings: dict[str, list] = {}
    for row in rows:
        original = memory_input(row["original_records"])
        aliases = {m["id"]: f"R{i}" for i, m in enumerate(original, 1)}
        for group, disposition in zip(row["candidates"], row["gate_decisions"], strict=True):
            proposal = apply_groups(original, [group])["memories"]

            def display(records, aliases=aliases):
                return [{**m, "id": aliases[m["id"]]} for m in records]

            body = {
                "original_records": display(original),
                "proposed_survivor_records": display(proposal),
                "question": deepcopy(public[row["case_id"]]["question"]),
                "decision_criteria": deepcopy(public[row["case_id"]]["decision_criteria"]),
                "query_time": fixed_query_time(original),
            }
            key = object_hash(body)
            if key in unique and canonical(unique[key]) != canonical(body):
                raise ValueError("Audit packet hash collision")
            unique[key] = body
            mappings.setdefault(key, []).append(
                {
                    "case_id": row["case_id"],
                    "threshold": row["threshold"],
                    "original_id_aliases": aliases,
                    "candidate": deepcopy(group),
                    "gate": deepcopy(disposition),
                }
            )
    order = sorted(unique)
    random.Random(PRESENTATION_SEED).shuffle(order)
    packets, evaluator_map, responses = [], {}, []
    for index, key in enumerate(order, 1):
        audit_id = f"audit-{index:03d}"
        packets.append({"audit_id": audit_id, **unique[key]})
        evaluator_map[audit_id] = {"packet_sha256": key, "sources": mappings[key]}
        responses.append({"audit_id": audit_id, **dict.fromkeys(JUDGMENTS)})
    validate_blinded(packets)
    return (
        packets,
        {"presentation_seed": PRESENTATION_SEED, "audit_mapping": evaluator_map},
        {
            "status": "pending",
            "reviewer_id": None,
            "review_type": None,
            "responses": responses,
        },
    )


def validate_blinded(packets: list[dict]) -> None:
    seen: set[str] = set()
    content: set[str] = set()
    for packet in packets:
        if set(packet) != PACKET_FIELDS or packet["audit_id"] in seen:
            raise ValueError("Unexpected audit metadata or duplicate ID")
        seen.add(packet["audit_id"])
        if any(
            set(m) != RECORD_FIELDS
            for field in ("original_records", "proposed_survivor_records")
            for m in packet[field]
        ):
            raise ValueError("Unexpected record annotation in reviewer packet")
        originals = {m["id"]: m for m in packet["original_records"]}
        if set(originals) != {f"R{i}" for i in range(1, len(originals) + 1)}:
            raise ValueError("Reviewer records must use local ordinal aliases")
        if any(originals.get(m["id"]) != m for m in packet["proposed_survivor_records"]):
            raise ValueError("Audit proposal rewrites source evidence")
        body = {k: v for k, v in packet.items() if k != "audit_id"}
        fingerprint = canonical(body)
        if fingerprint in content:
            raise ValueError("Duplicate reviewer content")
        content.add(fingerprint)
