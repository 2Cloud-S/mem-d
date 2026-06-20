# External Validation Plan (Pre-V0.8)

Date: 2026-06-19  
Scope: Controlled observation of Mem-D V0.7 on real-world Hugging Face datasets  
Authority: `V0.7-RELEASE-READINESS.md`, ADR-001/002/003

This is **not** a new benchmark framework, ADR, or architecture phase. It is a one-time validation exercise to observe Mem-D behavior on external conversational and profile memory data before V0.8 workflow planning.

---

## Objectives

Answer:

1. How does Mem-D behave on real-world conversational memory data?
2. Do recommendation distributions look reasonable?
3. Do simulation projections remain stable?
4. Are there failure patterns not covered by current gold fixtures?

**Constraints:** No changes to recommendation, simulation, governance, lifecycle, evolution, or policy logic. No threshold tuning. Observe only.

---

## Dataset selection rules

| Rule | Limit |
| --- | --- |
| Maximum datasets | 3 |
| Maximum total download | 500 MB |
| Priority | LongMemEval-style → user memory/profile → long-context chat |
| Avoid | Massive corpora, instruction-tuning, code, multimodal, gated access |

---

## Selected datasets (3)

### 1. LongMemEval Oracle (cleaned)

| Field | Value |
| --- | --- |
| **HF ID** | `xiaowu0162/longmemeval-cleaned` |
| **File** | `longmemeval_oracle.json` |
| **Download size** | ~15.4 MB |
| **License** | MIT (via LongMemEval / Anchor-benchmarks documentation) |
| **Instances** | 500 evaluation units; **sample 50** for validation (within 50–200 target) |
| **Why selected** | Priority #1 — canonical long-term interactive memory benchmark; oracle subset contains only evidence sessions (smallest, most memory-dense variant); Mem-D already has LongMemEval preprocessing |

### 2. LoCoMo-10 (long-term conversational memory)

| Field | Value |
| --- | --- |
| **Source** | `snap-research/locomo` (`data/locomo10.json`) |
| **HF mirror** | `desire2020/locomo-serialized` (594 KB parquet) |
| **Download size** | ~2.8 MB (GitHub raw JSON) |
| **License** | Research release (see snap-research/locomo repository) |
| **Instances** | 10 long-horizon two-speaker conversations (all included) |
| **Why selected** | Priority #3 — high-quality multi-session dialog memory; complements LongMemEval with narrative personal conversations rather than task-oriented QA haystacks |

### 3. PersonaLens (user profile / preference memory)

| Field | Value |
| --- | --- |
| **HF ID** | `AmazonScience/PersonaLens` |
| **Files** | `data/profile/user{N}/profile.json`, `tasks.json` for N=0..4 |
| **Download size** | ~2–5 MB (5 users, profile + tasks only) |
| **License** | CDLA-Permissive-2.0 (PersonaLens dataset card) |
| **Instances** | 5 user profiles |
| **Why selected** | Priority #2 — structured user preference and task-intent memory resembling agent profile stores; similar export pattern to existing PERMA benchmark without re-downloading the full 886 MB vendored PERMA tree |

**Total download (validation run): ~20 MB** (well under 500 MB cap)

---

## Excluded candidates

| Dataset | Reason excluded |
| --- | --- |
| `longmemeval_s.json` (~265 MB) | Exceeds per-dataset need; oracle subset sufficient |
| `longmemeval_m.json` (~2.6 GB) | Exceeds size cap |
| Full vendored `datasets/perma/` (~886 MB) | Already benchmarked; PersonaLens provides fresh HF profile sample |
| `marybal7/locomo` (1.99k QA rows) | Overlaps LoCoMo; QA-pair format less representative of memory exports |
| Instruction-tuning / code corpora | Out of scope per selection rules |

---

## Validation procedure

### Per dataset

1. **Acquire** dataset files (HF hub or documented upstream mirror).
2. **Convert** to Mem-D JSONL memory export (`id`, `content`, `timestamp` optional).
3. **Sample** to target scale (50 LongMemEval instances; all 10 LoCoMo; 5 PersonaLens users).
4. **Preprocess** LongMemEval only via existing `preprocess_longmemeval_jsonl` (no custom filters).
5. **Analyze** a stratified **250-record slice** per dataset (runtime cap; full export counts retained in metadata).
6. **Run** `analyze_file()` with default threshold and hashing embeddings (no model override).
7. **Collect** observation metrics (no scoring against gold labels).

### Metrics collected

| Category | Fields |
| --- | --- |
| Input | record count, conversation/instance count |
| Recommendations | merge/archive/review/keep resolution counts; conflict count |
| Simulation | memoryCountBefore/After, delta, merge/archive counts, warning counts |
| Warnings | code distribution; orphan merge frequency |
| Quality signals | unknown rate, duplicate %, compression opportunity (informational) |

### Execution

```bash
python scripts/run_external_validation.py
```

Outputs:

- `datasets/external_validation/*.jsonl` — converted exports
- `datasets/external_validation/results/*.json` — per-dataset observation summaries

---

## Failure analysis framework

After execution, classify observations:

| Pattern | Indicator |
| --- | --- |
| Excessive review rate | review resolutions > 50% of memories |
| Archive over-triggering | archive > merge on conversational personal data |
| Merge under-triggering | high duplicate % but merge count ≈ 0 |
| Simulation anomalies | warnings > 0; negative impossible deltas; orphan warnings |
| Explainability gaps | simulated events with empty evidenceRefs |
| Recommendation pathologies | conflictDetected on > 30% of memories |

Examples will cite specific memory content patterns from exports.

---

## Deliverables

| Artifact | Purpose |
| --- | --- |
| `docs/validation/EXTERNAL-VALIDATION-PLAN.md` | This plan |
| `docs/validation/EXTERNAL-VALIDATION-RESULTS.md` | Post-execution findings and V0.8 assessment |
| `scripts/run_external_validation.py` | One-off observation runner (not a benchmark track) |

---

## Non-goals

- Modify Mem-D behavior or thresholds
- Create ADRs or benchmark tracks
- Change gold fixture evaluation scores
- Label external data as ground truth
- Claim production-world accuracy

---

## Success criteria (observation)

Validation succeeds as an **observation exercise** if:

1. All three datasets convert and analyze without pipeline errors.
2. Recommendation and simulation outputs are produced for each export.
3. Failure patterns are documented with examples.
4. V0.8 readiness recommendation is stated with evidence.

Quantitative pass/fail thresholds are **not** applied — this is exploratory validation only.
