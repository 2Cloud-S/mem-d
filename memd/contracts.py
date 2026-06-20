from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class PlannerItemStatus(StrEnum):
    PROPOSED = "proposed"
    REQUIRES_REVIEW = "requires_review"
    BLOCKED = "blocked"
    DEFERRED = "deferred"


class OperatorItemStatus(StrEnum):
    NONE = "none"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class PlanAggregateStatus(StrEnum):
    INTEGRITY_BLOCKED = "integrity_blocked"
    EMPTY = "empty"
    ALL_KEEP = "all_keep"
    ALL_BLOCKED = "all_blocked"
    MIXED_BLOCKED = "mixed_blocked"
    MIXED_BLOCKED_REVIEW = "mixed_blocked_review"
    REQUIRES_REVIEW = "requires_review"
    PARTIALLY_APPROVED = "partially_approved"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    READY_FOR_EXECUTION = "ready_for_execution"
    PROPOSED = "proposed"


class WorkflowPlannerStatus(StrEnum):
    INITIAL = "initial"
    DECIDED = "decided"


class WorkflowPlanningMode(StrEnum):
    FULL = "full"
    RECOMMENDATIONS_ONLY = "recommendations_only"


class WorkflowStepType(StrEnum):
    REVIEW = "review"
    ARCHIVE = "archive"
    MERGE = "merge"
    RETAIN = "retain"
    HANDOFF = "handoff"


class WorkflowBlockerCode(StrEnum):
    INPUT_INTEGRITY = "INPUT_INTEGRITY"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    ORPHAN_MERGE_NO_KEEPER = "ORPHAN_MERGE_NO_KEEPER"
    DUPLICATE_REMOVAL_SKIPPED = "DUPLICATE_REMOVAL_SKIPPED"
    MISSING_SIMULATION = "MISSING_SIMULATION"
    MISSING_KEEPER = "MISSING_KEEPER"
    UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"
    STALE_EVIDENCE = "STALE_EVIDENCE"


class ReviewSubtype(StrEnum):
    GENERAL = "general"
    POLICY = "policy"
    POLICY_BLOCKED = "policy_blocked"
    UNKNOWN_CATEGORY = "unknown_category"
    LIFECYCLE = "lifecycle"
    LIFECYCLE_ALTERNATE = "lifecycle_alternate"
    LIFECYCLE_MIXED = "lifecycle_mixed"
    LOW_TRUST = "low_trust"
    CONFLICT = "conflict"
    SIMULATION_SAFETY = "simulation_safety"
    ORPHAN_MERGE_DOWNGRADE = "orphan_merge_downgrade"


class ReviewQueueId(StrEnum):
    SIMULATION_SAFETY = "review:simulation_safety"
    CONFLICT = "review:conflict"
    POLICY = "review:policy"
    UNKNOWN_CATEGORY = "review:unknown_category"
    LIFECYCLE = "review:lifecycle"
    LOW_TRUST = "review:low_trust"
    GENERAL = "review:general"


class ApprovalDecisionType(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"


SIMULATION_REF_PREFIXES: tuple[str, ...] = ("merge:", "archive:", "review:", "warning:")


def _normalize_optional_operation_id(value: str) -> str:
    if not value:
        return ""
    stripped = value.strip()
    if not stripped:
        raise ValueError("operation ID must not be whitespace-only")
    return stripped


def _normalize_operation_id_tuple(value: tuple[str, ...]) -> tuple[str, ...]:
    if not value:
        return ()
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        stripped = item.strip()
        if not stripped:
            raise ValueError("operation ID must not be empty or whitespace-only")
        if stripped in seen:
            raise ValueError("operation IDs must be unique after normalization")
        seen.add(stripped)
        normalized.append(stripped)
    return tuple(normalized)


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


class PlanningOptions(FrozenModel):
    includeKeep: bool = False


class MemoryRoleAssignment(FrozenModel):
    memoryId: str
    role: str

    @field_validator("memoryId", "role")
    @classmethod
    def require_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value


class ReviewRequirement(FrozenModel):
    required: bool
    reason: str = ""
    subtypes: tuple[ReviewSubtype, ...] = ()
    primaryQueueId: ReviewQueueId | None = None
    queueRefs: tuple[ReviewQueueId, ...] = ()
    escalationSignals: tuple[str, ...] = ()

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_required_shape(self) -> ReviewRequirement:
        unique_subtypes = tuple(dict.fromkeys(self.subtypes))
        unique_queues = tuple(dict.fromkeys(self.queueRefs))
        if len(unique_subtypes) != len(self.subtypes):
            raise ValueError("subtypes must not contain duplicates")
        if len(unique_queues) != len(self.queueRefs):
            raise ValueError("queueRefs must not contain duplicates")
        if self.required:
            if not self.reason:
                raise ValueError("reason is required when required is true")
            if not self.subtypes:
                raise ValueError("subtypes must be non-empty when required is true")
            if not self.queueRefs:
                raise ValueError("queueRefs must be non-empty when required is true")
            if self.primaryQueueId is None:
                raise ValueError("primaryQueueId is required when required is true")
            if self.primaryQueueId not in self.queueRefs:
                raise ValueError("primaryQueueId must be present in queueRefs")
        else:
            if self.subtypes:
                raise ValueError("subtypes must be empty when required is false")
            if self.primaryQueueId is not None:
                raise ValueError("primaryQueueId must be None when required is false")
            if self.queueRefs:
                raise ValueError("queueRefs must be empty when required is false")
            if self.escalationSignals:
                raise ValueError("escalationSignals must be empty when required is false")
        return self


class ApprovalDecision(FrozenModel):
    targetType: Literal["workflow_item"]
    targetId: str
    decision: ApprovalDecisionType
    rationale: str = ""
    decidedBy: str | None = None

    @field_validator("targetId")
    @classmethod
    def require_target_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("targetId must not be empty")
        return value


class WorkflowBlocker(FrozenModel):
    blockerId: str
    code: WorkflowBlockerCode
    message: str
    sourceLayer: str
    memoryId: str = ""
    recommendationId: str = ""
    overridable: bool

    @field_validator("blockerId", "message", "sourceLayer")
    @classmethod
    def require_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @model_validator(mode="after")
    def validate_non_overridable_codes(self) -> WorkflowBlocker:
        always_non_overridable = {
            WorkflowBlockerCode.INPUT_INTEGRITY,
            WorkflowBlockerCode.POLICY_BLOCKED,
            WorkflowBlockerCode.ORPHAN_MERGE_NO_KEEPER,
            WorkflowBlockerCode.DUPLICATE_REMOVAL_SKIPPED,
        }
        if self.code in always_non_overridable and self.overridable:
            raise ValueError(f"{self.code.value} must be non-overridable")
        return self


class WorkflowEvidence(FrozenModel):
    recommendationIds: tuple[str, ...] = ()
    memoryIds: tuple[str, ...] = ()
    actionIds: tuple[str, ...] = ()
    insightIds: tuple[str, ...] = ()
    simulationEventIds: tuple[str, ...] = ()
    validationRefs: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class WorkflowStepOperation(FrozenModel):
    stepType: WorkflowStepType
    keeperId: str = ""
    removableIds: tuple[str, ...] = ()
    archiveTargetIds: tuple[str, ...] = ()
    reviewTargetIds: tuple[str, ...] = ()
    recommendationIds: tuple[str, ...] = ()

    @field_validator("keeperId", mode="before")
    @classmethod
    def normalize_keeper_id(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return _normalize_optional_operation_id(value)

    @field_validator(
        "removableIds",
        "archiveTargetIds",
        "reviewTargetIds",
        "recommendationIds",
        mode="before",
    )
    @classmethod
    def normalize_id_sequences(cls, value: object) -> object:
        if isinstance(value, list):
            value = tuple(value)
        if not isinstance(value, tuple):
            return value
        return _normalize_operation_id_tuple(value)

    @model_validator(mode="after")
    def validate_operation_shape(self) -> WorkflowStepOperation:
        if self.stepType == WorkflowStepType.MERGE:
            if not self.keeperId:
                raise ValueError("MERGE operation requires non-empty keeperId")
            if not self.removableIds:
                raise ValueError("MERGE operation requires at least one removableId")
            if self.keeperId in self.removableIds:
                raise ValueError("keeperId must not appear in removableIds")
            if self.archiveTargetIds or self.reviewTargetIds:
                raise ValueError("MERGE operation must not include archive or review targets")
        elif self.stepType == WorkflowStepType.ARCHIVE:
            if self.keeperId or self.removableIds or self.reviewTargetIds:
                raise ValueError("ARCHIVE operation must not include merge or review fields")
            if not self.archiveTargetIds:
                raise ValueError("ARCHIVE operation requires at least one archiveTargetId")
        elif self.stepType == WorkflowStepType.REVIEW:
            if self.keeperId or self.removableIds or self.archiveTargetIds:
                raise ValueError("REVIEW operation must not include merge or archive fields")
            if not self.reviewTargetIds:
                raise ValueError("REVIEW operation requires at least one reviewTargetId")
        elif self.stepType in (WorkflowStepType.RETAIN, WorkflowStepType.HANDOFF):
            if self.keeperId or self.removableIds or self.archiveTargetIds or self.reviewTargetIds:
                raise ValueError(
                    "RETAIN/HANDOFF operations must not include removal or review targets"
                )
        return self


class WorkflowItem(FrozenModel):
    workflowItemId: str
    recommendationId: str
    action: RecommendationAction
    plannerItemStatus: PlannerItemStatus
    operatorItemStatus: OperatorItemStatus = OperatorItemStatus.NONE
    recommendationPriority: ActionPriority
    queueRank: int
    reviewRequirement: ReviewRequirement
    affectedMemoryIds: tuple[str, ...] = ()
    roles: tuple[MemoryRoleAssignment, ...] = ()
    policyDecision: PolicyDecision | None = None
    requiresHumanApproval: bool
    blockerRefs: tuple[str, ...] = ()
    simulationRefs: tuple[str, ...] = ()
    evidenceRefs: tuple[str, ...] = ()
    orderingKey: str
    conflictDetected: bool = False
    suppressedActions: tuple[RecommendationAction, ...] = ()

    @field_validator("workflowItemId", "recommendationId")
    @classmethod
    def require_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @model_validator(mode="after")
    def validate_structure(self) -> WorkflowItem:
        if len({role.memoryId for role in self.roles}) != len(self.roles):
            raise ValueError("roles must not contain duplicate memoryId values")
        if len(set(self.simulationRefs)) != len(self.simulationRefs):
            raise ValueError("simulationRefs must be unique")
        for reference in self.simulationRefs:
            if not reference.startswith(SIMULATION_REF_PREFIXES):
                raise ValueError(f"simulation ref '{reference}' must use an accepted prefix")
        requires_review = (
            self.action == RecommendationAction.REVIEW
            or self.requiresHumanApproval
            or self.plannerItemStatus == PlannerItemStatus.REQUIRES_REVIEW
            or self.policyDecision == PolicyDecision.REQUIRES_REVIEW
        )
        if requires_review and not self.reviewRequirement.required:
            raise ValueError(
                "reviewRequirement.required must be true when action is review, "
                "requiresHumanApproval is true, plannerItemStatus is requires_review, "
                "or policyDecision is requires_review"
            )
        return self


class WorkflowStep(FrozenModel):
    stepId: str
    sequence: int = Field(ge=1)
    stepType: WorkflowStepType
    workflowItemIds: tuple[str, ...] = ()
    dependsOnStepIds: tuple[str, ...] = ()
    plannerStepStatus: PlannerItemStatus
    operation: WorkflowStepOperation
    description: str = ""

    @field_validator("stepId")
    @classmethod
    def require_step_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("stepId must not be empty")
        return value

    @model_validator(mode="after")
    def validate_step_type_consistency(self) -> WorkflowStep:
        if self.stepType != self.operation.stepType:
            raise ValueError("stepType must match operation.stepType")
        return self


class WorkflowSummary(FrozenModel):
    totalItems: int = Field(default=0, ge=0)
    itemsByAction: dict[RecommendationAction, int] = Field(
        default_factory=lambda: {action: 0 for action in RecommendationAction}
    )
    itemsByPlannerStatus: dict[PlannerItemStatus, int] = Field(
        default_factory=lambda: {status: 0 for status in PlannerItemStatus}
    )
    itemsByOperatorStatus: dict[OperatorItemStatus, int] = Field(
        default_factory=lambda: {status: 0 for status in OperatorItemStatus}
    )
    itemsByRecommendationPriority: dict[ActionPriority, int] = Field(
        default_factory=lambda: {priority: 0 for priority in ActionPriority}
    )
    reviewQueueCounts: dict[ReviewQueueId, int] = Field(default_factory=dict)
    blockerCount: int = Field(default=0, ge=0)
    keepCount: int = Field(default=0, ge=0)
    estimatedStructuralDelta: int = 0

    @field_validator(
        "itemsByAction",
        "itemsByPlannerStatus",
        "itemsByOperatorStatus",
        "itemsByRecommendationPriority",
        "reviewQueueCounts",
        mode="before",
    )
    @classmethod
    def copy_mapping_inputs(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return dict(value)
        return value


class WorkflowPlan(FrozenModel):
    workflowPlanId: str
    sourceAnalysisRef: str
    simulationId: str = ""
    policyProfile: PolicyProfile
    plannerStatus: WorkflowPlannerStatus = WorkflowPlannerStatus.INITIAL
    aggregateStatus: PlanAggregateStatus
    items: tuple[WorkflowItem, ...] = ()
    steps: tuple[WorkflowStep, ...] = ()
    summary: WorkflowSummary
    reviewQueues: tuple[ReviewQueueId, ...] = ()
    blockers: tuple[WorkflowBlocker, ...] = ()
    evidence: WorkflowEvidence
    planningMode: WorkflowPlanningMode
    planningOptions: PlanningOptions = Field(default_factory=PlanningOptions)
    plannerVersion: str
    metricsDisclaimer: str = ""
    decisionsFingerprint: str = ""

    @field_validator("workflowPlanId")
    @classmethod
    def validate_workflow_plan_id(cls, value: str) -> str:
        value = value.strip()
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError("workflowPlanId must be a lowercase 64-char SHA-256 hex string")
        return value

    @field_validator("sourceAnalysisRef", "plannerVersion")
    @classmethod
    def require_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @model_validator(mode="after")
    def validate_plan_structure(self) -> WorkflowPlan:
        item_ids = [item.workflowItemId for item in self.items]
        recommendation_ids = [item.recommendationId for item in self.items]
        blocker_ids = [blocker.blockerId for blocker in self.blockers]
        step_ids = [step.stepId for step in self.steps]
        step_sequences = [step.sequence for step in self.steps]

        if len(set(item_ids)) != len(item_ids):
            raise ValueError("workflow item IDs must be unique")
        if len(set(recommendation_ids)) != len(recommendation_ids):
            raise ValueError("recommendation IDs must be unique")
        if len(set(blocker_ids)) != len(blocker_ids):
            raise ValueError("blocker IDs must be unique")
        if len(set(step_ids)) != len(step_ids):
            raise ValueError("step IDs must be unique")
        if len(set(step_sequences)) != len(step_sequences):
            raise ValueError("step sequences must be unique")
        if step_sequences and set(step_sequences) != set(range(1, len(step_sequences) + 1)):
            raise ValueError("step sequences must be gap-free and start at 1")

        blocker_lookup = set(blocker_ids)
        for item in self.items:
            for blocker_ref in item.blockerRefs:
                if blocker_ref not in blocker_lookup:
                    raise ValueError(
                        f"unknown blocker ref '{blocker_ref}' on item {item.workflowItemId}"
                    )

        if self.plannerStatus == WorkflowPlannerStatus.INITIAL:
            if any(item.operatorItemStatus != OperatorItemStatus.NONE for item in self.items):
                raise ValueError("initial plans must keep operatorItemStatus as NONE")
            if self.aggregateStatus == PlanAggregateStatus.READY_FOR_EXECUTION:
                raise ValueError("initial plans cannot be ready_for_execution")
            if self.decisionsFingerprint:
                raise ValueError("initial plans must have empty decisionsFingerprint")

        if self.aggregateStatus == PlanAggregateStatus.INTEGRITY_BLOCKED and not any(
            blocker.code == WorkflowBlockerCode.INPUT_INTEGRITY for blocker in self.blockers
        ):
            raise ValueError("integrity_blocked plans must include an INPUT_INTEGRITY blocker")
        return self


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
    recommendations: tuple[Recommendation, ...] = ()
    memoryResolutions: tuple[MemoryResolution, ...] = ()
    recommendationSummary: RecommendationSummary = Field(default_factory=RecommendationSummary)
    simulationReport: SimulationReport | None = None
    workflowPlan: WorkflowPlan | None = None


class SimulatedExplainability(FrozenModel):
    explainabilitySource: str
    recommendationId: str
    reason: str = ""
    evidenceRefs: tuple[str, ...] = ()
    resolutionSnapshot: dict[str, Any] = Field(default_factory=dict)


class SimulatedMergeGroup(FrozenModel):
    recommendationId: str
    keeperId: str
    removedIds: tuple[str, ...]
    clusterId: str = ""
    trustLevel: str = ""
    trusted: bool = False
    explainability: SimulatedExplainability


class SimulatedArchiveEntry(FrozenModel):
    memoryId: str
    lifecycleState: str
    recommendationId: str
    archivedRecord: MemoryRecord
    explainability: SimulatedExplainability


class SimulatedReviewEntry(FrozenModel):
    memoryId: str
    recommendationId: str
    reason: str = ""
    conflictDetected: bool = False
    suppressedActions: tuple[str, ...] = ()
    explainability: SimulatedExplainability
    orphanMergeDowngrade: bool = False


class SimulationWarning(FrozenModel):
    code: str
    memoryId: str = ""
    message: str
    recommendationId: str = ""


class SimulationMetrics(FrozenModel):
    memoryCountBefore: int = Field(default=0, ge=0)
    memoryCountAfter: int = Field(default=0, ge=0)
    memoryCountDelta: int = 0
    memoryReductionPercentage: float = Field(default=0.0, ge=0.0)

    estimatedRemovableBefore: int = Field(default=0, ge=0)
    estimatedRemovableAfter: int = Field(default=0, ge=0)
    estimatedDuplicateReduction: int = Field(default=0, ge=0)
    estimatedStructuralCompressionBefore: float = Field(default=0.0, ge=0.0)
    estimatedStructuralCompressionAfter: float = Field(default=0.0, ge=0.0)
    estimatedCompressionGain: float = 0.0
    estimatedTrustedRemovableBefore: int = Field(default=0, ge=0)
    estimatedTrustedRemovableAfter: int = Field(default=0, ge=0)
    estimatedTrustedStructuralCompressionBefore: float = Field(default=0.0, ge=0.0)
    estimatedTrustedStructuralCompressionAfter: float = Field(default=0.0, ge=0.0)
    estimatedTrustedCompressionGain: float = 0.0

    referenceCompressionOpportunity: float = Field(default=0.0, ge=0.0)
    referenceTrustedCompressionOpportunity: float = Field(default=0.0, ge=0.0)

    lifecycleDistributionBefore: dict[str, int] = Field(default_factory=dict)
    lifecycleDistributionAfter: dict[str, int] = Field(default_factory=dict)
    lifecycleDistributionChange: dict[str, int] = Field(default_factory=dict)
    archivedByLifecycleState: dict[str, int] = Field(default_factory=dict)

    totalResolutions: int = Field(default=0, ge=0)
    resolutionsApplied: int = Field(default=0, ge=0)
    resolutionsNoOp: int = Field(default=0, ge=0)
    mergeGroupsSimulated: int = Field(default=0, ge=0)
    archivesSimulated: int = Field(default=0, ge=0)
    recommendationUtilizationRate: float = Field(default=0.0, ge=0.0)
    recommendationsEligible: int = Field(default=0, ge=0)
    recommendationsWithStructuralEffect: int = Field(default=0, ge=0)
    recommendationOutcomeUtilizationRate: float = Field(default=0.0, ge=0.0)

    unresolvedReviewCount: int = Field(default=0, ge=0)
    conflictReviewCount: int = Field(default=0, ge=0)
    suppressedActionCount: int = Field(default=0, ge=0)
    simulationWarningCount: int = Field(default=0, ge=0)


class SimulationReport(FrozenModel):
    simulationId: str
    sourceMemoryCount: int = Field(default=0, ge=0)
    simulatedMemoryCount: int = Field(default=0, ge=0)
    simulatedMemories: tuple[MemoryRecord, ...] = ()
    simulatedMerges: tuple[SimulatedMergeGroup, ...] = ()
    simulatedArchives: tuple[SimulatedArchiveEntry, ...] = ()
    simulatedReviewQueue: tuple[SimulatedReviewEntry, ...] = ()
    simulationWarnings: tuple[SimulationWarning, ...] = ()
    metrics: SimulationMetrics
    analysisReportRef: str = ""
    policyProfile: str = ""
    simulationMode: str = "full"
    metricsDisclaimer: str = (
        "Structural estimates only; not benchmark-equivalent compression."
    )


AnalysisReport.model_rebuild()
