from __future__ import annotations

import argparse
from pathlib import Path

from memd.preprocessing.longmemeval import (
    default_output_paths,
    preprocess_longmemeval_jsonl,
    render_preprocess_report_markdown,
    write_preprocess_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Deterministically preprocess LongMemEval JSONL memory exports for Mem-D benchmarking."
        ),
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Input JSONL memory export dataset.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Cleaned JSONL output path. Defaults to <input>.cleaned.jsonl",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Preprocessing report JSON path. Defaults to <input>.preprocess-report.json",
    )
    parser.add_argument(
        "--markdown-report",
        type=Path,
        default=None,
        help="Optional Markdown report path.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    input_path: Path = args.input
    default_output, default_report = default_output_paths(input_path)
    output_path = args.output or default_output
    report_path = args.report or default_report

    report = preprocess_longmemeval_jsonl(input_path, output_path)
    write_preprocess_report(report_path, report)

    print("LongMemEval preprocessing complete")
    print(f"Input records: {report.originalRecordCount}")
    print(f"Removed assistant turns: {report.removedAssistantTurns}")
    print(f"Removed filler records: {report.removedFillerRecords}")
    print(f"Removed puzzle/roleplay/creative content: {report.removedExcludedContent}")
    print(f"Removed duplicate records: {report.removedDuplicateRecords}")
    print(f"Final records: {report.finalRecordCount}")
    print(f"Retention: {report.retentionPercentage}%")
    print(f"Cleaned dataset: {output_path}")
    print(f"Report: {report_path}")

    if args.markdown_report:
        args.markdown_report.write_text(
            render_preprocess_report_markdown(report),
            encoding="utf-8",
        )
        print(f"Markdown report: {args.markdown_report}")


if __name__ == "__main__":
    main()
