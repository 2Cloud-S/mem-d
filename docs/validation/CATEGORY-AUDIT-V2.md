# Category Audit V2

Status: Active

Purpose:

Explain why memories become `Unknown` and identify evidence-backed taxonomy blind spots.

This audit is diagnostic only. It does not change categories, add heuristics, alter clustering, or modify memory data.

---

## Outputs

Category Audit V2 adds:

- Unknown rate
- High-confidence Unknown rate
- Category confidence distribution
- Top Unknown causes
- Unknown pattern clusters
- Suggested taxonomy gaps
- Ranked reclassification candidates

---

## Unknown Pattern Clusters

Unknown memories are grouped by recurring diagnostic causes and suggested category mappings.

Each group includes:

- count
- cause
- theme terms
- suggested category
- representative examples
- average suggested mapping confidence

These groups are intended to help decide where taxonomy rules should improve next.

---

## Reclassification Candidates

Candidates are ranked by:

- suggested mapping confidence
- frequency of the recurring Unknown cause

They are review candidates only. Mem-D does not automatically reclassify records.

---

## Success Criteria

A human should be able to answer:

- Why are memories becoming Unknown?
- Which Unknown patterns repeat most often?
- Which taxonomy gaps have the most evidence?
- Which records should be inspected first before adding new rules?
