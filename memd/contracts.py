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


class AnalysisMetrics(FrozenModel):
    totalMemories: int = Field(ge=0)
    duplicateCount: int = Field(ge=0)
    duplicatePercentage: float = Field(ge=0.0, le=100.0)
    compressionOpportunity: float = Field(ge=0.0, le=100.0)
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


class AnalysisReport(FrozenModel):
    metrics: AnalysisMetrics
    clusters: tuple[DuplicateCluster, ...]
    memories: tuple[MemoryRecord, ...] = ()
    categories: tuple[CategorizedMemory, ...] = ()
    validation: dict[str, Any] = Field(default_factory=dict)
    insights: tuple[Insight, ...] = ()
