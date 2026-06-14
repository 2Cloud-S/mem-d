# Benchmark artifacts

Reproducible Mem-D benchmark outputs for real memory datasets.

## Layout

| File | Description |
| --- | --- |
| `{stem}.audit.raw.json` / `.md` | Dataset quality audit on raw export |
| `{stem}.preprocess-report.json` / `.md` | LongMemEval preprocessing summary |
| `{stem}.cleaned.jsonl` | Cleaned memory export (local, often gitignored) |
| `{stem}.audit.cleaned.json` / `.md` | Dataset quality audit on cleaned export |
| `{stem}.analysis.json` / `.md` | Full Mem-D analyze report |
| `{stem}.baseline.md` | One-page baseline summary |
| `clustering_quality.cluster-eval.json` / `.md` | Labelled clustering evaluation (optional) |

## Run

```bash
python scripts/run_longmemeval_benchmark.py datasets/evaluation/longmemeval_sample.jsonl
```

## Template

Use [BENCHMARK-BASELINE.md](BENCHMARK-BASELINE.md) as the section template for baseline summaries.

Full workflow: [docs/validation/BENCHMARK-WORKFLOW.md](../../docs/validation/BENCHMARK-WORKFLOW.md).
