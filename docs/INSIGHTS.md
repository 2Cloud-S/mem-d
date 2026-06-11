# Insight Engine

Status: Active

Purpose:

Convert existing analysis outputs into ranked, deterministic findings and recommendations.

The Insight Engine answers:

> What should I do next?

It does not change parsing, categorization, embedding, similarity, or clustering behavior.

---

## Design

Insights are rule-based and deterministic.

Each insight includes:

- severity
- explanation
- supporting evidence
- confidence
- estimated impact
- recommended action

Insights are generated from existing outputs:

- category distribution
- duplicate clusters
- exact duplicate groups
- Unknown memory rate
- compression opportunity
- cluster quality validation
- clustering evaluation metrics

---

## Insight Types

### Compression Insights

Triggered by compression opportunity and duplicate counts.

Examples:

- prioritize duplicate cleanup
- remove exact duplicate memories first
- investigate the largest duplicate cluster

### Category Quality Insights

Triggered by Unknown category rate or category imbalance.

Examples:

- review Unknown memories for missed patterns
- inspect dominant category growth

### Cluster Quality Insights

Triggered by possible false-positive clusters.

Examples:

- review low-similarity or mixed-category clusters before acting

### Evaluation Insights

Triggered by clustering validation metrics.

Examples:

- recall gap: precision is high but labelled duplicates are missed
- precision risk: false positives are present
- baseline recorded: evaluation is available for future comparison

---

## Ranking

Insights are sorted by:

1. severity
2. estimated impact
3. confidence
4. stable insight id

Severity order:

`critical > high > medium > low > info`

---

## Tradeoffs

The Insight Engine intentionally does not infer hidden intent with an LLM.

Benefits:

- explainable
- repeatable
- testable
- local-first
- provider-independent

Limitations:

- recommendations are only as good as the metrics and validation evidence
- rules may need tuning as datasets evolve
- insights do not automatically perform cleanup

---

## Report Surfaces

Insights are included in:

- terminal analysis report
- JSON analysis report
- Markdown analysis report
- JSON clustering evaluation report
- Markdown clustering evaluation report
- terminal clustering evaluation report

Generated report files should not be committed.
