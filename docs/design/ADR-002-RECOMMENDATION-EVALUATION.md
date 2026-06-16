# ADR-002: Recommendation Evaluation

Status: Accepted

Date: 2026-06-16

---

## Context

Mem-D V0.6 introduces a read-only **Recommendation Layer** (ADR-001) that emits memory-level governance guidance:

- `merge` — consolidate duplicate or preference-clustered memories
- `archive` — retire lifecycle-eligible memories
- `review` — escalate ambiguity, policy blocks, low trust, or conflicts
- `keep` — preserve stable active memories with no remediation signal

Recommendations are a **first-class product output**. They appear in `AnalysisReport`, JSON exports, Markdown reports, and terminal summaries alongside diagnostics, governance actions, and policy decisions.

Unlike clustering, lifecycle inference, or evolution auditing, recommendations are **decision-oriented**. They translate heterogeneous evidence into a single `resolvedAction` per memory and group-scoped `Recommendation` records. Downstream operators, simulation layers, and future workflow systems will treat these outputs as inputs to governance planning — even though Mem-D does not execute them.

Because recommendations directly influence future governance decisions, **recommendation quality must be measurable** before Mem-D progresses toward simulation (v0.7), workflows (v0.8), and external action systems (v1.0).

### Risks of unmeasured recommendations

| Failure mode | Consequence |
| --- | --- |
| **False merge recommendations** | Operators or automation may consolidate memories that should remain distinct. PERMA benchmark interpretation showed headline compression (59.21%) vastly exceeds trusted compression (8.77%) when template-shaped exports over-cluster. Un-gated merge recommendations would amplify that error. |
| **False archive recommendations** | Active or successor memories may be marked for retirement. Lifecycle false positives on `Deprecated`, `Superseded`, or `Historical` states become irreversible if acted upon externally. |
| **Incorrect review escalation** | Either too much review (noise, operator fatigue) or too little (unsafe merges/archives slip through). Policy-blocked merges, low-trust clusters, and unknown-category samples must escalate — not silently resolve to merge or keep. |
| **Incorrect keep recommendations** | Stable memories may be omitted from explicit resolution tracking, or conversely, memories needing review may default to implicit `keep` at insufficient confidence. |

### Lessons incorporated from prior benchmarking

**LongMemEval** established the pattern for conversational memory exports: cleaned inputs, reproducible analyze artifacts, and independent evaluation of lifecycle and evolution capabilities. LongMemEval-style unknown-category samples (e.g. template preference slots) must resolve to `review`, not `keep`, when taxonomy signals conflict with active lifecycle.

**PERMA benchmark interpretation** demonstrated that:

- Headline duplicate and compression metrics are misleading on synthetic task/profile exports.
- Low-trust, over-clustered groups (e.g. `cluster_8`, trust 0.48, policy `blocked`) must produce `review`, not `merge`, for all cluster members.
- Trusted compression and cluster trust — not headline `compressionOpportunity` — gate merge posture.

**Trust gating** and **recommendation conflict resolution** (ADR-001, V0.6 architecture) define deterministic precedence (`review` → `archive` → `merge` → `keep`) and a conflict matrix (e.g. merge + archive on the same memory → `review` with `conflictDetected`). Evaluation must verify these rules against labeled gold cases, not merely assert that recommendations exist.

### Existing evaluation precedent

Mem-D already benchmarks upstream capabilities independently:

| Capability | Gold fixture | Evaluation pattern |
| --- | --- | --- |
| Lifecycle inference | `tests/fixtures/lifecycle_gold.json` | Overall and per-state `resolvedAction` accuracy (`tests/test_lifecycle_evaluation.py`) |
| Evolution auditing | `tests/fixtures/evolution_gold.json` | Precision, recall, F1 per evolution signal type (`tests/test_evolution_evaluation.py`) |
| Recommendation resolution | `tests/fixtures/recommendation_gold.json` | 14 labeled cases covering merge, archive, review, keep, and conflict pairs — **fixture exists; formal evaluation runner deferred** |

Recommendation evaluation completes the validation stack for the governance output path. It does not replace lifecycle, evolution, clustering, or dataset-quality benchmarks.

---

## Decision

Mem-D will treat **recommendation quality as a benchmarked capability**.

Recommendation evaluation becomes a **required validation layer** between:

```
Recommendation Generation (ADR-001)
        ↓
Recommendation Evaluation (ADR-002)
        ↓
Simulation / Workflow / Action Systems (future)
```

No future execution-oriented capability should rely on **unmeasured** recommendation outputs.

Specifically:

1. **Gold-fixture evaluation** — labeled cases in `recommendation_gold.json` define expected `resolvedAction`, roles, and conflict outcomes per memory.
2. **Objective metrics** — overall accuracy, per-action accuracy, and conflict-resolution accuracy are computed from gold labels, not operator opinion.
3. **Regression discipline** — recommendation evaluation runs in the V0.6 test suite; failures block progression to simulation and workflow layers.
4. **Separation of concerns** — evaluation measures recommendation correctness only. Clustering, lifecycle, evolution, and memory quality remain independently benchmarked.

This ADR defines **what** must be measured and **why**. It does not specify implementation code, benchmark reports, or delivery sequencing beyond establishing evaluation as a gate.

---

## Alternatives Considered

### A. Rely on unit tests only

Unit tests in `test_recommendations.py` verify individual mapper and conflict behaviors but do not aggregate quality across representative cases.

**Rejected:** No overall accuracy signal; difficult to detect regressions across interacting rules.

### B. Use PERMA/LongMemEval artifacts as ground truth

External benchmark exports lack labeled per-memory `resolvedAction` expectations.

**Rejected:** Suitable for regression guards (distribution, trust posture) but not for objective accuracy. Gold fixtures with explicit labels are required.

### C. Defer evaluation until workflow layer

Measure recommendation quality only when operators act on recommendations.

**Rejected:** Unsafe. False merge/archive recommendations must be caught before any simulation or automation consumes them. ADR-001 explicitly requires benchmark discipline before execution paths.

### D. Subjective operator review as primary metric

Accept/reject surveys from human reviewers.

**Rejected:** Non-reproducible, not automatable, and confounds recommendation quality with user preference and domain context.

---

## Definition of Recommendation Quality

**Recommendation quality** is the degree to which generated recommendations match **expected governance outcomes derived from labeled evidence**.

Correctness is evaluated against:

| Label dimension | What is compared |
| --- | --- |
| **`resolvedAction`** | Per-memory authoritative action (`merge`, `archive`, `review`, `keep`) in `MemoryResolution` |
| **Conflict resolution outcome** | Whether `conflictDetected`, `suppressedActions`, and escalation to `review` match gold when competing signals exist |
| **Recommendation category** | Whether the emitted action type and role assignments (keeper, removable, retain, archive_candidate) match gold expectations |

Correctness is **not** evaluated against:

- Whether a human operator subjectively agrees with the recommendation
- Whether acting on the recommendation would improve agent performance
- Whether the underlying memory content is factually true

Gold labels encode **architecture-intended outcomes** given the supplied evidence payloads (governance actions, policy decisions, lifecycle assignments, cluster trust, category audit signals). The evaluation answers: *did the recommendation engine apply the documented rules correctly?*

---

## Evaluation Scope

Evaluation coverage is organized by recommendation action. Each scope includes **positive cases** (correct emission), **false positive guards** (must not emit wrong action), and **coverage gaps** (missed opportunities where gold expects action).

### Merge

| Coverage area | Examples from gold fixture |
| --- | --- |
| Correct merge recommendations | `trusted_merge_1` — HIGH trust, approved policy, Active lifecycle → merge with keeper/removable roles |
| False positive merges | Must not merge when trust is Low or policy is `blocked` (see `review_policy_blocked_merge`, `conflict_merge_review_blocked`) |
| Missed merge opportunities | Trusted approved clusters with Active members should resolve to merge, not review or keep |
| Trust-gating behavior | Merge only when cluster trust, policy approval, and confidence thresholds align; PERMA-style low-trust blocked clusters → review for all members |

### Archive

| Coverage area | Examples from gold fixture |
| --- | --- |
| Lifecycle-driven archive | `archive_superseded_1`, `archive_historical_1`, `archive_deprecated_1` — Superseded, Historical, Deprecated states |
| False archive recommendations | Active successor memories must not archive when gold expects `keep`/`retain` |
| Missed archive opportunities | Superseded or Deprecated memories without cluster membership must still archive (`conflict_archive_keep`) |

### Review

| Coverage area | Examples from gold fixture |
| --- | --- |
| Policy escalation | `review_policy_blocked_merge` — blocked merge → review |
| Conflicts | `conflict_archive_merge` — archive + merge on same memory → review with `conflictDetected` |
| Low trust conditions | `review_low_trust_cluster`, `conflict_merge_review_blocked` |
| Contradictions / mixed lifecycle | `review_mixed_lifecycle` — `alternateLifecycleSignals` → review |
| Unknown category handling | `review_unknown_category` — LongMemEval-style unknown sample beats active lifecycle keep |

### Keep

| Coverage area | Examples from gold fixture |
| --- | --- |
| Active memory preservation | `keep_active_stable` — stable Active, no signals → keep |
| Stable memory handling | Successor memories in supersede pairs (`la_s1_new` in `archive_superseded_1`) |
| No-action scenarios | Memories with no governance, lifecycle, or taxonomy signals default to implicit keep in `MemoryResolution` |

**Note:** Explicit `keep` recommendation records are optional (`includeKeep` in gold cases). Evaluation of `keep` primarily targets `MemoryResolution.resolvedAction`, consistent with ADR-001 default behavior.

---

## Metrics

### Overall accuracy

**Definition:** Fraction of evaluated memory-level resolutions where `predicted.resolvedAction == expected.resolvedAction`.

```
overall_accuracy = correct_resolutions / total_resolutions
```

Computed across all gold cases. Each memory ID in `expectedResolutions` contributes one evaluation point.

This is the primary quality gate metric.

### Per-action accuracy

**Definition:** Overall accuracy stratified by expected `resolvedAction`:

| Stratum | Measures |
| --- | --- |
| Merge accuracy | Correctness when gold expects `merge` |
| Archive accuracy | Correctness when gold expects `archive` |
| Review accuracy | Correctness when gold expects `review` |
| Keep accuracy | Correctness when gold expects `keep` |

Per-action accuracy identifies which action class regresses when overall accuracy is stable.

**Guard metrics** (derived from per-action strata, reported separately):

- **False positive rate per action** — predicted action when gold expects a different action
- **Miss rate per action** — gold expects action but prediction differs

### Conflict resolution accuracy

**Definition:** Fraction of gold cases tagged as conflict scenarios where all of the following hold:

1. `predicted.resolvedAction` matches `expected.resolvedAction` for every memory in the case
2. `predicted.conflictDetected` matches gold when specified
3. Competing signals resolve per the conflict matrix (e.g. merge + archive → review, not merge)

**Conflict case types** (minimum coverage):

| Pair | Gold case |
| --- | --- |
| merge + archive | `conflict_archive_merge` |
| merge + review (policy/trust block) | `conflict_merge_review_blocked`, `review_policy_blocked_merge` |
| archive + keep | `conflict_archive_keep`, `archive_superseded_1` |

Conflict resolution accuracy is reported at the **case level** (all memories in case must match) because partial correct resolution in a conflict scenario still represents a governance failure.

### Recommendation distribution

**Definition:** Count of emitted recommendations and resolutions by action category (`mergeCount`, `archiveCount`, `reviewCount`, `keepCount` from `RecommendationSummary`).

**Purpose:** Diagnostic and regression awareness only.

**Not a quality metric.** A skewed distribution is not inherently wrong — PERMA-style exports should produce predominantly `review` recommendations. Distribution alerts operators to posture shifts; it does not substitute for accuracy against gold labels.

---

## Explicit Non-Goals

Recommendation evaluation does **not** measure:

| Excluded dimension | Rationale |
| --- | --- |
| **User satisfaction** | Subjective; outside reproducible benchmark scope |
| **Memory quality** | Covered by dataset quality audit and meaningful-memory heuristics |
| **Clustering quality** | Independently assessed via cluster audit, trust scores, and duplicate metrics |
| **Lifecycle quality** | Independently benchmarked via `lifecycle_gold.json` |
| **Evolution quality** | Independently benchmarked via `evolution_gold.json` |
| **Policy profile correctness** | Policy is a separate layer; recommendations consume policy annotations as evidence |
| **Execution outcomes** | No merge/archive is performed; simulation validation is a future concern |
| **End-to-end agent performance** | LongMemEval MCQ accuracy and PERMA task success are out of Mem-D scope |

Failing lifecycle accuracy does not automatically fail recommendation evaluation, and vice versa. Each capability owns its gold fixture and metrics.

---

## Consequences

### Positive

- **Measurable recommendation quality** — objective accuracy against labeled evidence before any automation layer consumes outputs
- **Safer progression** toward governance workflows and external action systems
- **Benchmark-driven development** — gold cases encode architecture rules; regressions are detectable in CI
- **Regression detection** — changes to precedence, trust gating, or conflict resolution surface immediately in per-action and conflict metrics
- **Alignment with existing patterns** — reuses lifecycle/evolution gold-fixture evaluation discipline

### Negative

- **Gold fixture maintenance** — new recommendation rules require new or updated labeled cases in `recommendation_gold.json`
- **Coverage evolution** — benchmark coverage must grow as recommendation capabilities expand (keeper selection, insight wiring, deferred actions)
- **Additional validation burden** — contributors must understand conflict matrix semantics to author correct gold labels
- **Label authority** — gold labels represent architecture intent; disputes require architecture/ADR updates, not silent test changes

---

## Future Implications

### V0.6 Phase 3 — Recommendation evaluation

Phase 3 introduces the **recommendation evaluation runner**: a test module (following `test_lifecycle_evaluation.py` / `test_evolution_evaluation.py` patterns) that loads `recommendation_gold.json`, invokes `plan_recommendations()` per case, and reports overall accuracy, per-action accuracy, and conflict-resolution accuracy.

Phase 3 may also extend gold coverage (keeper selection, additional conflict pairs) and expose `--include-keep` for explicit keep recommendation records. Evaluation of `keep` resolutions proceeds regardless of keep record emission.

### Beyond Phase 3 (implementation concerns, not this ADR)

Future versions may add:

- **Recommendation precision and recall** at the group-recommendation level (not only per-memory resolution)
- **Confidence calibration** — whether reported confidence correlates with gold correctness
- **Expanded benchmark datasets** — LongMemEval/PERMA regression guards for recommendation distribution posture
- **Simulation validation** — dry-run impact estimates compared against expected removals (v0.7)

These are implementation and benchmarking concerns. They do not change the decision that objective gold-fixture evaluation is required before execution-oriented layers.

### Progression gate

Mem-D must not introduce simulation, workflow orchestration, or memory action execution until:

1. Recommendation evaluation runner exists and runs in CI
2. Overall accuracy and conflict-resolution accuracy meet maintainer-defined thresholds on `recommendation_gold.json`
3. PERMA/LongMemEval manual regression notes confirm review-dominant posture on template exports (no spurious merge surge)

---

## Relationship to ADR-001

| ADR | Responsibility |
| --- | --- |
| **ADR-001** | Establishes recommendation **generation**: contracts, precedence, conflict resolution, evidence requirements, pipeline integration |
| **ADR-002** | Establishes recommendation **validation**: quality definition, metrics, gold-fixture discipline, progression gate |

Together they form the foundation required before workflow or action systems are considered:

```
Diagnostics (existing)
    → Recommendations (ADR-001: generate)
    → Recommendation evaluation (ADR-002: validate)
    → Simulation / Workflows / Actions (future, gated)
```

ADR-001 states that benchmark discipline must prove recommendation quality before simulation. ADR-002 defines what "prove" means in measurable terms.

---

## References

- `docs/design/ADR-001-RECOMMENDATION-LAYER.md`
- `docs/design/V0.6-GOVERNANCE-RECOMMENDATION-ARCHITECTURE.md`
- `docs/validation/PERMA-BENCHMARK-INTERPRETATION.md`
- `docs/validation/BENCHMARK-EVIDENCE-SUMMARY.md`
- `tests/fixtures/recommendation_gold.json`
- `tests/fixtures/lifecycle_gold.json`
- `tests/fixtures/evolution_gold.json`
- `tests/test_lifecycle_evaluation.py`
- `tests/test_evolution_evaluation.py`
- `docs/validation/V0.6-PHASE2-INTEGRATION-AUDIT.md`
