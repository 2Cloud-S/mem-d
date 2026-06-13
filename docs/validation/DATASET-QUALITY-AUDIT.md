# Dataset Quality Audit

Status: Active

Purpose:

Measure memory **usefulness** in external datasets before using them as Mem-D benchmarks.

This audit is diagnostic only. It does not modify ingestion, categorization, clustering, governance, or policy behavior.

---

## What It Measures

For each memory export dataset, the audit reports:

- total records
- estimated meaningful memories
- estimated conversational noise
- average memory length
- category distribution
- Unknown rate
- duplicate rate
- top causes of low-quality memories
- benchmark suitability verdict
- preprocessing recommendations

The audit focuses on usefulness, not correctness. It does not score whether memories are factually true.

---

## Low-Quality Causes

Common causes include:

- assistant conversational turns
- assistant instructional dumps
- assistant generic filler
- ephemeral user queries
- puzzles or hypotheticals
- roleplay or creative writing
- code-generation artifacts
- terse or fragmented content
- Unknown category signals
- exact duplicate content
- low information density

---

## Benchmark Verdicts

- `suitable_with_filtering` — enough likely durable memories, but filtering is recommended
- `requires_preprocessing` — benchmark potential exists, but noise is high
- `poor_fit` — dataset is dominated by low-usefulness conversational content
- `companion_benchmark_metadata` — question/answer benchmark file, not a memory export

---

## CLI

Audit one or more dataset files:

```bash
python -m memd audit-dataset datasets/evaluation/longmemeval_sample.jsonl
python -m memd audit-dataset datasets/evaluation/longmemeval_sample.jsonl --format json
python -m memd audit-dataset datasets/evaluation --format markdown --output dataset-audit.md
```

Supported inputs:

- `.jsonl`
- `.json`
- `.csv`
- `.txt`

Pass a directory to audit all supported dataset files inside it.

---

## LongMemEval Guidance

Use the audit to compare:

- `longmemeval_sample.jsonl` — quick usefulness check
- `longmemeval_memories.jsonl` — full converted memory export
- `longmemeval_questions.jsonl` — companion benchmark metadata, not direct memory input

Expected pattern for converted chat datasets:

- high assistant-turn share
- meaningful user facts mixed with ephemeral queries
- elevated Unknown rate relative to product-memory exports
- duplicate content across turns or sessions

If the audit reports high conversational noise or assistant-turn share, filter assistant responses and ephemeral queries before running Mem-D analysis benchmarks.

---

## Success Criteria

The audit should answer:

1. Is this dataset suitable for benchmarking Mem-D?
2. Does it require preprocessing or filtering first?
3. What kinds of low-quality memories dominate the export?
