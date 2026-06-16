from pathlib import Path

import pytest
from typer.testing import CliRunner

from memd.cli.app import app
from memd.dataset_quality import audit_external_dataset, audit_external_datasets

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "longmemeval_audit_sample.jsonl"
QUESTIONS = FIXTURES / "longmemeval_questions_sample.jsonl"
EVAL_SAMPLE = Path("datasets/evaluation/longmemeval_sample.jsonl")


def test_dataset_quality_audit_reports_usefulness_metrics() -> None:
    audit = audit_external_dataset(SAMPLE)

    assert audit.datasetKind == "memory_export"
    assert audit.totalRecords == 6
    assert audit.estimatedMeaningfulMemories >= 1
    assert audit.estimatedConversationalNoise >= 1
    assert audit.averageMemoryLength > 0
    assert audit.categoryDistribution
    assert audit.unknownRate >= 0
    assert audit.duplicateRate > 0
    assert audit.topLowQualityCauses
    assert audit.benchmarkSuitability["verdict"] in {
        "suitable_with_filtering",
        "requires_preprocessing",
        "poor_fit",
    }
    assert audit.preprocessingRecommendations


def test_dataset_quality_audit_detects_assistant_noise_and_duplicates() -> None:
    audit = audit_external_dataset(SAMPLE)
    causes = {item["cause"] for item in audit.topLowQualityCauses}

    assert "assistant_turn" in causes
    assert "exact_duplicate_content" in causes
    assert audit.roleDistribution["assistant"] >= 1
    assert audit.roleDistribution["user"] >= 1


def test_dataset_quality_audit_handles_benchmark_questions_file() -> None:
    audit = audit_external_dataset(QUESTIONS)

    assert audit.datasetKind == "benchmark_questions"
    assert audit.totalRecords == 2
    assert audit.benchmarkSuitability["verdict"] == "companion_benchmark_metadata"
    assert audit.preprocessingRecommendations


def test_dataset_quality_audit_supports_multiple_datasets() -> None:
    report = audit_external_datasets([SAMPLE, QUESTIONS])

    assert report["datasetCount"] == 2
    assert len(report["datasets"]) == 2
    assert report["benchmarkReadiness"]["recommendedDataset"] == SAMPLE.name


@pytest.mark.skipif(not EVAL_SAMPLE.exists(), reason="LongMemEval sample dataset not present")
def test_dataset_quality_audit_runs_on_longmemeval_sample() -> None:
    audit = audit_external_dataset(EVAL_SAMPLE)

    assert audit.totalRecords > 100
    assert audit.meaningfulMemoryRate > 0
    assert audit.conversationalNoiseRate > 0
    assert audit.topLowQualityCauses


def test_cli_audit_dataset_json_output() -> None:
    result = CliRunner().invoke(
        app,
        ["audit-dataset", str(SAMPLE), "--format", "json"],
    )

    assert result.exit_code == 0
    assert '"datasetCount"' in result.output
    assert '"estimatedMeaningfulMemories"' in result.output
    assert '"estimatedConversationalNoise"' in result.output
    assert '"topLowQualityCauses"' in result.output
    assert '"benchmarkSuitability"' in result.output


def test_cli_audit_dataset_directory_output() -> None:
    result = CliRunner().invoke(
        app,
        ["audit-dataset", str(SAMPLE), str(QUESTIONS), "--format", "markdown"],
    )

    assert result.exit_code == 0
    assert "# Dataset Quality Audit" in result.output
    assert "longmemeval_audit_sample.jsonl" in result.output
