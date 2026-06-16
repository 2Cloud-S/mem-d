# PERMA Benchmark Interpretation Guide

Purpose: explain how to read `examples/benchmarks/perma_user108.*` artifacts without drawing invalid conclusions about Mem-D quality or PERMA agent performance.

This document is based on:

- `perma_user108.baseline.md`
- `perma_user108.audit.raw.md` / `.json`
- `perma_user108.analysis.md`
- `perma_user108.input.jsonl`
- Comparison with `longmemeval_sample.baseline.md`

---

## What the PERMA benchmark actually runs

The PERMA benchmark does **not** ingest native PERMA dialogue files (`tasks/<user>/raw_dialogues_*.json`) or evaluation MCQ metadata.

It runs Mem-D on a **deterministic synthetic export** built from:

- `datasets/perma/profile/<user>/profile.json` → affinity slot memories
- `datasets/perma/profile/<user>/tasks.json` → task intent/goal memories

Example source records:

```text
User user108 preference in Alarm: Alarm Recurring Preference = weekdays.
PERMA SD-Alarm-task-1 intent: Set a new alarm for tomorrow morning at your preferred wake-up time...
PERMA SD-Events-task-1 goal: The user receives a curated list of local event recommendations...
```

Pipeline used:

```text
generated JSONL export -> audit-dataset -> analyze -> baseline
```

There is **no LongMemEval-style preprocessing step**.

---

## Question 1: Unknown rate (~31%) and `poor_fit` verdict

### Answer: **B — PERMA export structure does not align well with Mem-D's current memory taxonomy and usefulness heuristics**

This is **not** strong evidence that Mem-D is performing poorly on PERMA-native memory content.

### Evidence

| Signal | Value | Interpretation |
| --- | ---: | --- |
| Unknown rate (audit + analyze) | 31.14% (71/228) | Driven by template-shaped affinity records |
| Meaningful memory rate | 0.0% | Audit marks 227/228 as mixed/uncertain |
| Conversational noise | 0.44% (1 record) | Not a transcript dataset |
| Audit verdict | `poor_fit` | Dataset usefulness for Mem-D memory benchmarking |
| Dominant low-quality cause | `unknown_category_signal` | 71 records |

Category distribution:

| Category | Count | Share |
| --- | ---: | ---: |
| Task | 117 | 51.3% |
| Unknown | 71 | 31.1% |
| Preference | 34 | 14.9% |
| Fact | 5 | 2.2% |
| Temporary | 1 | 0.4% |

### Why Unknown is high

Many Unknown records are **explicit preference-slot statements**, not ambiguous text.

From analysis insights and `cluster_1` samples:

- `perma_user108_affinity_1`: `User user108 preference in Alarm: Alarm Recurring Preference = weekdays.` → **Unknown**
- `perma_user108_affinity_17`: `User user108 preference in Calendar: Timezone = UTC+2.` → **Unknown**
- `perma_user108_affinity_30`: `User user108 preference in Flights: Seat Preference = window.` → **Unknown**

Mem-D V1 heuristics expect natural-language memory utterances (for example, "User prefers dark mode"), not schema-like `domain: field = value` templates. The word "preference" appears in content, but the rigid template often fails category rules and lands in Unknown.

### Why `poor_fit` appears

Audit output (`perma_user108.audit.raw.json`):

- `estimatedMeaningfulMemories`: 0
- `estimatedMixedOrUncertain`: 227
- `roleDistribution`: all 228 records have role `unknown`
- `sampleMeaningfulRecords`: empty

The dataset quality audit is tuned for conversational memory exports. A synthetic metadata flattening of PERMA profile/tasks is structurally unlike the exports Mem-D was designed to benchmark.

### What this does **not** mean

- It does **not** prove Mem-D cannot analyze PERMA.
- It does **not** measure PERMA MCQ accuracy, preference-tracking accuracy, or agent task success.
- It does **not** validate PERMA's native benchmark protocol.

### What this **does** mean

- Current PERMA-to-Mem-D export is a **format mismatch benchmark**.
- High Unknown and `poor_fit` are expected diagnostic signals for this export shape.
- Future contributors should treat these metrics as **export-fit evidence**, not model-failure evidence.

---

## Question 2: Compression opportunity (~59%)

### Answer: **B — Mostly repetitive structure in the PERMA profile/task export, not genuine durable-memory redundancy**

Headline compression (59.21%) is dominated by template repetition and lexical overlap, not verified duplicate memories.

### Headline vs trusted compression

| Metric | Value |
| --- | ---: |
| Compression opportunity | 59.21% |
| Trusted compression opportunity | 8.77% |
| Unverified compression opportunity | 50.44% |
| Removable duplicates (estimate) | 135 |
| Trusted removable duplicates | 20 |
| Unverified removable duplicates | 115 |
| Audit exact duplicate rate | 0.0% |

If 59% represented genuine redundancy, audit exact-duplicate rate would likely be non-zero. The gap between audit duplicate rate (0%) and analyze duplicate percentage (59.21%) is a strong indicator of **semantic over-grouping on shared templates**.

### Largest clusters (examples)

#### `cluster_1` (67 records) — affinity template bucket

- Trust: **Low (0.0)**
- Average similarity: **0.46**
- Cluster audit: `multiple-concepts`, contamination score 0.0746
- Policy action: **blocked** (`review_overclustered_group:cluster-1`)
- Shared terms: `preference, user108, preferred, rental, travel, type, music, time`
- Dominant category: Unknown (55/67)

Members are distinct affinity slots across unrelated domains (Alarm, Books, Flights, Hotels, Travel, etc.) grouped because they share the repeated prefix:

```text
User user108 preference in <Domain>: <Field> = <Value>.
```

These are **not** duplicates in the memory-engineering sense. They are separate preference dimensions forced into one topical cluster by template wording.

#### `cluster_8` (35 records) — task-goal template bucket

- Trust: **Low (0.0)**
- Average similarity: **0.40**
- Cluster audit: `multiple-concepts`
- Policy action: **blocked** (`review_overclustered_group:cluster-8`)
- Shared terms: `perma, goal, preferences, receives, list, curated, match, recommendations`
- Dominant category: Task (35/35)

Representative members:

- `PERMA SD-Events-task-1 goal: The user receives a curated list of local event recommendations...`
- `PERMA SD-Music-task-1 goal: The user receives a curated list of new music recommendations...`
- `PERMA SD-Restaurants-task-1 goal: The user receives a curated list of restaurant options...`

Different tasks, different domains, same boilerplate goal phrasing.

#### Smaller clusters with higher trust (limited genuine overlap)

Examples of higher-trust groups:

- `cluster_2` (2 records, High trust 0.85): two Books affinity lines
- `cluster_6` (3 records, High trust 0.85): Calendar task goals with similar scheduling language
- `cluster_10` (3 records, High trust 0.85): media/movie intent lines sharing genre/director phrasing

These explain the small trusted compression slice (8.77%), not the headline 59%.

### Contributor rule

For PERMA artifacts:

- Treat **trusted compression opportunity** as the conservative consolidation estimate.
- Treat headline compression opportunity as a **review queue inflated by export templating**.
- Do not use PERMA compression % as evidence that a real PERMA memory store contains 59% redundant memories.

---

## Question 3: LongMemEval vs PERMA — what each benchmark measures

| Dimension | LongMemEval benchmark | PERMA benchmark (current) |
| --- | --- | --- |
| Input nature | Real multi-turn conversation JSONL | Synthetic export from profile/tasks metadata |
| Preprocessing | Yes (assistant/filler/duplicate removal) | No |
| Primary question | How does Mem-D behave on cleaned conversational memory exports? | How does Mem-D behave when PERMA metadata is flattened into memory-like records? |
| Dataset quality verdict | `requires_preprocessing` -> `suitable_with_filtering` | `poor_fit` |
| Meaningful memory rate | 35.5% raw -> 83.42% cleaned | 0.0% |
| Unknown rate | 20.26% raw -> 34.92% cleaned | 31.14% |
| Compression opportunity | 26.72% (3.44% trusted) | 59.21% (8.77% trusted) |
| Evolution/lifecycle signal volume | High (dialogue temporal pairing noise) | Low (3 stale/temporary signals) |
| Ground truth | No labelled duplicate truth on export | No labelled duplicate truth on export |

### Valid conclusions

**LongMemEval**

- Mem-D can qualify conversation-heavy exports for analysis.
- Preprocessing materially improves benchmark readiness.
- Trust gating correctly flags mostly unverified compression on dialogue data.
- Analyze output is useful for diagnostic inspection of a realistic (but noisy) memory export.

**PERMA (current export path)**

- Mem-D pipeline runs reproducibly on PERMA-derived synthetic exports.
- Format mismatch produces expected `poor_fit`, high Unknown on templated affinities, and template-driven clustering.
- Trusted vs unverified compression separation works as intended (policy blocks over-clustered groups).
- PERMA benchmark evidence today is about **pipeline compatibility and diagnostic behavior**, not PERMA task accuracy.

### Misleading conclusions (do not publish)

| Misleading claim | Why it is wrong |
| --- | --- |
| "Mem-D fails on PERMA" | Current export is not native PERMA memory; Unknown/poor_fit reflect export shape. |
| "PERMA memories are 59% redundant" | Headline compression is template-driven over-clustering; trusted slice is 8.77%. |
| "PERMA Unknown rate proves bad categorization quality" | Many Unknowns are labelled preference slots with non-natural syntax. |
| "PERMA and LongMemEval Unknown rates are directly comparable" | Different export semantics and preprocessing paths. |
| "PERMA benchmark validates personalized memory agent performance" | No MCQ/interactive PERMA evaluation protocol is run. |
| "High Task share means PERMA is task-heavy memory" | Task dominance comes from exporting every task intent/goal as separate records. |

---

## How future contributors should use PERMA artifacts

### Safe uses

1. Verify benchmark orchestration reproducibility (`run_perma_benchmark.py`).
2. Inspect how Mem-D categorizes structured preference metadata.
3. Study cluster trust behavior on template-heavy datasets.
4. Compare trusted vs unverified compression to validate governance gating.

### Unsafe uses

1. Ranking Mem-D quality against other datasets using PERMA headline compression alone.
2. Treating `poor_fit` as a regression without export redesign.
3. Using PERMA benchmark output as PERMA paper-style evaluation evidence.
4. Consolidating clusters from PERMA export without manual review (especially `cluster_1` and `cluster_8`).

### Recommended reading order

1. `perma_user108.input.jsonl` (source shape)
2. `perma_user108.audit.raw.md` (usefulness verdict)
3. `perma_user108.baseline.md` (one-page summary)
4. `perma_user108.analysis.md` (cluster/trust/governance detail)

---

## Summary answers

| Question | Answer | One-line rationale |
| --- | --- | --- |
| Q1: Unknown + `poor_fit` | **B (format/taxonomy mismatch)** | Template affinity/task export is not a natural memory export; 71 Unknowns are mostly structured preference slots. |
| Q2: 59% compression | **B (repetitive export structure)** | 50.44% unverified; largest clusters are template buckets with Low trust and blocked policy actions. |
| Q3: LongMemEval vs PERMA | Different benchmarks | LongMemEval tests cleaned conversational exports; PERMA tests synthetic metadata export compatibility. |

---

## Related documents

- [PERMA-IMPLEMENTATION-STATUS.md](PERMA-IMPLEMENTATION-STATUS.md)
- [BENCHMARK-EVIDENCE-SUMMARY.md](BENCHMARK-EVIDENCE-SUMMARY.md)
- [V0.5.1-BENCHMARK-GAP-ANALYSIS.md](V0.5.1-BENCHMARK-GAP-ANALYSIS.md)
- [LONGMEMEVAL-BENCHMARK.md](../benchmarks/LONGMEMEVAL-BENCHMARK.md)
