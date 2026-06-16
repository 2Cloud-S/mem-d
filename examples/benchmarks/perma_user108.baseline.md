# Benchmark Baseline: perma_user108

Reproducible Mem-D benchmark summary. Generated from existing audit, preprocessing, and analysis reports — no additional metrics or intelligence layers.

## Dataset

- Source: `C:\Users\hp\OneDrive\Desktop\Dev-work\mem-d\examples\benchmarks\perma_user108.input.jsonl`
- Cleaned input: `C:\Users\hp\OneDrive\Desktop\Dev-work\mem-d\examples\benchmarks\perma_user108.input.jsonl`
- Benchmark stem: `perma_user108`

## Input Size

- Raw records: 228
- Records analyzed: 228

## Meaningful Memory Rate

- Raw audit meaningful rate: 0.0%
- Cleaned audit meaningful rate: 0.0%
- Primary baseline (cleaned audit): 0.0%

## Unknown Rate

- Raw audit: 31.14%
- Cleaned audit: 31.14%
- Analyze pipeline (Unknown category): 31.14%

## Duplicate Rate

- Raw audit duplicate rate: 0.0%
- Cleaned audit duplicate rate: 0.0%
- Analyze pipeline duplicate percentage: 59.21%
- Analyze pipeline removable duplicates: 135

## Compression Opportunity

- Compression opportunity: 59.21%
- Trusted compression opportunity: 8.77%
- Unverified compression opportunity: 50.44%

Compression drivers:
- 154 memories appear in duplicate clusters
- 19 duplicate clusters were detected
- 13 clusters are high-trust automatic consolidation candidates
- 135 records are estimated removable if each cluster keeps one representative
- 20 removable records are trusted

## Category Distribution

| Category | Count |
| --- | ---: |
| Task | 117 |
| Unknown | 71 |
| Preference | 34 |
| Fact | 5 |
| Temporary | 1 |
| Goal | 0 |
| Relationship | 0 |

## Evolution Signals

- Total evolution signals: 3
- Contradictions: 0
- Preference changes: 0
- Superseded memories: 0
- Stale memory candidates: 3
- Status transitions: 0
- Evolution confidence: 0.6167

## Lifecycle Distribution

| Lifecycle state | Count |
| --- | ---: |
| Temporary | 3 |
| Active | 0 |
| Completed | 0 |
| Deprecated | 0 |
| Historical | 0 |
| Superseded | 0 |

Overall lifecycle confidence: 0.6167

## Insights Summary

- **Review Unknown memories for missed patterns** (high): Sample Unknown records and decide whether to add rules or leave them as edge cases.
- **Prioritize trusted duplicate cleanup** (high): Auto-consolidate only High-trust clusters; manually review Medium and Low-trust clusters.
- **Review category disagreements inside duplicate clusters** (high): Inspect reclassification candidates, especially Fact vs Preference vs Unknown conflicts; do not change labels automatically.
- **Most compression opportunity is unverified** (high): Treat unverified compression as a review queue, not an automatic action.
- **Review cluster quality before trusting compression estimates** (medium): Audit the largest heterogeneous clusters before using them for cleanup.
- **Investigate the largest duplicate cluster** (medium): Open the largest cluster and verify all records share the same meaning.
- **Memory store is dominated by Task records** (low): Review whether this category should have tighter retention or deduplication rules.
