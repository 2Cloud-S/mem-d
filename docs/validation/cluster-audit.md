# Cluster Quality Audit

Status: Active

Purpose:

Validate whether the largest duplicate clusters represent true duplicate groups or broad topical similarity.

This audit does **not** change clustering logic.

---

## What Is Audited

For the top 10 largest clusters, Mem-D reports:

- cluster size
- average similarity
- pairwise similarity distribution
- dominant themes
- representative memories
- category mix
- outlier memories
- concept assessment
- heterogeneity reasons
- contamination score

---

## Why This Matters

Compression estimates assume clusters are valid duplicate groups.

If a large cluster contains multiple unrelated concepts, the compression estimate may be inflated.

The audit helps decide whether downstream recommendations can trust the cluster output.

---

## Heterogeneity Signals

A cluster may be flagged when:

- a large cluster has low median pairwise similarity
- similarity spread is wide
- more than two categories appear in one cluster
- no category dominates at least 75% of the cluster
- few shared terms exist across a large cluster
- one or more memories are low-similarity outliers

---

## Interpretation

`single-concept`

The cluster appears internally coherent enough to inspect as a duplicate group.

`multiple-concepts`

The cluster may be broad topical similarity or chained clustering. Review before using it for cleanup or compression estimates.

---

## Report Locations

JSON:

`validation.clusterQuality.largestClusterAudit`

Markdown:

`Validation Notes → Largest Cluster Audit`

Terminal:

Displays counts of possible over-clustering and contamination candidates.
