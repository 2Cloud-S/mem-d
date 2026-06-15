# Dataset Quality Audit

Dataset Quality Audit measures memory usefulness for external benchmark datasets. Diagnostic only; it does not modify ingestion or analysis behavior.

## Benchmark Readiness

- Recommended dataset: longmemeval_sample.jsonl
- Recommended verdict: requires_preprocessing

## longmemeval_sample.jsonl

- Path: `C:\Users\hp\OneDrive\Desktop\Dev-work\mem-d\datasets\evaluation\longmemeval_sample.jsonl`
- Kind: memory_export
- Total records: 2690
- Estimated meaningful memories: 955 (35.5%)
- Estimated conversational noise: 1391 (51.71%)
- Mixed or uncertain: 344
- Average memory length: 909.12 characters
- Unknown rate: 20.26%
- Duplicate rate: 2.27%
- Benchmark verdict: requires_preprocessing
- Benchmark summary: Dataset has benchmark potential, but conversational noise or weak memory signals are high enough that filtering is required.

Category distribution:
- Preference: 967
- Fact: 839
- Unknown: 545
- Task: 144
- Goal: 118
- Relationship: 54
- Temporary: 23

Role distribution:
- assistant: 1355
- user: 1335

Top low-quality causes:

| Cause | Count | % of records |
| --- | ---: | ---: |
| Assistant conversational turn | 1355 | 50.37% |
| No strong Mem-D category signal | 545 | 20.26% |
| Assistant generic encouragement or filler | 340 | 12.64% |
| Short user query without durable memory signal | 196 | 7.29% |
| Terse or fragmented content | 82 | 3.05% |
| Exact duplicate normalized content | 61 | 2.27% |
| Assistant instructional or list-style response | 17 | 0.63% |
| Code generation or programming artifact | 15 | 0.56% |
| Puzzle, riddle, or hypothetical scenario | 10 | 0.37% |
| Roleplay, script, or creative writing task | 2 | 0.07% |

Preprocessing recommendations:
- Filter assistant turns before benchmarking durable user memory.
- Remove long instructional assistant list responses.
- Separate ephemeral user questions from durable memory facts.
- Exclude puzzle, roleplay, and creative-writing sessions.
- Exclude code-generation artifacts unless testing technical memory.
- Deduplicate exact normalized content before clustering benchmarks.
