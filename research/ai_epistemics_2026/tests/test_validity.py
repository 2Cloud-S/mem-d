"""Offline experimental-validity tests. ALL transport/embedding doubles are synthetic fixtures."""

from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from memd.embeddings import EmbeddingEngine
from research.ai_epistemics_2026.harness.analysis import (
    bootstrap,
    compression_matches,
    family_metrics,
    score_frozen,
)
from research.ai_epistemics_2026.harness.artifacts import (
    RESEARCH,
    canonical,
    digest,
    freeze,
    verify,
    write_json,
    write_jsonl,
)
from research.ai_epistemics_2026.harness.backend import (
    BackendInvalid,
    MemdAdapter,
    TokenCounter,
    VerifiedEngine,
)
from research.ai_epistemics_2026.harness.execution import (
    InfrastructureFailure,
    execute,
    freeze_responses,
    parse_response,
)
from research.ai_epistemics_2026.harness.requests import build_requests, solver_payload
from research.ai_epistemics_2026.harness.runner import build_run
from research.ai_epistemics_2026.harness.transform import candidates, gate, memory_input, transform
from research.ai_epistemics_2026.validate_development import load_cases


@pytest.fixture
def records():
    return [
        {
            "id": "a",
            "content": "Test fixture duplicate",
            "source": "synthetic_test_fixture",
            "timestamp": "2026-01-01T00:00:00Z",
        },
        {
            "id": "b",
            "content": "Test fixture duplicate",
            "source": "synthetic_test_fixture",
            "timestamp": "2026-01-02T00:00:00Z",
        },
    ]


def permission():
    recommendations = [
        {
            "recommendationId": "rec:fixture",
            "action": "merge",
            "requiresHumanApproval": False,
            "conflictDetected": False,
            "affected_memories": [
                {"memoryId": "a", "role": "removable"},
                {"memoryId": "b", "role": "keeper"},
            ],
        }
    ]
    resolutions = [
        {
            "memoryId": "a",
            "resolvedAction": "merge",
            "role": "removable",
            "conflictDetected": False,
            "recommendationId": "rec:fixture",
        },
        {
            "memoryId": "b",
            "resolvedAction": "merge",
            "role": "keeper",
            "conflictDetected": False,
            "recommendationId": "rec:fixture",
        },
    ]
    return recommendations, resolutions


def group():
    return {"cluster_id": "fixture", "members": ["a", "b"], "medoid": "a"}


def test_exact_uses_payload_not_id_and_preserves_metadata(records):
    result = transform(records, "exact", [], [], 0)
    assert len(result["memories"]) == 2  # distinct timestamps are distinct evidence
    records[1]["timestamp"] = records[0]["timestamp"]
    result = transform(records, "exact", [], [], 0)
    assert result["removed_ids"] == ["b"]
    records[1]["source"] = "another witness"
    assert transform(records, "exact", [], [], 0)["removed_ids"] == []
    records[1]["source"] = records[0]["source"]
    records[1]["content"] += " "
    assert transform(records, "exact", [], [], 0)["removed_ids"] == []


def test_medoid_tie_and_connected_nonendpoint_group(records):
    records.append({**records[0], "id": "c"})
    matrix = [[1, 0.9, 0.2], [0.9, 1, 0.9], [0.2, 0.9, 1]]
    output = candidates(records, [{"clusterId": "x", "members": ["c", "a", "b"]}], matrix)
    assert output[0]["medoid"] == "b"  # use whole connected cluster, no post-hoc splitting
    two = candidates(records[:2], [{"clusterId": "x", "members": ["b", "a"]}], [[1, 0.8], [0.8, 1]])
    assert two[0]["medoid"] == "a"


def test_keeper_does_not_change_fixed_medoid(records):
    recs, resolutions = permission()
    decision = gate(group(), recs, resolutions)
    assert decision["allowed"] and decision["keeper_disagreement"]
    ungated = transform(records, "semantic", [group()], [decision], 1)
    gated = transform(records, "gated", [group()], [decision], 1)
    assert gated == ungated
    assert gated["memories"] == [records[0]]  # original medoid, not recommended keeper b


@pytest.mark.parametrize(
    "kind,reason",
    [
        ("missing_rec", "missing_merge_recommendation"),
        ("multiple_rec", "multiple_merge_recommendations"),
        ("partial", "partial_or_extra_members"),
        ("duplicate_affected", "duplicate_affected_memory"),
        ("missing_resolution", "missing_resolution"),
        ("duplicate_resolution", "duplicate_resolution"),
        ("approval", "approval_required"),
        ("conflict", "resolution_conflict"),
        ("rec_conflict", "recommendation_conflict"),
        ("review", "resolution_review"),
        ("keep", "resolution_keep"),
        ("archive", "resolution_archive"),
        ("reference", "recommendation_reference_mismatch"),
        ("role", "role_mismatch"),
        ("keepers", "invalid_keeper_count"),
    ],
)
def test_whole_group_veto(records, kind, reason):
    recs, resolutions = permission()
    if kind == "missing_rec":
        recs = []
    elif kind == "multiple_rec":
        recs.append(deepcopy(recs[0]))
    elif kind == "partial":
        recs[0]["affected_memories"].pop()
    elif kind == "duplicate_affected":
        recs[0]["affected_memories"].append(recs[0]["affected_memories"][0])
    elif kind == "missing_resolution":
        resolutions.pop()
    elif kind == "duplicate_resolution":
        resolutions.append(deepcopy(resolutions[0]))
    elif kind == "approval":
        recs[0]["requiresHumanApproval"] = True
    elif kind == "conflict":
        resolutions[0]["conflictDetected"] = True
    elif kind == "rec_conflict":
        recs[0]["conflictDetected"] = True
    elif kind in {"review", "keep", "archive"}:
        resolutions[0]["resolvedAction"] = kind
    elif kind == "reference":
        resolutions[0]["recommendationId"] = "wrong"
    elif kind == "role":
        recs[0]["affected_memories"][0]["role"] = "keeper"
    elif kind == "keepers":
        resolutions[0]["role"] = "keeper"
    decision = gate(group(), recs, resolutions)
    assert not decision["allowed"] and reason in decision["veto_reasons"]
    before = deepcopy(records)
    result = transform(records, "gated", [group()], [decision], 1)
    assert result["memories"] == records == before
    assert result["removed_ids"] == []


class SyntheticEncoder:
    """Only a test fixture; never used by the CLI or feasibility artifacts."""

    def encode(self, texts, **kwargs):
        return np.ones((len(texts), 384))


def synthetic_engine():
    engine = VerifiedEngine.__new__(VerifiedEngine)
    EmbeddingEngine.__init__(engine, model_name="synthetic_test_fixture")
    engine._model = SyntheticEncoder()
    engine.real_vectors = None
    engine.last_embeddings = None
    return engine


def test_real_pipeline_adapter_immutable_and_deterministic_with_fixture_vectors(records):
    adapter = MemdAdapter(synthetic_engine())
    before = deepcopy(records)
    a = adapter.analyze(list(reversed(records)), 0.55)
    b = adapter.analyze(records, 0.55)
    assert a == b
    assert records == before
    assert a["clusters"] and a["actions"]  # genuine evidence path, not injected HIGH-trust fields


def test_detects_silent_fallback(records):
    engine = synthetic_engine()
    engine._embed_with_sentence_transformers = lambda texts: (_ for _ in ()).throw(
        RuntimeError("bad")
    )
    with pytest.raises(BackendInvalid, match="hashing"):
        engine.embed(
            []
            if not records
            else [
                __import__("memd.contracts", fromlist=["MemoryRecord"]).MemoryRecord(**r)
                for r in records
            ]
        )


def test_annotations_cannot_influence_any_transform_or_request():
    cases = load_cases(RESEARCH / "development.jsonl")
    sentinel = deepcopy(cases)
    for case in sentinel:
        case["evaluator_only"] = {"SENTINEL_GOLD_DO_NOT_FORWARD": "SECRET"}
        case["category"] = "SENTINEL_CATEGORY"
        case["family_id"] = "SENTINEL_FAMILY"
        case["input"]["evaluator_only"] = "SENTINEL_EXTRA"
        for memory in case["input"]["memories"]:
            memory["metadata"] = {"SENTINEL_MEMORY_GOLD": "SECRET"}
    solver = {"model_id": "synthetic_test_fixture", "revision": "test", "temperature": 0}
    original = deepcopy(cases)
    a = build_run(cases, MemdAdapter(synthetic_engine()), TokenCounter(None), solver)
    b = build_run(sentinel, MemdAdapter(synthetic_engine()), TokenCounter(None), solver)
    assert a == b
    assert "SENTINEL" not in canonical(b)
    assert cases == original
    # Questions and criteria may affect solver requests, never policy transformations.
    changed = deepcopy(cases)
    for case in changed:
        case["input"]["question"] = "different question"
        case["input"]["decision_criteria"] = "different criteria"
    assert (
        build_run(changed, MemdAdapter(synthetic_engine()), TokenCounter(None), solver)[0] == a[0]
    )


def test_solver_order_time_and_exact_token_serialization(records):
    public = {
        "memories": records,
        "question": "q",
        "decision_criteria": "c",
        "answer_options": ["proceed", "do_not_proceed", "insufficient_evidence"],
    }
    payload = solver_payload(public, records[:1], 2026)
    assert payload["query_time"] == records[1]["timestamp"]  # even when newest record removed
    assert set(payload) == {
        "memories",
        "question",
        "decision_criteria",
        "answer_options",
        "query_time",
    }
    assert canonical(payload["memories"]) in canonical(payload)

    class SyntheticTokenizer:
        def encode(self, value, **kwargs):
            assert value == canonical(payload["memories"])
            assert kwargs == {"add_special_tokens": False, "truncation": False}
            return [123, 456, 789]  # unmistakably synthetic test token IDs

    counter = TokenCounter(None)
    assert counter.count(records) is None
    counter.tokenizer = SyntheticTokenizer()
    assert counter.count(payload["memories"]) == 3
    with pytest.raises(ValueError, match="unchanged"):
        solver_payload(public, [{**records[0], "content": "rewritten"}], 2026)


@pytest.mark.parametrize(
    "response",
    [
        {"status": "ok", "text": "not JSON"},
        {
            "status": "ok",
            "text": '{"answer_label":"proceed","answer_label":"proceed","justification":"x"}',
        },
        {"status": "ok", "text": '{"answer_label":"proceed","justification":"x","extra":1}'},
        {"status": "ok", "text": '{"answer_label":["proceed"],"justification":"x"}'},
        {"status": "ok", "text": '{"answer_label":"proceed","justification":""}'},
        {"status": "ok", "text": '{"answer_label":"PROCEED","justification":"x"}'},
        {"status": "ok", "text": '{"answer_label":"proceed","justification":true}'},
        {"status": "truncated", "text": '{"answer_label":"proceed","justification":"x"}'},
        {"status": "context_overflow", "text": ""},
        {"status": "refusal", "text": ""},
    ],
)
def test_invalid_outputs_are_errors(response):
    assert parse_response(response)["error"] == 1


def test_transport_retries_pair_exclusion_and_freeze(tmp_path, records):
    public = {
        "memories": records,
        "question": "q",
        "decision_criteria": "c",
        "answer_options": ["proceed", "do_not_proceed", "insufficient_evidence"],
    }
    outputs = {name: {"memories": records} for name in ("original", "exact", "semantic", "gated")}
    requests = build_requests(
        "dev_001",
        public,
        outputs,
        0.55,
        0,
        {"model_id": "synthetic_test_fixture", "revision": "test"},
    )[:4]

    class SyntheticTransport:
        provenance = "synthetic_test_fixture"

        def __init__(self):
            self.received = []

        def submit(self, request):
            assert set(request) == {"model", "messages"}
            self.received.append(deepcopy(request))
            if len(self.received) <= 3:
                raise InfrastructureFailure("fixture outage")
            return {"status": "ok", "text": '{"answer_label":"proceed","justification":"fixture"}'}

    transport = SyntheticTransport()
    responses = execute(requests, transport)
    assert len(transport.received) == 6
    assert transport.received[0] == transport.received[1] == transport.received[2]
    assert responses[0]["status"] == "infrastructure"
    source = b"synthetic_test_fixture"
    write_json(tmp_path / "manifest.json", {"data_sha256": digest(source)})
    write_jsonl(tmp_path / "requests.jsonl", requests)
    freeze(tmp_path, ["manifest.json", "requests.jsonl"])
    freeze_responses(tmp_path, responses)
    cases = [
        {
            "case_id": "dev_001",
            "family_id": "fixture",
            "evaluator_only": {"acceptable_answer_labels": ["proceed"]},
        }
    ]
    scored = score_frozen(tmp_path, cases, source)
    assert all(r["excluded"] for r in scored)
    assert family_metrics(scored, "gated")["excluded_blocks"] == 1
    (tmp_path / "requests.jsonl").write_text("tampered")
    with pytest.raises(ValueError, match="changed"):
        verify(tmp_path)


def example_rows():
    # Family A: case a has mean delta 1/2, case b has delta 1; family mean 3/4.
    # Family B: one case with delta -1. Equal-family overall delta = -1/8.
    rows = []
    for family, case, seed, base, gated in [
        ("A", "a", 1, 0, 1),
        ("A", "a", 2, 0, 0),
        ("A", "b", 1, 0, 1),
        ("B", "c", 1, 1, 0),
    ]:
        for condition, error in [("original", base), ("gated", gated)]:
            rows.append(
                {
                    "block_id": f"{case}{seed}",
                    "model_id": "synthetic_test_fixture",
                    "model_revision": "test",
                    "threshold": 0.55,
                    "prefix": 1,
                    "family_id": family,
                    "case_id": case,
                    "order_seed": seed,
                    "condition": condition,
                    "error": error,
                    "excluded": False,
                }
            )
    return rows


def test_family_weighting_and_bootstrap_by_hand():
    rows = example_rows()
    result = family_metrics(rows, "gated")
    assert result["family_values"]["A"][0] == 0.75
    assert result["paired_change"] == -0.125  # not row-weighted (+.25) or case-weighted (+1/6)
    assert result["introduced"] == {"numerator": 2, "denominator": 3}
    assert result["rescued"] == {"numerator": 1, "denominator": 1}
    boot = bootstrap(rows, "gated")
    # Two-family resamples yield only -1, -1/8, +3/4; percentile endpoints are exact.
    assert boot["paired_change_95ci"] == [-1, 0.75]
    assert boot["introduced_undefined_resamples"] > 0
    assert boot["rescued_undefined_resamples"] > 0
    assert boot == bootstrap(rows, "gated")


def test_compression_matching_is_label_blind_and_missing_tokens_not_estimated():
    points = [{"condition": "gated", "token_compression": 0.1, "threshold": 0.55, "prefix": 1}]
    for threshold, prefix in [(0.55, 1), (0.85, 2), (0.85, 1)]:
        points.append(
            {
                "condition": "semantic",
                "token_compression": 0.1,
                "threshold": threshold,
                "prefix": prefix,
            }
        )
    assert compression_matches(points)[0]["semantic"]["threshold"] == 0.85
    assert compression_matches(points)[0]["semantic"]["prefix"] == 1
    points[0]["token_compression"] = None
    assert compression_matches(points)[0]["semantic"] is None


def test_upstream_failure_fatal_downstream_failure_recorded(records, monkeypatch):
    from memd import pipeline

    adapter = MemdAdapter(synthetic_engine())

    def broken_workflow(report):
        raise RuntimeError("synthetic_test_fixture workflow failure")

    monkeypatch.setattr(pipeline, "plan_workflows", broken_workflow)
    observed = adapter.analyze(records, 0.55)
    assert not observed["pipeline_completed"]
    assert observed["post_recommendation_failure"]["stage"] == "workflow"
    assert observed["recommendations"]

    def broken_recommendations(*args, **kwargs):
        raise RuntimeError("synthetic_test_fixture upstream failure")

    monkeypatch.setattr(pipeline, "plan_recommendations", broken_recommendations)
    with pytest.raises(RuntimeError, match="upstream"):
        adapter.analyze(records, 0.55)


def test_invalid_response_is_not_retried_and_recovered_infrastructure_is_included():
    rows = [
        {"request_id": "fixture", "request": {"model": {"model_id": "fixture"}, "messages": []}}
    ]

    class SyntheticTransport:
        provenance = "synthetic_test_fixture"

        def __init__(self):
            self.calls = 0

        def submit(self, request):
            self.calls += 1
            if self.calls == 1:
                raise InfrastructureFailure("fixture temporary failure")
            return {"status": "ok", "text": "invalid JSON fixture"}

    transport = SyntheticTransport()
    result = execute(rows, transport)
    assert transport.calls == 2
    assert result[0]["status"] == "ok"
    assert parse_response(result[0])["error"] == 1  # neither exclusion nor a third repair call


def test_response_import_rejects_missing_pairs_and_illegal_retries(tmp_path):
    write_jsonl(tmp_path / "requests.jsonl", [{"request_id": "fixture"}])
    freeze(tmp_path, ["requests.jsonl"])
    with pytest.raises(ValueError, match="exactly once"):
        freeze_responses(tmp_path, [])
    response = {
        "request_id": "fixture",
        "status": "ok",
        "text": "x",
        "provenance": "synthetic_test_fixture",
        "attempts": [{"status": "ok", "text": "x"}, {"status": "ok", "text": "x"}],
    }
    with pytest.raises(ValueError, match="infrastructure"):
        freeze_responses(tmp_path, [response])


def test_gate_contrast_uses_paired_semantic_reference():
    from research.ai_epistemics_2026.harness.analysis import gate_contrast

    rows = example_rows()
    rows.extend(
        {**row, "condition": "semantic", "error": row["error"]}
        for row in list(rows)
        if row["condition"] == "original"
    )
    contrast = gate_contrast(rows)
    assert contrast["paired_change"] == -0.125
    assert contrast["paired_change_95ci"] == [-1, 0.75]


def test_seeded_survivor_orders_share_one_original_permutation(records):
    records.append({**records[0], "id": "c"})
    public = {
        "memories": records,
        "question": "q",
        "decision_criteria": "c",
        "answer_options": ["proceed", "do_not_proceed", "insufficient_evidence"],
    }
    for seed in (2026, 2027, 2028):
        full = solver_payload(public, records, seed)["memories"]
        partial = solver_payload(public, [records[0], records[2]], seed)["memories"]
        assert partial == [r for r in full if r["id"] != "b"]
        assert memory_input(list(reversed(records))) == memory_input(records)
