from memd.contracts import (
    ActionPriority,
    ActionType,
    ClusterTrustLevel,
    GovernanceAction,
    PolicyDecision,
    PolicyProfile,
)
from memd.policy import apply_policy


def test_balanced_policy_approves_high_trust_safe_action() -> None:
    actions, summary = apply_policy(
        (safe_merge_action(confidence=0.85),),
        PolicyProfile.BALANCED,
    )

    assert actions[0].policyDecision == PolicyDecision.APPROVED
    assert actions[0].policyRuleId == "balanced.approve-high-trust-safe-action"
    assert actions[0].policyExplanation
    assert summary.approvedActions == 1


def test_conservative_policy_requires_review_for_lower_confidence_safe_action() -> None:
    actions, summary = apply_policy(
        (safe_merge_action(confidence=0.85),),
        PolicyProfile.CONSERVATIVE,
    )

    assert actions[0].policyDecision == PolicyDecision.REQUIRES_REVIEW
    assert actions[0].policyRuleId == "conservative.default-review"
    assert summary.reviewRequiredActions == 1


def test_policy_blocks_low_trust_or_overclustered_action() -> None:
    actions, summary = apply_policy(
        (low_trust_review_action(),),
        PolicyProfile.BALANCED,
    )

    assert actions[0].policyDecision == PolicyDecision.BLOCKED
    assert actions[0].policyRuleId == "balanced.block-low-trust-or-overclustered"
    assert summary.blockedActions == 1


def test_aggressive_policy_approves_lower_confidence_safe_action() -> None:
    actions, summary = apply_policy(
        (safe_merge_action(confidence=0.75),),
        PolicyProfile.AGGRESSIVE,
    )

    assert actions[0].policyDecision == PolicyDecision.APPROVED
    assert actions[0].policyRuleId == "aggressive.approve-safe-action"
    assert summary.approvedActions == 1


def test_policy_routes_taxonomy_review_to_human_review() -> None:
    actions, summary = apply_policy(
        (taxonomy_review_action(),),
        PolicyProfile.BALANCED,
    )

    assert actions[0].policyDecision == PolicyDecision.REQUIRES_REVIEW
    assert actions[0].policyRuleId == "balanced.default-review"
    assert summary.reviewRequiredActions == 1


def safe_merge_action(confidence: float) -> GovernanceAction:
    return GovernanceAction(
        actionId="merge_cluster:cluster-1",
        actionType=ActionType.MERGE_CLUSTER,
        target={"clusterId": "cluster_1", "removableRecords": 1},
        title="Consolidate high-trust duplicate cluster cluster_1",
        rationale="High-trust duplicate cluster.",
        supportingEvidence=("trust level=High",),
        trustLevel=ClusterTrustLevel.HIGH,
        confidence=confidence,
        estimatedImpact="May safely remove 1 duplicate record.",
        requiresHumanApproval=False,
        priority=ActionPriority.HIGH,
        sourceSignals=("cluster_trust",),
    )


def low_trust_review_action() -> GovernanceAction:
    return GovernanceAction(
        actionId="review_cluster:cluster-1",
        actionType=ActionType.REVIEW_CLUSTER,
        target={"clusterId": "cluster_1", "removableRecords": 2},
        title="Review duplicate cluster cluster_1 before consolidation",
        rationale="Low-trust cluster.",
        supportingEvidence=("trust level=Low",),
        trustLevel=ClusterTrustLevel.LOW,
        confidence=0.3,
        estimatedImpact="Could save 2 records if validated.",
        requiresHumanApproval=True,
        priority=ActionPriority.HIGH,
        sourceSignals=("cluster_trust",),
    )


def taxonomy_review_action() -> GovernanceAction:
    return GovernanceAction(
        actionId="review_category_conflict:cluster-1",
        actionType=ActionType.REVIEW_CATEGORY_CONFLICT,
        target={"clusterId": "cluster_1"},
        title="Review category disagreement in cluster_1",
        rationale="Category conflict.",
        supportingEvidence=("category agreement rate=66.67%",),
        confidence=0.88,
        estimatedImpact="Review 1 possible category correction.",
        requiresHumanApproval=True,
        priority=ActionPriority.HIGH,
        sourceSignals=("category_consistency",),
    )
