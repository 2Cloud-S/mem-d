from memd.actions import plan_governance_actions
from memd.contracts import (
    ActionType,
    AnalysisMetrics,
    AnalysisReport,
    CategorizedMemory,
    ClusterTrustLevel,
    DuplicateCluster,
    Insight,
    InsightSeverity,
    MemoryCategory,
    PolicyProfile,
)
from memd.policy import apply_policy
from memd.reports import render_json, render_markdown


def test_high_trust_cluster_generates_merge_action() -> None:
    cluster = DuplicateCluster(
        clusterId="cluster_1",
        members=("mem_1", "mem_2"),
        averageSimilarity=0.96,
        trustScore=0.95,
        trustLevel=ClusterTrustLevel.HIGH,
        trustReasons=("high internal consistency",),
    )

    actions, summary = plan_governance_actions(
        clusters=(cluster,),
        categories=(
            CategorizedMemory(
                memoryId="mem_1",
                category=MemoryCategory.FACT,
                confidence=0.9,
            ),
            CategorizedMemory(
                memoryId="mem_2",
                category=MemoryCategory.FACT,
                confidence=0.9,
            ),
        ),
        validation={},
        insights=(compression_insight(),),
    )

    assert actions[0].actionType == ActionType.MERGE_CLUSTER
    assert actions[0].target["clusterId"] == "cluster_1"
    assert actions[0].requiresHumanApproval is False
    assert actions[0].supportingEvidence
    assert summary.safeActions == 1
    assert summary.estimatedTrustedSavings == 1


def test_contaminated_cluster_generates_review_action() -> None:
    cluster = DuplicateCluster(
        clusterId="cluster_1",
        members=("mem_1", "mem_2", "mem_3"),
        averageSimilarity=0.58,
        trustScore=0.4,
        trustLevel=ClusterTrustLevel.LOW,
        trustReasons=("contains low-similarity outliers",),
    )

    actions, summary = plan_governance_actions(
        clusters=(cluster,),
        categories=(),
        validation={
            "clusterQuality": {
                "clusterContamination": [
                    {
                        "clusterId": "cluster_1",
                        "contaminationScore": 0.33,
                        "outliers": [{"id": "mem_3"}],
                    }
                ]
            }
        },
        insights=(cluster_quality_insight(),),
    )

    review = actions[0]
    assert review.actionType == ActionType.REVIEW_CLUSTER
    assert review.requiresHumanApproval is True
    assert "contamination score=0.33" in review.supportingEvidence
    assert summary.reviewActions == 1
    assert summary.estimatedUnverifiedSavings == 2


def test_category_conflict_generates_taxonomy_review_action() -> None:
    actions, _summary = plan_governance_actions(
        clusters=(),
        categories=(),
        validation={
            "categoryQuality": {
                "categoryConsistency": {
                    "conflictClusters": [
                        {
                            "clusterId": "cluster_1",
                            "dominantCategory": "Preference",
                            "categoryAgreementRate": 66.67,
                            "categoryMix": {"Preference": 2, "Fact": 1},
                            "minorityCategories": [{"category": "Fact", "count": 1}],
                            "reclassificationCandidates": [
                                {"memoryId": "mem_3", "currentCategory": "Fact"}
                            ],
                        }
                    ]
                }
            }
        },
        insights=(category_consistency_insight(),),
    )

    action = actions[0]
    assert action.actionType == ActionType.REVIEW_CATEGORY_CONFLICT
    assert action.target["clusterId"] == "cluster_1"
    assert action.requiresHumanApproval is True
    assert "category_consistency" in action.sourceSignals


def test_unknown_memory_findings_generate_classification_review_action() -> None:
    actions, _summary = plan_governance_actions(
        clusters=(),
        categories=(),
        validation={
            "categoryQuality": {
                "unknownCount": 2,
                "unknownPercentage": 10.0,
                "unknownSamples": [
                    {"memoryId": "mem_1", "content": "Unclear memory"},
                    {"memoryId": "mem_2", "content": "Another unclear memory"},
                ],
            }
        },
        insights=(unknown_insight(),),
    )

    action = actions[0]
    assert action.actionType == ActionType.REVIEW_UNKNOWN_MEMORY
    assert action.target["unknownCount"] == 2
    assert action.requiresHumanApproval is True
    assert "category_quality.unknown" in action.sourceSignals


def test_actions_are_serialized_to_json_and_markdown_reports() -> None:
    cluster = DuplicateCluster(
        clusterId="cluster_1",
        members=("mem_1", "mem_2"),
        averageSimilarity=0.96,
        trustScore=0.95,
        trustLevel=ClusterTrustLevel.HIGH,
        trustReasons=("high internal consistency",),
    )
    actions, summary = plan_governance_actions(
        clusters=(cluster,),
        categories=(),
        validation={},
        insights=(compression_insight(),),
    )
    actions, policy_summary = apply_policy(actions, PolicyProfile.BALANCED)
    report = AnalysisReport(
        metrics=AnalysisMetrics(
            totalMemories=2,
            duplicateCount=1,
            duplicatePercentage=50.0,
            compressionOpportunity=50.0,
            categoryBreakdown={category: 0 for category in MemoryCategory},
        ),
        clusters=(cluster,),
        insights=(compression_insight(),),
        actions=actions,
        actionSummary=summary,
        policySummary=policy_summary,
    )

    json_report = render_json(report)
    markdown_report = render_markdown(report)

    assert '"actionSummary"' in json_report
    assert '"policySummary"' in json_report
    assert '"actions"' in json_report
    assert '"actionType": "merge_cluster"' in json_report
    assert '"policyDecision": "approved"' in json_report
    assert '"policyExplanation"' in json_report
    assert "## Action Plan" in markdown_report
    assert "## Policy Outcomes" in markdown_report
    assert "### Recommended Safe Actions" in markdown_report
    assert "### Recommended Review Actions" in markdown_report
    assert "### Deferred / Low-Priority Actions" in markdown_report


def compression_insight() -> Insight:
    return Insight(
        id="compression-high",
        title="Prioritize trusted duplicate cleanup",
        severity=InsightSeverity.HIGH,
        explanation="High-trust duplicates are available.",
        supportingEvidence=("trusted duplicate count=1",),
        confidence=0.9,
        estimatedImpact="1 record may be removable.",
        recommendedAction="Review the action plan.",
    )


def cluster_quality_insight() -> Insight:
    return Insight(
        id="cluster-quality-review",
        title="Review cluster quality before trusting compression estimates",
        severity=InsightSeverity.HIGH,
        explanation="Cluster needs review.",
        supportingEvidence=("contamination candidates=1",),
        confidence=0.8,
        estimatedImpact="Manual review reduces risk.",
        recommendedAction="Review contaminated clusters.",
    )


def category_consistency_insight() -> Insight:
    return Insight(
        id="category-consistency-conflicts",
        title="Review category disagreements inside duplicate clusters",
        severity=InsightSeverity.HIGH,
        explanation="Duplicate cluster has taxonomy disagreement.",
        supportingEvidence=("conflict clusters=1",),
        confidence=0.88,
        estimatedImpact="1 memory may need taxonomy review.",
        recommendedAction="Review category conflict.",
    )


def unknown_insight() -> Insight:
    return Insight(
        id="unknown-category-review",
        title="Review Unknown memories for missed patterns",
        severity=InsightSeverity.MEDIUM,
        explanation="Unknown categories need review.",
        supportingEvidence=("unknown memories=2",),
        confidence=0.85,
        estimatedImpact="Review 2 uncategorized memories.",
        recommendedAction="Review Unknown samples.",
    )
