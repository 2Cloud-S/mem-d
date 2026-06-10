from pathlib import Path

from memd.evaluation import (
    evaluate_dataset,
    expected_duplicate_pairs,
    load_evaluation_dataset,
    render_evaluation_json,
    render_evaluation_markdown,
)

DATASET = Path("datasets/validation/clustering_quality.json")


def test_expected_duplicate_pairs_from_labelled_dataset() -> None:
    dataset = load_evaluation_dataset(DATASET)

    pairs = expected_duplicate_pairs(dataset.memories)

    assert ("pref_ts_1", "pref_ts_2") in pairs
    assert ("docker_1", "docker_2") in pairs
    assert ("pref_ts_1", "non_ts_runtime") not in pairs


def test_evaluate_dataset_reports_objective_metrics() -> None:
    evaluation = evaluate_dataset(DATASET)

    assert evaluation.totalMemories == 16
    assert evaluation.trueDuplicatePairs == 7
    assert evaluation.precision == 1.0
    assert evaluation.recall == 0.5714
    assert evaluation.f1 == 0.7272
    assert evaluation.falsePositives == 0
    assert evaluation.falseNegatives == 3
    assert evaluation.clusterPurity == 1.0
    assert evaluation.clusterCoverage == 0.7273


def test_stricter_threshold_preserves_precision_but_reduces_recall() -> None:
    baseline = evaluate_dataset(DATASET, threshold=0.85)
    improved = evaluate_dataset(DATASET)

    assert baseline.precision == 1.0
    assert improved.precision == 1.0
    assert improved.recall > baseline.recall
    assert improved.clusterCoverage > baseline.clusterCoverage


def test_evaluation_reports_include_mistakes_and_cluster_content() -> None:
    evaluation = evaluate_dataset(DATASET)

    json_report = render_evaluation_json(evaluation)
    markdown_report = render_evaluation_markdown(evaluation)

    assert '"falsePositives"' in json_report
    assert '"falseNegatives"' in json_report
    assert "Clustering Evaluation" in markdown_report
    assert "False Positives" in markdown_report
    assert "False Negatives" in markdown_report
