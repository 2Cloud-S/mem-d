"""Actual constraint/tokenizer/Transformers checks; fixtures are never solver evidence."""

from __future__ import annotations

import json
import os
import tarfile
import time
from copy import deepcopy
from pathlib import Path

import pytest
import torch
from transformers import AutoTokenizer
from transformers.generation.logits_process import PrefixConstrainedLogitsProcessor

from research.ai_epistemics_2026.harness.analysis import score_frozen
from research.ai_epistemics_2026.harness.artifacts import RESEARCH, read_jsonl
from research.ai_epistemics_2026.harness.constrained import ConstrainedModel, parser, schema
from research.ai_epistemics_2026.harness.forced_choice import (
    LABELS,
    ForcedChoiceTransport,
    label_trie,
    parse_choice,
)
from research.ai_epistemics_2026.harness.forced_choice import (
    SYSTEM as CHOICE_SYSTEM,
)
from research.ai_epistemics_2026.harness.interface_pilot import (
    CALIBRATION,
    calibration_requests,
    format_metrics,
    lock,
    meets_thresholds,
    prepare,
)
from research.ai_epistemics_2026.harness.local_solver import validate_request
from research.ai_epistemics_2026.validate_development import load_cases


def accepts(text):
    value = parser()
    for char in text:
        if char not in value.get_allowed_characters():
            return False
        value = value.add_character(char)
    return value.can_end()


@pytest.mark.parametrize("label", ["proceed", "do_not_proceed", "insufficient_evidence"])
def test_actual_parser_all_labels_and_both_field_orders(label):
    for value in (
        {"answer_label": label, "justification": "Fictional evidence."},
        {"justification": "Fictional evidence.", "answer_label": label},
    ):
        assert accepts(json.dumps(value))


@pytest.mark.parametrize(
    "text",
    [
        '{"answer":"proceed","justification":"Evidence"}',
        '{"answer_label":"other","justification":"Evidence"}',
        '{"answer_label":"proceed"}',
        '{"answer_label":"proceed","justification":""}',
        '{"answer_label":"proceed","justification":"   "}',
        '{"answer_label":"proceed","justification":"Evidence","extra":0}',
        '{"answer_label":"proceed","answer_label":"proceed","justification":"Evidence"}',
        '{"answer_label":"proceed","justification":"Evidence"',
        '{"answer_label":"proceed","justification":"Evidence\\nnew line"}',
    ],
)
def test_actual_parser_blocks_shape_and_string_failures(text):
    assert not accepts(text)


@pytest.fixture(scope="module", params=lock()["models"][:2], ids=lambda m: m["family"])
def tokenizer_data(request):
    from lmformatenforcer.integrations.transformers import build_token_enforcer_tokenizer_data

    cache = os.getenv("MEMD_PHASE3B_CACHE")
    if not cache:
        pytest.skip("Set MEMD_PHASE3B_CACHE for real pinned-tokenizer constraint checks")
    model = request.param
    path = (
        Path(cache)
        / ("models--" + model["repo_id"].replace("/", "--"))
        / "snapshots"
        / model["revision"]
    )
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
    return tokenizer, build_token_enforcer_tokenizer_data(tokenizer)


def test_actual_token_paths_and_transformers_mask(tokenizer_data):
    from lmformatenforcer.integrations.transformers import (
        build_transformers_prefix_allowed_tokens_fn,
    )

    tokenizer, data = tokenizer_data
    for label in schema()["properties"]["answer_label"]["enum"]:
        callback = build_transformers_prefix_allowed_tokens_fn(data, parser())
        prefix = tokenizer.encode("Synthetic test prompt only.", add_special_tokens=False)
        processor = PrefixConstrainedLogitsProcessor(callback, 1)
        first_mask = processor(torch.tensor([prefix]), torch.zeros((1, len(tokenizer))))
        assert first_mask[0, tokenizer.eos_token_id].isneginf()
        target = json.dumps({"answer_label": label, "justification": "Synthetic test fixture."})
        for token in tokenizer.encode(target, add_special_tokens=False):
            assert token in callback(0, torch.tensor(prefix))
            prefix.append(token)
        assert tokenizer.eos_token_id in callback(0, torch.tensor(prefix))


def test_wrapper_supplies_fresh_constraints_to_actual_generate_boundary(tokenizer_data):
    tokenizer, _ = tokenizer_data

    class SyntheticModel:
        generation_config = object()

        def __init__(self):
            self.callbacks = []

        def generate(self, **kwargs):
            self.callbacks.append(kwargs["prefix_allowed_tokens_fn"])
            return "synthetic_test_fixture_only"

    model = SyntheticModel()
    wrapped = ConstrainedModel(model, tokenizer)
    wrapped.generate()
    wrapped.generate()
    assert model.callbacks[0] is not model.callbacks[1]
    with pytest.raises(ValueError):
        wrapped.generate(prefix_allowed_tokens_fn=lambda *_: [])


def test_calibration_allowlists_and_annotation_independence():
    items = read_jsonl(CALIBRATION)
    model = lock()["models"][0]
    before = calibration_requests(items, model)
    changed = deepcopy(items)
    for item in changed:
        item["evaluator_only"] = {"answer_label": "SENTINEL", "rationale": "SENTINEL"}
        item["category"] = "SENTINEL"
        item["family_id"] = "SENTINEL"
    assert calibration_requests(changed, model) == before
    for row in before:
        validate_request(row["request"], row["request"]["model"])
        assert "SENTINEL" not in json.dumps(row["request"])
    assert len(before) == 18
    assert len({r["case_id"] for r in before}) == 18
    assert not (
        {
            m["id"]
            for c in read_jsonl(RESEARCH / "development.jsonl")
            for m in c["input"]["memories"]
        }
        & {m["id"] for c in items for m in c["input"]["memories"]}
    )


def test_eligibility_complete_denominator_and_both_thresholds():
    thresholds = lock()["eligibility"]
    assert meets_thresholds(18, 15, 18, thresholds)
    assert not meets_thresholds(17, 17, 18, thresholds)
    assert not meets_thresholds(18, 14, 18, thresholds)
    assert not meets_thresholds(17, 15, 17, thresholds)


def test_format_wrong_and_exclusions_are_separate():
    rows = [
        {"condition": "fixture", "excluded": False, "error": 0, "parse_reason": "valid_label"},
        {"condition": "fixture", "excluded": False, "error": 1, "parse_reason": "valid_label"},
        {"condition": "fixture", "excluded": False, "error": 1, "parse_reason": "invalid_output"},
        {"condition": "fixture", "excluded": True, "error": None, "parse_reason": "infrastructure"},
    ]
    result = format_metrics(rows)["fixture"]
    assert (result["planned"], result["included"], result["excluded"]) == (4, 3, 1)
    assert (result["valid"], result["valid_but_wrong"], result["invalid_included"]) == (2, 1, 1)
    assert result["decision_accuracy_among_valid"] == 0.5


def test_no_new_trial_overwrite_or_early_fallback(tmp_path):
    with pytest.raises(ValueError, match="overwrite"):
        prepare("calibration", "Qwen2.5", tmp_path, tmp_path)
    with pytest.raises(ValueError, match="First test"):
        prepare("calibration", "Qwen2.5-1.5B", tmp_path, tmp_path / "new")


@pytest.mark.parametrize(
    "text",
    [
        "proceed ",
        " proceed",
        "Proceed",
        '"proceed"',
        '{"answer_label":"proceed"}',
        "proceed\n",
        "yes",
    ],
)
def test_forced_parser_never_normalizes(text):
    assert parse_choice({"status": "ok", "text": text})["error"] == 1


def test_forced_actual_token_trie_and_transport_submission(tokenizer_data):
    tokenizer, _ = tokenizer_data
    for label in LABELS:
        prefix = tokenizer.encode("Synthetic prompt only.", add_special_tokens=False)
        callback = label_trie(tokenizer, len(prefix))
        mask = PrefixConstrainedLogitsProcessor(callback, 1)
        assert mask(torch.tensor([prefix]), torch.zeros((1, len(tokenizer))))[
            0, tokenizer.eos_token_id
        ].isneginf()
        for token in tokenizer.encode(label, add_special_tokens=False):
            assert token in callback(0, torch.tensor(prefix))
            prefix.append(token)
        assert callback(0, torch.tensor(prefix)) == [tokenizer.eos_token_id]

    class SyntheticModel:
        def generate(self, **kwargs):
            # Clearly synthetic test fixture; no learned model/calibration result.
            assert kwargs["max_new_tokens"] == 24
            assert kwargs["do_sample"] is False
            assert "past_key_values" not in kwargs
            ids = kwargs["input_ids"][0].tolist()
            for token in tokenizer.encode("do_not_proceed", add_special_tokens=False):
                assert token in kwargs["prefix_allowed_tokens_fn"](0, torch.tensor(ids))
                ids.append(token)
            ids.append(tokenizer.eos_token_id)
            return torch.tensor([ids])

    value = ForcedChoiceTransport.__new__(ForcedChoiceTransport)
    value.provenance = "synthetic_test_fixture"
    value.tokenizer, value.model = tokenizer, SyntheticModel()
    value.identity = {"model_id": "synthetic_test_fixture", "revision": "test"}
    value.generation = {"max_total_tokens": 4096}
    value.limits = {"model_inference_seconds": 600, "submission_seconds": 90}
    value.started = time.perf_counter()
    request = calibration_requests(read_jsonl(CALIBRATION), lock()["models"][0])[0]["request"]
    request["model"].update(value.identity, max_output_tokens=24)
    request["messages"][0]["content"] = CHOICE_SYSTEM
    result = value.submit(request)
    assert result["submitted_request"] == request
    assert CHOICE_SYSTEM in result["rendered_prompt"]
    assert parse_choice(result)["label"] == "do_not_proceed"
    assert result["usage"]["completion_tokens"] == len(result["generated_token_ids"])


@pytest.mark.parametrize("family", ["qwen", "smol"])
def test_old_strict_scores_recompute_without_normalization(tmp_path, family):
    archive = RESEARCH / "artifacts/phase3-development-2026-11-14" / family / "run.tar.gz"
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            assert member.isfile() and len(Path(member.name).parts) == 2
            (tmp_path / Path(member.name).name).write_bytes(tar.extractfile(member).read())
    data = RESEARCH / "development.jsonl"
    assert score_frozen(tmp_path, load_cases(data), data.read_bytes()) == read_jsonl(
        tmp_path / "scores.jsonl"
    )
