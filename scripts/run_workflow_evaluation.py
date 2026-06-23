from __future__ import annotations

import argparse
import json
from pathlib import Path

from memd.benchmarks.workflow_evaluation import (
    evaluate_workflows,
    evaluation_result_to_dict,
    render_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run workflow gold evaluation and write benchmark artifacts.",
    )
    parser.add_argument(
        "--gold-path",
        type=Path,
        default=Path("tests/fixtures/workflow_gold.json"),
        help="Path to workflow_gold.json (default: tests/fixtures/workflow_gold.json).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("examples/benchmarks"),
        help="Directory for benchmark artifacts (default: examples/benchmarks).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    result = evaluate_workflows(args.gold_path)
    payload = evaluation_result_to_dict(result)

    json_path = output_dir / "workflow_evaluation.json"
    md_path = output_dir / "workflow_evaluation.md"

    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(result), encoding="utf-8")

    print("Workflow evaluation complete")
    print(f"Gold: {args.gold_path}")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print(f"Evaluation status: {result.evaluationStatus}")
    print(f"Gate passed: {result.gatePassed}")
    print(
        "Overall workflow accuracy: "
        f"{result.qualityMetrics['overallWorkflowAccuracy'].accuracy:.4f} "
        f"({result.qualityMetrics['overallWorkflowAccuracy'].passed}/"
        f"{result.qualityMetrics['overallWorkflowAccuracy'].total})"
    )


if __name__ == "__main__":
    main()
