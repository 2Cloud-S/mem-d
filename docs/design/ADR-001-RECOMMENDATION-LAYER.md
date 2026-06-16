# ADR-001: Governance Recommendation Layer

Status: Accepted (V0.6 Phase 1)

Date: 2026-06-16

---

## Problem

Mem-D V1 produces strong diagnostics: insights, governance actions, policy decisions, lifecycle inference, and evolution audits. Operators still must mentally translate cluster-level actions and validation payloads into memory-level decisions (merge, archive, review, keep).

Without a recommendation layer:

- Lifecycle and evolution evidence stays in `validation` and does not inform governance output.
- Competing signals (merge vs archive on the same memory) have no deterministic resolution.
- Downstream systems cannot consume a single per-memory `resolvedAction`.
- Benchmark evidence (e.g. PERMA trusted vs headline compression) is not reflected in recommendation posture.

Mem-D must evolve from **diagnostics** to **recommendations** without becoming an execution engine.

---

## Decision

Add a read-only **Recommendation Layer** (`memd/recommendations.py`) that:

1. Consumes existing evidence: governance actions, policy annotations, lifecycle, evolution, trust, compression, and category audit outputs.
2. Emits `Recommendation` records (group-scoped) and `MemoryResolution` records (one authoritative action per memory).
3. Applies architecture-defined **precedence**, **modifiers**, **conflict matrix**, and **deterministic tie-breaking**.
4. Requires **evidence** on every recommendation; never invents signals.

Phase 1 implements the engine in isolation. Pipeline wiring and report serialization are deferred to Phase 2.

---

## Alternatives Considered

### A. Extend `GovernanceAction` only

Reuse existing action types and add memory-level targets.

**Rejected:** Action types are cluster- and plan-oriented (`merge_cluster`, `review_unknown_memory`). Archive and keep are not represented. Would blur policy labeling with user-facing recommendation taxonomy.

### B. Multiple final actions per memory

Emit parallel `merge` and `archive` recommendations when signals conflict.

**Rejected:** Forces downstream consumers to guess. Violates evidence-driven governance; conflicts must escalate to `review`.

### C. Autonomous execution path

Recommendations trigger memory modification in the same release.

**Rejected:** Out of scope per `AGENTS.md`. Mem-D analyzes memory; it does not manage memory.

### D. New parallel module tree (`memd_v2_recommendations`)

**Rejected:** Prefer extending `memd/` with `recommendations.py` and contracts.

---

## Why the Recommendation Layer Exists

The product answers **"What is inside memory?"** and must next answer **"What should I consider doing?"** — still without doing it.

Recommended progression:

```
Diagnostics → Recommendations → Simulations (v0.7) → Workflows (v0.8) → Actions (v1.0)
```

The recommendation layer is the first structured bridge across that path.

---

## Why Execution Was Excluded

1. **Product scope:** Mem-D V1 is CLI analysis only; no MCP, SDK, or memory modification.
2. **Safety:** Merge and archive recommendations require human or external-system approval.
3. **Evidence integrity:** Execution would require survivor selection, rollback, and audit logs not yet designed.
4. **Benchmark discipline:** V0.6 proves recommendation quality before any simulation or workflow layer.

Policy `approved` labels a recommendation posture, not an execution authorization.

---

## Why Recommendation Precedence Exists

Signals arrive from independent subsystems (clustering, lifecycle, taxonomy). Without precedence:

- Low-trust clusters could surface as merge candidates.
- Deprecated memories in duplicate clusters could silently resolve to merge removable.
- Active lifecycle would mask unknown-category review needs.

Precedence order (`review` → `archive` → `merge` → `keep`) is **safety-biased**, not optimism-biased.

---

## Why Review Dominates Conflicts

When remediation paths disagree (archive vs merge on the same memory), automatic resolution would hide ambiguity. The conflict matrix routes these cases to `review` with `suppressedCandidates` preserved in evidence.

Review also absorbs:

- Policy-blocked merges
- Low-trust clustering
- `alternateLifecycleSignals`
- Taxonomy and unknown-category modifiers

This matches the governance design principle: **low-trust signals must not produce strong recommendations.**

---

## Why Trusted Compression Gates Merge

PERMA benchmark interpretation documented headline compression (59.21%) vs trusted compression (8.77%) on template-shaped exports. Headline duplicate rate includes low-trust over-clustered groups.

Merge recommendations require:

- HIGH cluster trust
- Policy approval
- Confidence ≥ `MERGE_MIN_CONFIDENCE` (0.80)
- `min(trustScore, averageSimilarity)` for confidence

Headline `compressionOpportunity` is never used as merge evidence.

---

## PERMA Benchmark Lessons Incorporated

| Lesson | Implementation |
| --- | --- |
| Template over-clustering inflates duplicate % | Low trust + over-clustering → `review`, merge disqualified |
| Policy blocks unsafe consolidation | Blocked merge actions → `review` with policy evidence |
| Trusted compression is the safe automation gate | Merge confidence uses cluster trust, not headline metrics |
| Unknown template preferences need taxonomy review | Unknown samples → `review` modifier beats `keep` |

---

## Future Implications

### V0.7 — Recommendation Simulation

`MemoryResolution` provides a stable per-memory input for dry-run impact estimates without mutation.

### V0.8 — Governance Workflows

Workflow engines can queue memories by `resolvedAction` and `recommendationId` without re-parsing validation blobs.

### V1.0 — Memory Governance & Action Engine

External execution systems consume recommendations + evidence + policy; Mem-D remains the evidence and recommendation authority.

---

## References

- `docs/design/V0.6-GOVERNANCE-RECOMMENDATION-ARCHITECTURE.md`
- `docs/validation/PERMA-BENCHMARK-INTERPRETATION.md`
- `docs/ACTION-PLANNING.md`
- `docs/POLICY-ENGINE.md`
- `.cursor/skills/memd-governance-design/SKILL.md`
