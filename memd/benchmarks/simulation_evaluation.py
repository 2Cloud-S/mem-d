from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Sequence, Tuple

from memd import __version__ as memd_version
from memd.contracts import (
    AnalysisReport,
    MemoryResolution,
    RecommendationAction,
)
from memd.metrics import calculate_metrics
from memd.recommendations import plan_recommendations
from memd.simulation import (
    DUPLICATE_REMOVAL_CODE,
    ORPHAN_MERGE_CODE,
    simulate_recommendations,
)
from memd.benchmarks.recommendation_evaluation import (
    _to_actions,
    _to_clusters,
    _to_memory_records,
)


FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
GOLD_PATH = FIXTURES / "simulation_gold.json"

PERCENT_TOLERANCE = 0.01
RATE_TOLERANCE = 0.0001
BENCHMARK_VERSION = "0.7.0"

MERGE_CASE_IDS = frozenset(
    {"sim_merge_1", "sim_mixed_recommendation_set", "sim_duplicate_removal_skipped"}
)
ARCHIVE_CASE_IDS = frozenset({"sim_archive_1", "sim_mixed_recommendation_set"})
REVIEW_CASE_IDS = frozenset(
    {"sim_review_1", "sim_conflict_archive_merge", "sim_orphan_merge_no_keeper"}
)
ORPHAN_CASE_IDS = frozenset({"sim_orphan_merge_no_keeper"})
WARNING_CASE_IDS = frozenset(
    {"sim_orphan_merge_no_keeper", "sim_duplicate_removal_skipped"}
)

GATING_EXPECTED_FIELDS = frozenset(
    {
        "memoryCountAfter",
        "activeMemoryIds",
        "removedIds",
        "mergeGroupsSimulated",
        "archivesSimulated",
        "unresolvedReviewCount",
        "reviewQueueSize",
        "conflictReviewCount",
        "simulationWarningCount",
        "warningCode",
        "orphanMergeDowngrade",
        "estimatedDuplicateReduction",
        "memoryCountDelta",
    }
)
DIAGNOSTIC_EXPECTED_FIELDS = frozenset(
    {"implicitKeepFallback", "resolutionFallbackExplainability"}
)
RECOGNIZED_EXPECTED_FIELDS = GATING_EXPECTED_FIELDS | DIAGNOSTIC_EXPECTED_FIELDS

SAFETY_PROPERTIES = (
    "source_immutability",
    "idempotency",
    "monotonic_reduction",
    "no_orphan_removal",
    "orphan_safety",
    "review_preservation",
    "duplicate_removal_safety",
)


@dataclass(frozen=True)
class CheckpointStats:
    passed: int
    total: int

    @property
    def accuracy(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total


@dataclass(frozen=True)
class SimulationEvaluationFailure:
    case_id: str
    checkpoint: str
    expected: Any
    actual: Any
    category: str


@dataclass(frozen=True)
class CaseEvaluationResult:
    case_id: str
    passed: bool
    checkpoints_passed: int
    checkpoints_total: int
    simulation_id: str


@dataclass(frozen=True)
class SafetyResult:
    passed: bool
    properties: Dict[str, bool]


@dataclass(frozen=True)
class SimulationEvaluationResult:
    passed_checkpoints: int
    total_checkpoints: int
    merge: CheckpointStats
    archive: CheckpointStats
    review: CheckpointStats
    warning: CheckpointStats
    orphan: CheckpointStats
    explainability: CheckpointStats
    metric_consistency: CheckpointStats
    safety: SafetyResult
    failures: Tuple[SimulationEvaluationFailure, ...]
    diagnostic: Dict[str, Any]
    cases: Tuple[CaseEvaluationResult, ...]
    case_count: int
    fixture_path: Path
    regression_guards: Dict[str, Any] = field(default_factory=dict)

    @property
    def overall_structural_accuracy(self) -> float:
        if self.total_checkpoints == 0:
            return 0.0
        return self.passed_checkpoints / self.total_checkpoints

    @property
    def merge_projection_accuracy(self) -> float:
        return self.merge.accuracy

    @property
    def archive_projection_accuracy(self) -> float:
        return self.archive.accuracy

    @property
    def review_preservation_accuracy(self) -> float:
        return self.review.accuracy

    @property
    def warning_accuracy(self) -> float:
        return self.warning.accuracy

    @property
    def orphan_merge_accuracy(self) -> float:
        return self.orphan.accuracy

    @property
    def explainability_accuracy(self) -> float:
        return self.explainability.accuracy

    @property
    def metric_consistency_accuracy(self) -> float:
        return self.metric_consistency.accuracy

    @property
    def gate_passed(self) -> bool:
        return (
            self.overall_structural_accuracy == 1.0
            and self.orphan_merge_accuracy == 1.0
            and self.safety.passed
            and not self.failures
        )


@dataclass
class _CategoryCounters:
    passed: int = 0
    total: int = 0


@dataclass
class _EvaluationAccumulator:
    overall: _CategoryCounters = field(default_factory=_CategoryCounters)
    merge: _CategoryCounters = field(default_factory=_CategoryCounters)
    archive: _CategoryCounters = field(default_factory=_CategoryCounters)
    review: _CategoryCounters = field(default_factory=_CategoryCounters)
    warning: _CategoryCounters = field(default_factory=_CategoryCounters)
    orphan: _CategoryCounters = field(default_factory=_CategoryCounters)
    explainability: _CategoryCounters = field(default_factory=_CategoryCounters)
    metric_consistency: _CategoryCounters = field(default_factory=_CategoryCounters)
    failures: List[SimulationEvaluationFailure] = field(default_factory=list)
    case_results: List[CaseEvaluationResult] = field(default_factory=list)
    safety_properties: Dict[str, bool] = field(
        default_factory=lambda: {name: True for name in SAFETY_PROPERTIES}
    )
    diagnostic_utilization: List[Dict[str, Any]] = field(default_factory=list)
    diagnostic_warnings: MutableMapping[str, int] = field(default_factory=dict)
    diagnostic_reductions: List[Dict[str, Any]] = field(default_factory=list)


def _load_gold_cases(path: Path) -> List[Mapping[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError("simulation_gold.json must contain a list in `cases`")
    return [case for case in cases if isinstance(case, dict)]


def build_report_from_case(case: Mapping[str, Any]) -> AnalysisReport:
    memories = _to_memory_records(case)
    clusters = _to_clusters(case)
    actions = _to_actions(case)
    validation = case.get("validation", {})
    if not isinstance(validation, dict):
        validation = {}
    include_keep = bool(case.get("includeKeep", False))

    metrics = calculate_metrics(memories, [], clusters, validation.get("categoryQuality"))

    if case.get("useExplicitResolutions"):
        raw_resolutions = case.get("memoryResolutions", [])
        resolutions: List[MemoryResolution] = []
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
            memories,
            clusters,
            validation,
            (),
            actions,
            metrics=metrics,
            include_keep=include_keep,
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


def _active_ids(simulation: Any) -> set[str]:
    return {memory.id for memory in simulation.simulatedMemories}


def _floats_close(actual: float, expected: float, tolerance: float) -> bool:
    return abs(actual - expected) <= tolerance


def _record_checkpoint(
    acc: _EvaluationAccumulator,
    *,
    case_id: str,
    checkpoint: str,
    passed: bool,
    categories: Sequence[str],
    expected: Any = None,
    actual: Any = None,
) -> None:
    acc.overall.total += 1
    if passed:
        acc.overall.passed += 1
    else:
        primary_category = categories[0] if categories else "overall"
        acc.failures.append(
            SimulationEvaluationFailure(
                case_id=case_id,
                checkpoint=checkpoint,
                expected=expected,
                actual=actual,
                category=primary_category,
            )
        )

    category_map = {
        "merge": acc.merge,
        "archive": acc.archive,
        "review": acc.review,
        "warning": acc.warning,
        "orphan": acc.orphan,
        "explainability": acc.explainability,
        "metric_consistency": acc.metric_consistency,
    }
    for category in categories:
        counter = category_map.get(category)
        if counter is None:
            continue
        counter.total += 1
        if passed:
            counter.passed += 1


def _categories_for_field(field: str, case_id: str) -> List[str]:
    categories = ["overall"]
    if field in {
        "memoryCountAfter",
        "activeMemoryIds",
        "removedIds",
        "mergeGroupsSimulated",
        "estimatedDuplicateReduction",
        "memoryCountDelta",
    }:
        if case_id in MERGE_CASE_IDS:
            categories.append("merge")
        if case_id in ARCHIVE_CASE_IDS:
            categories.append("archive")
        if case_id in REVIEW_CASE_IDS:
            categories.append("review")
    elif field in {"archivesSimulated"}:
        categories.append("archive")
    elif field in {
        "unresolvedReviewCount",
        "reviewQueueSize",
        "conflictReviewCount",
    }:
        categories.append("review")
    elif field in {
        "simulationWarningCount",
        "warningCode",
        "orphanMergeDowngrade",
    }:
        categories.append("warning")
        if case_id in ORPHAN_CASE_IDS:
            categories.append("orphan")
    return categories


def _evaluate_expected_fields(
    case: Mapping[str, Any],
    report: AnalysisReport,
    simulation: Any,
    acc: _EvaluationAccumulator,
) -> Tuple[int, int]:
    case_id = str(case["id"])
    expected = case.get("expected", {})
    if not isinstance(expected, dict):
        return 0, 0

    case_passed = 0
    case_total = 0
    before_ids = {memory.id for memory in report.memories}
    after_ids = _active_ids(simulation)

    for field_name, expected_value in expected.items():
        if field_name in DIAGNOSTIC_EXPECTED_FIELDS:
            continue
        if field_name not in GATING_EXPECTED_FIELDS:
            continue

        categories = _categories_for_field(field_name, case_id)
        passed = False
        actual: Any = None

        if field_name == "memoryCountAfter":
            actual = simulation.metrics.memoryCountAfter
            passed = (
                simulation.simulatedMemoryCount == expected_value
                and simulation.metrics.memoryCountAfter == expected_value
            )
        elif field_name == "activeMemoryIds":
            actual = sorted(after_ids)
            passed = after_ids == set(expected_value)
        elif field_name == "removedIds":
            actual = sorted(before_ids - after_ids)
            passed = sorted(before_ids - after_ids) == sorted(expected_value)
        elif field_name == "mergeGroupsSimulated":
            actual = simulation.metrics.mergeGroupsSimulated
            passed = (
                simulation.metrics.mergeGroupsSimulated == expected_value
                and len(simulation.simulatedMerges) == expected_value
            )
        elif field_name == "archivesSimulated":
            actual = simulation.metrics.archivesSimulated
            passed = (
                simulation.metrics.archivesSimulated == expected_value
                and len(simulation.simulatedArchives) == expected_value
            )
        elif field_name == "unresolvedReviewCount":
            actual = simulation.metrics.unresolvedReviewCount
            passed = simulation.metrics.unresolvedReviewCount == expected_value
        elif field_name == "reviewQueueSize":
            actual = len(simulation.simulatedReviewQueue)
            passed = len(simulation.simulatedReviewQueue) == expected_value
        elif field_name == "conflictReviewCount":
            actual = simulation.metrics.conflictReviewCount
            passed = simulation.metrics.conflictReviewCount == expected_value
        elif field_name == "simulationWarningCount":
            actual = simulation.metrics.simulationWarningCount
            passed = simulation.metrics.simulationWarningCount == expected_value
        elif field_name == "warningCode":
            codes = {warning.code for warning in simulation.simulationWarnings}
            actual = sorted(codes)
            passed = expected_value in codes
        elif field_name == "orphanMergeDowngrade":
            actual = any(
                entry.orphanMergeDowngrade for entry in simulation.simulatedReviewQueue
            )
            passed = actual == expected_value
        elif field_name == "estimatedDuplicateReduction":
            actual = simulation.metrics.estimatedDuplicateReduction
            passed = simulation.metrics.estimatedDuplicateReduction == expected_value
        elif field_name == "memoryCountDelta":
            actual = simulation.metrics.memoryCountDelta
            passed = simulation.metrics.memoryCountDelta == expected_value

        case_total += 1
        if passed:
            case_passed += 1
        _record_checkpoint(
            acc,
            case_id=case_id,
            checkpoint=field_name,
            passed=passed,
            categories=categories,
            expected=expected_value,
            actual=actual,
        )

    return case_passed, case_total


def _evaluate_derived_checkpoints(
    case: Mapping[str, Any],
    report: AnalysisReport,
    simulation: Any,
    acc: _EvaluationAccumulator,
) -> Tuple[int, int]:
    case_id = str(case["id"])
    case_passed = 0
    case_total = 0
    before_ids = {memory.id for memory in report.memories}
    after_ids = _active_ids(simulation)
    metrics = simulation.metrics

    def record(
        checkpoint: str,
        passed: bool,
        categories: Sequence[str],
        expected: Any = None,
        actual: Any = None,
    ) -> None:
        nonlocal case_passed, case_total
        case_total += 1
        if passed:
            case_passed += 1
        _record_checkpoint(
            acc,
            case_id=case_id,
            checkpoint=checkpoint,
            passed=passed,
            categories=categories,
            expected=expected,
            actual=actual,
        )

    if case_id in MERGE_CASE_IDS:
        for merge in simulation.simulatedMerges:
            source = next(
                (memory for memory in report.memories if memory.id == merge.keeperId),
                None,
            )
            keeper = next(
                (memory for memory in simulation.simulatedMemories if memory.id == merge.keeperId),
                None,
            )
            content_match = (
                source is not None
                and keeper is not None
                and keeper.content == source.content
            )
            record(
                "keeper_content_unchanged",
                content_match,
                ["overall", "merge"],
                expected=source.content if source else None,
                actual=keeper.content if keeper else None,
            )

    if case_id in ARCHIVE_CASE_IDS:
        for archive in simulation.simulatedArchives:
            source = next(
                (memory for memory in report.memories if memory.id == archive.memoryId),
                None,
            )
            content_match = (
                source is not None
                and archive.archivedRecord.content == source.content
            )
            record(
                "archive_record_preserved",
                content_match,
                ["overall", "archive"],
                expected=source.content if source else None,
                actual=archive.archivedRecord.content,
            )

    if case_id in {"sim_review_1", "sim_conflict_archive_merge"}:
        record(
            "review_no_structural_removal",
            metrics.memoryCountAfter == metrics.memoryCountBefore,
            ["overall", "review"],
            expected=metrics.memoryCountBefore,
            actual=metrics.memoryCountAfter,
        )
        for resolution in report.memoryResolutions:
            if resolution.resolvedAction == RecommendationAction.REVIEW:
                record(
                    f"review_id_preserved:{resolution.memoryId}",
                    resolution.memoryId in after_ids,
                    ["overall", "review"],
                    expected=True,
                    actual=resolution.memoryId in after_ids,
                )

    if case_id not in WARNING_CASE_IDS:
        record(
            "no_unexpected_warnings",
            len(simulation.simulationWarnings) == 0,
            ["overall", "warning"],
            expected=0,
            actual=len(simulation.simulationWarnings),
        )

    for merge in simulation.simulatedMerges:
        refs = merge.explainability.evidenceRefs
        passed = bool(refs) and any(ref.startswith("resolution:") for ref in refs)
        record(
            f"explainability_merge:{merge.keeperId}",
            passed,
            ["overall", "explainability"],
            expected="non-empty evidenceRefs with resolution: prefix",
            actual=list(refs),
        )

    for archive in simulation.simulatedArchives:
        refs = archive.explainability.evidenceRefs
        passed = bool(refs) and any(ref.startswith("resolution:") for ref in refs)
        record(
            f"explainability_archive:{archive.memoryId}",
            passed,
            ["overall", "explainability"],
            expected="non-empty evidenceRefs with resolution: prefix",
            actual=list(refs),
        )

    for entry in simulation.simulatedReviewQueue:
        refs = entry.explainability.evidenceRefs
        passed = bool(refs) and any(ref.startswith("resolution:") for ref in refs)
        record(
            f"explainability_review:{entry.memoryId}",
            passed,
            ["overall", "explainability"],
            expected="non-empty evidenceRefs with resolution: prefix",
            actual=list(refs),
        )

    expected_delta = metrics.memoryCountAfter - metrics.memoryCountBefore
    record(
        "metric_memory_count_delta",
        metrics.memoryCountDelta == expected_delta,
        ["overall", "metric_consistency"],
        expected=expected_delta,
        actual=metrics.memoryCountDelta,
    )

    record(
        "metric_trusted_gain_bound",
        metrics.estimatedTrustedCompressionGain
        <= metrics.estimatedCompressionGain + PERCENT_TOLERANCE,
        ["overall", "metric_consistency"],
        expected=f"<= {metrics.estimatedCompressionGain + PERCENT_TOLERANCE}",
        actual=metrics.estimatedTrustedCompressionGain,
    )

    effect_ids = {entry.recommendationId for entry in simulation.simulatedMerges} | {
        entry.recommendationId for entry in simulation.simulatedArchives
    }
    record(
        "metric_structural_effect_count",
        metrics.recommendationsWithStructuralEffect == len(effect_ids),
        ["overall", "metric_consistency"],
        expected=len(effect_ids),
        actual=metrics.recommendationsWithStructuralEffect,
    )

    orphan_downgraded = {
        entry.memoryId
        for entry in simulation.simulatedReviewQueue
        if entry.orphanMergeDowngrade
    }
    expected_unresolved = 0
    for resolution in report.memoryResolutions:
        if (
            resolution.resolvedAction == RecommendationAction.REVIEW
            or resolution.memoryId in orphan_downgraded
            or resolution.conflictDetected
        ):
            expected_unresolved += 1
    record(
        "metric_unresolved_review_count",
        metrics.unresolvedReviewCount == expected_unresolved,
        ["overall", "metric_consistency"],
        expected=expected_unresolved,
        actual=metrics.unresolvedReviewCount,
    )

    if case_id in ORPHAN_CASE_IDS:
        orphan_passed = (
            metrics.memoryCountAfter == metrics.memoryCountBefore
            and any(w.code == ORPHAN_MERGE_CODE for w in simulation.simulationWarnings)
            and any(entry.orphanMergeDowngrade for entry in simulation.simulatedReviewQueue)
            and metrics.mergeGroupsSimulated == 0
            and not (before_ids - after_ids)
        )
        record(
            "orphan_case_complete",
            orphan_passed,
            ["overall", "orphan", "warning"],
            expected="no removal, warning, downgrade, zero merge groups",
            actual={
                "memoryCountAfter": metrics.memoryCountAfter,
                "memoryCountBefore": metrics.memoryCountBefore,
                "warningCodes": [w.code for w in simulation.simulationWarnings],
                "mergeGroupsSimulated": metrics.mergeGroupsSimulated,
            },
        )

    return case_passed, case_total


def _validate_safety(
    case: Mapping[str, Any],
    report: AnalysisReport,
    simulation: Any,
    acc: _EvaluationAccumulator,
    *,
    pre_simulation_snapshot: Mapping[str, Any],
    pre_simulation_memories: Sequence[Any],
) -> None:
    case_id = str(case["id"])

    if report.model_dump() != pre_simulation_snapshot:
        acc.safety_properties["source_immutability"] = False
        acc.failures.append(
            SimulationEvaluationFailure(
                case_id=case_id,
                checkpoint="source_immutability",
                expected="unchanged report snapshot",
                actual="report mutated",
                category="safety",
            )
        )
    if list(report.memories) != list(pre_simulation_memories):
        acc.safety_properties["source_immutability"] = False
    for original, current in zip(pre_simulation_memories, report.memories, strict=False):
        if original is not current:
            acc.safety_properties["source_immutability"] = False
            break

    first_dump = simulation.model_dump()
    second = simulate_recommendations(report)
    if first_dump != second.model_dump() or first_dump.get("simulationId") != second.simulationId:
        acc.safety_properties["idempotency"] = False
        acc.failures.append(
            SimulationEvaluationFailure(
                case_id=case_id,
                checkpoint="idempotency",
                expected=first_dump.get("simulationId"),
                actual=second.simulationId,
                category="safety",
            )
        )

    if simulation.metrics.memoryCountAfter > simulation.metrics.memoryCountBefore:
        acc.safety_properties["monotonic_reduction"] = False
        acc.failures.append(
            SimulationEvaluationFailure(
                case_id=case_id,
                checkpoint="monotonic_reduction",
                expected=f"<= {simulation.metrics.memoryCountBefore}",
                actual=simulation.metrics.memoryCountAfter,
                category="safety",
            )
        )

    before_ids = {memory.id for memory in report.memories}
    after_ids = _active_ids(simulation)
    removed = before_ids - after_ids
    logged_removals: set[str] = set()
    for merge in simulation.simulatedMerges:
        logged_removals.update(merge.removedIds)
    logged_removals.update(entry.memoryId for entry in simulation.simulatedArchives)
    if removed != logged_removals:
        acc.safety_properties["no_orphan_removal"] = False
        acc.failures.append(
            SimulationEvaluationFailure(
                case_id=case_id,
                checkpoint="no_orphan_removal",
                expected=sorted(logged_removals),
                actual=sorted(removed),
                category="safety",
            )
        )

    if case_id == "sim_orphan_merge_no_keeper":
        if removed:
            acc.safety_properties["orphan_safety"] = False
        if not any(w.code == ORPHAN_MERGE_CODE for w in simulation.simulationWarnings):
            acc.safety_properties["orphan_safety"] = False

    if case_id == "sim_review_1":
        if len(simulation.simulatedMemories) != len(report.memories):
            acc.safety_properties["review_preservation"] = False
        for resolution in report.memoryResolutions:
            if resolution.resolvedAction == RecommendationAction.REVIEW:
                if resolution.memoryId not in after_ids:
                    acc.safety_properties["review_preservation"] = False

    if case_id == "sim_duplicate_removal_skipped":
        if not any(w.code == DUPLICATE_REMOVAL_CODE for w in simulation.simulationWarnings):
            acc.safety_properties["duplicate_removal_safety"] = False


def _collect_diagnostic(
    case: Mapping[str, Any],
    simulation: Any,
    acc: _EvaluationAccumulator,
) -> None:
    case_id = str(case["id"])
    metrics = simulation.metrics
    acc.diagnostic_utilization.append(
        {
            "caseId": case_id,
            "recommendationUtilizationRate": metrics.recommendationUtilizationRate,
            "recommendationOutcomeUtilizationRate": metrics.recommendationOutcomeUtilizationRate,
            "simulationId": simulation.simulationId,
            "diagnosticOnly": True,
        }
    )
    acc.diagnostic_reductions.append(
        {
            "caseId": case_id,
            "memoryCountDelta": metrics.memoryCountDelta,
            "estimatedDuplicateReduction": metrics.estimatedDuplicateReduction,
            "diagnosticOnly": True,
        }
    )
    for warning in simulation.simulationWarnings:
        acc.diagnostic_warnings[warning.code] = (
            acc.diagnostic_warnings.get(warning.code, 0) + 1
        )


def evaluate_simulations(gold_path: Path | None = None) -> SimulationEvaluationResult:
    """
    Evaluate simulation quality against the gold fixture.

    Evaluation-only helper. Does not modify simulation or pipeline behavior.
    """
    path = gold_path or GOLD_PATH
    cases = _load_gold_cases(path)
    acc = _EvaluationAccumulator()

    for case in cases:
        case_id = str(case["id"])
        report = build_report_from_case(case)
        original_resolutions = copy.deepcopy(report.memoryResolutions)
        pre_simulation_snapshot = report.model_dump()
        pre_simulation_memories = list(report.memories)
        simulation = simulate_recommendations(report)

        field_passed, field_total = _evaluate_expected_fields(case, report, simulation, acc)
        derived_passed, derived_total = _evaluate_derived_checkpoints(
            case, report, simulation, acc
        )
        _validate_safety(
            case,
            report,
            simulation,
            acc,
            pre_simulation_snapshot=pre_simulation_snapshot,
            pre_simulation_memories=pre_simulation_memories,
        )
        _collect_diagnostic(case, simulation, acc)

        if case_id in ORPHAN_CASE_IDS and report.memoryResolutions != original_resolutions:
            acc.safety_properties["orphan_safety"] = False
            acc.failures.append(
                SimulationEvaluationFailure(
                    case_id=case_id,
                    checkpoint="orphan_resolutions_unchanged",
                    expected="unchanged memoryResolutions",
                    actual="mutated",
                    category="safety",
                )
            )

        case_passed = (field_passed + derived_passed) == (field_total + derived_total)
        acc.case_results.append(
            CaseEvaluationResult(
                case_id=case_id,
                passed=case_passed,
                checkpoints_passed=field_passed + derived_passed,
                checkpoints_total=field_total + derived_total,
                simulation_id=simulation.simulationId,
            )
        )

    safety_passed = all(acc.safety_properties.values())
    diagnostic = {
        "recommendationUtilizationDistribution": acc.diagnostic_utilization,
        "warningDistribution": dict(acc.diagnostic_warnings),
        "projectedReductionDistribution": acc.diagnostic_reductions,
        "diagnosticOnly": True,
    }

    return SimulationEvaluationResult(
        passed_checkpoints=acc.overall.passed,
        total_checkpoints=acc.overall.total,
        merge=CheckpointStats(acc.merge.passed, acc.merge.total),
        archive=CheckpointStats(acc.archive.passed, acc.archive.total),
        review=CheckpointStats(acc.review.passed, acc.review.total),
        warning=CheckpointStats(acc.warning.passed, acc.warning.total),
        orphan=CheckpointStats(acc.orphan.passed, acc.orphan.total),
        explainability=CheckpointStats(acc.explainability.passed, acc.explainability.total),
        metric_consistency=CheckpointStats(
            acc.metric_consistency.passed, acc.metric_consistency.total
        ),
        safety=SafetyResult(passed=safety_passed, properties=dict(acc.safety_properties)),
        failures=tuple(acc.failures),
        diagnostic=diagnostic,
        cases=tuple(acc.case_results),
        case_count=len(cases),
        fixture_path=path,
        regression_guards={
            "longmemeval": {"passed": None, "notes": "Not run; regression guard only"},
            "perma": {"passed": None, "notes": "Not run; regression guard only"},
            "diagnosticOnly": True,
        },
    )


def evaluation_result_to_dict(result: SimulationEvaluationResult) -> Dict[str, Any]:
    return {
        "benchmark": "simulation_evaluation",
        "version": BENCHMARK_VERSION,
        "fixture": str(result.fixture_path),
        "simulationMode": "full",
        "caseCount": result.case_count,
        "overallStructuralAccuracy": result.overall_structural_accuracy,
        "passedCheckpoints": result.passed_checkpoints,
        "totalCheckpoints": result.total_checkpoints,
        "mergeProjectionAccuracy": result.merge_projection_accuracy,
        "archiveProjectionAccuracy": result.archive_projection_accuracy,
        "reviewPreservationAccuracy": result.review_preservation_accuracy,
        "warningAccuracy": result.warning_accuracy,
        "orphanMergeAccuracy": result.orphan_merge_accuracy,
        "explainabilityAccuracy": result.explainability_accuracy,
        "metricConsistencyAccuracy": result.metric_consistency_accuracy,
        "gatePassed": result.gate_passed,
        "safety": {
            "passed": result.safety.passed,
            "properties": list(SAFETY_PROPERTIES),
            "details": result.safety.properties,
        },
        "diagnostic": result.diagnostic,
        "regressionGuards": result.regression_guards,
        "failures": [
            {
                "caseId": failure.case_id,
                "checkpoint": failure.checkpoint,
                "expected": failure.expected,
                "actual": failure.actual,
                "category": failure.category,
            }
            for failure in result.failures
        ],
        "cases": [
            {
                "id": case.case_id,
                "passed": case.passed,
                "checkpointsPassed": case.checkpoints_passed,
                "checkpointsTotal": case.checkpoints_total,
                "simulationId": case.simulation_id,
            }
            for case in result.cases
        ],
        "metadata": {
            "evaluatedAt": datetime.now(timezone.utc).isoformat(),
            "memdVersion": memd_version,
            "metricsDisclaimer": (
                "Structural estimates only; not benchmark-equivalent compression."
            ),
        },
    }


def render_markdown(result: SimulationEvaluationResult) -> str:
    data = evaluation_result_to_dict(result)
    lines: List[str] = [
        "# Simulation Evaluation Benchmark",
        "",
        "Reproducible Mem-D simulation quality summary.",
        f"Generated from `{data['fixture']}`.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Overall structural accuracy | {data['overallStructuralAccuracy']:.4f} "
        f"({data['passedCheckpoints']}/{data['totalCheckpoints']}) |",
        f"| Safety passed | {data['safety']['passed']} |",
        f"| Gate passed | {data['gatePassed']} |",
        f"| Gold cases | {data['caseCount']} |",
        "",
        "## Per-Dimension Accuracy",
        "",
        "| Dimension | Accuracy | Passed | Total |",
        "| --- | ---: | ---: | ---: |",
    ]

    dimensions = [
        ("Merge projection", "mergeProjectionAccuracy", result.merge),
        ("Archive projection", "archiveProjectionAccuracy", result.archive),
        ("Review preservation", "reviewPreservationAccuracy", result.review),
        ("Warning", "warningAccuracy", result.warning),
        ("Orphan merge", "orphanMergeAccuracy", result.orphan),
        ("Explainability", "explainabilityAccuracy", result.explainability),
        ("Metric consistency", "metricConsistencyAccuracy", result.metric_consistency),
    ]
    for label, key, stats in dimensions:
        lines.append(
            f"| {label} | {data[key]:.4f} | {stats.passed} | {stats.total} |"
        )

    lines.extend(
        [
            "",
            "## Safety Properties",
            "",
            "| Property | Passed |",
            "| --- | --- |",
        ]
    )
    for prop in SAFETY_PROPERTIES:
        passed = result.safety.properties.get(prop, False)
        lines.append(f"| {prop} | {passed} |")

    lines.extend(
        [
            "",
            "## Diagnostic Distribution (non-gating)",
            "",
            "### Recommendation utilization",
            "",
            "| Case | Utilization | Outcome utilization |",
            "| --- | ---: | ---: |",
        ]
    )
    for entry in data["diagnostic"]["recommendationUtilizationDistribution"]:
        lines.append(
            f"| {entry['caseId']} | {entry['recommendationUtilizationRate']:.4f} | "
            f"{entry['recommendationOutcomeUtilizationRate']:.4f} |"
        )

    lines.extend(
        [
            "",
            "### Warning distribution",
            "",
            "| Code | Count |",
            "| --- | ---: |",
        ]
    )
    warning_dist = data["diagnostic"]["warningDistribution"]
    if warning_dist:
        for code, count in sorted(warning_dist.items()):
            lines.append(f"| {code} | {count} |")
    else:
        lines.append("| (none) | 0 |")

    lines.extend(
        [
            "",
            "## Regression Guards (non-gating)",
            "",
            "| Export | Passed | Notes |",
            "| --- | --- | --- |",
        ]
    )
    for export in ("longmemeval", "perma"):
        guard = data["regressionGuards"][export]
        passed_label = guard["passed"] if guard["passed"] is not None else "not run"
        lines.append(f"| {export} | {passed_label} | {guard['notes']} |")

    lines.extend(
        [
            "",
            "## Case Results",
            "",
            "| Case | Passed | Checkpoints | Simulation ID |",
            "| --- | --- | ---: | --- |",
        ]
    )
    for case in data["cases"]:
        lines.append(
            f"| {case['id']} | {case['passed']} | "
            f"{case['checkpointsPassed']}/{case['checkpointsTotal']} | "
            f"`{case['simulationId']}` |"
        )

    if data["failures"]:
        lines.extend(["", "## Failures", ""])
        for failure in data["failures"]:
            lines.append(
                f"- **{failure['caseId']}** / `{failure['checkpoint']}` "
                f"({failure['category']}): expected `{failure['expected']}`, "
                f"actual `{failure['actual']}`"
            )

    lines.extend(
        [
            "",
            "## Disclaimer",
            "",
            data["metadata"]["metricsDisclaimer"],
            "",
            "## Reproduce",
            "",
            "```bash",
            "python scripts/run_simulation_evaluation.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"
