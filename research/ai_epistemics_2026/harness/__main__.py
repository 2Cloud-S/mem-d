"""CLI: prepare requests/feasibility offline; import and score future frozen responses."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from ..validate_development import load_cases, validate_cases
from .analysis import bootstrap, family_metrics, gate_contrast, score_frozen
from .artifacts import RESEARCH, read_jsonl, write_json, write_jsonl
from .backend import MemdAdapter, TokenCounter, VerifiedEngine, snapshot
from .execution import freeze_responses
from .runner import dry_run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("dry-run", help="Never submits solver calls")
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--data", type=Path, default=RESEARCH / "development.jsonl")
    prepare.add_argument("--cache", type=Path, required=True)
    prepare.add_argument("--download", action="store_true", help="Allow pinned model downloads")
    prepare.add_argument("--without-tokenizer", action="store_true")
    prepare.add_argument("--solver-model", help="Optional future solver ID; does not submit calls")
    prepare.add_argument("--solver-revision", help="Required together with --solver-model")
    imported = commands.add_parser(
        "import-responses", help="Freeze future real transport responses"
    )
    imported.add_argument("--run", type=Path, required=True)
    imported.add_argument("--responses", type=Path, required=True)
    score = commands.add_parser("score", help="Offline post-freeze analysis, no model calls")
    score.add_argument("--run", type=Path, required=True)
    score.add_argument("--data", type=Path, default=RESEARCH / "development.jsonl")
    args = parser.parse_args()
    try:
        if args.command == "dry-run":
            if bool(args.solver_model) != bool(args.solver_revision):
                raise ValueError("Provide both --solver-model and --solver-revision, or neither")
            lock = json.loads((RESEARCH / "model-lock.json").read_text())
            path, info = snapshot(lock["embedding"], args.cache, args.download)
            lock["embedding"] = info
            counter = TokenCounter(None)
            if not args.without_tokenizer:
                token_path, token_info = snapshot(
                    lock["tokenizer"], args.cache, args.download, tokenizer_only=True
                )
                counter = TokenCounter(token_path, token_info)
            result = dry_run(
                args.data,
                args.output,
                MemdAdapter(VerifiedEngine(path)),
                counter,
                lock,
                {"model_id": args.solver_model, "revision": args.solver_revision}
                if args.solver_model
                else None,
            )
            print(
                json.dumps(
                    {
                        k: v
                        for k, v in result.items()
                        if k not in {"operating_points", "compression_matches"}
                    },
                    indent=2,
                )
            )
        elif args.command == "import-responses":
            responses = read_jsonl(args.responses)
            if any(r.get("provenance") != "real" for r in responses):
                raise ValueError("Synthetic transport fixtures are permitted in tests only")
            freeze_responses(args.run, responses)
        else:
            cases = load_cases(args.data)
            validate_cases(cases)
            rows = score_frozen(args.run, cases, args.data.read_bytes())
            if any(r["provenance"] != "real" for r in rows):
                raise ValueError("Refusing to publish analysis of synthetic test fixtures")
            if any(
                r["model_id"] == "UNASSIGNED" or r["model_revision"] == "UNASSIGNED" for r in rows
            ):
                raise ValueError("Downstream model revisions must be pinned before execution")
            partitions = defaultdict(list)
            for row in rows:
                partitions[
                    (row["model_id"], row["model_revision"], row["threshold"], row["prefix"])
                ].append(row)
            summaries = []
            for key, values in sorted(partitions.items()):
                for condition in ("original", "exact", "semantic", "gated"):
                    summaries.append(
                        {
                            "model_id": key[0],
                            "model_revision": key[1],
                            "threshold": key[2],
                            "prefix": key[3],
                            **family_metrics(values, condition),
                            **bootstrap(values, condition),
                        }
                    )
                summaries.append(
                    {
                        "model_id": key[0],
                        "model_revision": key[1],
                        "threshold": key[2],
                        "prefix": key[3],
                        "comparison": "gated_minus_semantic",
                        **gate_contrast(values),
                    }
                )
            if (args.run / "scores.jsonl").exists():
                raise ValueError("Refusing to replace prior scoring")
            write_jsonl(args.run / "scores.jsonl", rows)
            write_json(args.run / "decision-analysis.json", summaries)
    except (ValueError, OSError, RuntimeError, ImportError) as error:
        # A failed backend never falls through into another embedding method.
        if args.command == "dry-run" and not args.output.exists():
            args.output.mkdir(parents=True)
            write_json(
                args.output / "blocked.json",
                {
                    "status": "invalid_or_blocked",
                    "reason": f"{type(error).__name__}: {error}",
                    "solver_calls": 0,
                },
            )
        parser.exit(1, f"Research run failed: {error}\n")


if __name__ == "__main__":
    main()
