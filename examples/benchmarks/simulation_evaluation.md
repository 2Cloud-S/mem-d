# Simulation Evaluation Benchmark

Reproducible Mem-D simulation quality summary.
Generated from `tests\fixtures\simulation_gold.json`.

## Summary

| Metric | Value |
| --- | --- |
| Overall structural accuracy | 1.0000 (119/119) |
| Safety passed | True |
| Gate passed | True |
| Gold cases | 9 |

## Per-Dimension Accuracy

| Dimension | Accuracy | Passed | Total |
| --- | ---: | ---: | ---: |
| Merge projection | 1.0000 | 18 | 18 |
| Archive projection | 1.0000 | 18 | 18 |
| Review preservation | 1.0000 | 25 | 25 |
| Warning | 1.0000 | 14 | 14 |
| Orphan merge | 1.0000 | 4 | 4 |
| Explainability | 1.0000 | 9 | 9 |
| Metric consistency | 1.0000 | 36 | 36 |

## Safety Properties

| Property | Passed |
| --- | --- |
| source_immutability | True |
| idempotency | True |
| monotonic_reduction | True |
| no_orphan_removal | True |
| orphan_safety | True |
| review_preservation | True |
| duplicate_removal_safety | True |

## Diagnostic Distribution (non-gating)

### Recommendation utilization

| Case | Utilization | Outcome utilization |
| --- | ---: | ---: |
| sim_merge_1 | 0.5000 | 1.0000 |
| sim_archive_1 | 0.5000 | 1.0000 |
| sim_review_1 | 0.0000 | 0.0000 |
| sim_keep_1 | 0.0000 | 0.0000 |
| sim_conflict_archive_merge | 0.0000 | 0.0000 |
| sim_orphan_merge_no_keeper | 0.0000 | 0.0000 |
| sim_implicit_keep_fallback | 0.0000 | 0.0000 |
| sim_mixed_recommendation_set | 0.5000 | 1.0000 |
| sim_duplicate_removal_skipped | 0.3333 | 0.5000 |

### Warning distribution

| Code | Count |
| --- | ---: |
| DUPLICATE_REMOVAL_SKIPPED | 1 |
| ORPHAN_MERGE_NO_KEEPER | 1 |

## Regression Guards (non-gating)

| Export | Passed | Notes |
| --- | --- | --- |
| longmemeval | not run | Not run; regression guard only |
| perma | not run | Not run; regression guard only |

## Case Results

| Case | Passed | Checkpoints | Simulation ID |
| --- | --- | ---: | --- |
| sim_merge_1 | True | 15/15 | `70545399de51085fa1874d91b0df93fdcd5614aa26bc2255e4485293385c5ccd` |
| sim_archive_1 | True | 13/13 | `222dea0d5d1de731b6e9200c30d1be6ebd35b63ee44f6fee6d1ad27d9fa75b6f` |
| sim_review_1 | True | 15/15 | `4ca078aff781cddf816adabf22cd175127a5bc2234df995389256d0b00b292d6` |
| sim_keep_1 | True | 9/9 | `364b5b8b825ea810c3923da470f62c149b9f28d00c286056757f08b39e7dcaf8` |
| sim_conflict_archive_merge | True | 15/15 | `5a22f6e8c89bd4fd6fe599aaf2bcd45610b3058b2e758c4e05cfb060545bd0c1` |
| sim_orphan_merge_no_keeper | True | 15/15 | `eceae870b8bcee47ee48f3a312c383bbf4e4995c87592a670955d8f8abb6930b` |
| sim_implicit_keep_fallback | True | 8/8 | `886f5f9cad56e4c7c8fb93e1f5424419ada283290a87d1d0e9b55895ad3f9cef` |
| sim_mixed_recommendation_set | True | 16/16 | `c643d3e7e9a56a0ceeab3a0f43a5f1d0f1ba40d2956ab0f3b848c0f70374c503` |
| sim_duplicate_removal_skipped | True | 13/13 | `36a2f0ec4bbb56b2e0c426ea14266423e6d7658eefdb67cb3a0a067ac149261d` |

## Disclaimer

Structural estimates only; not benchmark-equivalent compression.

## Reproduce

```bash
python scripts/run_simulation_evaluation.py
```
