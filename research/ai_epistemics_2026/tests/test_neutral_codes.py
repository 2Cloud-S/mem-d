"""Validity checks and hand-calculated synthetic fixtures; no empirical model outputs."""

from __future__ import annotations

import json
import os
import time
from copy import deepcopy
from pathlib import Path

import pytest
import torch
from transformers import AutoTokenizer
from transformers.generation.logits_process import PrefixConstrainedLogitsProcessor

from research.ai_epistemics_2026.harness.artifacts import (
    canonical,
    freeze,
    read_jsonl,
    write_json,
)
from research.ai_epistemics_2026.harness.code_diagnostic import (
    CALIBRATION,
    balanced_schedule,
    development_requests,
    diagnostic_requests,
    lock,
    prepare,
    summarize,
    verified_eligibility,
)
from research.ai_epistemics_2026.harness.neutral_codes import (
    CODES,
    LABELS,
    MAPPINGS,
    SYSTEM,
    NeutralCodeTransport,
    allowed_codes,
    parse_code,
    render_codes,
    request_mapping,
    response_parser,
)
from research.ai_epistemics_2026.harness.pilot import reuse_plan
from research.ai_epistemics_2026.harness.requests import solver_payload


def test_complete_grid_and_annotation_isolation():
    items = read_jsonl(CALIBRATION)
    rows = diagnostic_requests(items, lock()["model"])
    changed = deepcopy(items)
    for item in changed:
        item["evaluator_only"] = {"answer_label": "SENTINEL", "rationale": "SENTINEL"}
        item["family_id"] = item["category"] = "SENTINEL"
    assert diagnostic_requests(changed, lock()["model"]) == rows
    assert len(rows) == len({r["request_id"] for r in rows}) == 108
    assert len({r["block_id"] for r in rows}) == 108
    public = {i["calibration_id"]: i["input"] for i in items}
    for row in rows:
        body = json.loads(row["request"]["messages"][1]["content"])
        assert body.pop("answer_code_mapping") == MAPPINGS[row["mapping_index"]]
        original = public[row["case_id"]]
        assert body == solver_payload(original, original["memories"], 2026)
        assert "SENTINEL" not in canonical(row["request"])
    assert all(not r["reused"] for r in reuse_plan(rows))


def test_every_mapping_is_bijective_and_decodes_without_gold():
    assert len({canonical(m) for m in MAPPINGS}) == 6
    for mapping in MAPPINGS:
        for code in CODES:
            assert parse_code({"status": "ok", "text": code}, mapping)["label"] == mapping[code]
    for code in CODES:
        assert sorted(m[code] for m in MAPPINGS) == sorted(list(LABELS) * 2)


@pytest.mark.parametrize("text", [" A", "A ", "A\n", '"A"', "proceed", "AB", "D", ""])
def test_strict_code_parser_never_repairs(text):
    assert parse_code({"status": "ok", "text": text}, MAPPINGS[0])["error"] == 1


def test_failure_reasons_remain_distinct():
    assert parse_code({"status": "infrastructure", "text": "A"}, MAPPINGS[0])["error"] is None
    assert parse_code({"status": "truncated", "text": "A"}, MAPPINGS[0])["error"] == 1
    with pytest.raises(ValueError):
        parse_code({"status": "ok", "text": "A"}, dict.fromkeys(CODES, "proceed"))


def fixture_rows(always_a=False):
    """Synthetic hand-calculation fixture, never an inference or published result."""
    rows = []
    for i in range(18):
        gold = LABELS[i % 3]
        for index, mapping in enumerate(MAPPINGS):
            code = "A" if always_a else next(k for k, v in mapping.items() if v == gold)
            rows.append(
                {
                    "case_id": f"synthetic_fixture_{i}",
                    "mapping_index": index,
                    "gold_label": gold,
                    "code": code,
                    "label": mapping[code],
                    "valid": True,
                    "correct": mapping[code] == gold,
                    "reason": "valid_label",
                }
            )
    return rows


def test_hand_calculated_preference_and_invariance():
    preference = summarize(fixture_rows(always_a=True))
    assert preference["correct"] == 36 and not preference["eligible"]
    assert preference["output_code_distribution_valid"] == {"A": 108, "B": 0, "C": 0}
    assert preference["items_changing_semantic_answer_among_valid"] == 18
    assert preference["items_same_code_all_six_valid"] == 18
    assert all(p["correct"] == 6 for p in preference["by_permutation"].values())
    assert all(p["correct"] == 12 for p in preference["by_semantic_class"].values())
    invariant = summarize(fixture_rows())
    assert invariant["correct"] == 108 and invariant["eligible"]
    assert invariant["items_invariant_semantics_all_six_valid"] == 18
    assert invariant["items_changing_code_among_valid"] == 18


def test_aggregate_thresholds_full_denominator_and_missing_pairs():
    rows = fixture_rows()
    for row in rows[:21]:
        row["correct"] = False
    assert summarize(rows)["eligible"]  # 87/108
    rows[21]["correct"] = False
    assert not summarize(rows)["eligible"]
    rows = fixture_rows()
    for row in rows[:5]:
        row.update(valid=False, correct=False, label=None, code=None, reason="infrastructure")
    assert summarize(rows)["eligible"]  # 103/108 valid
    rows[5].update(valid=False, correct=False, label=None, code=None, reason="infrastructure")
    assert not summarize(rows)["eligible"]
    with pytest.raises(ValueError):
        summarize(rows[:-1])


@pytest.fixture(scope="module")
def tokenizer():
    cache = os.getenv("MEMD_PHASE3B_CACHE")
    if not cache:
        pytest.skip("Set MEMD_PHASE3B_CACHE for actual cached Qwen1.5B tokenizer")
    spec = lock()["model"]
    path = (
        Path(cache)
        / ("models--" + spec["repo_id"].replace("/", "--"))
        / "snapshots"
        / spec["revision"]
    )
    return AutoTokenizer.from_pretrained(path, local_files_only=True)


def test_actual_boundaries_equal_code_choices_and_gold_free_transport(tokenizer):
    rows = diagnostic_requests(read_jsonl(CALIBRATION), lock()["model"])
    for row in rows:
        rendered = render_codes(tokenizer, row["request"], row["request"]["model"])
        assert rendered["answer_code_token_ids"] == {"A": 32, "B": 33, "C": 34}
    request = rows[0]["request"]
    rendered = render_codes(tokenizer, request, request["model"])
    prefix = tokenizer.encode(rendered["rendered_prompt"], add_special_tokens=False)
    callback = allowed_codes(rendered["answer_code_token_ids"], len(prefix), tokenizer.eos_token_id)
    logits = torch.zeros((1, len(tokenizer)))
    logits[0, tokenizer.eos_token_id] = 1000
    masked = PrefixConstrainedLogitsProcessor(callback, 1)(torch.tensor([prefix]), logits)
    assert masked[0, tokenizer.eos_token_id].isneginf()
    assert torch.isfinite(masked).sum() == 3
    for code in CODES:
        ids = prefix + [rendered["answer_code_token_ids"][code]]
        assert callback(0, torch.tensor(ids)) == [tokenizer.eos_token_id]

    class SyntheticModel:
        def generate(self, **kwargs):
            assert kwargs["max_new_tokens"] == 2 and kwargs["do_sample"] is False
            assert set(kwargs["prefix_allowed_tokens_fn"](0, kwargs["input_ids"][0])) == {
                32,
                33,
                34,
            }
            ids = kwargs["input_ids"][0].tolist() + [34, tokenizer.eos_token_id]
            return torch.tensor([ids])

    transport = NeutralCodeTransport.__new__(NeutralCodeTransport)
    transport.provenance = "synthetic_test_fixture"
    transport.model, transport.tokenizer = SyntheticModel(), tokenizer
    transport.identity = request["model"]
    transport.started = time.perf_counter()
    transport.limits = lock()["limits"]
    transport.generation = lock()["generation"]
    result = transport.submit(request)
    assert result["text"] == "C" and result["usage"]["completion_tokens"] == 2
    assert result["submitted_request"] == request and SYSTEM in result["rendered_prompt"]
    result["request_id"] = rows[0]["request_id"]
    assert response_parser(rows)(result)["label"] == request_mapping(request)["C"]


def test_balanced_development_mapping_and_complete_request_reuse():
    ids = [f"synthetic_case_{i:02d}" for i in range(20)]
    schedule = balanced_schedule(ids)
    assert balanced_schedule(ids[::-1]) == schedule
    assert [sum(r["mapping_index"] == i for r in schedule) for i in range(6)] == [10] * 6
    item = read_jsonl(CALIBRATION)[0]["input"]
    public = {cid: deepcopy(item) for cid in ids}
    selected = {
        c: {
            "point_id": "synthetic_fixture",
            "outputs": {cid: {"memories": item["memories"]} for cid in ids},
        }
        for c in ("original", "exact", "similarity_first", "gated")
    }
    rows, _ = development_requests(public, selected, lock()["model"])
    plan = reuse_plan(rows)
    assert len(rows) == 240 and len({r["owner_request_id"] for r in plan}) == 60
    block = rows[0]["block_id"]
    paired = [r for r in rows if r["block_id"] == block]
    assert len({canonical(request_mapping(r["request"])) for r in paired}) == 1
    paired = deepcopy(paired)
    payload = json.loads(paired[-1]["request"]["messages"][1]["content"])
    index = (paired[-1]["mapping_index"] + 1) % 6
    payload["answer_code_mapping"] = MAPPINGS[index]
    paired[-1]["request"]["messages"][1]["content"] = canonical(payload)
    assert len({r["owner_request_id"] for r in reuse_plan(paired)}) == 2


def test_failed_or_synthetic_diagnostic_cannot_unlock_development(tmp_path):
    write_json(tmp_path / "manifest.json", {"experiment": "neutral-code-diagnostic"})
    write_json(tmp_path / "diagnostic-analysis.json", {"eligible": False, "provenance": "real"})
    for filename, name in [
        ("freeze.json", "manifest.json"),
        ("responses.freeze.json", "manifest.json"),
        ("execution.freeze.json", "manifest.json"),
        ("analysis.freeze.json", "diagnostic-analysis.json"),
    ]:
        freeze(tmp_path, [name], filename)
    with pytest.raises(ValueError, match="failed"):
        verified_eligibility(tmp_path)
    with pytest.raises(ValueError):
        prepare("development", tmp_path, tmp_path / "new", tmp_path, tmp_path, tmp_path)
    assert not (tmp_path / "new").exists()
