from __future__ import annotations

import argparse
from pathlib import Path

from memd.benchmarks.workflow import run_longmemeval_benchmark
from memd.defaults import DEFAULT_SIMILARITY_THRESHOLD


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the LongMemEval benchmark pipeline: audit, preprocess, analyze, "
            "and write artifacts to examples/benchmarks/."
        ),
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Raw LongMemEval-style JSONL memory export.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("examples/benchmarks"),
        help="Directory for benchmark artifacts (default: examples/benchmarks).",
    )
    parser.add_argument(
        "--stem",
        type=str,
        default=None,
        help="Artifact filename stem (default: input filename without extension).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_SIMILARITY_THRESHOLD,
        help=f"Duplicate similarity threshold (default: {DEFAULT_SIMILARITY_THRESHOLD}).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Optional local embedding model name.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = run_longmemeval_benchmark(
        args.input,
        args.output_dir,
        stem=args.stem,
        threshold=args.threshold,
        model_name=args.model,
    )

    print("LongMemEval benchmark complete")
    print(f"Input: {result.input_path}")
    print(f"Output directory: {result.output_dir}")
    print(f"Stem: {result.stem}")
    for label, path in result.paths.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
