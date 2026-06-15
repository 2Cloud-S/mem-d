# Dataset Quality Audit

Dataset Quality Audit measures memory usefulness for external benchmark datasets. Diagnostic only; it does not modify ingestion or analysis behavior.

## Benchmark Readiness

- Recommended dataset: longmemeval_sample.cleaned.jsonl
- Recommended verdict: suitable_with_filtering

## longmemeval_sample.cleaned.jsonl

- Path: `C:\Users\hp\OneDrive\Desktop\Dev-work\mem-d\examples\benchmarks\longmemeval_sample.cleaned.jsonl`
- Kind: memory_export
- Total records: 1134
- Estimated meaningful memories: 946 (83.42%)
- Estimated conversational noise: 0 (0.0%)
- Mixed or uncertain: 188
- Average memory length: 245.73 characters
- Unknown rate: 34.92%
- Duplicate rate: 0.0%
- Benchmark verdict: suitable_with_filtering
- Benchmark summary: Dataset contains enough likely durable memories for Mem-D benchmarking, but preprocessing or filtering is recommended before analysis.

Category distribution:
- Unknown: 396
- Preference: 308
- Fact: 293
- Task: 57
- Goal: 48
- Relationship: 20
- Temporary: 12

Role distribution:
- user: 1134

Top low-quality causes:

| Cause | Count | % of records |
| --- | ---: | ---: |
| No strong Mem-D category signal | 396 | 34.92% |
| Terse or fragmented content | 38 | 3.35% |
| Short user query without durable memory signal | 21 | 1.85% |

Preprocessing recommendations:
- Separate ephemeral user questions from durable memory facts.
