# External Validation Results (Pre-V0.8)

Date: 2026-06-19  
Exercise: Controlled observation of Mem-D V0.7 on Hugging Face datasets  
Plan: [EXTERNAL-VALIDATION-PLAN.md](EXTERNAL-VALIDATION-PLAN.md)  
Machine summary: `datasets/external_validation/results/external_validation_summary.json`

This is **not** a benchmark score and does not modify gold-fixture evaluation results.

---

## Executive summary

Mem-D V0.7 runs end-to-end on three external memory-style datasets without pipeline errors. Recommendation and simulation layers produce outputs on all exports. Behavior diverges sharply from gold-fixture posture:

| Dataset | Dominant posture | Key gap vs gold fixtures |
| --- | --- | --- |
| LongMemEval Oracle | **Review-heavy (97.6%)** | Lifecycle marks most turns Deprecated → review escalation; zero merges despite 51.6% duplicate signal |
| LoCoMo-10 | **Keep-heavy (79.6%)** | Conversational chit-chat → Unknown category (46.8%); low structural effect |
| PersonaLens | **Review-heavy (82.5%)** | Profile/task metadata → Unknown (75.2%); high duplicate clustering but limited merge resolution |

Simulation remained **stable** (zero warnings, zero orphan merges, no explainability gaps on analyzed slices). Real-world failure patterns center on **review dominance**, **categorization unknowns**, and **merge under-utilization** on conversational data — patterns largely absent from current gold fixtures.

**Recommendation: proceed to V0.8 with limitations** — workflow architecture may begin, but should assume review-dominant external posture and weak categorization on non-canonical memory text.

---

## Dataset inventory

| # | Dataset | HF / source | License | Download | Export scale | Analysis slice |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | LongMemEval Oracle (cleaned) | `xiaowu0162/longmemeval-cleaned` | MIT | 15.4 MB | 50 instances → 1,319 raw → 1,108 cleaned | 250 records |
| 2 | LoCoMo-10 | `snap-research/locomo` (GitHub JSON) | Research release | 2.8 MB | 10 conversations → 5,882 turns | 250 records |
| 3 | PersonaLens profiles | `AmazonScience/PersonaLens` | CDLA-Permissive-2.0 | ~2 MB (5 users) | 5 users → 1,098 memories | 246 records |

**Total download: ~17.4 MB** (under 500 MB cap)

---

## Methodology

1. Converted each dataset to Mem-D JSONL (`id`, `content`, optional `timestamp`, `metadata`).
2. Applied existing LongMemEval preprocessing only (no custom filters).
3. Used stratified **250-record analysis slices** per dataset for comparable runtime (~2.7 min total pipeline execution); full export counts preserved in metadata.
4. Ran `analyze_file()` with default threshold and hashing embeddings (no threshold tuning, no model override).
5. Collected recommendation resolution counts, conflict counts, simulation metrics, and warning distributions.

**Command executed:**

```bash
python scripts/run_external_validation.py
```

**Runtime:** ~163 seconds for three datasets (250-record slices).

---

## Aggregate statistics

### Recommendation resolution distribution (analysis slices)

| Dataset | Memories analyzed | Merge | Archive | Review | Keep | Review rate | Conflicts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LongMemEval Oracle | 250 | 0 | 6 | 244 | 0 | **97.6%** | 0 |
| LoCoMo-10 | 250 | 0 | 1 | 50 | 199 | 20.0% | 0 |
| PersonaLens | 246 | 17 | 0 | 203 | 26 | **82.5%** | 0 |

### Simulation metrics (analysis slices)

| Dataset | Before → After | Delta | Merge groups | Archives | Warnings | Orphan warnings | Explainability gaps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LongMemEval Oracle | 250 → 244 | -6 | 0 | 6 | 0 | 0 | 0 |
| LoCoMo-10 | 250 → 249 | -1 | 0 | 1 | 0 | 0 | 0 |
| PersonaLens | 246 → 233 | -13 | 4 | 0 | 0 | 0 | 0 |

### Structural / quality signals

| Dataset | Duplicate % | Unknown rate | Trusted compression % | Preprocess retention (LME only) |
| --- | ---: | ---: | ---: | ---: |
| LongMemEval Oracle | 51.6 | 20.0% | 2.4 | 84.0% (1,108 / 1,319) |
| LoCoMo-10 | 3.2 | **46.8%** | 1.2 | — |
| PersonaLens | **81.7** | **75.2%** | 15.5 | — |

---

## Notable findings

### 1. Review-dominant posture on LongMemEval and PersonaLens

LongMemEval oracle slice resolves **244/250 (97.6%)** to `review`. PersonaLens resolves **203/246 (82.5%)** to `review`. Gold fixtures expect balanced merge/archive/review/keep paths; external data skews heavily toward review escalation.

**LongMemEval driver:** Lifecycle distribution shows **249/250 Deprecated** on the analysis slice — evolution/lifecycle signals treat multi-turn dialog turns as superseded, triggering review-biased resolution. This pattern is not represented in `simulation_gold.json` or `recommendation_gold.json`.

**PersonaLens driver:** Profile strings like `User 0 preference in Alarm: Alarm Sound Preference = upbeat music` classify as **Unknown** (75.2% unknown rate), lacking lifecycle/evolution evidence for merge/archive paths.

### 2. Merge under-triggering on conversational data

LongMemEval shows **51.6% duplicate percentage** but **zero merge resolutions** and **zero simulated merge groups** on the analysis slice. High duplicate signal does not translate to merge recommendations when lifecycle/review signals dominate.

LoCoMo shows low duplicate rate (3.2%) and zero merges — expected for narrative dialog with diverse utterances.

PersonaLens shows **81.7% duplicate rate** with **17 merge resolutions** and **4 simulated merge groups** — merge path activates on repetitive profile/task template text.

### 3. LoCoMo behaves most like “stable keep” memory

LoCoMo slice: **199 keep (79.6%)**, **20% review**, **46.8% unknown** from conversational openers (`"Hey Mel! Good to see you!"`). Simulation effect minimal (1 archive). This resembles expected read-only posture for social dialog not captured as durable user facts.

### 4. Simulation stability holds on external data

Across all three datasets:

- **Zero** simulation warnings (`ORPHAN_MERGE_NO_KEEPER`, `DUPLICATE_REMOVAL_SKIPPED` absent)
- **Zero** explainability gaps on simulated events
- Monotonic reduction preserved (after ≤ before)
- Idempotent, deterministic pipeline (no errors)

Simulation structural metrics show review-dominant posture (`unresolvedReviewCount` high) but no safety anomalies.

### 5. Categorization is the primary external bottleneck

Unknown-category rates: **20% (LME), 46.8% (LoCoMo), 75.2% (PersonaLens)**. Gold fixtures use hand-crafted memory text matching V1 heuristics; external exports expose categorization weakness as upstream review pressure.

---

## Failure cases

### F1 — Excessive review rate (LongMemEval)

| Field | Value |
| --- | --- |
| Pattern | Review pathologies |
| Rate | 97.6% review resolutions |
| Example IDs | `lme_08f4fc43_1` … `lme_08f4fc43_5` |
| Example content | Multi-turn user/assistant dialog from oracle sessions |
| Mechanism | Lifecycle `Deprecated` on 249/250 memories → review escalation |
| Gold coverage | **Not covered** — gold cases use explicit lifecycle assignments, not bulk deprecated dialog |

### F2 — Merge under-triggering despite duplicates (LongMemEval)

| Field | Value |
| --- | --- |
| Pattern | Merge under-triggering |
| Signal | 51.6% duplicatePercentage, 129 estimated removable before simulation |
| Outcome | 0 merge resolutions, 0 mergeGroupsSimulated |
| Mechanism | Review/lifecycle precedence suppresses merge path |
| Gold coverage | Partial — gold has merge cases but not review-dominated duplicate haystacks |

### F3 — Profile metadata unknowns (PersonaLens)

| Field | Value |
| --- | --- |
| Pattern | Categorization failure → review cascade |
| Rate | 75.2% unknown category |
| Examples | `User 0 preference in Alarm: Alarm Recurring Preference = weekdays.` |
| Outcome | 82.5% review despite high duplicate clustering |
| Gold coverage | **Not covered** — no profile-template gold cases |

### F4 — Conversational noise unknowns (LoCoMo)

| Field | Value |
| --- | --- |
| Pattern | Conversational filler not categorized |
| Examples | `"Hey Caroline! Good to see you! I'm swamped with the kids & work."` |
| Rate | 46.8% unknown; 20% review |
| Simulation | Minimal structural effect (1 archive) |
| Gold coverage | Partial — `sim_review_1` covers review but not social-dialog unknowns at scale |

### F5 — Archive over-triggering on deprecated lifecycle (LongMemEval)

| Field | Value |
| --- | --- |
| Pattern | Archive on deprecated lifecycle |
| Count | 6 archive resolutions, 6 archivesSimulated |
| Context | 249 Deprecated lifecycle assignments |
| Note | Archive count small vs review, but archive:merge ratio infinite (6:0) on slice |

---

## Recommendations

### For V0.8 workflow planning

1. **Assume review-dominant queues** on real conversational exports — workflow orchestration should prioritize review routing, human-in-the-loop, and queue management over automated merge/archive execution.
2. **Do not treat duplicate percentage as merge readiness** on lifecycle-heavy dialog — external LongMemEval shows high duplicate signal with zero merge outcomes.
3. **Treat categorization as upstream dependency** — profile-template and conversational text need preprocessing or categorization extensions before recommendation quality improves on external data.
4. **Simulation layer is externally stable** — dry-run projections are safe to consume in workflow design; warnings and orphan guards did not fire on external slices.

### Post-release hardening (not V0.8 blockers)

| Item | Priority |
| --- | --- |
| Expand gold fixtures with review-dominant + lifecycle-deprecated dialog cases | Medium |
| Add profile-template / PersonaLens-style categorization fixtures | Medium |
| Document expected external posture in operator guides | Low |
| Optional: full-export analysis job (not 250-record slices) for longitudinal tracking | Low |

### Explicit non-recommendations

- Do **not** tune recommendation thresholds based on this exercise (observation only).
- Do **not** reinterpret gold-fixture 1.0 accuracy as external-world performance.
- Do **not** block V0.8 on achieving merge rates on LongMemEval dialog haystacks.

---

## V0.8 readiness assessment

| Criterion | Assessment |
| --- | --- |
| Pipeline runs on external HF data | **Pass** |
| Recommendation distributions observable | **Pass** — review-dominant on 2/3 datasets |
| Simulation stability on external data | **Pass** — zero warnings, monotonic reduction |
| Failure patterns documented | **Pass** — review dominance, unknown categorization, merge under-use |
| Gold fixture gaps identified | **Pass** |
| External data validates gold accuracy | **N/A** — no external labels; not a scoring exercise |

### Verdict

**Proceed to V0.8 with limitations.**

V0.8 workflow architecture may begin. External validation confirms Mem-D is **operationally ready** for workflow design (read-only analysis + simulation on real exports) but **not representative** of gold-fixture recommendation posture on conversational and profile-derived memory.

Workflow design should explicitly handle:

- Review-heavy queues (primary external outcome)
- Low-trust structural effects on dialog-heavy exports
- Categorization preprocessing as optional workflow stage (analysis-only, not mutation)

---

## Commands and artifacts

```bash
# Full validation run
python scripts/run_external_validation.py

# Outputs
datasets/external_validation/results/external_validation_summary.json
datasets/external_validation/longmemeval_oracle_50.{raw,cleaned,analysis}.jsonl
datasets/external_validation/locomo10.raw.{jsonl,analysis.jsonl}
datasets/external_validation/personalens.raw.{jsonl,analysis.jsonl}
```

---

## References

- [EXTERNAL-VALIDATION-PLAN.md](EXTERNAL-VALIDATION-PLAN.md)
- [V0.7-RELEASE-READINESS.md](V0.7-RELEASE-READINESS.md)
- ADR-001 / ADR-002 / ADR-003 (layer boundaries unchanged)
