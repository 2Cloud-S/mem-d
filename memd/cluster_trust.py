from __future__ import annotations

from collections.abc import Mapping, Sequence

from memd.contracts import ClusterTrustLevel, DuplicateCluster


def apply_cluster_trust_scores(
    clusters: Sequence[DuplicateCluster],
    cluster_audit: Mapping[str, object],
) -> list[DuplicateCluster]:
    audits = {
        str(audit.get("clusterId")): audit
        for audit in cluster_audit.get("allClusterAudits", [])
        if isinstance(audit, dict)
    }
    return [
        apply_cluster_trust_score(cluster, audits.get(cluster.clusterId, {}))
        for cluster in clusters
    ]


def apply_cluster_trust_score(
    cluster: DuplicateCluster,
    audit: Mapping[str, object],
) -> DuplicateCluster:
    score, reasons = score_cluster_trust(cluster, audit)
    level = trust_level(score)
    action = recommended_action(level)
    return cluster.model_copy(
        update={
            "trustScore": score,
            "trustLevel": level,
            "trustReasons": tuple(reasons),
            "recommendedAction": action,
        }
    )


def score_cluster_trust(
    cluster: DuplicateCluster,
    audit: Mapping[str, object],
) -> tuple[float, list[str]]:
    score = 1.0
    reasons: list[str] = []
    size = int_value(audit.get("size"), default=len(cluster.members))
    distribution = dict_value(audit.get("similarityDistribution"))
    contamination = float_value(audit.get("contaminationScore"))
    category_mix = dict_value(audit.get("categoryMix"))
    concept = str(audit.get("conceptAssessment") or "multiple-concepts")

    if size > 50:
        score -= 0.2
        reasons.append("large cluster requires stronger evidence")
    elif size > 10:
        score -= 0.1
        reasons.append("medium-large cluster needs review")

    average = float_value(audit.get("averageSimilarity"), cluster.averageSimilarity)
    if average < 0.5:
        score -= 0.25
        reasons.append("low average similarity")
    elif average < 0.65:
        score -= 0.15
        reasons.append("moderate average similarity")

    median = float_value(distribution.get("median"))
    if median and median < 0.4:
        score -= 0.25
        reasons.append("low median pairwise similarity")
    elif median and median < 0.55:
        score -= 0.15
        reasons.append("moderate median pairwise similarity")

    spread = float_value(distribution.get("spread"))
    if spread >= 0.45:
        score -= 0.15
        reasons.append("wide similarity spread")

    if contamination > 0:
        penalty = min(0.25, contamination * 1.5)
        score -= penalty
        reasons.append("contains low-similarity outliers")

    if len(category_mix) > 2:
        score -= 0.15
        reasons.append("mixed memory categories")
    if category_mix and size:
        dominant = max((int_value(value) for value in category_mix.values()), default=0)
        if dominant / size < 0.75:
            score -= 0.15
            reasons.append("no dominant category")

    if concept == "multiple-concepts":
        score -= 0.25
        reasons.append("audit assessed multiple concepts")

    if not reasons:
        reasons.append("high internal consistency")

    return max(0.0, round(score, 4)), reasons


def trust_level(score: float) -> ClusterTrustLevel:
    if score >= 0.8:
        return ClusterTrustLevel.HIGH
    if score >= 0.55:
        return ClusterTrustLevel.MEDIUM
    return ClusterTrustLevel.LOW


def recommended_action(level: ClusterTrustLevel) -> str:
    if level == ClusterTrustLevel.HIGH:
        return "Recommended for automatic consolidation"
    if level == ClusterTrustLevel.MEDIUM:
        return "Manual review recommended before consolidation"
    return "Do not auto-consolidate; manual review required"


def dict_value(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def list_value(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return []


def float_value(value: object, default: float = 0.0) -> float:
    if isinstance(value, int | float):
        return float(value)
    return default


def int_value(value: object, default: int = 0) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default
