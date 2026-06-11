# Action Planning Layer

Status: Active

Purpose:

Convert existing Mem-D analysis outputs into structured, machine-readable governance actions.

The Action Planning Layer answers:

> What should I do next, and why?

It does not execute actions, modify memories, delete records, merge records, rewrite categories, or change clustering behavior.

---

## Design

Actions are deterministic planning artifacts.

Each action includes:

- action ID
- action type
- target
- title
- rationale
- supporting evidence
- trust level
- confidence
- estimated impact
- human approval requirement
- priority
- source signals

The planner consumes evidence already produced by the system:

- ranked insights
- duplicate clusters
- cluster trust scores
- cluster audit contamination and over-clustering diagnostics
- category consistency conflicts
- Unknown category samples

---

## Action Types

### merge_cluster

Generated for High-trust duplicate clusters that are not category-specific preference groups.

These actions are safe consolidation candidates, but they remain recommendations only.

### consolidate_preferences

Generated for High-trust clusters dominated by Preference memories.

Preference consolidation is separated because preference memories are often user-facing and may need stronger downstream policy controls.

### review_cluster

Generated for Medium/Low-trust clusters or clusters with contamination signals.

These actions require human approval.

### review_overclustered_group

Generated when the cluster audit suggests a cluster may contain multiple concepts or broad topical similarity.

### review_category_conflict

Generated when highly similar memories in the same duplicate cluster disagree on category.

This is a taxonomy-quality action, not a clustering action.

### review_unknown_memory

Generated when Unknown-category memories exist.

The target includes a bounded sample of Unknown memory IDs and the total Unknown count.

### ignore_low_value_issue

Generated for low-severity or informational insights.

These are deferred so reports can distinguish immediate governance work from low-priority observations.

---

## Report Grouping

Reports separate actions into:

- Recommended Safe Actions
- Recommended Review Actions
- Deferred / Low-Priority Actions

Safe actions do not require human approval and are backed by High-trust duplicate evidence.

Review actions require human approval because they involve uncertainty, contamination, over-clustering, category disagreement, or Unknown taxonomy findings.

Deferred actions are low-priority observations that do not need immediate work.

---

## Summary Metrics

The action plan includes:

- totalActions
- safeActions
- reviewActions
- estimatedTrustedSavings
- estimatedUnverifiedSavings
- actionsByPriority

Trusted savings come from safe merge/consolidation candidates.

Unverified savings come from review actions where records may be removable only after validation.

---

## Governance Pipeline Fit

Current V1 pipeline:

Parser -> Normalizer -> Categorizer -> Embedder -> Similarity -> Clustering -> Metrics -> Validation -> Insights -> Action Planning -> Policy Engine -> Reporting

The planner is intentionally downstream of validation and insights.

It bridges analysis and future memory lifecycle management while preserving the current V1 scope:

- no MCP
- no SDK
- no dashboard
- no cloud execution
- no memory modification

The Policy Engine can consume the action JSON, but execution is out of scope for V1.
