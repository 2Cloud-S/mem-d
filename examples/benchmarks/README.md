# Benchmark artifacts

Reproducible Mem-D benchmark outputs for real memory datasets.

## Committed to git

These files are intended for GitHub-visible benchmark evidence:

| Pattern | Example |
| --- | --- |
| `{stem}.baseline.md` | `longmemeval_sample.baseline.md` |
| `{stem}.audit.raw.md` | `longmemeval_sample.audit.raw.md` |
| `{stem}.audit.cleaned.md` | `longmemeval_sample.audit.cleaned.md` |
| `{stem}.preprocess-report.md` | `longmemeval_sample.preprocess-report.md` |
| `{stem}.audit.*.json` | `longmemeval_sample.audit.raw.json` |
| `{stem}.preprocess-report.json` | `longmemeval_sample.preprocess-report.json` |
| `BENCHMARK-BASELINE.md` | Baseline section template |

## Gitignored (local only)

| Pattern | Reason |
| --- | --- |
| `{stem}.cleaned.jsonl` | Large cleaned export |
| `{stem}.analysis.json` / `.md` | Large full analyze reports |
| `*-eval.json` / `*-eval.md` | Optional cluster eval outputs |
| `datasets/evaluation/*.jsonl` | Raw benchmark datasets |

## Layout

| File | Description |
| --- | --- |
| `{stem}.audit.raw.json` / `.md` | Dataset quality audit on raw export |
| `{stem}.preprocess-report.json` / `.md` | LongMemEval preprocessing summary |
| `{stem}.cleaned.jsonl` | Cleaned memory export (local) |
| `{stem}.audit.cleaned.json` / `.md` | Dataset quality audit on cleaned export |
| `{stem}.analysis.json` / `.md` | Full Mem-D analyze report (local) |
| `{stem}.baseline.md` | One-page benchmark summary |
| `clustering_quality.cluster-eval.json` / `.md` | Labelled clustering evaluation (optional) |

## Run

```bash
python scripts/run_longmemeval_benchmark.py datasets/evaluation/longmemeval_sample.jsonl
```

## References

- [BENCHMARK-BASELINE.md](BENCHMARK-BASELINE.md) — baseline section template
- [docs/validation/BENCHMARK-WORKFLOW.md](../../docs/validation/BENCHMARK-WORKFLOW.md) — full pipeline
- [docs/validation/BENCHMARK-EVIDENCE-SUMMARY.md](../../docs/validation/BENCHMARK-EVIDENCE-SUMMARY.md) — sprint 1 findings
