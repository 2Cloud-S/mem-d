from memd.cluster_trust import apply_cluster_trust_score
from memd.contracts import ClusterTrustLevel, DuplicateCluster


def test_high_trust_cluster_is_recommended_for_automatic_consolidation() -> None:
    cluster = DuplicateCluster(
        clusterId="cluster_1",
        members=("mem_1", "mem_2"),
        averageSimilarity=0.98,
    )
    audit = {
        "clusterId": "cluster_1",
        "size": 2,
        "averageSimilarity": 0.98,
        "similarityDistribution": {
            "median": 0.98,
            "spread": 0.02,
        },
        "categoryMix": {"Preference": 2},
        "outlierMemories": [],
        "contaminationScore": 0.0,
        "conceptAssessment": "single-concept",
    }

    trusted = apply_cluster_trust_score(cluster, audit)

    assert trusted.trustLevel == ClusterTrustLevel.HIGH
    assert trusted.trustScore >= 0.8
    assert trusted.recommendedAction == "Recommended for automatic consolidation"


def test_low_trust_cluster_requires_manual_review() -> None:
    cluster = DuplicateCluster(
        clusterId="cluster_1",
        members=tuple(f"mem_{index}" for index in range(25)),
        averageSimilarity=0.45,
    )
    audit = {
        "clusterId": "cluster_1",
        "size": 25,
        "averageSimilarity": 0.45,
        "similarityDistribution": {
            "median": 0.35,
            "spread": 0.8,
        },
        "categoryMix": {"Preference": 10, "Fact": 8, "Task": 7},
        "outlierMemories": [{"id": "mem_9"}],
        "contaminationScore": 0.2,
        "conceptAssessment": "multiple-concepts",
    }

    trusted = apply_cluster_trust_score(cluster, audit)

    assert trusted.trustLevel == ClusterTrustLevel.LOW
    assert trusted.trustScore < 0.55
    assert "manual review required" in trusted.recommendedAction.lower()
