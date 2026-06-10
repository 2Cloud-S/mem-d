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
