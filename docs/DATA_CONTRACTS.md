# Data Contracts

Version: V1

Status: Active

---

# Purpose

This document defines all canonical data structures used throughout Mem-D.

Every module must consume and emit these contracts.

Changing a contract requires updating this document.

---

# MemoryRecord

Represents a normalized memory item.

```ts
interface MemoryRecord {
    id: string
    content: string
    source?: string
    timestamp?: string
    metadata?: Record<string, any>
}
```

Example:

```json
{
  "id": "mem_001",
  "content": "User prefers dark mode",
  "source": "chat_history",
  "timestamp": "2026-06-10T12:00:00Z"
}
```

---

# CategorizedMemory

Output from Categorization Engine.

```ts
interface CategorizedMemory {
    memoryId: string
    category: MemoryCategory
    confidence: number
}
```

---

# MemoryCategory

```ts
type MemoryCategory =
    | "Preference"
    | "Fact"
    | "Task"
    | "Goal"
    | "Relationship"
    | "Temporary"
    | "Unknown"
```

---

# EmbeddedMemory

Output from Embedding Engine.

```ts
interface EmbeddedMemory {
    memoryId: string
    embedding: number[]
}
```

---

# SimilarityRecord

Represents similarity between two memories.

```ts
interface SimilarityRecord {
    memoryA: string
    memoryB: string
    similarity: number
}
```

Range:

0.0 → 1.0

---

# DuplicateCluster

Represents semantically similar memory groups.

```ts
interface DuplicateCluster {
    clusterId: string
    members: string[]
    averageSimilarity: number
}
```

Example:

```json
{
  "clusterId": "cluster_12",
  "members": [
    "mem_1",
    "mem_7",
    "mem_18"
  ],
  "averageSimilarity": 0.92
}
```

---

# AnalysisMetrics

```ts
interface AnalysisMetrics {
    totalMemories: number
    duplicateCount: number
    duplicatePercentage: number
    compressionOpportunity: number

    categoryBreakdown: {
        Preference: number
        Fact: number
        Task: number
        Goal: number
        Relationship: number
        Temporary: number
        Unknown: number
    }
}
```

---

# AnalysisReport

Final report produced by Mem-D.

```ts
interface AnalysisReport {
    metrics: AnalysisMetrics
    clusters: DuplicateCluster[]
}
```

---

# Contract Rules

1. IDs must be unique.

2. Similarity values must be normalized between 0 and 1.

3. Confidence values must be normalized between 0 and 1.

4. Contracts are immutable after generation.

5. Engines may enrich contracts but must not break compatibility.