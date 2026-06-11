# Mem-D Analyze

Local-first CLI for analyzing agent memory exports.

Mem-D answers: **what is in memory, how redundant is it, and how much could be compressed?**

This is an early V1 build — functional, but not polished. Feedback and contributions welcome.

## Status

- **Version:** 0.1.0 (V1 Aplha)
- **Scope:** Read-only analysis via CLI

## Features

- Parse memory exports: JSON, CSV, TXT
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

The default threshold is `0.55`, chosen from the labelled validation fixture to improve near-duplicate recall while preserving high precision. See [Docs/validation/CLUSTERING.md](docs/validation/CLUSTERING.md) for the measured tradeoffs.

## Input formats

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