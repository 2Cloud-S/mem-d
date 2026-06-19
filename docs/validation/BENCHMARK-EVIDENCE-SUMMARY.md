# Benchmark Evidence Summary

Reproducible benchmark evidence for Mem-D V0.5.1 based on artifacts in [examples/benchmarks/](../../examples/benchmarks/).

Workflow reference: [BENCHMARK-WORKFLOW.md](BENCHMARK-WORKFLOW.md)

---

## Reproducibility status

- LongMemEval benchmark workflow is reproducible via `scripts/run_longmemeval_benchmark.py`.
- PERMA benchmark workflow is now reproducible via `scripts/run_perma_benchmark.py`.
- Cluster evaluation remains reproducible via `memd evaluate-clusters`.
- Benchmark test reproducibility issue (fixture-directory overreach) was fixed in `tests/test_dataset_quality.py`.
  - Details: [V0.5.1-REPRODUCIBILITY-STATUS.md](V0.5.1-REPRODUCIBILITY-STATUS.md)

---

## LongMemEval results

**Dataset:** `longmemeval_sample` (2,690 raw records)  
**Pipeline:** `audit-dataset` -> preprocess -> cleaned audit -> analyze

| Metric | Raw | Cleaned |
| --- | --- | --- |
| Records | 2,690 | 1,134 |
| Meaningful memory rate | 35.5% | 83.42% |
| Conversational noise | 51.71% | 0.0% |
| Unknown rate | 20.26% | 34.92% |
| Duplicate rate (audit) | 2.27% | 0.0% |
| Benchmark verdict | `requires_preprocessing` | `suitable_with_filtering` |
| Retention after preprocessing | — | 42.16% |

| Analyze metric (cleaned) | Value |
| --- | ---: |
| Compression opportunity | 26.72% |
| Trusted compression opportunity | 3.44% |
| Unverified compression opportunity | 23.28% |
| Duplicate clusters | 58 |
| Removable duplicates | 303 |
| Governance actions | 79 (30 approved, 28 blocked) |

Artifact: [longmemeval_sample.baseline.md](../../examples/benchmarks/longmemeval_sample.baseline.md)

---

## PERMA benchmark results

**Dataset source:** `datasets/perma/profile/user108/{profile.json,tasks.json}`  
**Generated input:** `examples/benchmarks/perma_user108.input.jsonl` (228 records)  
**Pipeline:** generated export -> `audit-dataset` -> `analyze` -> baseline

| Metric | Value |
| --- | ---: |
| Records analyzed | 228 |
| Meaningful memory rate (audit) | 0.0% |
| Conversational noise (audit) | 0.44% |
| Unknown rate | 31.14% |
| Duplicate rate (audit) | 0.0% |
| Audit verdict | `poor_fit` |
| Duplicate percentage (analyze) | 59.21% |
| Compression opportunity | 59.21% |
| Trusted compression opportunity | 8.77% |
| Unverified compression opportunity | 50.44% |

Interpretation:
- Current PERMA export for Mem-D benchmarking is profile/task metadata-derived text, not a native memory export.
- It is reproducible and analyzable, but quality verdict is `poor_fit`; this is evidence, not a claim of production-ready PERMA fitness.

Artifacts:
- [perma_user108.baseline.md](../../examples/benchmarks/perma_user108.baseline.md)
- [perma_user108.audit.raw.md](../../examples/benchmarks/perma_user108.audit.raw.md)

Implementation details: [PERMA-IMPLEMENTATION-STATUS.md](PERMA-IMPLEMENTATION-STATUS.md)

---

## Clustering evaluation results

**Fixture:** `datasets/validation/clustering_quality.json`

| Metric | Value |
| --- | ---: |
| Precision | 1.0 |
| Recall | 0.5714 |
| F1 | 0.7272 |
| Cluster purity | 1.0 |
| Cluster coverage | 0.7273 |
| False positives | 0 |
| False negatives | 3 |

---

## Recommendation evaluation results

**Fixture:** `tests/fixtures/recommendation_gold.json`

| Metric | Value |
| --- | ---: |
| Overall accuracy | 1.0000 (22/22) |
| Merge accuracy | 1.0000 (3/3) |
| Archive accuracy | 1.0000 (5/5) |
| Review accuracy | 1.0000 (11/11) |
| Keep accuracy | 1.0000 (3/3) |
| Conflict resolution accuracy | 1.0000 (3/3) |

**Artifacts:**
- [recommendation_evaluation.md](../../examples/benchmarks/recommendation_evaluation.md)
- [recommendation_evaluation.json](../../examples/benchmarks/recommendation_evaluation.json)

---

## Simulation evaluation results

**Fixture:** `tests/fixtures/simulation_gold.json`

| Metric | Value |
| --- | ---: |
| Overall structural accuracy | 1.0000 (119/119) |
| Merge projection accuracy | 1.0000 |
| Archive projection accuracy | 1.0000 |
| Review preservation accuracy | 1.0000 |
| Warning accuracy | 1.0000 |
| Orphan merge accuracy | 1.0000 |
| Explainability accuracy | 1.0000 |
| Metric consistency accuracy | 1.0000 |
| Safety passed | Yes |
| Gate passed | Yes |

**Artifacts:**
- [simulation_evaluation.md](../../examples/benchmarks/simulation_evaluation.md)
- [simulation_evaluation.json](../../examples/benchmarks/simulation_evaluation.json)

Implementation details: [V0.7-PHASE3-IMPLEMENTATION.md](V0.7-PHASE3-IMPLEMENTATION.md)

---

## Benchmark coverage status

| Capability | Reproducible | Ground Truth | Report Exists | Status |
| --- | --- | --- | --- | --- |
| Dataset Quality | Yes | Partial | Yes | Mostly Complete |
| Preprocessing | Yes (LongMemEval) | Partial | Yes | Mostly Complete |
| Duplicate Detection | Yes | Yes | Yes | Complete |
| Evolution | Yes | Yes | Yes | Complete |
| Lifecycle | Yes | Yes | Yes | Complete |
| Governance recommendations | Yes | Yes | Yes | Complete |
| Simulation projection | Yes | Yes | Yes | Complete |
| Categorization | Yes | No | Partial | Partial |
| PERMA | Yes (user-level benchmark run) | No | Yes | Partial |

---

## Remaining benchmark gaps (v0.5.1 view)

- No ground-truth accuracy benchmark yet for categorization quality.
- No trust-calibration benchmark labels for cluster trust scoring.
- PERMA benchmark currently uses deterministic profile/task-derived export and should be treated as initial reproducible evidence, not final quality validation.

---

## Reproduce

```bash
# LongMemEval
python scripts/run_longmemeval_benchmark.py datasets/evaluation/longmemeval_sample.jsonl

# PERMA (user-level)
python scripts/run_perma_benchmark.py --user-id user108

# Clustering evaluation
python -m memd evaluate-clusters datasets/validation/clustering_quality.json

# Lifecycle evaluation
python -m pytest tests/test_lifecycle_evaluation.py -q

# Evolution evaluation
python -m pytest tests/test_evolution_evaluation.py -q

# Recommendation evaluation
python scripts/run_recommendation_evaluation.py

# Simulation evaluation
python scripts/run_simulation_evaluation.py
```
