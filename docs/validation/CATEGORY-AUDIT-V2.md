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
- Taxonomy discovery candidate categories
- Semantic theme analysis for Unknown memories
- Unknown resolution audit

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

## Taxonomy Discovery

Taxonomy Discovery groups Unknown memories into semantic candidate categories.

Each candidate includes:

- label
- memory count
- representative examples
- confidence
- suggested mapping
- issue type
- estimated Unknown-rate reduction

Issue types:

- `classifier_failure`: the memory likely belongs to an existing category, but current heuristics do not capture the shape.
- `taxonomy_gap`: the memory shape may need a new first-class category or explicit product decision.

This section helps decide whether to expand the taxonomy based on repeated evidence from real datasets.

---

## Semantic Theme Analysis

Semantic Theme Analysis groups Unknown memories by meaning rather than lexical structure.

It separates:

- **formatting issues**: terse or fragmented memories that are Unknown because of shape, not missing taxonomy coverage
- **semantic themes**: recurring concepts such as Architecture, Constraint, Principle, Decision, Dependency, Workflow Rule, and Context

Each candidate semantic category includes:

- evidence count
- representative examples
- confidence
- category purity
- suggested mapping
- recurring concepts within the theme

Category purity estimates how consistently memories in a theme share the same primary semantic label and strong theme signals.

This section is diagnostic only. It does not modify categorization or taxonomy.

---

## Unknown Resolution Audit

Unknown Resolution Audit quantifies how much of the Unknown category is caused by classifier failure versus taxonomy gaps.

Every Unknown memory receives:

- a likely resolution type:
  - `classifier_failure`
  - `taxonomy_gap`
  - `unresolved`
- confidence
- rationale
- suggested category when applicable

Aggregate metrics include:

- `classifierFailureCount`
- `taxonomyGapCount`
- `unresolvedCount`
- `estimatedUnknownReduction`

The audit also surfaces:

- top recurring causes with resolution breakdowns
- resolution groups with representative examples

This answers:

"How much of Unknown can be fixed by improving categorization, and how much requires expanding the taxonomy?"

Diagnostic only. It does not change categorization, memory types, clustering, trust scoring, governance, or actions.

---

## Success Criteria

A human should be able to answer:

- Why are memories becoming Unknown?
- Which Unknown patterns repeat most often?
- Which taxonomy gaps have the most evidence?
- Which records should be inspected first before adding new rules?
- Which candidate categories would reduce Unknown rate the most?
