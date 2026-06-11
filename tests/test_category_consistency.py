from memd.category_consistency import audit_category_consistency
from memd.contracts import (
    CategorizedMemory,
    ClusterTrustLevel,
    DuplicateCluster,
    MemoryCategory,
    MemoryRecord,
)


def test_category_consistency_audit_flags_cluster_disagreement() -> None:
    records = [
        MemoryRecord(id="mem_1", content="User prefers TypeScript"),
        MemoryRecord(id="mem_2", content="User likes TypeScript"),
        MemoryRecord(id="mem_3", content="TypeScript is used for backend services"),
    ]
    categories = [
        CategorizedMemory(
            memoryId="mem_1",
            category=MemoryCategory.PREFERENCE,
            confidence=0.9,
        ),
        CategorizedMemory(
            memoryId="mem_2",
            category=MemoryCategory.PREFERENCE,
            confidence=0.9,
        ),
        CategorizedMemory(
            memoryId="mem_3",
            category=MemoryCategory.FACT,
            confidence=0.7,
            reason="factual technology usage",
        ),
    ]
    clusters = [
        DuplicateCluster(
            clusterId="cluster_1",
            members=("mem_1", "mem_2", "mem_3"),
            averageSimilarity=0.91,
            trustLevel=ClusterTrustLevel.HIGH,
        )
    ]

    audit = audit_category_consistency(records, categories, clusters)

    assert audit["categoryAgreementRate"] == 66.67
    assert audit["conflictClusterCount"] == 1
    assert audit["reclassificationOpportunityCount"] == 1
    assert audit["conflictClusters"][0]["dominantCategory"] == "Preference"
    assert audit["conflictClusters"][0]["minorityCategories"][0]["category"] == "Fact"
    assert audit["reclassificationCandidates"][0]["memoryId"] == "mem_3"
    assert audit["reclassificationCandidates"][0]["suggestedCategory"] == "Preference"
    assert audit["priorityConflicts"]


def test_category_consistency_audit_reports_full_agreement() -> None:
    records = [
        MemoryRecord(id="mem_1", content="User prefers dark mode"),
        MemoryRecord(id="mem_2", content="User likes dark themes"),
    ]
    categories = [
        CategorizedMemory(
            memoryId="mem_1",
            category=MemoryCategory.PREFERENCE,
            confidence=0.9,
        ),
        CategorizedMemory(
            memoryId="mem_2",
            category=MemoryCategory.PREFERENCE,
            confidence=0.9,
        ),
    ]
    clusters = [
        DuplicateCluster(
            clusterId="cluster_1",
            members=("mem_1", "mem_2"),
            averageSimilarity=0.95,
        )
    ]

    audit = audit_category_consistency(records, categories, clusters)

    assert audit["categoryAgreementRate"] == 100.0
    assert audit["conflictClusterCount"] == 0
    assert audit["reclassificationOpportunityCount"] == 0
