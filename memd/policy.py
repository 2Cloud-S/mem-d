from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from memd.contracts import (
    ActionType,
    ClusterTrustLevel,
    GovernanceAction,
    PolicyDecision,
    PolicyProfile,
    PolicySummary,
)


def apply_policy(
    actions: Sequence[GovernanceAction],
    profile: PolicyProfile = PolicyProfile.BALANCED,
) -> tuple[tuple[GovernanceAction, ...], PolicySummary]:
    decided = tuple(apply_policy_to_action(action, profile) for action in actions)
    return decided, summarize_policy(decided, profile)


def apply_policy_to_action(
    action: GovernanceAction,
    profile: PolicyProfile,
) -> GovernanceAction:
    decision, rule_id, explanation = evaluate_action(action, profile)
    return action.model_copy(
        update={
            "policyDecision": decision,
            "policyProfile": profile,
            "policyRuleId": rule_id,
            "policyExplanation": explanation,
        }
    )


def evaluate_action(
    action: GovernanceAction,
    profile: PolicyProfile,
) -> tuple[PolicyDecision, str, str]:
    if profile == PolicyProfile.CONSERVATIVE:
        return conservative_decision(action)
    if profile == PolicyProfile.AGGRESSIVE:
        return aggressive_decision(action)
    return balanced_decision(action)


def conservative_decision(action: GovernanceAction) -> tuple[PolicyDecision, str, str]:
    if action.actionType == ActionType.IGNORE_LOW_VALUE_ISSUE:
        return (
            PolicyDecision.APPROVED,
            "conservative.defer-low-value",
            "Low-value informational items can be automatically deferred.",
        )
    if is_overclustered_or_low_trust(action):
        return (
            PolicyDecision.BLOCKED,
            "conservative.block-low-trust-or-overclustered",
            "Conservative policy blocks low-trust or over-clustered recommendations.",
        )
    if is_safe_merge(action) and action.confidence >= 0.9:
        return (
            PolicyDecision.APPROVED,
            "conservative.approve-high-confidence-merge",
            "High-trust merge action meets conservative confidence requirements.",
        )
    return (
        PolicyDecision.REQUIRES_REVIEW,
        "conservative.default-review",
        "Conservative policy requires human review unless an action is clearly safe.",
    )


def balanced_decision(action: GovernanceAction) -> tuple[PolicyDecision, str, str]:
    if action.actionType == ActionType.IGNORE_LOW_VALUE_ISSUE:
        return (
            PolicyDecision.APPROVED,
            "balanced.defer-low-value",
            "Low-value informational items can be automatically deferred.",
        )
    if is_overclustered_or_low_trust(action):
        return (
            PolicyDecision.BLOCKED,
            "balanced.block-low-trust-or-overclustered",
            "Balanced policy blocks low-trust or over-clustered recommendations.",
        )
    if is_safe_merge(action) and action.confidence >= 0.8:
        return (
            PolicyDecision.APPROVED,
            "balanced.approve-high-trust-safe-action",
            "High-trust action meets balanced automatic approval requirements.",
        )
    return (
        PolicyDecision.REQUIRES_REVIEW,
        "balanced.default-review",
        "Balanced policy requires review for non-safe or uncertain governance actions.",
    )


def aggressive_decision(action: GovernanceAction) -> tuple[PolicyDecision, str, str]:
    if action.actionType == ActionType.IGNORE_LOW_VALUE_ISSUE:
        return (
            PolicyDecision.APPROVED,
            "aggressive.defer-low-value",
            "Low-value informational items can be automatically deferred.",
        )
    if (
        action.actionType == ActionType.REVIEW_OVERCLUSTERED_GROUP
        and action.trustLevel == ClusterTrustLevel.LOW
    ):
        return (
            PolicyDecision.BLOCKED,
            "aggressive.block-low-trust-overclustered",
            "Aggressive policy still blocks low-trust over-clustered groups.",
        )
    if is_safe_merge(action) and action.confidence >= 0.7:
        return (
            PolicyDecision.APPROVED,
            "aggressive.approve-safe-action",
            "High-trust safe action meets aggressive approval requirements.",
        )
    return (
        PolicyDecision.REQUIRES_REVIEW,
        "aggressive.default-review",
        "Aggressive policy still routes uncertain, taxonomy, and unknown-memory actions to review.",
    )


def summarize_policy(
    actions: Sequence[GovernanceAction],
    profile: PolicyProfile,
) -> PolicySummary:
    decision_counts = Counter(
        action.policyDecision
        for action in actions
        if action.policyDecision is not None
    )
    rule_counts = Counter(action.policyRuleId for action in actions if action.policyRuleId)
    return PolicySummary(
        profile=profile,
        totalDecisions=len(actions),
        approvedActions=decision_counts.get(PolicyDecision.APPROVED, 0),
        reviewRequiredActions=decision_counts.get(PolicyDecision.REQUIRES_REVIEW, 0),
        blockedActions=decision_counts.get(PolicyDecision.BLOCKED, 0),
        decisionsByType={
            decision: decision_counts.get(decision, 0)
            for decision in PolicyDecision
        },
        matchedRules=dict(rule_counts),
    )


def is_safe_merge(action: GovernanceAction) -> bool:
    return (
        action.actionType in {ActionType.MERGE_CLUSTER, ActionType.CONSOLIDATE_PREFERENCES}
        and not action.requiresHumanApproval
        and action.trustLevel == ClusterTrustLevel.HIGH
    )


def is_overclustered_or_low_trust(action: GovernanceAction) -> bool:
    return (
        action.actionType == ActionType.REVIEW_OVERCLUSTERED_GROUP
        or action.trustLevel == ClusterTrustLevel.LOW
    )
