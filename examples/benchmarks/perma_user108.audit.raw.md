# Dataset Quality Audit

Dataset Quality Audit measures memory usefulness for external benchmark datasets. Diagnostic only; it does not modify ingestion or analysis behavior.

## Benchmark Readiness

- Recommended dataset: perma_user108.input.jsonl
- Recommended verdict: poor_fit

## perma_user108.input.jsonl

- Path: `C:\Users\hp\OneDrive\Desktop\Dev-work\mem-d\examples\benchmarks\perma_user108.input.jsonl`
- Kind: memory_export
- Total records: 228
- Estimated meaningful memories: 0 (0.0%)
- Estimated conversational noise: 1 (0.44%)
- Mixed or uncertain: 227
- Average memory length: 136.94 characters
- Unknown rate: 31.14%
- Duplicate rate: 0.0%
- Benchmark verdict: poor_fit
- Benchmark summary: Dataset appears dominated by conversational turns or low-usefulness content and is a weak direct fit for Mem-D memory analysis benchmarks.

Category distribution:
- Task: 117
- Unknown: 71
- Preference: 34
- Fact: 5
- Temporary: 1

Role distribution:
- unknown: 228

Top low-quality causes:

| Cause | Count | % of records |
| --- | ---: | ---: |
| No strong Mem-D category signal | 71 | 31.14% |
| Terse or fragmented content | 1 | 0.44% |

Preprocessing recommendations:
- No major preprocessing blockers detected from usefulness signals.
