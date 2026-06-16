from __future__ import annotations

import json
from pathlib import Path

from memd.contracts import (
    ActionPriority,
    ActionType,
    CategorizedMemory,
    ClusterTrustLevel,
    DuplicateCluster,
    GovernanceAction,
    MemoryCategory,
    MemoryRecord,
    PolicyDecision,
    PolicyProfile,
    RecommendationAction,
)
from memd.memory_evolution import audit_memory_evolution
from memd.memory_lifecycle import infer_memory_lifecycle
from memd.recommendations import (
    ARCHIVE_MIN_CONFIDENCE,
    MERGE_MIN_CONFIDENCE,
    RecommendationCandidate,
    conflict_matrix,
    plan_recommendations,
)

FIXTURES = Path(__file__).parent / "fixtures"
GOLD_PATH = FIXTURES / "recommendation_gold.json"


def load_gold_cases() -> list[dict[str, object]]:
    payload = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    cases = payload.get("cases", [])
    assert isinstance(cases, list)
    return [case for case in cases if isinstance(case, dict)]


def to_memory_records(case: dict[str, object]) -> list[MemoryRecord]:
    raw = case.get("memories", [])
    records: list[MemoryRecord] = []
    if not isinstance(raw, list):
        return records
    for item in raw:
        if isinstance(item, dict):
            records.append(
                MemoryRecord(
                    id=str(item["id"]),
                    content=str(item["content"]),
                    timestamp=str(item["timestamp"]) if item.get("timestamp") else None,
                )
            )
    return records


def to_clusters(case: dict[str, object]) -> list[DuplicateCluster]:
    raw = case.get("clusters", [])
    clusters: list[DuplicateCluster] = []
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


def to_actions(case: dict[str, object]) -> list[GovernanceAction]:
    raw = case.get("actions", [])
    actions: list[GovernanceAction] = []
    if not isinstance(raw, list):
        return actions
    for item in raw:
        if not isinstance(item, dict):
            continue
        trust = item.get("trustLevel")
        actions.append(
            GovernanceAction(
                actionId=str(item["actionId"]),
                actionType=ActionType(str(item["actionType"])),
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


def resolution_map(
    memories: list[MemoryRecord],
    clusters: list[DuplicateCluster],
    validation: dict[str, object],
    actions: list[GovernanceAction],
    *,
    include_keep: bool = False,
) -> dict[str, object]:
    _recommendations, resolutions, _summary = plan_recommendations(
        memories=memories,
        clusters=clusters,
        validation=validation,
        insights=(),
        actions=actions,
        include_keep=include_keep,
    )
    return {resolution.memoryId: resolution for resolution in resolutions}


def test_conflict_matrix_documented_pairs() -> None:
    review_candidate = RecommendationCandidate(
        action=RecommendationAction.REVIEW, confidence=0.85, role="review"
    )
    keep_candidate = RecommendationCandidate(
        action=RecommendationAction.KEEP, confidence=0.96, role="retain"
    )
    archive_candidate = RecommendationCandidate(
        action=RecommendationAction.ARCHIVE, confidence=0.89, role="archive_candidate"
    )
    merge_candidate = RecommendationCandidate(
        action=RecommendationAction.MERGE, confidence=0.93, role="removable"
    )

    assert (
        conflict_matrix(
            RecommendationAction.KEEP,
            RecommendationAction.REVIEW,
            keep_candidate,
            review_candidate,
        )
        == RecommendationAction.REVIEW
    )
    assert (
        conflict_matrix(
            RecommendationAction.KEEP,
            RecommendationAction.ARCHIVE,
            keep_candidate,
            archive_candidate,
        )
        == RecommendationAction.ARCHIVE
    )
    assert (
        conflict_matrix(
            RecommendationAction.ARCHIVE,
            RecommendationAction.MERGE,
            archive_candidate,
            merge_candidate,
        )
        == RecommendationAction.REVIEW
    )
    assert (
        conflict_matrix(
            RecommendationAction.MERGE,
            RecommendationAction.REVIEW,
            merge_candidate,
            review_candidate,
        )
        == RecommendationAction.REVIEW
    )


def test_keep_plus_archive_below_threshold_becomes_review() -> None:
    keep_candidate = RecommendationCandidate(
        action=RecommendationAction.KEEP, confidence=0.96, role="retain"
    )
    archive_candidate = RecommendationCandidate(
        action=RecommendationAction.ARCHIVE,
        confidence=ARCHIVE_MIN_CONFIDENCE - 0.05,
        role="archive_candidate",
    )
    assert (
        conflict_matrix(
            RecommendationAction.KEEP,
            RecommendationAction.ARCHIVE,
            keep_candidate,
            archive_candidate,
        )
        == RecommendationAction.REVIEW
    )


def test_plan_recommendations_is_deterministic() -> None:
    case = next(item for item in load_gold_cases() if item["id"] == "trusted_merge_1")
    memories = to_memory_records(case)
    clusters = to_clusters(case)
    actions = to_actions(case)
    validation = dict(case.get("validation", {}))  # type: ignore[arg-type]

    first = plan_recommendations(memories, clusters, validation, (), actions)
    second = plan_recommendations(memories, clusters, validation, (), actions)
    assert first == second


def test_trusted_merge_generates_merge_recommendation() -> None:
    case = next(item for item in load_gold_cases() if item["id"] == "trusted_merge_1")
    memories = to_memory_records(case)
    clusters = to_clusters(case)
    actions = to_actions(case)
    validation = dict(case.get("validation", {}))  # type: ignore[arg-type]

    recommendations, resolutions, summary = plan_recommendations(
        memories, clusters, validation, (), actions
    )
    merge_recs = [item for item in recommendations if item.action == RecommendationAction.MERGE]
    assert len(merge_recs) == 1
    assert merge_recs[0].confidence >= MERGE_MIN_CONFIDENCE
    assert len(merge_recs[0].evidence) >= 2
    assert summary.mergeCount == 1
    assert all(resolution.resolvedAction == RecommendationAction.MERGE for resolution in resolutions)


def test_policy_blocked_merge_becomes_review() -> None:
    case = next(item for item in load_gold_cases() if item["id"] == "review_policy_blocked_merge")
    resolutions = resolution_map(
        to_memory_records(case),
        to_clusters(case),
        dict(case.get("validation", {})),  # type: ignore[arg-type]
        to_actions(case),
    )
    assert resolutions["pb_a"].resolvedAction == RecommendationAction.REVIEW
    assert resolutions["pb_b"].resolvedAction == RecommendationAction.REVIEW
    recommendations = plan_recommendations(
        to_memory_records(case),
        to_clusters(case),
        dict(case.get("validation", {})),  # type: ignore[arg-type]
        (),
        to_actions(case),
    )[0]
    review = next(item for item in recommendations if item.action == RecommendationAction.REVIEW)
    assert any(evidence.source == "policy" for evidence in review.evidence)


def test_archive_merge_conflict_escalates_to_review() -> None:
    case = next(item for item in load_gold_cases() if item["id"] == "conflict_archive_merge")
    resolutions = resolution_map(
        to_memory_records(case),
        to_clusters(case),
        dict(case.get("validation", {})),  # type: ignore[arg-type]
        to_actions(case),
    )
    assert resolutions["la_p1_old"].resolvedAction == RecommendationAction.REVIEW
    assert resolutions["la_p1_old"].conflictDetected is True
    assert RecommendationAction.ARCHIVE in resolutions["la_p1_old"].suppressedActions
    assert RecommendationAction.MERGE in resolutions["la_p1_old"].suppressedActions
    assert resolutions["la_p1_new"].resolvedAction == RecommendationAction.MERGE
    assert resolutions["la_p1_new"].role == "keeper"


def test_active_plus_unknown_becomes_review() -> None:
    case = next(item for item in load_gold_cases() if item["id"] == "review_unknown_category")
    resolutions = resolution_map(
        to_memory_records(case),
        to_clusters(case),
        dict(case.get("validation", {})),  # type: ignore[arg-type]
        to_actions(case),
        include_keep=True,
    )
    assert resolutions["lme_442"].resolvedAction == RecommendationAction.REVIEW
    assert RecommendationAction.KEEP in resolutions["lme_442"].suppressedActions


def test_include_keep_emits_keep_recommendation() -> None:
    case = next(item for item in load_gold_cases() if item["id"] == "keep_active_stable")
    recommendations, resolution_list, summary = plan_recommendations(
        to_memory_records(case),
        to_clusters(case),
        dict(case.get("validation", {})),  # type: ignore[arg-type]
        (),
        to_actions(case),
        include_keep=True,
    )
    resolutions = {item.memoryId: item for item in resolution_list}
    assert resolutions["mem_99"].resolvedAction == RecommendationAction.KEEP
    assert any(item.action == RecommendationAction.KEEP for item in recommendations)
    assert summary.keepCount == 1


def test_recommendation_gold_fixture_expected_resolutions() -> None:
    failures: list[str] = []
    for case in load_gold_cases():
        case_id = str(case["id"])
        include_keep = bool(case.get("includeKeep", False))
        resolutions = resolution_map(
            to_memory_records(case),
            to_clusters(case),
            dict(case.get("validation", {})),  # type: ignore[arg-type]
            to_actions(case),
            include_keep=include_keep,
        )
        expected = case.get("expectedResolutions", {})
        if not isinstance(expected, dict):
            failures.append(f"{case_id}: invalid expectedResolutions")
            continue
        for memory_id, expectation in expected.items():
            if not isinstance(expectation, dict):
                continue
            resolution = resolutions.get(str(memory_id))
            if resolution is None:
                failures.append(f"{case_id}:{memory_id} missing resolution")
                continue
            expected_action = expectation.get("resolvedAction")
            if resolution.resolvedAction.value != expected_action:
                failures.append(
                    f"{case_id}:{memory_id} expected {expected_action}, "
                    f"got {resolution.resolvedAction.value}"
                )
            expected_role = expectation.get("role")
            if expected_role and resolution.role != expected_role:
                failures.append(
                    f"{case_id}:{memory_id} expected role {expected_role}, got {resolution.role}"
                )
            if expectation.get("conflictDetected") and not resolution.conflictDetected:
                failures.append(f"{case_id}:{memory_id} expected conflictDetected")
    assert not failures, "\n".join(failures)


def test_lifecycle_pipeline_integration_for_archive_case() -> None:
    lifecycle_case = json.loads((FIXTURES / "lifecycle_gold.json").read_text(encoding="utf-8"))
    case = next(item for item in lifecycle_case["cases"] if item["id"] == "superseded_active_1")
    records = [
        MemoryRecord(
            id=str(item["id"]),
            content=str(item["content"]),
            timestamp=str(item.get("timestamp")),
        )
        for item in case["memories"]
    ]
    categories = [
        CategorizedMemory(
            memoryId=str(item["id"]),
            category=MemoryCategory(str(item.get("category", "Fact"))),
            confidence=0.9,
        )
        for item in case["memories"]
    ]
    evolution = audit_memory_evolution(records, categories)
    lifecycle = infer_memory_lifecycle(evolution)
    validation = {"memoryLifecycle": lifecycle, "memoryEvolutionAudit": evolution}
    resolutions = resolution_map(records, [], validation, [], include_keep=True)
    assert resolutions["la_s1_old"].resolvedAction == RecommendationAction.ARCHIVE
    assert resolutions["la_s1_new"].resolvedAction == RecommendationAction.KEEP


def test_summary_counts_match_recommendations() -> None:
    case = next(item for item in load_gold_cases() if item["id"] == "conflict_archive_merge")
    recommendations, _resolutions, summary = plan_recommendations(
        to_memory_records(case),
        to_clusters(case),
        dict(case.get("validation", {})),  # type: ignore[arg-type]
        (),
        to_actions(case),
    )
    assert summary.totalRecommendations == len(recommendations)
    assert summary.memoryResolutionCount == len(to_memory_records(case))
