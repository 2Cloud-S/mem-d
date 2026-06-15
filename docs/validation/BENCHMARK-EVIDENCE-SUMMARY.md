# Benchmark Evidence Summary

Sprint 1 reproducible benchmark evidence for Mem-D V1. Generated from committed artifacts under [examples/benchmarks/](../../examples/benchmarks/). No new metrics or intelligence layers were added for this summary.

Workflow reference: [BENCHMARK-WORKFLOW.md](BENCHMARK-WORKFLOW.md)

---

## LongMemEval results

**Dataset:** `longmemeval_sample` (local JSONL export, 2,690 raw records)  
**Pipeline:** `audit-dataset` → preprocess → `audit-dataset` (cleaned) → `analyze`

### Raw vs cleaned

| Metric | Raw | Cleaned |
| --- | --- | --- |
| Records | 2,690 | 1,134 |
| Meaningful memory rate | 35.5% | 83.42% |
| Conversational noise | 51.71% | 0.0% |
| Unknown rate | 20.26% | 34.92% |
| Duplicate rate (audit) | 2.27% | 0.0% |
| Benchmark verdict | `requires_preprocessing` | `suitable_with_filtering` |
| Retention after preprocessing | — | 42.16% |

### Analyze (cleaned export only)

| Metric | Value |
| --- | ---: |
| Compression opportunity | 26.72% |
| Trusted compression opportunity | 3.44% |
| Unverified compression opportunity | 23.28% |
| Duplicate clusters | 58 |
| Removable duplicates (estimate) | 303 |
| High-trust consolidation candidates | 30 clusters |
| Unknown category share | 34.92% (396 records) |
| Category agreement in clusters | 57.89% |
| Governance actions | 79 (30 approved, 28 blocked) |

### Preprocessing removals

| Cause | Count |
| --- | ---: |
| Assistant turns | 1,355 |
| Filler records | 185 |
| Puzzle / roleplay / creative | 3 |
| Exact duplicates | 13 |

### Evolution and lifecycle (analyze)

| Signal | Count |
| --- | ---: |
| Total evolution signals | 12,886 |
| Preference changes | 273 |
| Superseded memory detections | 8,712 |
| Stale memory candidates | 1,134 |
| Status transition candidates | 2,766 |
| Contradictions | 1 |
| Lifecycle: Superseded | 709 |
| Lifecycle: Active | 165 |
| Lifecycle: Deprecated | 154 |

Artifact: [longmemeval_sample.baseline.md](../../examples/benchmarks/longmemeval_sample.baseline.md)

---

## Clustering results

**Fixture:** `datasets/validation/clustering_quality.json`  
**Default threshold:** 0.55 (dependency-free fallback embeddings)

| Metric | Value |
| --- | ---: |
| Precision | 1.0 |
| Recall | 0.5714 |
| F1 | 0.7272 |
| Cluster purity | 1.0 |
| Cluster coverage | 0.7273 |
| False positives | 0 |
| False negatives | 3 |

Threshold tradeoff on the labelled fixture (see [CLUSTERING.md](clustering.md)):

| Threshold | Precision | Recall | F1 |
| ---: | ---: | ---: | ---: |
| 0.85 | 1.0 | 0.1429 | 0.2501 |
| 0.65 | 1.0 | 0.2857 | 0.4444 |
| **0.55** | **1.0** | **0.5714** | **0.7272** |
| 0.50 | 1.0 | 0.7143 | 0.8333 |

`0.55` was chosen as the default because it improves recall and coverage while preserving zero false positives on the labelled validation set.

---

## Key findings

1. **Raw LongMemEval is a transcript, not a memory export.** 51.7% conversational noise and 50.4% assistant turns make direct analyze unsuitable (`requires_preprocessing`).

2. **Preprocessing preserves durable memory.** Meaningful-memory count drops only 955 → 946 while removing 1,556 records; retention is 42.16%.

3. **Unknown rises after cleaning** (20.3% → 34.9%) because surviving user turns are often short queries without strong V1 category signal.

4. **Headline compression is mostly unverified on LongMemEval.** 26.7% compression opportunity vs 3.4% trusted; `cluster_1` (227 records, low trust) dominates the estimate.

5. **Clustering evaluation shows high precision, moderate recall.** F1 0.73 at threshold 0.55 with zero false positives on the labelled fixture.

6. **Trust gating works as designed.** Policy blocked 28 of 79 governance actions on LongMemEval; insights flag unverified compression before cleanup.

---

## Current benchmark limitations

| Limitation | Notes |
| --- | --- |
| **Local dataset only** | Raw LongMemEval JSONL is gitignored; reproduce via `scripts/run_longmemeval_benchmark.py` |
| **Large analyze outputs not committed** | Full `*.analysis.json` / `.md` stay local; baseline markdown is the published summary |
| **No labelled LongMemEval ground truth** | Analyze metrics are diagnostic, not precision/recall scored against gold duplicates |
| **Evolution/lifecycle noise on dialogue data** | High superseded and status-transition counts reflect pair-level detection on multi-session queries |
| **Mem-D Project report is pre-evolution** | `examples/memd_project_report_v0.3.0.json` lacks lifecycle/evolution fields from current pipeline |
| **Single LongMemEval sample** | One local slice; not a full LongMemEval corpus run |
| **Fallback embeddings** | Default clustering uses local lexical fallback unless `[embeddings]` extra is installed |
| **PERMA / other benchmarks** | Not yet run; strategy documented separately |

---

## Reproduce

```bash
# LongMemEval pipeline (requires local datasets/evaluation/longmemeval_sample.jsonl)
python scripts/run_longmemeval_benchmark.py datasets/evaluation/longmemeval_sample.jsonl

# Clustering evaluation
python -m memd evaluate-clusters datasets/validation/clustering_quality.json
```

Committed evidence: [examples/benchmarks/](../../examples/benchmarks/)
