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
    assert 0.0 <= evaluation.precision <= 1.0
    assert 0.0 <= evaluation.recall <= 1.0
    assert 0.0 <= evaluation.clusterPurity <= 1.0
    assert 0.0 <= evaluation.clusterCoverage <= 1.0


def test_evaluation_reports_include_mistakes_and_cluster_content() -> None:
    evaluation = evaluate_dataset(DATASET)

    json_report = render_evaluation_json(evaluation)
    markdown_report = render_evaluation_markdown(evaluation)

    assert '"falsePositives"' in json_report
    assert '"falseNegatives"' in json_report
    assert "Clustering Evaluation" in markdown_report
    assert "False Positives" in markdown_report
    assert "False Negatives" in markdown_report
