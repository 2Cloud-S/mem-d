from memd.category_audit import audit_category_quality_v2
from memd.contracts import CategorizedMemory, MemoryCategory, MemoryRecord


def test_category_audit_v2_groups_unknown_causes_and_suggests_mappings() -> None:
    records = [
        MemoryRecord(id="mem_1", content="API token rotation depends on platform rollout"),
        MemoryRecord(id="mem_2", content="Cache schema depends on database migration"),
        MemoryRecord(id="mem_3", content="Billing insight shows duplicate webhook retries"),
        MemoryRecord(id="mem_4", content="Maybe consolidate retry settings later"),
        MemoryRecord(id="mem_5", content="tiny note"),
    ]
    categories = [
        CategorizedMemory(
            memoryId=record.id,
            category=MemoryCategory.UNKNOWN,
            confidence=0.2,
            reason="No V1 heuristic matched; inspect manually.",
        )
        for record in records
    ]

    audit = audit_category_quality_v2(records, categories)

    assert audit["unknownRate"] == 100.0
    assert audit["highConfidenceUnknownRate"] == 0.0
    assert audit["unknownClusters"]
    assert audit["topUnknownCauses"][0]["count"] >= 1
    assert audit["suggestedTaxonomyGaps"]
    assert audit["reclassificationCandidates"]
    assert audit["categoryConfidenceDistribution"]["buckets"]["low"] == 5
    discovery = audit["taxonomyDiscovery"]
    assert discovery["candidateCategories"]
    assert discovery["taxonomyGaps"]
    assert discovery["classifierFailures"]
    assert discovery["candidateCategories"][0]["label"]
    assert discovery["candidateCategories"][0]["estimatedUnknownRateReduction"] > 0


def test_category_audit_v2_ranks_candidates_by_confidence_and_frequency() -> None:
    records = [
        MemoryRecord(id="mem_1", content="Preference acceptable without explicit verb"),
        MemoryRecord(id="mem_2", content="This approach is better for onboarding"),
        MemoryRecord(id="mem_3", content="Service cache token config"),
    ]
    categories = [
        CategorizedMemory(
            memoryId=record.id,
            category=MemoryCategory.UNKNOWN,
            confidence=0.2,
        )
        for record in records
    ]

    audit = audit_category_quality_v2(records, categories)
    candidates = audit["reclassificationCandidates"]

    assert candidates[0]["suggestedCategory"] == MemoryCategory.PREFERENCE.value
    assert candidates[0]["confidence"] >= candidates[-1]["confidence"]
    assert all(candidate["frequency"] >= 1 for candidate in candidates)


def test_taxonomy_discovery_distinguishes_gaps_from_classifier_failures() -> None:
    records = [
        MemoryRecord(id="mem_1", content="Billing insight shows retry loops"),
        MemoryRecord(id="mem_2", content="Cache token config pipeline"),
        MemoryRecord(id="mem_3", content="Project note"),
    ]
    categories = [
        CategorizedMemory(
            memoryId=record.id,
            category=MemoryCategory.UNKNOWN,
            confidence=0.2,
        )
        for record in records
    ]

    audit = audit_category_quality_v2(records, categories)
    discovery = audit["taxonomyDiscovery"]
    gap_labels = {candidate["label"] for candidate in discovery["taxonomyGaps"]}
    failure_labels = {candidate["label"] for candidate in discovery["classifierFailures"]}

    assert "Derived Insight" in gap_labels
    assert "Technical Fragment" in failure_labels
    assert discovery["estimatedTaxonomyGapUnknownCount"] >= 1
    assert discovery["estimatedResolvableUnknownCount"] >= 1
