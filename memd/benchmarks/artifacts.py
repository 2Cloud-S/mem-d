from __future__ import annotations

from pathlib import Path


def benchmark_artifact_paths(output_dir: Path, stem: str) -> dict[str, Path]:
    """Return canonical benchmark artifact paths for a dataset stem."""
    output_dir = output_dir.resolve()
    return {
        "audit_raw_json": output_dir / f"{stem}.audit.raw.json",
        "audit_raw_markdown": output_dir / f"{stem}.audit.raw.md",
        "audit_cleaned_json": output_dir / f"{stem}.audit.cleaned.json",
        "audit_cleaned_markdown": output_dir / f"{stem}.audit.cleaned.md",
        "cleaned_jsonl": output_dir / f"{stem}.cleaned.jsonl",
        "preprocess_report_json": output_dir / f"{stem}.preprocess-report.json",
        "preprocess_report_markdown": output_dir / f"{stem}.preprocess-report.md",
        "analysis_json": output_dir / f"{stem}.analysis.json",
        "analysis_markdown": output_dir / f"{stem}.analysis.md",
        "baseline_markdown": output_dir / f"{stem}.baseline.md",
    }
