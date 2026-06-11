from memd.cluster_audit import audit_largest_clusters
from memd.contracts import (
    CategorizedMemory,
    DuplicateCluster,
    EmbeddedMemory,
    MemoryCategory,
    MemoryRecord,
)


def test_audit_largest_clusters_flags_heterogeneous_cluster() -> None:
    records = [
        MemoryRecord(id="mem_1", content="User prefers TypeScript for backend projects"),
        MemoryRecord(id="mem_2", content="User likes TypeScript for new services"),
        MemoryRecord(id="mem_3", content="Reminder: renew SSL certificate tomorrow"),
        MemoryRecord(id="mem_4", content="PostgreSQL is running on RDS"),
    ]
    categories = [
        CategorizedMemory(memoryId="mem_1", category=MemoryCategory.PREFERENCE, confidence=0.9),
        CategorizedMemory(memoryId="mem_2", category=MemoryCategory.PREFERENCE, confidence=0.9),
        CategorizedMemory(memoryId="mem_3", category=MemoryCategory.TASK, confidence=0.9),
        CategorizedMemory(memoryId="mem_4", category=MemoryCategory.FACT, confidence=0.9),
    ]
    embeddings = [
        EmbeddedMemory(memoryId="mem_1", embedding=(1.0, 0.0, 0.0)),
        EmbeddedMemory(memoryId="mem_2", embedding=(0.95, 0.05, 0.0)),
        EmbeddedMemory(memoryId="mem_3", embedding=(0.2, 0.8, 0.0)),
        EmbeddedMemory(memoryId="mem_4", embedding=(0.0, 0.0, 1.0)),
    ]
    clusters = [
        DuplicateCluster(
            clusterId="cluster_1",
            members=("mem_1", "mem_2", "mem_3", "mem_4"),
            averageSimilarity=0.5,
        )
    ]

    audit = audit_largest_clusters(records, categories, clusters, embeddings)

    cluster_audit = audit["largestClusterAudits"][0]
    assert cluster_audit["size"] == 4
    assert cluster_audit["similarityDistribution"]["spread"] > 0
    assert cluster_audit["representativeMemories"]
    assert cluster_audit["appearsHeterogeneous"] is True
    assert audit["overClusteringCandidates"]
    assert audit["clusterContamination"]
