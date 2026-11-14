"""Validate and preserve separate completed/partial reviews; never invent independent review."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from ..validate_development import unique_object
from .artifacts import digest, freeze, verify, write_json
from .blind_audits import JUDGMENTS

CHOICES = set(JUDGMENTS) - {
    "original_justified_decision",
    "proposed_justified_decision",
    "rationale",
}


def validate_submission(directory: Path, submission: dict) -> dict:
    verify(directory)
    template = json.loads((directory / "response-template.json").read_text())
    if set(submission) != set(template):
        raise ValueError("Unexpected review envelope")
    if submission["status"] not in {"completed", "partial"}:
        raise ValueError("Import requires a completed or explicitly partial submission")
    reviewer = submission["reviewer_id"]
    if not isinstance(reviewer, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", reviewer):
        raise ValueError("Use a neutral reviewer ID with letters, digits, underscores or hyphens")
    if submission["review_type"] not in {"independent_human", "assistant"}:
        raise ValueError(
            "Reviewer must accurately declare independent_human or assistant provenance"
        )
    expected = {r["audit_id"] for r in template["responses"]}
    responses = submission["responses"]
    if (
        not isinstance(responses, list)
        or len(responses) != len(expected)
        or {r.get("audit_id") for r in responses} != expected
    ):
        raise ValueError("Each audit ID must appear exactly once")
    completed = 0
    for response in responses:
        if set(response) != {"audit_id", *JUDGMENTS}:
            raise ValueError("Unexpected response fields")
        values = [response[k] for k in JUDGMENTS]
        if all(v is None for v in values) and submission["status"] == "partial":
            continue
        if any(v is None for v in values):
            raise ValueError(
                "Fill a whole packet or leave the whole packet null in partial submissions"
            )
        for key in CHOICES:
            allowed = (
                {"yes", "no"} if key in {"ambiguous", "unscorable"} else {"yes", "no", "uncertain"}
            )
            if response[key] not in allowed:
                raise ValueError(f"Invalid judgment: {key}")
        for key in set(JUDGMENTS) - CHOICES:
            if not isinstance(response[key], str) or not response[key].strip():
                raise ValueError(f"Expected evidence-based text: {key}")
        completed += 1
    if not completed:
        raise ValueError("No completed judgments to import")
    return {
        "reviewer_id": reviewer,
        "review_type": submission["review_type"],
        "status": submission["status"],
        "packets_completed": completed,
        "packets_planned": len(expected),
        "provenance_note": (
            "Self-declared; importer validates structure, not human identity or independence"
        ),
    }


def import_review(directory: Path, source: Path, destination: Path) -> dict:
    raw = source.read_bytes()
    submission = json.loads(raw, object_pairs_hook=unique_object)
    summary = validate_submission(directory, submission)
    target = destination / summary["reviewer_id"]
    if target.exists():
        raise ValueError("Keep independent submissions separate; never overwrite a reviewer")
    target.mkdir(parents=True)
    (target / "submission.json").write_bytes(raw)
    write_json(
        target / "provenance.json",
        {
            **summary,
            "submission_sha256": digest(raw),
            "packet_freeze_sha256": digest((directory / "freeze.json").read_bytes()),
            "adjudication": "not performed",
        },
    )
    freeze(target, ["submission.json", "provenance.json"])
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packets", type=Path, required=True, help="Original reviewer directory")
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(import_review(args.packets, args.submission, args.output), indent=2))


if __name__ == "__main__":
    main()
