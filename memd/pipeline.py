from __future__ import annotations

from pathlib import Path

from memd.categorization import categorize_records
from memd.category_consistency import audit_category_consistency
from memd.cluster_audit import audit_largest_clusters
from memd.cluster_trust import apply_cluster_trust_scores
from memd.clustering import cluster_duplicates
from memd.contracts import AnalysisReport
from memd.defaults import DEFAULT_SIMILARITY_THRESHOLD
from memd.embeddings import EmbeddingEngine
from memd.insights import generate_analysis_insights
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
    cluster_audit = audit_largest_clusters(records, categories, clusters, embeddings)
    clusters = apply_cluster_trust_scores(clusters, cluster_audit)
    category_consistency = audit_category_consistency(records, categories, clusters)
    metrics = calculate_metrics(records, categories, clusters, category_consistency)
    validation = build_validation_summary(
        records,
        categories,
        clusters,
        cluster_audit,
        category_consistency,
    )
    insights = generate_analysis_insights(metrics, clusters, validation)
    return AnalysisReport(
        metrics=metrics,
        clusters=tuple(clusters),
        memories=tuple(records),
        categories=tuple(categories),
        validation=validation,
        insights=insights,
    )
