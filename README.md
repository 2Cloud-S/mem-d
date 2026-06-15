# Mem-D Analyze

Local-first CLI for analyzing agent memory exports.

Mem-D answers: **what is in memory, how redundant is it, and how much could be compressed?**

This is an early V1 build — functional, but not polished. Feedback and contributions welcome.

## Status

- **Version:** 0.1.0 (V1 Aplha)
- **Scope:** Read-only analysis via CLI

## Features

- Parse memory exports: JSON, JSONL, CSV, TXT
- Heuristic categorization (Preference, Fact, Task, Goal, Relationship, Temporary, Unknown)
- Semantic duplicate clustering (DBSCAN + cosine similarity)
- Metrics: category distribution, duplicate %, compression opportunity
- Ranked, rule-based insights with recommended actions
- Output: terminal report, JSON, Markdown

## Requirements

- Python 3.10+
- Windows, macOS, or Linux

## Install

```bash
git clone <https://github.com/2Cloud-S/mem-d>
cd mem-d

python -m pip install -e ".[dev]"
```

Optional — better semantic duplicate detection with local embedding models:

```bash
python -m pip install -e ".[dev,embeddings]"
```

## Quick start

```bash
# Help
python -m memd --help

# Analyze a memory export (terminal report)
python -m memd analyze tests/fixtures/memories.json

# JSON output
python -m memd analyze memory.json --format json

# Markdown report to file
python -m memd analyze memory.json --format markdown --output report.md

# Tune similarity threshold after evaluation
python -m memd analyze memory.json --threshold 0.55

# Use a local embedding model (requires [embeddings] extra)
python -m memd analyze memory.json --model BAAI/bge-small-en-v1.5
```

## Clustering evaluation

Use the labelled validation fixture to measure duplicate-clustering quality:

```bash
python -m memd evaluate-clusters datasets/validation/clustering_quality.json
python -m memd evaluate-clusters datasets/validation/clustering_quality.json --format json
python -m memd evaluate-clusters datasets/validation/clustering_quality.json --format markdown --output clustering-eval.md
```

The evaluation report includes precision, recall, F1, false positives, false negatives, cluster purity, cluster coverage, and examples of clustering mistakes.

The default threshold is `0.55`, chosen from the labelled validation fixture to improve near-duplicate recall while preserving high precision. See [docs/validation/CLUSTERING.md](docs/validation/CLUSTERING.md) for the measured tradeoffs.

## Benchmark Results

Evidence from the first benchmark sprint on a local LongMemEval sample (`longmemeval_sample`, 2,690 raw records). Committed summaries live in [examples/benchmarks/](examples/benchmarks/). Full narrative: [docs/validation/BENCHMARK-EVIDENCE-SUMMARY.md](docs/validation/BENCHMARK-EVIDENCE-SUMMARY.md).

### LongMemEval (raw vs cleaned)

| Metric | Raw | Cleaned |
| --- | --- | --- |
| Records | 2,690 | 1,134 |
| Meaningful memory rate | 35.5% | 83.42% |
| Conversational noise | 51.71% | 0.0% |
| Unknown rate | 20.26% | 34.92% |
| Duplicate rate (audit) | 2.27% | 0.0% |
| Benchmark verdict | `requires_preprocessing` | `suitable_with_filtering` |
| Compression opportunity (analyze) | — | 26.72% |
| Trusted compression (analyze) | — | 3.44% |
| Duplicate clusters (analyze) | — | 58 |

Preprocessing retained **42.16%** of records (removed 1,355 assistant turns, 185 filler records, 3 excluded-content records, 13 exact duplicates). Analyze metrics apply to the cleaned export only.

### Clustering evaluation (`clustering_quality.json`, threshold 0.55)

| Metric | Value |
| --- | ---: |
| Precision | 1.0 |
| Recall | 0.5714 |
| F1 | 0.7272 |
| Cluster purity | 1.0 |
| Cluster coverage | 0.7273 |
| False positives | 0 |
| False negatives | 3 |

Labelled fixture evaluation is independent of LongMemEval. See [docs/validation/CLUSTERING.md](docs/validation/CLUSTERING.md) for threshold tradeoffs.

### Workflow

`audit-dataset` → preprocess → `audit-dataset` (cleaned) → `analyze` → baseline summary, with optional `evaluate-clusters` on the labelled fixture. Details: [docs/validation/BENCHMARK-WORKFLOW.md](docs/validation/BENCHMARK-WORKFLOW.md).

## Reproducible Benchmark Workflow

Run the full LongMemEval evidence pipeline (requires a local copy of the dataset):

```bash
python scripts/run_longmemeval_benchmark.py datasets/evaluation/longmemeval_sample.jsonl
```

Place the raw JSONL at `datasets/evaluation/longmemeval_sample.jsonl` (gitignored). The script writes artifacts to `examples/benchmarks/`:

| Artifact | Committed to git | Description |
| --- | --- | --- |
| `{stem}.audit.raw.md` | Yes | Raw dataset quality audit |
| `{stem}.audit.cleaned.md` | Yes | Cleaned dataset quality audit |
| `{stem}.preprocess-report.md` | Yes | Preprocessing summary |
| `{stem}.baseline.md` | Yes | One-page benchmark baseline |
| `{stem}.audit.*.json` | Yes | Machine-readable audit reports |
| `{stem}.preprocess-report.json` | Yes | Machine-readable preprocess report |
| `{stem}.cleaned.jsonl` | No | Cleaned memory export (large) |
| `{stem}.analysis.json` / `.md` | No | Full analyze report (large) |

Optional clustering evaluation:

```bash
python -m memd evaluate-clusters datasets/validation/clustering_quality.json --format markdown --output examples/benchmarks/clustering_quality.cluster-eval.md
```

## Dataset quality audit

Before using external datasets such as LongMemEval as Mem-D benchmarks, audit memory usefulness:

```bash
python -m memd audit-dataset datasets/evaluation/longmemeval_sample.jsonl
python -m memd audit-dataset datasets/evaluation --format json
python -m memd audit-dataset datasets/evaluation/longmemeval_sample.jsonl --format markdown --output dataset-audit.md
```

The report estimates meaningful memories, conversational noise, Unknown rate, duplicate rate, and preprocessing needs. See [docs/validation/DATASET-QUALITY-AUDIT.md](docs/validation/DATASET-QUALITY-AUDIT.md).

## Input formats

### JSONL

One JSON object per line. Blank lines are ignored. Lines with empty `content` are skipped.

```jsonl
{"memory_id": "mem_1", "content": "User prefers dark mode"}
{"memory_id": "mem_2", "content": "User likes dark themes"}
```

### JSON

Array of objects, or an object with a `memories` / `items` / `records` key:

```json
[
  { "id": "mem_1", "content": "User prefers dark mode" },
  { "id": "mem_2", "content": "User likes dark themes" }
]
```

### CSV

Header row with at least a `content` column (also accepts `text`, `memory`, `message`).

### TXT

One memory per line.

## Development

```bash
# Run tests
python -m pytest

# Lint
python -m ruff check .

# Benchmark (10k synthetic records)
python scripts/benchmark_10k.py
```

## Project layout

```
memd/              Python package (CLI + analysis pipeline)
tests/             Unit and CLI tests
docs/              Product & technical specifications
scripts/           Benchmarks and utilities
```

## Documentation


| Doc                                                            | Purpose                            |
| -------------------------------------------------------------- | ---------------------------------- |
| [docs/PRD.md](docs/PRD.md)                                     | Product requirements               |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)                           | Architecture                       |
| [docs/DATA_CONTRACTS.md](docs/DATA_CONTRACTS.md)               | Data contracts                     |
| [docs/DECISIONS.md](docs/DECISIONS.md)                         | Architectural decisions            |
| [docs/INSIGHTS.md](docs/INSIGHTS.md)                           | Insight Engine rules and tradeoffs |
| [docs/ACTION-PLANNING.md](docs/ACTION-PLANNING.md)             | Governance action planning         |
| [docs/POLICY-ENGINE.md](docs/POLICY-ENGINE.md)                 | Governance policy decisions        |
| [docs/validation/CATEGORY-AUDIT-V2.md](docs/validation/CATEGORY-AUDIT-V2.md) | Unknown category diagnostics |
| [docs/validation/DATASET-QUALITY-AUDIT.md](docs/validation/DATASET-QUALITY-AUDIT.md) | External dataset usefulness audit |
| [docs/validation/BENCHMARK-WORKFLOW.md](docs/validation/BENCHMARK-WORKFLOW.md) | Reproducible benchmark pipeline |
| [docs/validation/BENCHMARK-EVIDENCE-SUMMARY.md](docs/validation/BENCHMARK-EVIDENCE-SUMMARY.md) | Sprint 1 benchmark findings |
| [docs/validation/CLUSTER-AUDIT.md](docs/validation/CLUSTER-AUDIT.md) | Largest-cluster quality audit |
| [docs/validation/CLUSTERING.md](docs/validation/CLUSTERING.md) | Clustering validation metrics      |
| [AGENTS.md](AGENTS.md)                                         | Agent/contributor scope            |


## Design principles

- **Local first** — runs on your machine, no cloud required
- **Read only** — never modifies input files
- **Provider independent** — no OpenAI/Anthropic/Gemini dependency for core features
- **Explainable** — categories and clusters trace back to inputs

## License

MIT — see [LICENSE](LICENSE).