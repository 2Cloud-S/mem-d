from __future__ import annotations

from pathlib import Path

from memd.categorization import categorize_records
from memd.clustering import cluster_duplicates
from memd.contracts import AnalysisReport
from memd.defaults import DEFAULT_SIMILARITY_THRESHOLD
from memd.embeddings import EmbeddingEngine
from memd.inspection import build_validation_summary, enrich_clusters
from memd.metrics import calculate_metrics
from memd.normalization import normalize_records
from memd.parser import load_memory_file


def analyze_file(
    path: Path,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    model_name: str | None = None,
) -> AnalysisReport:
    parsed = load_memory_file(path)
    records = normalize_records(parsed)
    categories = categorize_records(records)
    embeddings = EmbeddingEngine(model_name=model_name).embed(records)
    raw_clusters = cluster_duplicates(embeddings, threshold=threshold)
    clusters = enrich_clusters(records, categories, raw_clusters)
    metrics = calculate_metrics(records, categories, clusters)
    return AnalysisReport(
        metrics=metrics,
        clusters=tuple(clusters),
        memories=tuple(records),
        categories=tuple(categories),
        validation=build_validation_summary(records, categories, clusters),
    )
