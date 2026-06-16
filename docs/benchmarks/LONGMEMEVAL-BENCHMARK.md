# LongMemEval Benchmark

## Objective

LongMemEval was selected as an external benchmark dataset to test Mem-D on a realistic, conversation-heavy memory export rather than only curated internal fixtures.  
The objective of this benchmark is to produce reproducible evidence for:

- dataset readiness before analysis (`audit-dataset`)
- deterministic preprocessing impact on memory quality
- downstream Mem-D analysis behavior on cleaned memory data

This report is based only on existing benchmark artifacts in `examples/benchmarks/`.

## Dataset Overview

### Raw sample

- Source: `datasets/evaluation/longmemeval_sample.jsonl`
- Total records: 2,690
- Role mix: 1,355 assistant turns, 1,335 user turns
- Initial audit verdict: `requires_preprocessing`

### Cleaned sample

- Output: `examples/benchmarks/longmemeval_sample.cleaned.jsonl`
- Total records: 1,134
- Retention: 42.16%
- Role mix: user-only after preprocessing
- Cleaned audit verdict: `suitable_with_filtering`

### Preprocessing workflow

Applied deterministic filtering (no model-side behavior change):

| Preprocessing action | Records removed |
| --- | ---: |
| Assistant turns | 1,355 |
| Filler records | 185 |
| Puzzle/roleplay/creative content | 3 |
| Exact duplicate records | 13 |
| **Total removed** | **1,556** |

## Raw Dataset Audit Results

| Metric | Raw value |
| --- | ---: |
| Meaningful memory rate | 35.5% (955/2,690) |
| Conversational noise rate | 51.71% (1,391/2,690) |
| Unknown rate | 20.26% |
| Duplicate rate | 2.27% |
| Benchmark suitability verdict | `requires_preprocessing` |

Audit summary: the raw sample has benchmark potential, but conversational noise and weak memory signals are high enough that filtering is required.

## Cleaned Dataset Audit Results

| Metric | Cleaned value |
| --- | ---: |
| Meaningful memory rate | 83.42% (946/1,134) |
| Conversational noise rate | 0.0% (0/1,134) |
| Unknown rate | 34.92% |
| Duplicate rate | 0.0% |
| Benchmark suitability verdict | `suitable_with_filtering` |

Audit summary: the cleaned sample contains enough likely durable memories for Mem-D benchmarking, with additional filtering still recommended.

## Memory Analysis Results

### Category distribution

| Category | Count |
| --- | ---: |
| Unknown | 396 |
| Preference | 308 |
| Fact | 293 |
| Task | 57 |
| Goal | 48 |
| Relationship | 20 |
| Temporary | 12 |

Unknown category share in analyze output: 34.92%.

### Duplicate and compression findings

| Metric | Value |
| --- | ---: |
| Duplicate clusters | 58 |
| Duplicate memories (removable estimate) | 303 |
| Compression opportunity | 26.72% |
| Trusted compression opportunity | 3.44% |
| Unverified compression opportunity | 23.28% |
| High-trust consolidation candidates | 30 clusters |

### Evolution findings

| Evolution signal | Count |
| --- | ---: |
| Total evolution signals | 12,886 |
| Contradictions | 1 |
| Preference changes | 273 |
| Superseded memories | 8,712 |
| Stale memory candidates | 1,134 |
| Status transition candidates | 2,766 |
| Evolution confidence | 0.6739 |

### Lifecycle findings

| Lifecycle state | Count |
| --- | ---: |
| Superseded | 709 |
| Active | 165 |
| Deprecated | 154 |
| Historical | 87 |
| Temporary | 12 |
| Completed | 7 |
| Lifecycle confidence | 0.5985 |

### Governance findings

| Governance metric | Value |
| --- | ---: |
| Total actions | 79 |
| Approved actions | 30 |
| Review-required actions | 21 |
| Blocked actions | 28 |
| Safe actions | 30 |
| Review actions | 49 |
| Estimated trusted savings | 39 |
| Estimated unverified savings | 264 |

Top ranked governance insights:

1. Review Unknown memories for missed patterns.
2. Review category disagreements inside duplicate clusters.
3. Most compression opportunity is unverified.

## Key Observations

1. Preprocessing materially improved benchmark readiness: meaningful memory rate increased from 35.5% to 83.42%, and conversational noise dropped from 51.71% to 0.0%.
2. Unknown share increased after cleaning (20.26% to 34.92%), indicating that assistant-turn removal exposed more user turns without strong V1 category signals.
3. Compression opportunity is significant (26.72%) but mostly unverified (23.28%), so analyze output supports review-first consolidation rather than bulk automatic cleanup.
4. Evolution and lifecycle modules produce strong temporal signal volume on the cleaned export, with superseded and status-transition detections dominating counts.
5. Governance policy behavior is conservative: 28 blocked actions and 21 review-required actions out of 79 total.

## Limitations

1. **LongMemEval is conversation-oriented.** The raw sample contains many conversational assistant turns and interaction artifacts.
2. **Not all turns are durable memories.** Even after preprocessing, some user turns remain ephemeral or weakly structured for long-term memory use.
3. **Unknown rate interpretation requires care.** A higher Unknown rate in cleaned data does not automatically mean lower dataset quality; it can reflect current V1 taxonomy boundaries on realistic user phrasing.
4. **Analyze metrics are diagnostic, not task-accuracy benchmarks.** This report describes memory composition, redundancy, evolution, and governance signals, not MCQ/QA performance.

## Conclusions

Current benchmark evidence supports the following:

- Mem-D can reproducibly qualify a conversation-heavy external dataset for memory analysis via audit + deterministic preprocessing.
- On cleaned LongMemEval, Mem-D produces detailed evidence for composition, duplication/compression, temporal evolution, lifecycle state inference, and governance recommendations.
- The benchmark confirms Mem-D's practical value as an inspection and decision-support layer for memory exports, with explicit trust gating before consolidation.
