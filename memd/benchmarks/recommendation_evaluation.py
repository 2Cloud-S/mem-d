from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Sequence

import json

from memd.contracts import (
    ActionPriority,
    ClusterTrustLevel,
    DuplicateCluster,
    GovernanceAction,
    MemoryRecord,
    PolicyDecision,
    PolicyProfile,
    RecommendationAction,
)
from memd.recommendations import plan_recommendations


# Resolve from repository root (../.. from memd/benchmarks/).
# This keeps the default fixture path stable for:
# - direct API use (evaluate_recommendations())
# - script execution from repo root
# - pytest execution
FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
GOLD_PATH = FIXTURES / "recommendation_gold.json"


@dataclass(frozen=True)
class PerActionStats:
    action: RecommendationAction
    correct: int
    total: int

    @property
    def accuracy(self) -> float:
        if self.total == 0:
            return 0.0
        return self.correct / self.total


@dataclass(frozen=True)
class ConflictStats:
    passed: int
    total: int

    @property
    def accuracy(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total


@dataclass(frozen=True)
class RecommendationEvaluationResult:
    overall_correct: int
    overall_total: int
    per_action: Dict[RecommendationAction, PerActionStats]
    conflict: ConflictStats
    resolution_distribution: Dict[RecommendationAction, int]
    case_count: int
    fixture_path: Path

    @property
    def overall_accuracy(self) -> float:
        if self.overall_total == 0:
            return 0.0
        return self.overall_correct / self.overall_total


def _load_gold_cases(path: Path) -> List[Mapping[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError("recommendation_gold.json must contain a list in `cases`")
    return [case for case in cases if isinstance(case, dict)]


def _to_memory_records(case: Mapping[str, Any]) -> List[MemoryRecord]:
    raw = case.get("memories", [])
    records: List[MemoryRecord] = []
    if not isinstance(raw, list):
        return records
    for item in raw:
        if not isinstance(item, dict):
            continue
        records.append(
            MemoryRecord(
                id=str(item["id"]),
                content=str(item["content"]),
                timestamp=str(item["timestamp"]) if item.get("timestamp") else None,
            )
        )
    return records


def _to_clusters(case: Mapping[str, Any]) -> List[DuplicateCluster]:
    raw = case.get("clusters", [])
    clusters: List[DuplicateCluster] = []
    if not isinstance(raw, list):
        return clusters
    for item in raw:
        if not isinstance(item, dict):
            continue
        clusters.append(
            DuplicateCluster(
                clusterId=str(item["clusterId"]),
                members=tuple(str(member) for member in item.get("members", [])),
                averageSimilarity=float(item.get("averageSimilarity", 0.0)),
                trustScore=float(item.get("trustScore", 0.0)),
                trustLevel=ClusterTrustLevel(str(item.get("trustLevel", "Low"))),
            )
        )
    return clusters


def _to_actions(case: Mapping[str, Any]) -> List[GovernanceAction]:
    raw = case.get("actions", [])
    actions: List[GovernanceAction] = []
    if not isinstance(raw, list):
        return actions
    for item in raw:
        if not isinstance(item, dict):
            continue
        trust = item.get("trustLevel")
        actions.append(
            GovernanceAction(
                actionId=str(item["actionId"]),
                actionType=str(item["actionType"]),
                target=dict(item.get("target", {})),
                title=str(item.get("title", item["actionId"])),
                rationale=str(item.get("rationale", "")),
                supportingEvidence=tuple(item.get("supportingEvidence", [])),
                trustLevel=ClusterTrustLevel(trust) if trust else None,
                confidence=float(item.get("confidence", 0.0)),
                estimatedImpact=str(item.get("estimatedImpact", "")),
                requiresHumanApproval=bool(item.get("requiresHumanApproval", True)),
                priority=ActionPriority(str(item.get("priority", "medium"))),
                sourceSignals=tuple(item.get("sourceSignals", ("test",))),
                policyDecision=PolicyDecision(str(item["policyDecision"]))
                if item.get("policyDecision")
                else None,
                policyProfile=PolicyProfile(str(item["policyProfile"]))
                if item.get("policyProfile")
                else None,
                policyRuleId=str(item.get("policyRuleId", "")),
                policyExplanation=str(item.get("policyExplanation", "")),
            )
        )
    return actions


def _resolution_map(
    memories: Sequence[MemoryRecord],
    clusters: Sequence[DuplicateCluster],
    validation: Mapping[str, Any],
    actions: Sequence[GovernanceAction],
    *,
    include_keep: bool,
) -> Dict[str, Any]:
    _recommendations, resolutions, _summary = plan_recommendations(
        memories=memories,
        clusters=clusters,
        validation=validation,
        insights=(),
        actions=actions,
        include_keep=include_keep,
    )
    return {resolution.memoryId: resolution for resolution in resolutions}


def _is_conflict_case(case: Mapping[str, Any]) -> bool:
    """
    Conflict coverage is intentionally scoped to explicitly conflict-labeled cases.

    This preserves stable historical metrics across fixture revisions and avoids
    broadening the conflict denominator implicitly from non-conflict action cases.
    """
    case_id = str(case.get("id", ""))
    if case_id.startswith("conflict_"):
        return True
    expected = case.get("expectedResolutions", {})
    if isinstance(expected, dict):
        for expectation in expected.values():
            if isinstance(expectation, dict) and expectation.get("conflictDetected"):
                return True
    return False


def evaluate_recommendations(gold_path: Path | None = None) -> RecommendationEvaluationResult:
    """
    Evaluate recommendation quality against the gold fixture.

    This is an evaluation-only helper. It does not modify recommendations or pipeline behavior.
    """
    path = gold_path or GOLD_PATH
    cases = _load_gold_cases(path)

    primary_actions = (
        RecommendationAction.MERGE,
        RecommendationAction.ARCHIVE,
        RecommendationAction.REVIEW,
        RecommendationAction.KEEP,
    )

    overall_correct = 0
    overall_total = 0

    per_action_correct: MutableMapping[RecommendationAction, int] = {
        action: 0 for action in primary_actions
    }
    per_action_total: MutableMapping[RecommendationAction, int] = {
        action: 0 for action in primary_actions
    }

    resolution_distribution: MutableMapping[RecommendationAction, int] = {
        action: 0 for action in primary_actions
    }

    conflict_total = 0
    conflict_passed = 0

    for case in cases:
        include_keep = bool(case.get("includeKeep", False))
        memories = _to_memory_records(case)
        clusters = _to_clusters(case)
        actions = _to_actions(case)
        validation = case.get("validation", {})
        if not isinstance(validation, dict):
            validation = {}

        resolutions = _resolution_map(
            memories,
            clusters,
            validation,
            actions,
            include_keep=include_keep,
        )

        # Update diagnostic distribution from predicted resolutions.
        for resolution in resolutions.values():
            if resolution.resolvedAction in resolution_distribution:
                resolution_distribution[resolution.resolvedAction] += 1

        expected = case.get("expectedResolutions", {})
        if not isinstance(expected, dict):
            continue

        case_conflict = _is_conflict_case(case)
        if case_conflict:
            conflict_total += 1
            case_passed = True
            evaluated_any = False
        else:
            case_passed = False  # irrelevant unless case_conflict is True

        for memory_id, expectation in expected.items():
            if not isinstance(expectation, dict):
                continue

            expected_action_raw = expectation.get("resolvedAction")
            expected_action = RecommendationAction(str(expected_action_raw))
            if expected_action not in per_action_total:
                raise ValueError(
                    f"Unexpected expected resolvedAction '{expected_action.value}' in "
                    f"{case.get('id')}:{memory_id}. Expected one of: "
                    f"{', '.join(action.value for action in per_action_total)}"
                )

            overall_total += 1
            per_action_total[expected_action] += 1

            resolution = resolutions.get(str(memory_id))
            if resolution is None:
                if case_conflict:
                    case_passed = False
                continue

            evaluated_any = True

            action_matches = resolution.resolvedAction == expected_action
            if action_matches:
                overall_correct += 1
                per_action_correct[expected_action] += 1
            else:
                if case_conflict:
                    case_passed = False

            expected_role = expectation.get("role")
            if isinstance(expected_role, str) and resolution.role != expected_role:
                if case_conflict:
                    case_passed = False

            if "conflictDetected" in expectation:
                expected_conflict_detected = bool(expectation.get("conflictDetected"))
                if resolution.conflictDetected != expected_conflict_detected:
                    if case_conflict:
                        case_passed = False

            if "suppressedActions" in expectation:
                expected_suppressed_actions = expectation.get("suppressedActions")
                if isinstance(expected_suppressed_actions, list):
                    expected_set = {
                        RecommendationAction(str(item))
                        for item in expected_suppressed_actions
                    }
                    actual_set = set(resolution.suppressedActions)
                    if expected_set != actual_set and case_conflict:
                        case_passed = False

        if case_conflict and case_passed and evaluated_any:
            conflict_passed += 1

    per_action_stats: Dict[RecommendationAction, PerActionStats] = {}
    for action in (
        RecommendationAction.MERGE,
        RecommendationAction.ARCHIVE,
        RecommendationAction.REVIEW,
        RecommendationAction.KEEP,
    ):
        per_action_stats[action] = PerActionStats(
            action=action,
            correct=per_action_correct.get(action, 0),
            total=per_action_total.get(action, 0),
        )

    conflict_stats = ConflictStats(passed=conflict_passed, total=conflict_total)

    return RecommendationEvaluationResult(
        overall_correct=overall_correct,
        overall_total=overall_total,
        per_action=per_action_stats,
        conflict=conflict_stats,
        resolution_distribution=dict(resolution_distribution),
        case_count=len(cases),
        fixture_path=path,
    )


def evaluation_result_to_dict(result: RecommendationEvaluationResult) -> Dict[str, Any]:
    return {
        "benchmark": "recommendation_evaluation",
        "fixture": str(result.fixture_path),
        "caseCount": result.case_count,
        "overallAccuracy": result.overall_accuracy,
        "correctResolutions": result.overall_correct,
        "totalResolutions": result.overall_total,
        "perActionAccuracy": {
            action.value: {
                "accuracy": stats.accuracy,
                "correct": stats.correct,
                "total": stats.total,
            }
            for action, stats in result.per_action.items()
        },
        "conflictResolutionAccuracy": result.conflict.accuracy,
        "passedConflictCases": result.conflict.passed,
        "totalConflictCases": result.conflict.total,
        "distribution": {
            "resolutions": {action.value: count for action, count in result.resolution_distribution.items()},
        },
    }


def render_markdown(result: RecommendationEvaluationResult) -> str:
    data = evaluation_result_to_dict(result)
    lines: List[str] = []
    lines.extend(
        [
            "# Recommendation Evaluation Benchmark",
            "",
            "Reproducible Mem-D recommendation quality summary.",
            f"Generated from `{data['fixture']}`.",
            "",
            "## Summary",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Overall accuracy | {data['overallAccuracy']:.4f} "
            f"({data['correctResolutions']}/{data['totalResolutions']}) |",
            f"| Conflict resolution accuracy | {data['conflictResolutionAccuracy']:.4f} "
            f"({data['passedConflictCases']}/{data['totalConflictCases']}) |",
            f"| Gold cases | {data['caseCount']} |",
            "",
            "## Per-Action Accuracy",
            "",
            "| Action | Accuracy | Correct | Total |",
            "| --- | ---: | ---: | ---: |",
        ]
    )

    per_action = data["perActionAccuracy"]
    for action in ("merge", "archive", "review", "keep"):
        stats = per_action.get(action, {"accuracy": 0.0, "correct": 0, "total": 0})
        lines.append(
            f"| {action} | {stats['accuracy']:.4f} | "
            f"{stats['correct']} | {stats['total']} |"
        )

    dist = data["distribution"]["resolutions"]
    lines.extend(
        [
            "",
            "## Resolution Distribution (diagnostic)",
            "",
            "| Action | Count |",
            "| --- | ---: |",
        ]
    )
    for action in ("merge", "archive", "review", "keep"):
        lines.append(f"| {action} | {dist.get(action, 0)} |")

    lines.extend(
        [
            "",
            "## Reproduce",
            "",
            "```bash",
            "python scripts/run_recommendation_evaluation.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"

