"""Offline transport/provenance/review tests. All generated answers here are synthetic fixtures."""

from __future__ import annotations

import json
import time
from copy import deepcopy
from types import SimpleNamespace

import pytest
import torch

from research.ai_epistemics_2026.harness.artifacts import (
    canonical,
    freeze,
    read_jsonl,
    write_json,
    write_jsonl,
)
from research.ai_epistemics_2026.harness.blind_audits import JUDGMENTS
from research.ai_epistemics_2026.harness.execution import parse_response
from research.ai_epistemics_2026.harness.local_solver import (
    LocalTransport,
    render_request,
    validate_request,
)
from research.ai_epistemics_2026.harness.pilot import reuse_plan, run
from research.ai_epistemics_2026.harness.pilot_analysis import contrast
from research.ai_epistemics_2026.harness.requests import SYSTEM
from research.ai_epistemics_2026.harness.review_import import import_review, validate_submission


def request():
    return {
        "model": {
            "model_id": "synthetic_test_fixture",
            "revision": "test",
            "temperature": 0,
            "max_output_tokens": 256,
            "generation_seed": 2026,
        },
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": canonical(
                    {
                        "memories": [
                            {
                                "id": "fixture",
                                "content": "Fixture evidence",
                                "source": "test",
                                "timestamp": "2026-01-01T00:00:00Z",
                            }
                        ],
                        "question": "Fixture?",
                        "decision_criteria": "Fixture criteria",
                        "answer_options": ["proceed", "do_not_proceed", "insufficient_evidence"],
                        "query_time": "2026-01-01T00:00:00Z",
                    }
                ),
            },
        ],
    }


class SyntheticTokenizer:
    eos_token_id = 99
    pad_token_id = 0

    def apply_chat_template(self, messages, **kwargs):
        assert kwargs == {"tokenize": False, "add_generation_prompt": True}
        return canonical(messages)

    def encode(self, text, **kwargs):
        assert kwargs == {"add_special_tokens": False, "truncation": False}
        return [1, 2, 3]

    def __call__(self, text, **kwargs):
        assert kwargs == {"return_tensors": "pt", "add_special_tokens": False, "truncation": False}
        return {
            "input_ids": torch.tensor([[1, 2, 3]]),
            "attention_mask": torch.ones((1, 3), dtype=torch.long),
        }

    def decode(self, tokens, skip_special_tokens):
        return '{"answer_label":"proceed","justification":"synthetic test fixture"}' + (
            "" if skip_special_tokens else "<eos>"
        )


class SyntheticModel:
    generation_config = SimpleNamespace(eos_token_id=99)

    def __init__(self, timeout=False, error=False, eos=99):
        self.calls = 0
        self.timeout = timeout
        self.error = error
        self.eos = eos

    def generate(self, **kwargs):
        self.calls += 1
        assert kwargs["do_sample"] is False and kwargs["max_new_tokens"] == 256
        assert "past_key_values" not in kwargs
        assert kwargs["temperature"] is None
        if self.error:
            raise RuntimeError("synthetic_test_fixture generation error")
        if self.timeout:
            kwargs["stopping_criteria"][0].expired = True
        return torch.tensor([[1, 2, 3, 10, self.eos]])


def transport(**kwargs):
    value = LocalTransport.__new__(LocalTransport)
    value.provenance = "synthetic_test_fixture"
    value.identity = request()["model"]
    value.generation = {"max_total_tokens": 4096}
    value.limits = {"model_inference_seconds": 1200, "submission_seconds": 60}
    value.tokenizer = SyntheticTokenizer()
    value.model = SyntheticModel(**kwargs)
    value.started = time.perf_counter()
    return value


def test_allowlist_rejects_annotations_and_changed_settings():
    req = request()
    validate_request(req, req["model"])
    for location in ("root", "payload", "memory", "model"):
        changed = deepcopy(req)
        if location == "root":
            changed["evaluator_only"] = "SENTINEL"
        elif location == "model":
            changed["model"]["gold"] = "SENTINEL"
        else:
            body = json.loads(changed["messages"][1]["content"])
            (body if location == "payload" else body["memories"][0])["gold"] = "SENTINEL"
            changed["messages"][1]["content"] = canonical(body)
        with pytest.raises(ValueError):
            validate_request(changed, req["model"])
    req["model"]["max_output_tokens"] = 257
    with pytest.raises(ValueError):
        validate_request(req, req["model"])


def test_stateless_generation_retains_actual_submission_and_token_usage():
    value = transport()
    req = request()
    first = value.submit(req)
    second = value.submit(req)
    assert value.model.calls == 2
    assert first["status"] == second["status"] == "ok"
    assert first["usage"] == {"prompt_tokens": 3, "completion_tokens": 2}
    assert first["submitted_request"] == req
    assert first["generated_token_ids"] == [10, 99]
    assert first["raw_decoded_with_special_tokens"].endswith("<eos>")
    assert parse_response(first)["label"] == "proceed"
    assert render_request(value.tokenizer, req, req["model"])["input_token_ids_sha256"]


@pytest.mark.parametrize(
    "kwargs,status",
    [
        ({"timeout": True}, "infrastructure"),
        ({"error": True}, "infrastructure"),
        ({"eos": 11}, "truncated"),
    ],
)
def test_time_runtime_and_truncation_are_distinct(kwargs, status):
    result = transport(**kwargs).submit(request())
    assert result["status"] == status
    assert result["inference_submitted"] is True
    if status == "truncated":
        assert parse_response(result)["error"] == 1
    else:
        assert parse_response(result)["error"] is None


def test_context_and_run_budget_never_fake_successful_outputs():
    value = transport()
    value.generation["max_total_tokens"] = 100
    assert value.submit(request())["status"] == "context_overflow"
    assert value.model.calls == 0
    value.started -= 1300
    result = value.submit(request())
    assert result["status"] == "infrastructure" and result["inference_submitted"] is False
    assert value.model.calls == 0


def test_reuse_only_inside_case_model_order_block(tmp_path):
    rows = []
    for block in ("caseA-seed1", "caseA-seed2", "caseB-seed1"):
        for condition in ("original", "exact", "similarity_first", "gated"):
            rows.append(
                {
                    "block_id": block,
                    "request_id": block + condition,
                    "condition": condition,
                    "request": request(),
                }
            )
    plan = reuse_plan(rows)
    assert sum(r["reused"] for r in plan) == 9
    assert len({r["owner_request_id"] for r in plan}) == 3
    write_json(tmp_path / "manifest.json", {})
    write_jsonl(tmp_path / "requests.jsonl", rows)
    write_json(tmp_path / "reuse-plan.json", plan)
    freeze(tmp_path, ["manifest.json", "requests.jsonl", "reuse-plan.json"])
    value = transport()
    result = run(tmp_path, value)
    assert result["actual_inference_attempts"] == value.model.calls == 3
    assert result["reused_logical_requests"] == 9
    assert result["actual_generated_token_usage"]["completion_tokens"] == 6
    assert len(read_jsonl(tmp_path / "responses.jsonl")) == 12
    assert len(read_jsonl(tmp_path / "physical-submissions.jsonl")) == 3
    assert any(
        "reused_from_request_id" in r["attempts"][0]
        for r in read_jsonl(tmp_path / "responses.jsonl")
    )
    with pytest.raises(ValueError, match="rerun"):
        run(tmp_path, value)


def test_contrasts_do_not_pool_reused_conditions_as_observations():
    rows = []
    for family, error in [("fixtureA", 0), ("fixtureB", 1)]:
        for condition in ("original", "exact", "similarity_first", "gated"):
            rows.append(
                {
                    "case_id": family,
                    "family_id": family,
                    "block_id": family,
                    "model_id": "synthetic_test_fixture",
                    "model_revision": "test",
                    "threshold": 0.95,
                    "prefix": 3,
                    "condition": condition,
                    "error": error if condition != "similarity_first" else 1,
                    "excluded": False,
                }
            )
    report = contrast(rows, "gated", "exact")
    assert report["included_families"] == 2
    assert report["paired_change"] == 0
    assert contrast(rows, "gated", "similarity_first")["paired_change"] == -0.5


def packet_directory(tmp_path):
    directory = tmp_path / "reviewer"
    directory.mkdir()
    template = {
        "status": "pending",
        "reviewer_id": None,
        "review_type": None,
        "responses": [{"audit_id": "fixture-1", **dict.fromkeys(JUDGMENTS)}],
    }
    write_json(directory / "response-template.json", template)
    freeze(directory, ["response-template.json"])
    return directory, template


def synthetic_completed(template):
    """Synthetic assistant fixture ONLY, not a human submission or published agreement."""
    result = deepcopy(template)
    result.update(status="completed", reviewer_id="synthetic_fixture_A", review_type="assistant")
    for key in JUDGMENTS:
        result["responses"][0][key] = (
            "synthetic fixture rationale"
            if key in {"rationale", "original_justified_decision", "proposed_justified_decision"}
            else "no"
        )
    return result


def test_review_import_preserves_separate_provenance_and_never_fills_forms(tmp_path):
    directory, blank = packet_directory(tmp_path)
    before = (directory / "response-template.json").read_bytes()
    with pytest.raises(ValueError):
        validate_submission(directory, blank)
    value = synthetic_completed(blank)
    source = tmp_path / "synthetic-review.json"
    write_json(source, value)
    summary = import_review(directory, source, tmp_path / "reviews")
    assert summary["review_type"] == "assistant"
    assert "Self-declared" in summary["provenance_note"]
    assert (directory / "response-template.json").read_bytes() == before
    assert (
        tmp_path / "reviews/synthetic_fixture_A/submission.json"
    ).read_bytes() == source.read_bytes()
    with pytest.raises(ValueError, match="overwrite"):
        import_review(directory, source, tmp_path / "reviews")
    value["reviewer_id"] = "synthetic_fixture_B"
    write_json(source, value)
    import_review(directory, source, tmp_path / "reviews")
    assert len(list((tmp_path / "reviews").iterdir())) == 2


@pytest.mark.parametrize(
    "mutation", ["missing", "unknown", "bad_judgment", "empty_rationale", "false_completed"]
)
def test_review_validation_rejects_invalid_completed_forms(tmp_path, mutation):
    directory, blank = packet_directory(tmp_path)
    value = synthetic_completed(blank)
    if mutation == "missing":
        value["responses"] = []
    elif mutation == "unknown":
        value["responses"][0]["audit_id"] = "not-in-packets"
    elif mutation == "bad_judgment":
        value["responses"][0]["time_changed"] = "maybe"
    elif mutation == "empty_rationale":
        value["responses"][0]["rationale"] = ""
    elif mutation == "false_completed":
        value["responses"][0]["scope_changed"] = None
    with pytest.raises(ValueError):
        validate_submission(directory, value)
