"""Future solver transport boundary. No provider or network implementation is bundled."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Protocol

from ..validate_development import unique_object
from .artifacts import freeze, read_jsonl, verify, write_jsonl

STATUSES = {"ok", "truncated", "refusal", "context_overflow", "infrastructure"}


class InfrastructureFailure(RuntimeError):
    pass


class Transport(Protocol):
    provenance: str  # 'real' or 'synthetic_test_fixture'

    def submit(self, request: dict) -> dict:
        """Return {status, text}; receive ONLY model/messages, never routing or gold."""
        ...


def parse_response(response: dict) -> dict:
    status = response["status"]
    if status not in STATUSES:
        raise ValueError("Unknown response status")
    if status == "infrastructure":
        return {"error": None, "reason": "infrastructure", "label": None}
    if status != "ok":
        return {"error": 1, "reason": status, "label": None}
    try:
        value = json.loads(response["text"], object_pairs_hook=unique_object)
        if (
            not isinstance(value, dict)
            or set(value) != {"answer_label", "justification"}
            or not all(isinstance(v, str) and v.strip() for v in value.values())
            or value["answer_label"] not in {"proceed", "do_not_proceed", "insufficient_evidence"}
        ):
            raise ValueError("Invalid response shape or label")
    except (ValueError, TypeError):
        return {"error": 1, "reason": "invalid_output", "label": None}
    return {"error": None, "reason": "valid_label", "label": value["answer_label"]}


def execute(requests: list[dict], transport: Transport) -> list[dict]:
    """Identical retries only for infrastructure; all responses remain auditable."""
    if transport.provenance not in {"real", "synthetic_test_fixture"}:
        raise ValueError("Transport must declare response provenance")
    output = []
    for row in requests:
        if transport.provenance == "real" and any(
            row["request"]["model"].get(key) in {None, "", "UNASSIGNED"}
            for key in ("model_id", "revision")
        ):
            raise ValueError("Pin downstream model and revision before real transport use")
        attempts = []
        for _ in range(3):  # original attempt plus at most two retries
            try:
                result = transport.submit(deepcopy(row["request"]))
            except InfrastructureFailure as error:
                result = {"status": "infrastructure", "text": "", "message": str(error)}
            if result["status"] not in STATUSES or not isinstance(result.get("text"), str):
                raise ValueError("Transport returned invalid status/text")
            attempts.append(deepcopy(result))
            if result["status"] != "infrastructure":
                break
        output.append(
            {
                "request_id": row["request_id"],
                "status": result["status"],
                "text": result["text"],
                "attempts": attempts,
                "provenance": transport.provenance,
            }
        )
    return output


def freeze_responses(directory, responses: list[dict]) -> None:
    verify(directory)
    if (directory / "responses.jsonl").exists():
        raise ValueError("Refusing to replace responses")
    expected = {r["request_id"] for r in read_jsonl(directory / "requests.jsonl")}
    actual = [r.get("request_id") for r in responses]
    if len(set(actual)) != len(actual) or set(actual) != expected:
        raise ValueError("Responses must match all frozen requests exactly once")
    for response in responses:
        if set(response) != {"request_id", "status", "text", "attempts", "provenance"}:
            raise ValueError("Unexpected response envelope")
        attempts = response["attempts"]
        if not isinstance(attempts, list) or not 1 <= len(attempts) <= 3:
            raise ValueError("Expected one attempt and at most two retries")
        if response["provenance"] not in {"real", "synthetic_test_fixture"}:
            raise ValueError("Missing response provenance")
        for attempt in attempts:
            if attempt.get("status") not in STATUSES or not isinstance(attempt.get("text"), str):
                raise ValueError("Invalid attempt envelope")
        if any(a["status"] != "infrastructure" for a in attempts[:-1]):
            raise ValueError("Only infrastructure failures may be retried")
        if any(response[k] != attempts[-1][k] for k in ("status", "text")):
            raise ValueError("Final response differs from logged final attempt")
    write_jsonl(directory / "responses.jsonl", responses)
    freeze(directory, ["responses.jsonl"], "responses.freeze.json")
