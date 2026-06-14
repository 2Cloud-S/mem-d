# Benchmark Baseline Template

Copy this structure when documenting a Mem-D benchmark run. Replace placeholders with values from audit, preprocessing, and analysis reports.

For automated generation, run:

```bash
python scripts/run_longmemeval_benchmark.py <dataset.jsonl>
```

That writes `{stem}.baseline.md` beside the other artifacts in `examples/benchmarks/`.

---

## Dataset

- **Source:** `{path/to/raw/dataset.jsonl}`
- **Cleaned input:** `{path/to/stem.cleaned.jsonl}`
- **Benchmark stem:** `{stem}`
- **Mem-D version:** `{version}`

## Input Size

- Raw records: `{N}`
- Cleaned records: `{N}`
- Retention after preprocessing: `{percent}%`
- Records analyzed: `{N}`

## Meaningful Memory Rate

- Raw audit meaningful rate: `{percent}%`
- Cleaned audit meaningful rate: `{percent}%`

## Unknown Rate

- Raw audit Unknown rate: `{percent}%`
- Cleaned audit Unknown rate: `{percent}%`
- Analyze pipeline Unknown category: `{percent}%`

## Duplicate Rate

- Raw audit duplicate rate: `{percent}%`
- Cleaned audit duplicate rate: `{percent}%`
- Analyze pipeline duplicate percentage: `{percent}%`
- Analyze pipeline removable duplicates: `{count}`

## Compression Opportunity

- Compression opportunity: `{percent}%`
- Trusted compression opportunity: `{percent}%`
- Unverified compression opportunity: `{percent}%`

## Category Distribution

| Category | Count |
| --- | ---: |
| `{Category}` | `{count}` |

## Evolution Signals

- Total evolution signals: `{count}`
- Contradictions: `{count}`
- Preference changes: `{count}`
- Superseded memories: `{count}`
- Stale memory candidates: `{count}`
- Status transitions: `{count}`

## Lifecycle Distribution

| Lifecycle state | Count |
| --- | ---: |
| Active | `{count}` |
| Historical | `{count}` |
| Superseded | `{count}` |
| Deprecated | `{count}` |
| Temporary | `{count}` |
| Completed | `{count}` |

## Insights Summary

- `{insight title}` (`{severity}`): `{recommended action}`

---

## Artifact checklist

| File | Step |
| --- | --- |
| `{stem}.audit.raw.json` | audit-dataset (raw) |
| `{stem}.preprocess-report.json` | preprocess |
| `{stem}.audit.cleaned.json` | audit-dataset (cleaned) |
| `{stem}.analysis.json` | analyze |
| `{stem}.baseline.md` | baseline summary |
| `clustering_quality.cluster-eval.json` | evaluate-clusters (optional) |

See [docs/validation/BENCHMARK-WORKFLOW.md](../../docs/validation/BENCHMARK-WORKFLOW.md) for the full pipeline.
