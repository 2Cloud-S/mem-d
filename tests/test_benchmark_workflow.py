from pathlib import Path

from memd.benchmarks.artifacts import benchmark_artifact_paths
from memd.benchmarks.baseline import render_baseline_markdown
from memd.benchmarks.workflow import run_longmemeval_benchmark

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "longmemeval_audit_sample.jsonl"


def test_benchmark_artifact_paths_use_canonical_names() -> None:
    paths = benchmark_artifact_paths(Path("examples/benchmarks"), "longmemeval_sample")

    assert paths["audit_raw_json"].name == "longmemeval_sample.audit.raw.json"
    assert paths["preprocess_report_json"].name == "longmemeval_sample.preprocess-report.json"
    assert paths["analysis_json"].name == "longmemeval_sample.analysis.json"
    assert paths["baseline_markdown"].name == "longmemeval_sample.baseline.md"


def test_render_baseline_markdown_includes_required_sections() -> None:
    markdown = render_baseline_markdown(
        dataset="sample",
        input_path="datasets/evaluation/sample.jsonl",
        cleaned_path="examples/benchmarks/sample.cleaned.jsonl",
        raw_audit={
            "datasets": [
                {
                    "totalRecords": 100,
                    "meaningfulMemoryRate": 35.5,
                    "unknownRate": 20.3,
                    "duplicateRate": 1.2,
                }
            ]
        },
        cleaned_audit={
            "datasets": [
                {
                    "totalRecords": 42,
                    "meaningfulMemoryRate": 83.4,
                    "unknownRate": 34.9,
                    "duplicateRate": 0.0,
                    "categoryDistribution": {"Fact": 10, "Unknown": 15},
                }
            ]
        },
        preprocess_report={
            "originalRecordCount": 100,
            "finalRecordCount": 42,
            "retentionPercentage": 42.0,
        },
        analysis={
            "metrics": {
                "totalMemories": 42,
                "duplicatePercentage": 5.0,
                "compressionOpportunity": 5.0,
                "duplicateCount": 2,
                "categoryBreakdown": {"Fact": 10, "Unknown": 15, "Preference": 17},
            },
            "validation": {
                "memoryEvolutionAudit": {
                    "totalEvolutionSignals": 3,
                    "contradictionCount": 1,
                    "preferenceChangeCount": 1,
                    "supersededMemoryCount": 0,
                    "staleMemoryCount": 1,
                    "statusTransitionCount": 0,
                },
                "memoryLifecycle": {
                    "lifecycleCounts": {"Active": 30, "Historical": 12},
                },
            },
            "insights": [
                {
                    "title": "Moderate duplicate compression opportunity",
                    "severity": "medium",
                    "recommendedAction": "Review duplicate clusters before consolidation.",
                }
            ],
        },
    )

    for section in (
        "## Dataset",
        "## Input Size",
        "## Meaningful Memory Rate",
        "## Unknown Rate",
        "## Duplicate Rate",
        "## Compression Opportunity",
        "## Category Distribution",
        "## Evolution Signals",
        "## Lifecycle Distribution",
        "## Insights Summary",
    ):
        assert section in markdown
    assert "83.4" in markdown
    assert "Active" in markdown


def test_run_longmemeval_benchmark_writes_artifacts(tmp_path: Path) -> None:
    result = run_longmemeval_benchmark(SAMPLE, tmp_path, stem="fixture_sample")

    assert result.stem == "fixture_sample"
    for path in result.paths.values():
        assert path.exists(), f"missing artifact: {path}"

    baseline = result.paths["baseline_markdown"].read_text(encoding="utf-8")
    assert "# Benchmark Baseline: fixture_sample" in baseline
    assert result.paths["cleaned_jsonl"].read_text(encoding="utf-8").strip()
