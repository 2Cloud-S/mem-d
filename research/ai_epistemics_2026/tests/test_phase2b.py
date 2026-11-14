"""Budget and audit validity tests; synthetic counters here are test fixtures, never findings."""

from __future__ import annotations

import json
import os
import tarfile
from copy import deepcopy
from pathlib import Path

import pytest

from research.ai_epistemics_2026.harness.artifacts import RESEARCH, canonical
from research.ai_epistemics_2026.harness.backend import TokenCounter, snapshot
from research.ai_epistemics_2026.harness.blind_audits import (
    JUDGMENTS,
    PACKET_FIELDS,
    make_blinded_audits,
    validate_blinded,
)
from research.ai_epistemics_2026.harness.budgets import (
    apply_groups,
    build_points,
    corpus_bytes,
    global_ranking,
    ordered_records,
    payload_identity,
    token_match,
)
from research.ai_epistemics_2026.harness.phase2b import load_frozen
from research.ai_epistemics_2026.harness.requests import solver_payload


def fixture_rows():
    rows = []
    public = {}
    for cid, prefix, similarity, allowed in [
        ("case-A", "a", 0.8, True),
        ("case-B", "b", 0.9, False),
    ]:
        records = [
            {
                "id": prefix + str(i),
                "content": f"Synthetic fixture {prefix} {i}",
                "source": "synthetic_test_fixture",
                "timestamp": "2026-01-01T00:00:00Z",
            }
            for i in (1, 2)
        ]
        group = {
            "members": [m["id"] for m in records],
            "medoid": prefix + "1",
            "mean_similarity": similarity,
            "cluster_id": "fixture",
        }
        rows.append(
            {
                "case_id": cid,
                "threshold": 0.55,
                "original_records": records,
                "candidates": [group],
                "gate_decisions": [
                    {"allowed": allowed, "veto_reasons": [] if allowed else ["resolution_review"]}
                ],
            }
        )
        public[cid] = {
            "memories": records,
            "question": "Synthetic fixture question?",
            "decision_criteria": "Synthetic criteria",
            "answer_options": ["proceed"],
        }
    return rows, public


class SyntheticCounter:
    """Explicit hand-calculated token costs, not character counts or a real run backend."""

    def count(self, records):
        ids = frozenset(m["id"] for m in records)
        return {
            frozenset(["a1", "a2"]): 100,
            frozenset(["a1"]): 70,
            frozenset(["b1", "b2"]): 100,
            frozenset(["b1"]): 90,
        }[ids]


def test_global_ranking_uses_similarity_then_original_ids_not_case_order():
    rows, _ = fixture_rows()
    ranked = global_ranking(rows)
    assert [r["case_id"] for r in ranked] == ["case-B", "case-A"]
    rows[1]["candidates"][0]["mean_similarity"] = 0.8
    assert [r["case_id"] for r in global_ranking(list(reversed(rows)))] == ["case-A", "case-B"]
    rows[0]["case_id"] = "ZZZ"
    rows[1]["case_id"] = "AAA"
    assert [r["case_id"] for r in global_ranking(rows)] == ["ZZZ", "AAA"]


def test_unrounded_similarity_precedes_id_ties():
    rows, _ = fixture_rows()
    rows[0]["candidates"][0]["mean_similarity"] = 0.90000000000001
    assert global_ranking(rows)[0]["case_id"] == "case-A"


def test_all_global_prefixes_and_no_cross_case_merges():
    rows, _ = fixture_rows()
    before = deepcopy(rows)
    points, ranking = build_points(rows, SyntheticCounter())
    controls = [p for p in points if p["method"] == "similarity_first"]
    assert [p["prefix"] for p in controls] == [0, 1, 2]
    assert [p["metrics"]["tokens_saved_mean_orders"] for p in controls] == [0, 10, 40]
    assert controls[1]["outputs"]["case-A"]["memories"] == rows[0]["original_records"]
    assert controls[1]["outputs"]["case-B"]["removed_ids"] == ["b2"]
    assert rows == before
    assert ranking[0]["group"] == rows[1]["candidates"][0]
    with pytest.raises(ValueError, match="cross-case"):
        apply_groups(rows[0]["original_records"], [rows[1]["candidates"][0]])
    assert rows == before


def test_labels_categories_and_dispositions_cannot_change_control_order_or_matching():
    rows, _ = fixture_rows()
    original, _ = build_points(rows, SyntheticCounter())
    changed = deepcopy(rows)
    for row in changed:
        row.update(
            category="SENTINEL",
            family_id="SENTINEL",
            evaluator_only="SENTINEL",
            question="SENTINEL",
            gold_answer="SENTINEL",
        )
    again, _ = build_points(changed, SyntheticCounter())
    assert original == again
    target = next(p for p in original if p["method"] == "gated")
    controls = [p for p in original if p["method"] == "similarity_first"]
    altered_dispositions = deepcopy(rows)
    for row in altered_dispositions:
        row["gate_decisions"][0]["allowed"] = not row["gate_decisions"][0]["allowed"]
    altered, _ = build_points(altered_dispositions, SyntheticCounter())
    assert controls == [p for p in altered if p["method"] == "similarity_first"]
    assert token_match(target, controls) == token_match(
        target, [p for p in again if p["method"] == "similarity_first"]
    )


def point(name, saved, prefix=0, before=30000, threshold=0.55):
    return {
        "point_id": name,
        "threshold": threshold,
        "prefix": prefix,
        "metrics": {"original_tokens_seed_sum": before, "tokens_saved_seed_sum": saved},
    }


def test_matching_exact_integer_tokens_tie_tolerance_and_unmatched_hand_calculated():
    target = point("gate", 1000)
    # Equidistant in token cost: use smaller prefix regardless of condition/safety metadata.
    low, high = point("low", 990, 2), point("high", 1010, 1)
    result = token_match(target, [low, high])
    assert result["control"] == "high"
    assert result["absolute_token_gap_mean_orders"] == 10 / 3
    assert result["gap_relative_to_target_savings"] == 0.01
    assert token_match(target, [point("boundary", 1600)])["status"] == "matched"
    outside = token_match(target, [point("outside", 1601)])
    assert outside["status"] == "unmatched" and outside["control"] is None
    assert outside["nearest_control"] == "outside"
    assert (
        token_match(target, [point("other threshold", 1000, threshold=0.95)])["status"]
        == "unmatched"
    )


def test_matching_reports_permissive_absolute_tolerance_and_zero_points():
    result = token_match(point("gate", 300, before=30000), [point("zero", 0, before=30000)])
    assert result["status"] == "matched"  # 1 percentage point, yet ALL gate savings unmatched
    assert result["gap_relative_to_target_savings"] == 1
    assert not result["both_save_positive_tokens"]


def test_missing_tokenizer_is_unavailable_not_estimated():
    target = point("gate", None)
    assert token_match(target, [point("x", 0)])["status"] == "tokens_unavailable"


def test_identity_checks_full_bytes_not_token_totals():
    rows, public = fixture_rows()
    points, _ = build_points(rows, SyntheticCounter())
    gated = next(p for p in points if p["method"] == "gated")
    copy = deepcopy(gated)
    same = payload_identity(gated, copy, public)
    assert same["byte_identical_survivor_payloads"] and same["byte_identical_solver_messages"]
    copy["outputs"]["case-A"]["memories"][0]["content"] = "Changed with unchanged token metadata"
    # The solver builder refuses rewritten records, rather than allowing a false identity.
    assert corpus_bytes(copy) != corpus_bytes(gated)
    with pytest.raises(ValueError, match="unchanged"):
        payload_identity(gated, copy, public)
    # Two honest survivors with the same test token cost can still have different record IDs.
    copy = deepcopy(gated)
    copy["outputs"]["case-A"]["memories"] = [deepcopy(rows[0]["original_records"][1])]
    result = payload_identity(gated, copy, public)
    assert not result["byte_identical_survivor_payloads"]
    assert not result["byte_identical_solver_messages"]
    assert result["differing_case_ids"] == ["case-A"]


def test_record_order_matches_existing_solver_serialization():
    rows, public = fixture_rows()
    for row in rows:
        for seed in (2026, 2027, 2028):
            original = row["original_records"]
            partial = original[:1]
            assert (
                ordered_records(original, partial, seed)
                == solver_payload(public[row["case_id"]], partial, seed)["memories"]
            )


def test_audit_deduplicates_proposals_hides_provenance_and_does_not_fill_responses():
    rows, public = fixture_rows()
    repeated = deepcopy(rows[0])
    repeated["threshold"] = 0.95
    repeated["gate_decisions"][0]["allowed"] = False
    packets, mapping, template = make_blinded_audits(rows + [repeated], public)
    assert len(packets) == 2  # three source proposals, same actual transformation deduplicated
    assert sorted(len(v["sources"]) for v in mapping["audit_mapping"].values()) == [1, 2]
    for packet in packets:
        assert set(packet) == PACKET_FIELDS
        assert all(m["id"] in {"R1", "R2"} for m in packet["original_records"])
        assert len(packet["proposed_survivor_records"]) == 1
    assert "case-A" not in canonical(packets)
    assert "mean_similarity" not in canonical(packets)
    assert "allowed" not in canonical(packets)
    assert "threshold" not in canonical(packets)
    assert template["status"] == "pending" and template["reviewer_id"] is None
    assert template["review_type"] is None
    assert all(response[k] is None for response in template["responses"] for k in JUDGMENTS)
    assert len({p["audit_id"] for p in packets}) == 2
    assert (packets, mapping, template) == make_blinded_audits(rows + [repeated], public)


def test_audit_changes_only_with_reviewable_evidence_not_labels_or_veto():
    rows, public = fixture_rows()
    packets, _, _ = make_blinded_audits(rows, public)
    changed = deepcopy(rows)
    for row in changed:
        row.update(category="SENTINEL", family_id="SENTINEL", evaluator_only="SENTINEL")
        row["gate_decisions"][0]["allowed"] = not row["gate_decisions"][0]["allowed"]
    altered_public = deepcopy(public)
    for value in altered_public.values():
        value.update(gold_answer="SENTINEL", rationale="SENTINEL", decisive_evidence="SENTINEL")
    assert packets == make_blinded_audits(changed, altered_public)[0]
    duplicated = deepcopy(rows[0])
    altered_public[duplicated["case_id"]]["question"] = "Different decision relevance?"
    assert packets != make_blinded_audits(rows, altered_public)[0]


def test_blinded_validator_rejects_extra_labels_and_rewritten_evidence():
    rows, public = fixture_rows()
    packets, _, _ = make_blinded_audits(rows, public)
    leaked = deepcopy(packets)
    leaked[0]["gold_answer"] = "proceed"
    with pytest.raises(ValueError, match="metadata"):
        validate_blinded(leaked)
    changed = deepcopy(packets)
    changed[0]["proposed_survivor_records"][0]["source"] = "another source"
    with pytest.raises(ValueError, match="rewrites"):
        validate_blinded(changed)


@pytest.fixture
def frozen_run(tmp_path):
    archive = RESEARCH / "artifacts/phase2-development-2026-11-14/run.tar.gz"
    with tarfile.open(archive) as tar:
        tar.extractall(tmp_path, filter="data")
    return tmp_path / "phase2-run"


def test_frozen_candidates_medoids_gate_and_historical_payloads_are_unchanged(frozen_run):
    rows, public, _ = load_frozen(frozen_run, RESEARCH / "development.jsonl")
    assert len(rows) == 120 and len(public) == 20
    assert all(len(row["candidates"]) <= 1 and row["prefix"] == 1 for row in rows)
    assert sum(len(row["candidates"]) for row in rows) == 90


def test_actual_pinned_token_counts_and_exact_identity(frozen_run):
    cache = os.environ.get("MEMD_RESEARCH_MODEL_CACHE")
    if not cache:
        pytest.skip("Set MEMD_RESEARCH_MODEL_CACHE to run pinned-tokenizer integration offline")
    rows, public, manifest = load_frozen(frozen_run, RESEARCH / "development.jsonl")
    path, info = snapshot(
        manifest["model_lock"]["tokenizer"], Path(cache), False, tokenizer_only=True
    )
    assert info["files_sha256"] == manifest["tokenizer"]["files_sha256"]
    points, _ = build_points([r for r in rows if r["threshold"] == 0.55], TokenCounter(path, info))
    anchors = {p["method"]: p for p in points if p["method"] != "similarity_first"}
    assert anchors["gated"]["metrics"]["tokens_saved_mean_orders"] == 136
    assert payload_identity(anchors["gated"], anchors["exact"], public)[
        "byte_identical_solver_messages"
    ]
    for anchor in anchors.values():
        assert anchor["metrics"]["original_tokens_seed_sum"] == 3290 * 3
    frozen = json.loads((frozen_run / "manifest.json").read_text())
    assert frozen["tokenizer"]["revision"] == info["revision"]


def test_complete_offline_run_freezes_selection_and_blinded_artifacts(frozen_run, tmp_path):
    cache = os.environ.get("MEMD_RESEARCH_MODEL_CACHE")
    if not cache:
        pytest.skip("Pinned-tokenizer integration requires MEMD_RESEARCH_MODEL_CACHE")
    from research.ai_epistemics_2026.harness.artifacts import verify
    from research.ai_epistemics_2026.harness.phase2b import prepare

    first, second = tmp_path / "first", tmp_path / "second"
    result = prepare(frozen_run, RESEARCH / "development.jsonl", first, Path(cache))
    assert result == {
        "operating_points": 114,
        "unique_audit_packets": 29,
        "source_group_proposals": 90,
        "matched_thresholds": 6,
        "human_review_status": "pending",
        "solver_calls": 0,
    }
    prepare(frozen_run, RESEARCH / "development.jsonl", second, Path(cache))
    for directory in (first, second):
        verify(directory, "selection.freeze.json")
        verify(directory, "analysis.freeze.json")
        verify(directory / "reviewer")
        verify(directory / "evaluator-only")
    for name in (
        "points.jsonl",
        "matching.json",
        "rankings.json",
        "comparisons.json",
        "reviewer/packets.json",
        "reviewer/response-template.json",
        "evaluator-only/audit-map.json",
    ):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    report = json.loads((first / "comparisons.json").read_text())
    at_95 = next(c for c in report["comparisons"] if c["threshold"] == 0.95)
    assert at_95["incremental_tokens_saved_over_exact_mean_orders"] == 58
    assert at_95["match"]["absolute_token_gap_mean_orders"] == 2
    assert not at_95["gated_vs_selected_control"]["byte_identical_solver_messages"]
    assert at_95["gated_vs_selected_control"]["differing_case_ids"] == ["dev_005", "dev_016"]
    for comparison in report["comparisons"][:-1]:
        assert comparison["gated_vs_exact"]["byte_identical_survivor_payloads"]
        assert comparison["gated_vs_selected_control"]["byte_identical_solver_messages"]
    with pytest.raises(ValueError, match="overwrite"):
        prepare(frozen_run, RESEARCH / "development.jsonl", first, Path(cache))
