# ADR-003: Simulation Evaluation

Status: Proposed

Date: 2026-06-17

---

## Context

Mem-D V0.7 introduces a read-only **Simulation Layer** that projects hypothetical store outcomes from V0.6 recommendation outputs. Simulation consumes:

- `Recommendation`
- `MemoryResolution`
- `RecommendationSummary`

and produces:

- `SimulationReport`
- `SimulationMetrics`
- `SimulatedMergeGroup`
- `SimulatedArchiveEntry`
- `SimulatedReviewEntry`
- `SimulationWarning`

Simulation is integrated into the normal analysis path:

```
AnalysisReport → simulationReport
```

and appears in JSON, Markdown, and terminal output. Simulation remains **read-only**, **non-executing**, **non-persistent**, and **dry-run only**. No workflow or action systems exist.

V0.7 Phase 1 implemented the simulation engine. Phase 2 integrated simulation into `analyze_file()` and reporting surfaces. Architecture audits approved both phases with limitations. **Formal simulation evaluation — an aggregated benchmark runner with published quality metrics — does not yet exist.**

ADR-002 established that recommendation quality must be measured before downstream systems consume recommendation outputs. The same discipline applies to simulation: **recommendation correctness does not imply simulation correctness.**

### Risks of unmeasured simulation

| Failure mode | Consequence |
| --- | --- |
| **Incorrect merge projection** | Dry-run reports remove wrong memories; operators or future workflows plan against false store deltas |
| **Incorrect archive projection** | Active memories appear archived in simulation; lifecycle distribution metrics mislead |
| **Review mishandling** | Review resolutions remove memories or fail to appear in review queue; unresolved counts wrong |
| **Orphan-merge safety failure** | Removals occur without keeper; violates architecture safety model |
| **Metric inconsistency** | Structural estimates contradict store composition; trusted gain exceeds headline gain |
| **Explainability gaps** | Simulated events lack traceability; operators cannot audit why a removal was projected |
| **False confidence from recommendation accuracy** | High recommendation evaluation scores mask simulation bugs |

A correct recommendation can still produce an incorrect simulation. Example: valid merge resolutions with correct keeper/removable roles may still be applied in wrong order, double-removed, or projected with wrong structural metrics if simulation logic regresses.

Simulation evaluation is required **before** workflow architecture, workflow execution, action systems, or automation layers are considered.

---

## Decision

Mem-D will treat **simulation quality as a benchmarked capability**.

Simulation evaluation becomes a **required validation layer** between:

```
Simulation Generation (V0.7 architecture + implementation)
        ↓
Simulation Evaluation (ADR-003)
        ↓
Workflow / Action / Automation Systems (future, gated)
```

Specifically:

1. **Gold-fixture evaluation** — labeled cases in `simulation_gold.json` define expected structural outcomes given known recommendation inputs.
2. **Objective metrics** — structural accuracy dimensions are computed from gold labels, not operator opinion.
3. **Safety invariants** — mandatory property tests enforce read-only guarantees and simulation safety semantics.
4. **Regression discipline** — simulation evaluation runs in CI; failures block progression to workflow and action layers.
5. **Separation of concerns** — simulation evaluation measures structural projection correctness only. Recommendation, lifecycle, evolution, clustering, and execution quality remain independently benchmarked.

This ADR defines **what** must be measured and **why**. It does not specify implementation code, benchmark reports, or Phase 3 delivery sequencing beyond establishing evaluation as a gate.

---

## 1. Purpose

Simulation evaluation exists to answer:

> **Given known recommendation inputs, does simulation project the correct hypothetical store outcome?**

It does **not** answer:

> **Were the recommendations correct?** (ADR-002)

> **Should memories have been merged or archived in production?** (execution / operator domain)

Simulation evaluation validates the **dry-run projection layer** in isolation. It ensures that `simulate_recommendations()` faithfully implements documented simulation semantics before any downstream system treats `SimulationReport` as operational input.

**Why simulation evaluation is independent of recommendation evaluation:**

| Dimension | Recommendation evaluation (ADR-002) | Simulation evaluation (ADR-003) |
| --- | --- | --- |
| Input | Evidence payloads, governance, lifecycle | `MemoryResolution` + `Recommendation` outputs |
| Question | Did we resolve the right action per memory? | Did we project the right store shape if those resolutions were applied? |
| Failure example | Wrong `resolvedAction` | Correct `merge` resolution but wrong keeper retained |
| Ground truth | Expected `resolvedAction` labels | Expected active store, logs, warnings, metrics |

Both layers must pass before workflow architecture proceeds.

---

## 2. Scope

### In scope

Simulation evaluation measures:

| Dimension | What is validated |
| --- | --- |
| **Structural projections** | Active memory set after simulation (`S_after`) matches gold |
| **Simulated removals** | Merge removables and archive candidates removed correctly |
| **Review preservation** | Review resolutions never remove memories; queue accounting correct |
| **Warning generation** | Safety warnings (`ORPHAN_MERGE_NO_KEEPER`, `DUPLICATE_REMOVAL_SKIPPED`) emitted when gold expects them |
| **Explainability generation** | Simulated events carry `explainabilitySource`, `reason`, and non-empty `evidenceRefs` per architecture |
| **Metrics consistency** | `SimulationMetrics` align with store composition and event logs; structural estimates internally consistent |

### Out of scope

Simulation evaluation does **not** measure:

| Excluded dimension | Owner |
| --- | --- |
| Recommendation quality | ADR-002 / `recommendation_gold.json` |
| Lifecycle inference quality | `lifecycle_gold.json` |
| Evolution audit quality | `evolution_gold.json` |
| Clustering quality | Cluster audit, trust scores, duplicate metrics |
| Workflow quality | Future V0.8+ |
| Execution outcomes | Future V1.0+ |
| Operator preference or user satisfaction | Subjective; non-reproducible |
| Business or agent performance outcomes | Outside Mem-D CLI scope |
| Benchmark-equivalent compression claims | Structural estimates only; not LongMemEval/PERMA equivalence |

---

## 3. Evaluation Philosophy

**Simulation quality is structural correctness.**

Evaluation asks whether the simulation engine correctly implements documented semantics — application order, role handling, safety guards, metrics formulas, and explainability paths — given labeled inputs.

Simulation quality is **not**:

- Operator preference ("I would not merge these")
- User satisfaction with report readability
- Business outcome ("storage costs decreased")
- Proof that simulated actions should be executed in production

Gold labels encode **architecture-intended structural outcomes** given supplied `MemoryResolution` records and supporting validation context. The evaluation answers: *did simulation project the documented dry-run outcome correctly?*

---

## 4. Primary Evaluation Unit

### Authoritative object: `SimulationReport`

`SimulationReport` is the **authoritative evaluation object**. All quality judgments derive from comparing a produced `SimulationReport` against gold expectations for the same input `AnalysisReport`.

Evaluation inspects:

| Field group | Role in evaluation |
| --- | --- |
| `simulatedMemories` / `simulatedMemoryCount` | Ground truth for active store composition |
| `simulatedMerges` | Merge projection correctness (keeper, removedIds) |
| `simulatedArchives` | Archive projection correctness (memoryId, archivedRecord) |
| `simulatedReviewQueue` | Review and orphan-downgrade accounting |
| `simulationWarnings` | Safety warning correctness |
| `simulationId` | Determinism verification |

### Supporting evidence: `SimulationMetrics`

`SimulationMetrics` provides **supporting evidence** for evaluation. Metrics must be **consistent with** the event logs and store composition, but metric equality alone is insufficient for quality judgment.

Example: correct `memoryCountAfter` with incorrect `simulatedMerges` composition is a simulation failure even if aggregate counts match.

Metrics are evaluated for:

- Consistency with `S_before` / `S_after`
- Consistency with merge/archive event logs
- Internal structural relationships (e.g. trusted gain ≤ headline structural gain)
- Alignment with hardened architecture formulas

Metrics labeled `estimated*` are **structural estimates**. Evaluation verifies formula correctness against gold; it does **not** compare them to LongMemEval or PERMA compression percentages.

---

## 5. Gold Fixture Strategy

### Canonical source

`tests/fixtures/simulation_gold.json` is the **canonical benchmark source** for simulation evaluation.

Each case specifies:

- Input memories, clusters, actions, validation payloads
- Optional `useExplicitResolutions` for edge-case resolution injection
- An `expected` block with structural outcome labels

### Current case coverage (baseline)

| Case ID | Scenario |
| --- | --- |
| `sim_merge_1` | Trusted merge removal |
| `sim_archive_1` | Superseded archive |
| `sim_review_1` | Review queue; no removal |
| `sim_keep_1` | Implicit keep; no removal |
| `sim_conflict_archive_merge` | Conflict → review; no structural effect |
| `sim_orphan_merge_no_keeper` | Orphan safety; warning + downgrade |
| `sim_implicit_keep_fallback` | Resolution fallback explainability |
| `sim_mixed_recommendation_set` | Merge + archive ordering |
| `sim_duplicate_removal_skipped` | Duplicate removal warning path |

### Gold expectation categories

| Category | Expected fields (examples) |
| --- | --- |
| **Merge projections** | `memoryCountAfter`, `activeMemoryIds`, `removedIds`, `mergeGroupsSimulated`, keeper + removed sets |
| **Archive projections** | `archivesSimulated`, `removedIds`, lifecycle state in archive log |
| **Review queue outcomes** | `reviewQueueSize`, `unresolvedReviewCount`, no removals |
| **Warnings** | `warningCode`, `simulationWarningCount`, `orphanMergeDowngrade` |
| **Explainability** | `resolutionFallbackExplainability`, `implicitKeepFallback` flags |
| **Utilization metrics** | `estimatedDuplicateReduction`, `memoryCountDelta`, `recommendationsWithStructuralEffect` |

Gold cases may be built via `plan_recommendations()` helpers or explicit resolutions. Full-pipeline cases (via `analyze_file()`) may supplement gold coverage but do not replace labeled fixture authority.

### Label authority

Gold labels represent **simulation architecture intent**. Disputes require architecture or ADR updates — not silent test changes.

---

## 6. Evaluation Metrics

Metrics divide into **quality metrics** (gate progression) and **diagnostic metrics** (regression awareness only).

### Quality metrics

#### Overall structural accuracy

**Definition:** Fraction of gold evaluation checkpoints across all cases where predicted simulation outcome matches expected label.

```
overall_structural_accuracy = correct_checkpoints / total_checkpoints
```

A **checkpoint** is an atomic expected assertion: e.g. `memoryCountAfter`, `activeMemoryIds`, `warningCode`, `mergeGroupsSimulated`. Case-level pass requires all specified checkpoints in that case to match.

Primary quality gate metric.

#### Merge projection accuracy

**Definition:** Fraction of merge-scenario checkpoints where:

- `activeMemoryIds` match gold
- `simulatedMerges[].keeperId` and `removedIds` match expected groups
- Keeper content unchanged (no fusion)
- `mergeGroupsSimulated` matches gold

Evaluated on cases tagged merge (`sim_merge_1`, `sim_mixed_recommendation_set`, etc.).

#### Archive projection accuracy

**Definition:** Fraction of archive-scenario checkpoints where:

- Archived memory absent from active store
- `simulatedArchives[].memoryId` and `archivedRecord` present
- `archivesSimulated` matches gold
- Lifecycle state captured correctly

#### Review preservation accuracy

**Definition:** Fraction of review-scenario checkpoints where:

- All review-resolution memory IDs remain in active store
- `simulatedReviewQueue` size and membership match gold
- `unresolvedReviewCount` matches gold
- No structural removal occurred

#### Warning accuracy

**Definition:** Fraction of warning-scenario checkpoints where:

- Expected warning codes present in `simulationWarnings`
- `simulationWarningCount` matches gold
- Unexpected warnings absent on happy paths

Covers `ORPHAN_MERGE_NO_KEEPER`, `DUPLICATE_REMOVAL_SKIPPED`, and future warning types.

#### Orphan merge handling accuracy

**Definition:** Case-level pass on orphan scenarios when **all** hold:

1. No memory removals (`memoryCountAfter == memoryCountBefore`)
2. `ORPHAN_MERGE_NO_KEEPER` warning emitted
3. `orphanMergeDowngrade` entries in review queue
4. `mergeGroupsSimulated == 0`
5. Input `memoryResolutions` unchanged

Reported separately from general warning accuracy because orphan safety is a hard gate.

#### Explainability accuracy

**Definition:** Fraction of simulated events (merge, archive, review) where:

- `explainability.recommendationId` non-empty
- `explainability.evidenceRefs` non-empty
- `explainabilitySource` matches gold expectation (`recommendation` vs `resolution_fallback`)
- Fallback reason templates match architecture when `Recommendation` absent

Implicit keep paths satisfy completeness via `resolution_fallback` without requiring `Recommendation` records.

#### Metric consistency accuracy

**Definition:** Fraction of cases where `SimulationMetrics` are internally consistent:

- `memoryCountDelta == memoryCountAfter - memoryCountBefore`
- `estimatedDuplicateReduction` aligns with cluster removable-slot math on `S_after`
- `estimatedTrustedCompressionGain <= estimatedCompressionGain`
- `recommendationsWithStructuralEffect` matches distinct IDs in merge/archive logs
- `unresolvedReviewCount` matches architecture formula (review + orphan downgrade + conflictDetected)

### Diagnostic metrics

**Not quality gates.** Reported for regression awareness:

| Metric | Purpose |
| --- | --- |
| `recommendationUtilizationRate` | Per-memory removal rate; posture shift detection |
| `recommendationOutcomeUtilizationRate` | Per-recommendation-group structural effect rate |
| `conflictReviewCount` | Conflict-heavy export detection |
| `suppressedActionCount` | Resolution complexity indicator |
| `simulationId` stability | Determinism smoke check across runs |
| Lifecycle distribution deltas | Structural posture on labeled exports |

Diagnostic metrics may appear in benchmark artifacts but **do not substitute** for gold-fixture structural accuracy.

---

## 7. Safety Evaluation

Safety properties are **mandatory benchmark requirements**, not optional smoke tests. Failures block progression regardless of structural accuracy on happy paths.

| Property | Requirement | Benchmark enforcement |
| --- | --- | --- |
| **Source immutability** | `AnalysisReport.memories`, `recommendations`, `memoryResolutions` unchanged after simulation | Property test in CI; must pass on every run |
| **Idempotency** | Repeated simulation yields identical `SimulationReport` | Determinism test; `simulationId` stable |
| **No orphan removal** | Every removed ID appears in merge or archive log | Property test on all gold cases |
| **Review preservation** | Review resolutions never remove memories | Dedicated tests + gold cases |
| **Duplicate removal safety** | `DUPLICATE_REMOVAL_SKIPPED` when archive targets already-removed memory | Gold case `sim_duplicate_removal_skipped` |
| **Monotonic reduction** | `memoryCountAfter <= memoryCountBefore` when only merge/archive remove | Parametrized property test |
| **Orphan merge safety** | No removal when keeper absent; warning + downgrade | Gold case + dedicated tests |

Safety invariants are evaluated **in addition to** gold structural accuracy. A single safety failure fails simulation evaluation regardless of accuracy score.

---

## 8. Regression Guards

### Role of LongMemEval and PERMA

LongMemEval and PERMA exports serve as **regression indicators** for simulation posture and stability. They are **not simulation ground truth**.

| Aspect | LongMemEval / PERMA | Simulation gold fixture |
| --- | --- | --- |
| Purpose | Posture and stability guards | Objective structural accuracy |
| Labels | No per-simulation expected outcomes | Explicit `expected` blocks |
| Metrics compared | Inequality guards only | Exact checkpoint matching |
| Compression figures | Reference context only | Not equivalence targets |

### Permitted regression guards

When simulation runs on published benchmark exports (`simulationMode = full`), CI may assert **structural guard inequalities** only:

1. `estimatedTrustedCompressionGain <= estimatedCompressionGain`
2. Review-dominant exports: `unresolvedReviewCount / memoryCountBefore > resolutionsApplied / memoryCountBefore`
3. **Conditional:** when `recommendationsWithStructuralEffect > 0` for merge recommendations, `estimatedDuplicateReduction > 0`

Guards detect posture drift. They **do not** assert equivalence to published LongMemEval or PERMA compression percentages.

### Ground truth authority

**Simulation accuracy comes exclusively from gold fixtures.** Regression guards supplement; they never override or replace labeled expected outcomes.

---

## 9. CI Requirements

Simulation evaluation follows the benchmark discipline established by ADR-002 and existing lifecycle/evolution evaluation patterns.

### Evaluation runner

A dedicated evaluation module (future: `tests/test_simulation_evaluation.py`, following `test_lifecycle_evaluation.py` / `test_recommendation_evaluation.py`) must:

1. Load `simulation_gold.json`
2. Build `AnalysisReport` per case (helper or pipeline)
3. Invoke `simulate_recommendations(report)`
4. Compare `SimulationReport` against gold checkpoints
5. Aggregate quality metrics (overall structural accuracy, per-dimension accuracy)
6. Report pass/fail with case-level detail

Unit tests in `test_simulation.py` remain necessary but **insufficient** as the sole evaluation signal.

### Benchmark artifact generation

Published artifacts (future):

| Artifact | Purpose |
| --- | --- |
| `examples/benchmarks/simulation_evaluation.json` | Aggregated quality and diagnostic metrics |
| `examples/benchmarks/simulation_evaluation.md` | Human-readable evaluation summary |
| `scripts/run_simulation_evaluation.py` | Reproducible local/CI runner |

Artifacts must include:

- `simulationMode`
- `metricsDisclaimer` (structural estimates only)
- Quality metric rollups
- Case-level pass/fail table
- Observed regression guard results (LongMemEval/PERMA) when run

### Regression gating

Simulation evaluation failures **block**:

- V0.8 workflow architecture approval
- Workflow execution design
- Action system design
- Automation layer design

CI must run simulation evaluation alongside existing test suites. Safety property failures fail immediately regardless of accuracy score.

### Deterministic outputs

Evaluation requires:

- Stable `simulationId` for identical inputs
- Reproducible gold comparisons (exact match on integers and sets; tolerance rules for floats documented in evaluation plan)
- No nondeterministic fields in comparison payloads

---

## 10. Progression Gate

Simulation evaluation must be **completed and benchmarked** before the following may proceed:

| Blocked until gate passes | Rationale |
| --- | --- |
| Workflow architecture (V0.8) | Workflows consume simulated store projections |
| Workflow execution | Execution plans depend on dry-run impact estimates |
| Action systems (V1.0) | Actions require validated pre-execution modeling |
| Automation layers | Automation must not consume unmeasured simulation output |

### Minimum gate criteria

1. Simulation evaluation runner exists and runs in CI
2. Overall structural accuracy meets maintainer-defined threshold on `simulation_gold.json`
3. Orphan merge handling accuracy = 100% on labeled cases
4. All safety invariants pass on every CI run
5. LongMemEval/PERMA regression guards documented with observed deltas (when run)
6. Simulation labeled as dry-run / structural estimate in all report surfaces (Phase 2 complete)

Recommendation evaluation (ADR-002) remains a **prerequisite**. Simulation evaluation adds a second validation layer; it does not replace recommendation benchmarking.

---

## Relationship to Existing ADRs

### Layer responsibilities

| ADR | Layer | Responsibility |
| --- | --- | --- |
| **ADR-001** | Recommendation generation | Emit `Recommendation`, `MemoryResolution`, evidence-bearing guidance |
| **ADR-002** | Recommendation evaluation | Measure recommendation correctness against gold labels |
| **ADR-003** | Simulation evaluation | Measure structural projection correctness against gold labels |

### Expected progression

```
Diagnostics
    → Recommendations (ADR-001: generate)
    → Recommendation Evaluation (ADR-002: validate recommendations)
    → Simulation (V0.7: project dry-run outcomes)
    → Simulation Evaluation (ADR-003: validate simulation)
    → Future Workflows (V0.8, gated)
    → Future Actions (V1.0, gated)
```

ADR-001 requires benchmark discipline before simulation. ADR-002 defines recommendation measurement. ADR-003 defines simulation measurement. None authorize execution.

### Dependency chain

```
ADR-002 PASS ──→ Simulation implementation (V0.7)
Simulation implementation + integration ──→ ADR-003 evaluation
ADR-003 PASS ──→ Workflow / action architecture
```

Simulation evaluation assumes recommendation outputs are present and structurally valid. It does not re-adjudicate recommendation correctness.

---

## Alternatives Considered

### A. Rely on unit tests in `test_simulation.py` only

**Rejected:** Unit and parametrized gold tests exist but do not aggregate quality across dimensions or publish benchmark artifacts. No overall structural accuracy signal for progression gating.

### B. Use LongMemEval/PERMA as simulation ground truth

**Rejected:** External exports lack labeled per-simulation expected outcomes. Suitable for regression guards only.

### C. Defer simulation evaluation until workflow layer

**Rejected:** Workflows will consume `SimulationReport` as operational input. Structural projection bugs must be caught before workflow design encodes assumptions about dry-run semantics.

### D. Conflate simulation evaluation with recommendation evaluation

**Rejected:** Independent failure modes. High recommendation accuracy does not guarantee correct merge ordering, orphan safety, or metric consistency.

### E. Operator review as primary simulation metric

**Rejected:** Non-reproducible; confounds structural correctness with operator preference and domain judgment.

---

## Non-Goals

ADR-003 does **not**:

- Define workflow architecture (V0.8)
- Define action systems or execution semantics (V1.0)
- Define automation or orchestration layers
- Define execution success criteria
- Redesign simulation behavior or semantics
- Modify ADR-001 or ADR-002
- Specify Phase 3 implementation code, runners, or fixtures
- Authorize memory modification, persistence, or external system writes

---

## Consequences

### Positive

- **Measurable simulation quality** before workflow or action layers consume dry-run output
- **Independent validation** of structural projection separate from recommendation correctness
- **Safety-gated progression** via mandatory invariants
- **Benchmark-driven development** aligned with lifecycle, evolution, and recommendation evaluation patterns
- **Clear ground truth authority** (gold fixtures) vs regression posture (LongMemEval/PERMA)

### Negative

- **Gold fixture maintenance** — new simulation semantics require new or updated labeled cases
- **Dual benchmark stack** — contributors must understand both ADR-002 and ADR-003 evaluation boundaries
- **Coverage evolution** — gold cases must grow with simulation modes (`merge_only`, `archive_only`) and new warning types
- **Label disputes** require architecture updates, not silent test changes

---

## References

- `docs/design/ADR-001-RECOMMENDATION-LAYER.md`
- `docs/design/ADR-002-RECOMMENDATION-EVALUATION.md`
- `docs/design/V0.7-SIMULATION-ARCHITECTURE.md`
- `docs/validation/V0.7-ARCHITECTURE-HARDENING.md`
- `docs/validation/V0.7-PHASE1-ARCHITECTURE-AUDIT.md`
- `docs/validation/V0.7-PHASE2-INTEGRATION-AUDIT.md`
- `tests/fixtures/simulation_gold.json`
- `tests/test_simulation.py`
- `docs/validation/PERMA-BENCHMARK-INTERPRETATION.md`
- `docs/validation/BENCHMARK-EVIDENCE-SUMMARY.md`
