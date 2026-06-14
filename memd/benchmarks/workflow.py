from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from memd.benchmarks.artifacts import benchmark_artifact_paths
from memd.benchmarks.baseline import render_baseline_markdown
from memd.contracts import PolicyProfile
from memd.dataset_quality import audit_external_datasets, render_dataset_quality_markdown
from memd.defaults import DEFAULT_SIMILARITY_THRESHOLD
from memd.pipeline import analyze_file
from memd.preprocessing.longmemeval import (
    preprocess_longmemeval_jsonl,
    render_preprocess_report_markdown,
    write_preprocess_report,
)
from memd.reports import render_json, render_markdown, write_report


@dataclass(frozen=True)
class BenchmarkRunResult:
    input_path: Path
    output_dir: Path
    stem: str
    paths: dict[str, Path]


def run_longmemeval_benchmark(
    input_path: Path,
    output_dir: Path,
    *,
    stem: str | None = None,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    model_name: str | None = None,
    policy_profile: PolicyProfile = PolicyProfile.BALANCED,
) -> BenchmarkRunResult:
    """Run audit → preprocess → analyze and write benchmark artifacts."""
    input_path = input_path.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset_stem = stem or input_path.stem
    paths = benchmark_artifact_paths(output_dir, dataset_stem)

    raw_audit = audit_external_datasets([input_path])
    _write_json(paths["audit_raw_json"], raw_audit)
    write_report(paths["audit_raw_markdown"], render_dataset_quality_markdown(raw_audit))

    preprocess_report = preprocess_longmemeval_jsonl(input_path, paths["cleaned_jsonl"])
    write_preprocess_report(paths["preprocess_report_json"], preprocess_report)
    paths["preprocess_report_markdown"].write_text(
        render_preprocess_report_markdown(preprocess_report),
        encoding="utf-8",
    )

    cleaned_audit = audit_external_datasets([paths["cleaned_jsonl"]])
    _write_json(paths["audit_cleaned_json"], cleaned_audit)
    write_report(
        paths["audit_cleaned_markdown"],
        render_dataset_quality_markdown(cleaned_audit),
    )

    analysis_report = analyze_file(
        paths["cleaned_jsonl"],
        threshold=threshold,
        model_name=model_name,
        policy_profile=policy_profile,
    )
    write_report(paths["analysis_json"], render_json(analysis_report))
    write_report(paths["analysis_markdown"], render_markdown(analysis_report))

    analysis_dict = json.loads(render_json(analysis_report))
    baseline = render_baseline_markdown(
        dataset=dataset_stem,
        input_path=str(input_path),
        cleaned_path=str(paths["cleaned_jsonl"]),
        raw_audit=raw_audit,
        cleaned_audit=cleaned_audit,
        preprocess_report=preprocess_report.to_dict(),
        analysis=analysis_dict,
    )
    paths["baseline_markdown"].write_text(baseline, encoding="utf-8")

    return BenchmarkRunResult(
        input_path=input_path,
        output_dir=output_dir,
        stem=dataset_stem,
        paths=paths,
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
