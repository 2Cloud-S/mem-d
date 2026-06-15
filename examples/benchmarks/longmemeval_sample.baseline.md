# Benchmark Baseline: longmemeval_sample

Reproducible Mem-D benchmark summary. Generated from existing audit, preprocessing, and analysis reports — no additional metrics or intelligence layers.

## Dataset

- Source: `C:\Users\hp\OneDrive\Desktop\Dev-work\mem-d\datasets\evaluation\longmemeval_sample.jsonl`
- Cleaned input: `C:\Users\hp\OneDrive\Desktop\Dev-work\mem-d\examples\benchmarks\longmemeval_sample.cleaned.jsonl`
- Benchmark stem: `longmemeval_sample`

## Input Size

- Raw records: 2690
- Cleaned records: 1134
- Retention after preprocessing: 42.16%
- Records analyzed: 1134

## Meaningful Memory Rate

- Raw audit meaningful rate: 35.5%
- Cleaned audit meaningful rate: 83.42%
- Primary baseline (cleaned audit): 83.42%

## Unknown Rate

- Raw audit: 20.26%
- Cleaned audit: 34.92%
- Analyze pipeline (Unknown category): 34.92%

## Duplicate Rate

- Raw audit duplicate rate: 2.27%
- Cleaned audit duplicate rate: 0.0%
- Analyze pipeline duplicate percentage: 26.72%
- Analyze pipeline removable duplicates: 303

## Compression Opportunity

- Compression opportunity: 26.72%
- Trusted compression opportunity: 3.44%
- Unverified compression opportunity: 23.28%

Compression drivers:
- 361 memories appear in duplicate clusters
- 58 duplicate clusters were detected
- 30 clusters are high-trust automatic consolidation candidates
- 303 records are estimated removable if each cluster keeps one representative
- 39 removable records are trusted

## Category Distribution

| Category | Count |
| --- | ---: |
| Unknown | 396 |
| Preference | 308 |
| Fact | 293 |
| Task | 57 |
| Goal | 48 |
| Relationship | 20 |
| Temporary | 12 |

## Evolution Signals

- Total evolution signals: 12886
- Contradictions: 1
- Preference changes: 273
- Superseded memories: 8712
- Stale memory candidates: 1134
- Status transitions: 2766
- Evolution confidence: 0.6739

## Lifecycle Distribution

| Lifecycle state | Count |
| --- | ---: |
| Superseded | 709 |
| Active | 165 |
| Deprecated | 154 |
| Historical | 87 |
| Temporary | 12 |
| Completed | 7 |

Overall lifecycle confidence: 0.5985

## Insights Summary

- **Review Unknown memories for missed patterns** (high): Sample Unknown records and decide whether to add rules or leave them as edge cases.
- **Review category disagreements inside duplicate clusters** (high): Inspect reclassification candidates, especially Fact vs Preference vs Unknown conflicts; do not change labels automatically.
- **Most compression opportunity is unverified** (high): Treat unverified compression as a review queue, not an automatic action.
- **Review duplicate clusters before cleanup** (medium): Consolidate High-trust clusters first, then inspect unverified clusters.
- **Remove exact duplicate memories first** (medium): Deduplicate exact groups before reviewing semantic near-duplicates.
- **Review cluster quality before trusting compression estimates** (medium): Audit the largest heterogeneous clusters before using them for cleanup.
- **Investigate the largest duplicate cluster** (medium): Open the largest cluster and verify all records share the same meaning.
