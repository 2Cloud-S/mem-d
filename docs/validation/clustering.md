# Clustering Validation

Status: Active

Purpose:

Measure duplicate-clustering quality objectively before changing the clustering algorithm.

---

## Why this exists

The current clustering engine runs and scales, but correctness must be measured with labelled data.

Manual inspection is useful for debugging, but future improvements need stable metrics:

- Precision
- Recall
- F1
- False positives
- False negatives
- Cluster purity
- Cluster coverage

---

## Validation dataset

Primary fixture:

`datasets/validation/clustering_quality.json`

Each memory may include:

```json
{
  "id": "pref_ts_1",
  "content": "User prefers TypeScript for all new projects.",
  "duplicateGroup": "pref_typescript",
  "duplicateType": "near"
}
```

Rules:

1. Memories with the same `duplicateGroup` are expected duplicates.
2. Memories without `duplicateGroup` are known non-duplicates or distractors.
3. `nonDuplicatePairs` stores explicit hard negatives.

---

## Command

```bash
python -m memd evaluate-clusters datasets/validation/clustering_quality.json
python -m memd evaluate-clusters datasets/validation/clustering_quality.json --format json
python -m memd evaluate-clusters datasets/validation/clustering_quality.json --format markdown --output clustering-eval.md
```

Optional:

```bash
python -m memd evaluate-clusters datasets/validation/clustering_quality.json --threshold 0.80
python -m memd evaluate-clusters datasets/validation/clustering_quality.json --model BAAI/bge-small-en-v1.5
```

Default threshold:

`0.55`

---

## Metrics

Pairwise duplicate decisions are compared against labels.

Precision:

`true positive predicted duplicate pairs / all predicted duplicate pairs`

Recall:

`true positive predicted duplicate pairs / labelled duplicate pairs`

False positives:

Pairs clustered together but not labelled duplicates.

False negatives:

Labelled duplicate pairs that were not clustered together.

Cluster purity:

For each predicted cluster, the dominant labelled group count divided by cluster size, weighted across clusters.

Cluster coverage:

Labelled duplicate memories that appeared in any predicted cluster.

---

## Interpretation

This framework does not improve clustering directly.

It establishes a repeatable scorecard so future changes to:

- embedding model
- similarity threshold
- clustering algorithm
- text normalization

can be compared scientifically.

---

## Current baseline

The first validation baseline used the original token hashing fallback at threshold `0.85`.

| Threshold | Precision | Recall | F1 | Purity | Coverage | False Positives | False Negatives |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.85 | 1.0 | 0.1429 | 0.2501 | 1.0 | 0.1818 | 0 | 6 |

Root cause:

The original fallback represented exact token overlap well but missed near-duplicates where meaning was carried by related lexical forms:

- `dev` vs `development`
- `trace` vs `tracing`
- `cache` vs `caching`
- `cert` vs `certificate`
- `renew` vs `renewal`

---

## Lightweight local fallback improvement

The fallback embedding now remains local and dependency-free but uses:

- token normalization
- small alias mapping
- character n-grams
- token bigrams

No external APIs, hosted services, or model downloads are required.

Measured threshold tradeoff on `clustering_quality.json`:

| Threshold | Precision | Recall | F1 | Purity | Coverage | False Positives | False Negatives |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.85 | 1.0 | 0.1429 | 0.2501 | 1.0 | 0.1818 | 0 | 6 |
| 0.65 | 1.0 | 0.2857 | 0.4444 | 1.0 | 0.3636 | 0 | 5 |
| 0.55 | 1.0 | 0.5714 | 0.7272 | 1.0 | 0.7273 | 0 | 3 |
| 0.50 | 1.0 | 0.7143 | 0.8333 | 1.0 | 0.9091 | 0 | 2 |
| 0.40 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0 | 0 |

Large-dataset clustering volume check on `datasets/memories.json`:

| Threshold | Clusters | Compression Opportunity | Largest Cluster |
| ---: | ---: | ---: | ---: |
| 0.70 | 69 | 28.0% | 197 |
| 0.65 | 98 | 34.2% | 197 |
| 0.60 | 114 | 41.8% | 198 |
| 0.55 | 130 | 49.5% | 288 |
| 0.50 | 130 | 60.0% | 357 |

Decision:

Use `0.55` as the default threshold for the dependency-free fallback.

Reason:

It improves recall and coverage substantially while preserving zero false positives on the labelled validation fixture. Lower thresholds score better on the small fixture, but the 1000-memory dataset shows rapidly increasing cluster size and compression estimates, which may indicate over-clustering.

Tradeoff:

The fallback is still lexical, not truly semantic. It improves related-word matching but does not replace a local embedding model such as BGE or e5 for deeper paraphrases.
