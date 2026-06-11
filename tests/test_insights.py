from memd.contracts import AnalysisMetrics, DuplicateCluster, InsightSeverity, MemoryCategory
from memd.insights import generate_analysis_insights, generate_evaluation_insights


def test_generate_analysis_insights_prioritizes_actions() -> None:
    metrics = AnalysisMetrics(
        totalMemories=100,
        duplicateCount=35,
        duplicatePercentage=35,
        compressionOpportunity=35,
        trustedDuplicateCount=5,
        unverifiedDuplicateCount=30,
        trustedCompressionOpportunity=5,
        unverifiedCompressionOpportunity=30,
        categoryBreakdown={
            MemoryCategory.PREFERENCE: 40,
            MemoryCategory.FACT: 20,
            MemoryCategory.TASK: 10,
            MemoryCategory.GOAL: 10,
            MemoryCategory.RELATIONSHIP: 5,
            MemoryCategory.TEMPORARY: 0,
            MemoryCategory.UNKNOWN: 15,
        },
        compressionReasons=("40 memories appear in duplicate clusters",),
    )
    clusters = [
        DuplicateCluster(
            clusterId="cluster_1",
            members=tuple(f"mem_{index}" for index in range(20)),
            averageSimilarity=0.9,
            sharedTerms=("typescript",),
        )
    ]
    validation = {
        "categoryQuality": {
            "unknownCount": 15,
            "unknownPercentage": 15,
            "unknownSamples": [{"memoryId": "mem_unknown", "content": "Unclear memory"}],
        },
        "clusterQuality": {
            "possibleFalsePositiveClusters": [],
            "exactDuplicateGroups": [{"count": 20, "content": "User prefers TypeScript"}],
        },
        "compressionDrivers": {
            "largestClusterDrivers": [
                {"clusterId": "cluster_1", "size": 20, "sharedTerms": ["typescript"]}
            ]
        },
    }

    insights = generate_analysis_insights(metrics, clusters, validation)

    assert insights
    assert insights[0].severity in {InsightSeverity.HIGH, InsightSeverity.MEDIUM}
    assert all(insight.recommendedAction for insight in insights)
    assert any(insight.id == "compression-high" for insight in insights)
    assert any(insight.id == "compression-mostly-unverified" for insight in insights)
    assert any(insight.id == "unknown-category-review" for insight in insights)


def test_generate_evaluation_insights_reports_recall_gap() -> None:
    insights = generate_evaluation_insights(
        {
            "precision": 1.0,
            "recall": 0.5714,
            "f1": 0.7272,
            "clusterPurity": 1.0,
            "clusterCoverage": 0.7273,
            "falsePositives": 0,
            "falseNegatives": 3,
        }
    )

    assert insights[0].id == "eval-recall-gap"
    assert insights[0].recommendedAction
