from memd.clustering import cluster_duplicates
from memd.contracts import CategorizedMemory, EmbeddedMemory, MemoryCategory, MemoryRecord
from memd.inspection import build_validation_summary, enrich_clusters
from memd.metrics import calculate_metrics


def test_cluster_duplicates_and_metrics() -> None:
    embeddings = [
        EmbeddedMemory(memoryId="mem_1", embedding=(1.0, 0.0, 0.0)),
        EmbeddedMemory(memoryId="mem_2", embedding=(0.99, 0.01, 0.0)),
        EmbeddedMemory(memoryId="mem_3", embedding=(0.0, 1.0, 0.0)),
    ]

    raw_clusters = cluster_duplicates(embeddings, threshold=0.95)

    assert len(raw_clusters) == 1
    assert raw_clusters[0].members == ("mem_1", "mem_2")

    records = [
        MemoryRecord(id="mem_1", content="User prefers dark mode"),
        MemoryRecord(id="mem_2", content="User likes dark themes"),
        MemoryRecord(id="mem_3", content="Follow up tomorrow"),
    ]
    categories = [
        CategorizedMemory(memoryId="mem_1", category=MemoryCategory.PREFERENCE, confidence=0.9),
        CategorizedMemory(memoryId="mem_2", category=MemoryCategory.PREFERENCE, confidence=0.9),
        CategorizedMemory(memoryId="mem_3", category=MemoryCategory.TASK, confidence=0.9),
    ]
    clusters = enrich_clusters(records, categories, raw_clusters)

    metrics = calculate_metrics(records, categories, clusters)

    assert clusters[0].sharedTerms
    assert clusters[0].reasons
    assert metrics.totalMemories == 3
    assert metrics.duplicateCount == 1
    assert metrics.compressionOpportunity == 33.33
    assert metrics.categoryBreakdown[MemoryCategory.PREFERENCE] == 2
    assert metrics.compressionReasons

    validation = build_validation_summary(records, categories, clusters)

    assert validation["compressionDrivers"]["estimatedRemovableRecords"] == 1
    assert validation["clusterQuality"]["largestClusters"][0]["records"][0]["content"]
