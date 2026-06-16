from __future__ import annotations

from pathlib import Path

from memd.actions import plan_governance_actions
from memd.categorization import categorize_records
from memd.category_audit import audit_category_quality_v2
from memd.category_consistency import audit_category_consistency
from memd.cluster_audit import audit_largest_clusters
from memd.cluster_trust import apply_cluster_trust_scores
from memd.clustering import cluster_duplicates
from memd.contracts import AnalysisReport, PolicyProfile
from memd.defaults import DEFAULT_SIMILARITY_THRESHOLD
from memd.embeddings import EmbeddingEngine
from memd.insights import generate_analysis_insights
from memd.inspection import build_validation_summary, enrich_clusters
from memd.memory_evolution import audit_memory_evolution
from memd.memory_lifecycle import infer_memory_lifecycle
from memd.metrics import calculate_metrics
from memd.normalization import normalize_records
from memd.parser import load_memory_file
from memd.policy import apply_policy
from memd.recommendations import plan_recommendations


def analyze_file(
    path: Path,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    model_name: str | None = None,
    policy_profile: PolicyProfile = PolicyProfile.BALANCED,
) -> AnalysisReport:
    parsed = load_memory_file(path)
    records = normalize_records(parsed)
    categories = categorize_records(records)
    embeddings = EmbeddingEngine(model_name=model_name).embed(records)
    raw_clusters = cluster_duplicates(embeddings, threshold=threshold)
    clusters = enrich_clusters(records, categories, raw_clusters)
    cluster_audit = audit_largest_clusters(records, categories, clusters, embeddings)
    clusters = apply_cluster_trust_scores(clusters, cluster_audit)
    category_audit_v2 = audit_category_quality_v2(records, categories)
    category_consistency = audit_category_consistency(records, categories, clusters)
    memory_evolution_audit = audit_memory_evolution(records, categories, embeddings)
    memory_lifecycle = infer_memory_lifecycle(memory_evolution_audit)
    metrics = calculate_metrics(records, categories, clusters, category_consistency)
    validation = build_validation_summary(
        records,
        categories,
        clusters,
        cluster_audit,
        category_consistency,
        category_audit_v2,
        memory_evolution_audit,
        memory_lifecycle,
    )
    insights = generate_analysis_insights(metrics, clusters, validation)
    actions, action_summary = plan_governance_actions(
        clusters,
        categories,
        validation,
        insights,
    )
    actions, policy_summary = apply_policy(actions, policy_profile)
    recommendations, memory_resolutions, recommendation_summary = plan_recommendations(
        records,
        clusters,
        validation,
        insights,
        actions,
        metrics=metrics,
    )
    return AnalysisReport(
        metrics=metrics,
        clusters=tuple(clusters),
        memories=tuple(records),
        categories=tuple(categories),
        validation=validation,
        insights=insights,
        actions=actions,
        actionSummary=action_summary,
        policySummary=policy_summary,
        recommendations=recommendations,
        memoryResolutions=memory_resolutions,
        recommendationSummary=recommendation_summary,
    )
