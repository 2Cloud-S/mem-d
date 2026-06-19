from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from memd.contracts import (
    ActionPlanSummary,
    ActionPriority,
    AnalysisMetrics,
    AnalysisReport,
    MemoryCategory,
    PolicySummary,
    RecommendationAction,
    MemoryResolution,
)
from memd.metrics import calculate_metrics
from memd.recommendations import plan_recommendations
from memd.simulation import (
    DUPLICATE_REMOVAL_CODE,
    ORPHAN_MERGE_CODE,
    simulate_recommendations,
)
from tests.test_recommendations import to_actions, to_clusters, to_memory_records

FIXTURES = Path(__file__).parent / "fixtures"
GOLD_PATH = FIXTURES / "simulation_gold.json"


def load_simulation_cases() -> list[dict[str, object]]:
    payload = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    cases = payload.get("cases", [])
    assert isinstance(cases, list)
    return [case for case in cases if isinstance(case, dict)]


def build_report_from_case(case: dict[str, object]) -> AnalysisReport:
    memories = to_memory_records(case)
    clusters = to_clusters(case)
    actions = to_actions(case)
    validation = dict(case.get("validation", {}))
    include_keep = bool(case.get("includeKeep", False))

    metrics = calculate_metrics(memories, [], clusters, validation.get("categoryQuality"))

    if case.get("useExplicitResolutions"):
        raw_resolutions = case.get("memoryResolutions", [])
        resolutions: list[MemoryResolution] = []
        if isinstance(raw_resolutions, list):
            for item in raw_resolutions:
                if isinstance(item, dict):
                    resolutions.append(
                        MemoryResolution(
                            memoryId=str(item["memoryId"]),
                            resolvedAction=RecommendationAction(str(item["resolvedAction"])),
                            role=str(item.get("role", "")),
                            confidence=float(item.get("confidence", 0.0)),
                            recommendationId=str(item["recommendationId"]),
                            conflictDetected=bool(item.get("conflictDetected", False)),
                            suppressedActions=tuple(
                                RecommendationAction(str(action))
                                for action in item.get("suppressedActions", [])
                            ),
                        )
                    )
        recommendations = ()
        summary = plan_recommendations(
            memories, clusters, validation, (), actions, metrics=metrics, include_keep=include_keep
        )[2]
        return AnalysisReport(
            metrics=metrics,
            clusters=tuple(clusters),
            memories=tuple(memories),
            validation=validation,
            actions=tuple(actions),
            recommendations=recommendations,
            memoryResolutions=tuple(resolutions),
            recommendationSummary=summary,
        )

    recommendations, resolutions, summary = plan_recommendations(
        memories,
        clusters,
        validation,
        (),
        actions,
        metrics=metrics,
        include_keep=include_keep,
    )
    return AnalysisReport(
        metrics=metrics,
        clusters=tuple(clusters),
        memories=tuple(memories),
        validation=validation,
        actions=tuple(actions),
        recommendations=recommendations,
        memoryResolutions=resolutions,
        recommendationSummary=summary,
    )


def active_ids(simulation) -> set[str]:
    return {memory.id for memory in simulation.simulatedMemories}


@pytest.mark.parametrize("case", load_simulation_cases(), ids=lambda c: str(c["id"]))
def test_simulation_gold_fixture_expectations(case: dict[str, object]) -> None:
    report = build_report_from_case(case)
    simulation = simulate_recommendations(report)
    expected = case.get("expected", {})
    assert isinstance(expected, dict)

    assert simulation.simulatedMemoryCount == expected.get("memoryCountAfter")
    assert simulation.metrics.memoryCountAfter == expected.get("memoryCountAfter")

    if "activeMemoryIds" in expected:
        assert active_ids(simulation) == set(expected["activeMemoryIds"])

    if "removedIds" in expected:
        before = {memory.id for memory in report.memories}
        after = active_ids(simulation)
        assert sorted(before - after) == sorted(expected["removedIds"])

    if "estimatedDuplicateReduction" in expected:
        assert (
            simulation.metrics.estimatedDuplicateReduction
            == expected["estimatedDuplicateReduction"]
        )

    if "memoryCountDelta" in expected:
        assert simulation.metrics.memoryCountDelta == expected["memoryCountDelta"]

    if "mergeGroupsSimulated" in expected:
        assert simulation.metrics.mergeGroupsSimulated == expected["mergeGroupsSimulated"]
        assert len(simulation.simulatedMerges) == expected["mergeGroupsSimulated"]

    if "archivesSimulated" in expected:
        assert simulation.metrics.archivesSimulated == expected["archivesSimulated"]
        assert len(simulation.simulatedArchives) == expected["archivesSimulated"]

    if "unresolvedReviewCount" in expected:
        assert simulation.metrics.unresolvedReviewCount == expected["unresolvedReviewCount"]

    if "conflictReviewCount" in expected:
        assert simulation.metrics.conflictReviewCount == expected["conflictReviewCount"]

    if "simulationWarningCount" in expected:
        assert simulation.metrics.simulationWarningCount == expected["simulationWarningCount"]

    if expected.get("warningCode"):
        codes = {warning.code for warning in simulation.simulationWarnings}
        assert expected["warningCode"] in codes

    if expected.get("orphanMergeDowngrade"):
        assert any(entry.orphanMergeDowngrade for entry in simulation.simulatedReviewQueue)

    if expected.get("implicitKeepFallback") or expected.get("resolutionFallbackExplainability"):
        for resolution in report.memoryResolutions:
            if resolution.recommendationId.startswith("rec:implicit:keep:"):
                matching = [
                    rec
                    for rec in report.recommendations
                    if rec.recommendationId == resolution.recommendationId
                ]
                assert not matching

    if "reviewQueueSize" in expected:
        assert len(simulation.simulatedReviewQueue) == expected["reviewQueueSize"]


def test_source_report_unchanged_after_simulation() -> None:
    case = next(item for item in load_simulation_cases() if item["id"] == "sim_mixed_recommendation_set")
    report = build_report_from_case(case)
    snapshot = report.model_dump()
    memory_objects = list(report.memories)

    simulate_recommendations(report)

    assert report.model_dump() == snapshot
    assert list(report.memories) == memory_objects
    for original, current in zip(memory_objects, report.memories, strict=True):
        assert original is current


def test_simulation_is_deterministic() -> None:
    case = next(item for item in load_simulation_cases() if item["id"] == "sim_merge_1")
    report = build_report_from_case(case)
    first = simulate_recommendations(report).model_dump()
    second = simulate_recommendations(report).model_dump()
    assert first == second
    assert first["simulationId"] == second["simulationId"]


def test_review_resolutions_never_remove_memories() -> None:
    case = next(item for item in load_simulation_cases() if item["id"] == "sim_review_1")
    report = build_report_from_case(case)
    simulation = simulate_recommendations(report)
    assert len(simulation.simulatedMemories) == len(report.memories)
    for resolution in report.memoryResolutions:
        if resolution.resolvedAction == RecommendationAction.REVIEW:
            assert resolution.memoryId in active_ids(simulation)


def test_keep_resolutions_never_remove_memories() -> None:
    case = next(item for item in load_simulation_cases() if item["id"] == "sim_keep_1")
    report = build_report_from_case(case)
    simulation = simulate_recommendations(report)
    assert len(simulation.simulatedMemories) == len(report.memories)
    for resolution in report.memoryResolutions:
        if resolution.resolvedAction == RecommendationAction.KEEP:
            assert resolution.memoryId in active_ids(simulation)


def test_orphan_merge_emits_warning_and_preserves_store() -> None:
    case = next(item for item in load_simulation_cases() if item["id"] == "sim_orphan_merge_no_keeper")
    report = build_report_from_case(case)
    original_resolutions = copy.deepcopy(report.memoryResolutions)
    simulation = simulate_recommendations(report)

    assert report.memoryResolutions == original_resolutions
    assert len(simulation.simulatedMemories) == len(report.memories)
    assert any(warning.code == ORPHAN_MERGE_CODE for warning in simulation.simulationWarnings)
    assert simulation.metrics.mergeGroupsSimulated == 0


def test_merge_removal_preserves_keeper_content() -> None:
    case = next(item for item in load_simulation_cases() if item["id"] == "sim_merge_1")
    report = build_report_from_case(case)
    keeper_content = next(m.content for m in report.memories if m.id == "tm_b")
    simulation = simulate_recommendations(report)
    keeper = next(m for m in simulation.simulatedMemories if m.id == "tm_b")
    assert keeper.content == keeper_content


def test_explainability_fallback_on_implicit_keep() -> None:
    case = next(item for item in load_simulation_cases() if item["id"] == "sim_implicit_keep_fallback")
    report = build_report_from_case(case)
    simulation = simulate_recommendations(report)
    for resolution in report.memoryResolutions:
        if resolution.recommendationId.startswith("rec:implicit:keep:"):
            assert resolution.resolvedAction == RecommendationAction.KEEP
    assert simulation.metrics.unresolvedReviewCount == 0


def test_simulated_archive_preserves_record_in_log() -> None:
    case = next(item for item in load_simulation_cases() if item["id"] == "sim_archive_1")
    report = build_report_from_case(case)
    original = next(m for m in report.memories if m.id == "la_s1_old")
    simulation = simulate_recommendations(report)
    archived = simulation.simulatedArchives[0]
    assert archived.memoryId == "la_s1_old"
    assert archived.archivedRecord.content == original.content
    assert archived.explainability.evidenceRefs


def test_simulated_merge_has_explainability_refs() -> None:
    case = next(item for item in load_simulation_cases() if item["id"] == "sim_merge_1")
    report = build_report_from_case(case)
    simulation = simulate_recommendations(report)
    merge = simulation.simulatedMerges[0]
    assert merge.explainability.explainabilitySource in {"recommendation", "resolution_fallback"}
    assert merge.explainability.evidenceRefs
    assert any(ref.startswith("resolution:") for ref in merge.explainability.evidenceRefs)


def test_metrics_are_structural_estimates_not_reanalysis() -> None:
    case = next(item for item in load_simulation_cases() if item["id"] == "sim_merge_1")
    report = build_report_from_case(case)
    simulation = simulate_recommendations(report)
    assert simulation.metricsDisclaimer.startswith("Structural estimates")
    assert simulation.metrics.referenceCompressionOpportunity == report.metrics.compressionOpportunity
    assert simulation.metrics.estimatedCompressionGain >= 0.0


def test_recommendation_outcome_utilization_rate() -> None:
    case = next(item for item in load_simulation_cases() if item["id"] == "sim_mixed_recommendation_set")
    report = build_report_from_case(case)
    simulation = simulate_recommendations(report)
    assert simulation.metrics.recommendationsWithStructuralEffect >= 1
    assert 0.0 < simulation.metrics.recommendationOutcomeUtilizationRate <= 1.0


def test_application_order_merge_before_archive() -> None:
    """Archive must not run before merge; mixed case removes both merge removable and archive."""
    case = next(item for item in load_simulation_cases() if item["id"] == "sim_mixed_recommendation_set")
    report = build_report_from_case(case)
    simulation = simulate_recommendations(report)
    assert "mx_a" not in active_ids(simulation)
    assert "mx_old" not in active_ids(simulation)
    assert "mx_b" in active_ids(simulation)
    assert "mx_new" in active_ids(simulation)


def test_empty_memories_returns_zero_deltas() -> None:
    report = AnalysisReport(
        metrics=AnalysisMetrics(
            totalMemories=0,
            duplicateCount=0,
            duplicatePercentage=0.0,
            compressionOpportunity=0.0,
            categoryBreakdown={category: 0 for category in MemoryCategory},
        ),
        clusters=(),
        memories=(),
        actionSummary=ActionPlanSummary(
            totalActions=0,
            safeActions=0,
            reviewActions=0,
            estimatedTrustedSavings=0,
            estimatedUnverifiedSavings=0,
            actionsByPriority={priority: 0 for priority in ActionPriority},
        ),
        policySummary=PolicySummary(),
    )
    simulation = simulate_recommendations(report)
    assert simulation.metrics.memoryCountDelta == 0
    assert simulation.metrics.estimatedDuplicateReduction == 0
    assert simulation.simulatedMemories == ()


def test_lifecycle_distribution_excludes_removed_memories() -> None:
    case = next(item for item in load_simulation_cases() if item["id"] == "sim_archive_1")
    report = build_report_from_case(case)
    simulation = simulate_recommendations(report)
    assert simulation.metrics.lifecycleDistributionBefore.get("Superseded", 0) == 1
    assert simulation.metrics.lifecycleDistributionAfter.get("Superseded", 0) == 0
    assert simulation.metrics.lifecycleDistributionChange.get("Superseded", 0) == -1


def test_duplicate_removal_warning_when_already_removed() -> None:
    case = next(item for item in load_simulation_cases() if item["id"] == "sim_mixed_recommendation_set")
    report = build_report_from_case(case)
    simulation = simulate_recommendations(report)
    duplicate_warnings = [
        w for w in simulation.simulationWarnings if w.code == DUPLICATE_REMOVAL_CODE
    ]
    assert not duplicate_warnings


def test_duplicate_removal_skipped_positive_path() -> None:
    case = next(item for item in load_simulation_cases() if item["id"] == "sim_duplicate_removal_skipped")
    report = build_report_from_case(case)
    simulation = simulate_recommendations(report)
    assert any(warning.code == DUPLICATE_REMOVAL_CODE for warning in simulation.simulationWarnings)
    assert simulation.metrics.simulationWarningCount == 1
    assert simulation.metrics.archivesSimulated == 0
    assert simulation.metrics.mergeGroupsSimulated == 1
    assert active_ids(simulation) == {"dr_k"}


def test_copy_isolation_preserves_report_fields() -> None:
    case = next(item for item in load_simulation_cases() if item["id"] == "sim_mixed_recommendation_set")
    report = build_report_from_case(case)
    memory_objects = list(report.memories)
    recommendation_objects = list(report.recommendations)
    resolution_objects = list(report.memoryResolutions)
    snapshot = report.model_dump()

    simulate_recommendations(report)

    assert report.model_dump() == snapshot
    assert list(report.memories) == memory_objects
    assert list(report.recommendations) == recommendation_objects
    assert list(report.memoryResolutions) == resolution_objects
    for original, current in zip(memory_objects, report.memories, strict=True):
        assert original is current


@pytest.mark.parametrize("case", load_simulation_cases(), ids=lambda c: str(c["id"]))
def test_monotonic_reduction_never_increases_store(case: dict[str, object]) -> None:
    report = build_report_from_case(case)
    simulation = simulate_recommendations(report)
    assert simulation.metrics.memoryCountAfter <= simulation.metrics.memoryCountBefore


@pytest.mark.parametrize("case", load_simulation_cases(), ids=lambda c: str(c["id"]))
def test_no_orphan_removal_every_removed_id_is_logged(case: dict[str, object]) -> None:
    report = build_report_from_case(case)
    simulation = simulate_recommendations(report)
    before = {memory.id for memory in report.memories}
    after = active_ids(simulation)
    removed = before - after
    logged_removals = set()
    for merge in simulation.simulatedMerges:
        logged_removals.update(merge.removedIds)
    logged_removals.update(entry.memoryId for entry in simulation.simulatedArchives)
    assert removed == logged_removals


def test_fallback_enrichment_from_validation_evidence() -> None:
    from memd.simulation import (
        _build_explainability,
        _cluster_by_member,
        _lifecycle_by_id,
    )

    case = next(item for item in load_simulation_cases() if item["id"] == "sim_implicit_keep_fallback")
    report = build_report_from_case(case)
    report = report.model_copy(
        update={
            "validation": {
                **report.validation,
                "memoryEvolutionAudit": {
                    "supersededMemories": [
                        {
                            "caseId": "superseded_ik_1_ik_2",
                            "involvedMemories": [
                                {"memoryId": "ik_1", "content": "Stable fact about deployment region."}
                            ],
                        }
                    ]
                },
                "categoryQuality": {
                    "categoryConsistency": {
                        "reclassificationCandidates": [
                            {
                                "memoryId": "ik_1",
                                "clusterId": "cluster_ik",
                                "currentCategory": "Fact",
                                "suggestedCategory": "Preference",
                            }
                        ]
                    }
                },
            }
        }
    )
    resolution = next(r for r in report.memoryResolutions if r.memoryId == "ik_1")
    assert resolution.recommendationId.startswith("rec:implicit:keep:")
    explainability = _build_explainability(
        resolution,
        None,
        report,
        _lifecycle_by_id(report.validation),
        _cluster_by_member(report.clusters),
    )
    assert explainability.explainabilitySource == "resolution_fallback"
    assert any(ref.startswith("lifecycle:") for ref in explainability.evidenceRefs)
    assert any(ref.startswith("category_quality:") for ref in explainability.evidenceRefs)
