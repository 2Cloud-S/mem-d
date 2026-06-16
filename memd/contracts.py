from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MemoryCategory(StrEnum):
    PREFERENCE = "Preference"
    FACT = "Fact"
    TASK = "Task"
    GOAL = "Goal"
    RELATIONSHIP = "Relationship"
    TEMPORARY = "Temporary"
    UNKNOWN = "Unknown"


class InsightSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ClusterTrustLevel(StrEnum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class ActionType(StrEnum):
    MERGE_CLUSTER = "merge_cluster"
    REVIEW_CLUSTER = "review_cluster"
    REVIEW_CATEGORY_CONFLICT = "review_category_conflict"
    REVIEW_UNKNOWN_MEMORY = "review_unknown_memory"
    CONSOLIDATE_PREFERENCES = "consolidate_preferences"
    REVIEW_OVERCLUSTERED_GROUP = "review_overclustered_group"
    IGNORE_LOW_VALUE_ISSUE = "ignore_low_value_issue"


class ActionPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    DEFERRED = "deferred"


class PolicyProfile(StrEnum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


class PolicyDecision(StrEnum):
    APPROVED = "approved"
    REQUIRES_REVIEW = "requires_review"
    BLOCKED = "blocked"


class RecommendationAction(StrEnum):
    MERGE = "merge"
    ARCHIVE = "archive"
    REVIEW = "review"
    KEEP = "keep"
    DEFER = "defer"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class MemoryRecord(FrozenModel):
    id: str
    content: str
    source: str | None = None
    timestamp: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", "content")
    @classmethod
    def require_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value


class CategorizedMemory(FrozenModel):
    memoryId: str
    category: MemoryCategory
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""
    matchedSignals: tuple[str, ...] = ()


class EmbeddedMemory(FrozenModel):
    memoryId: str
    embedding: tuple[float, ...]


class SimilarityRecord(FrozenModel):
    memoryA: str
    memoryB: str
    similarity: float = Field(ge=0.0, le=1.0)


class DuplicateCluster(FrozenModel):
    clusterId: str
    members: tuple[str, ...]
    averageSimilarity: float = Field(ge=0.0, le=1.0)
    sharedTerms: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    trustScore: float = Field(default=0.0, ge=0.0, le=1.0)
    trustLevel: ClusterTrustLevel = ClusterTrustLevel.LOW
    trustReasons: tuple[str, ...] = ()
    recommendedAction: str = "Manual review required"


class AnalysisMetrics(FrozenModel):
    totalMemories: int = Field(ge=0)
    duplicateCount: int = Field(ge=0)
    duplicatePercentage: float = Field(ge=0.0, le=100.0)
    compressionOpportunity: float = Field(ge=0.0, le=100.0)
    trustedDuplicateCount: int = Field(default=0, ge=0)
    unverifiedDuplicateCount: int = Field(default=0, ge=0)
    trustedCompressionOpportunity: float = Field(default=0.0, ge=0.0, le=100.0)
    unverifiedCompressionOpportunity: float = Field(default=0.0, ge=0.0, le=100.0)
    categoryAgreementRate: float = Field(default=100.0, ge=0.0, le=100.0)
    reclassificationOpportunityCount: int = Field(default=0, ge=0)
    categoryBreakdown: dict[MemoryCategory, int]
    compressionReasons: tuple[str, ...] = ()


class Insight(FrozenModel):
    id: str
    title: str
    severity: InsightSeverity
    explanation: str
    supportingEvidence: tuple[str, ...]
    confidence: float = Field(ge=0.0, le=1.0)
    estimatedImpact: str
    recommendedAction: str


class GovernanceAction(FrozenModel):
    actionId: str
    actionType: ActionType
    target: dict[str, Any]
    title: str
    rationale: str
    supportingEvidence: tuple[str, ...]
    trustLevel: ClusterTrustLevel | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    estimatedImpact: str
    requiresHumanApproval: bool
    priority: ActionPriority
    sourceSignals: tuple[str, ...]
    policyDecision: PolicyDecision | None = None
    policyProfile: PolicyProfile | None = None
    policyRuleId: str = ""
    policyExplanation: str = ""


class ActionPlanSummary(FrozenModel):
    totalActions: int = Field(ge=0)
    safeActions: int = Field(ge=0)
    reviewActions: int = Field(ge=0)
    estimatedTrustedSavings: int = Field(ge=0)
    estimatedUnverifiedSavings: int = Field(ge=0)
    actionsByPriority: dict[ActionPriority, int]


class PolicySummary(FrozenModel):
    profile: PolicyProfile = PolicyProfile.BALANCED
    totalDecisions: int = Field(default=0, ge=0)
    approvedActions: int = Field(default=0, ge=0)
    reviewRequiredActions: int = Field(default=0, ge=0)
    blockedActions: int = Field(default=0, ge=0)
    decisionsByType: dict[PolicyDecision, int] = Field(default_factory=dict)
    matchedRules: dict[str, int] = Field(default_factory=dict)


class AnalysisReport(FrozenModel):
    metrics: AnalysisMetrics
    clusters: tuple[DuplicateCluster, ...]
    memories: tuple[MemoryRecord, ...] = ()
    categories: tuple[CategorizedMemory, ...] = ()
    validation: dict[str, Any] = Field(default_factory=dict)
    insights: tuple[Insight, ...] = ()
    actions: tuple[GovernanceAction, ...] = ()
    actionSummary: ActionPlanSummary = Field(
        default_factory=lambda: ActionPlanSummary(
            totalActions=0,
            safeActions=0,
            reviewActions=0,
            estimatedTrustedSavings=0,
            estimatedUnverifiedSavings=0,
            actionsByPriority={priority: 0 for priority in ActionPriority},
        )
    )
    policySummary: PolicySummary = Field(default_factory=PolicySummary)


class RecommendationEvidence(FrozenModel):
    source: str
    signal: str
    value: float | str | None = None
    caseId: str = ""
    ruleId: str = ""
    actionId: str = ""
    insightId: str = ""


class AffectedMemory(FrozenModel):
    memoryId: str
    role: str
    lifecycleState: str = ""


class Recommendation(FrozenModel):
    recommendationId: str
    action: RecommendationAction
    subtype: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    affected_memories: tuple[AffectedMemory, ...]
    evidence: tuple[RecommendationEvidence, ...]
    estimatedImpact: dict[str, Any] = Field(default_factory=dict)
    priority: ActionPriority
    requiresHumanApproval: bool
    sourceActionIds: tuple[str, ...] = ()
    sourceInsightIds: tuple[str, ...] = ()
    suppressedCandidates: tuple[dict[str, Any], ...] = ()
    conflictDetected: bool = False


class MemoryResolution(FrozenModel):
    memoryId: str
    resolvedAction: RecommendationAction
    role: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    recommendationId: str
    suppressedActions: tuple[RecommendationAction, ...] = ()
    conflictDetected: bool = False


class RecommendationSummary(FrozenModel):
    totalRecommendations: int = Field(default=0, ge=0)
    mergeCount: int = Field(default=0, ge=0)
    archiveCount: int = Field(default=0, ge=0)
    reviewCount: int = Field(default=0, ge=0)
    keepCount: int = Field(default=0, ge=0)
    deferredCount: int = Field(default=0, ge=0)
    memoryResolutionCount: int = Field(default=0, ge=0)
    estimatedTrustedRemovals: int = Field(default=0, ge=0)
    estimatedArchivableRecords: int = Field(default=0, ge=0)
    recommendationsByPriority: dict[ActionPriority, int] = Field(
        default_factory=lambda: {priority: 0 for priority in ActionPriority}
    )
