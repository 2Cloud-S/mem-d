# Recommendation Evaluation Benchmark

Reproducible Mem-D recommendation quality summary.
Generated from `tests\fixtures\recommendation_gold.json`.

## Summary

| Metric | Value |
| --- | --- |
| Overall accuracy | 1.0000 (22/22) |
| Conflict resolution accuracy | 1.0000 (3/3) |
| Gold cases | 14 |

## Per-Action Accuracy

| Action | Accuracy | Correct | Total |
| --- | ---: | ---: | ---: |
| merge | 1.0000 | 3 | 3 |
| archive | 1.0000 | 5 | 5 |
| review | 1.0000 | 11 | 11 |
| keep | 1.0000 | 3 | 3 |

## Resolution Distribution (diagnostic)

| Action | Count |
| --- | ---: |
| merge | 3 |
| archive | 5 |
| review | 11 |
| keep | 5 |

## Reproduce

```bash
python scripts/run_recommendation_evaluation.py
```
