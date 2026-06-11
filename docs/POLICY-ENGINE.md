# Policy Engine

Status: Active

Purpose:

Apply configurable governance rules to planned actions.

The Policy Engine answers:

> Is this recommended action approved, review-required, or blocked under the selected governance profile?

It does not execute actions, modify memories, delete records, merge records, rewrite categories, or change clustering behavior.

---

## Design

Policy decisions are deterministic and explainable.

Each governance action receives:

- policy decision
- policy profile
- matched rule ID
- policy explanation

Policy decisions are attached to the action plan so downstream systems can audit why an action was allowed, routed to review, or blocked.

---

## Built-In Profiles

### conservative

Approves only the safest high-confidence merge actions.

Low-trust or over-clustered recommendations are blocked.

Most other actions require human review.

### balanced

Default profile.

Approves High-trust safe actions with sufficient confidence.

Blocks low-trust or over-clustered recommendations.

Routes taxonomy, Unknown-category, and uncertain actions to review.

### aggressive

Approves safe actions at a lower confidence threshold.

Still routes uncertain, taxonomy, and Unknown-category actions to review.

Still blocks Low-trust over-clustered groups.

---

## Decisions

### approved

The policy allows the action as an automatically approved recommendation.

Approval is not execution.

### requires_review

The action is useful but requires human or policy-owner review before downstream execution.

### blocked

The action is not permitted under the selected policy profile.

Blocked actions remain visible in reports for auditability.

---

## Pipeline Fit

Current V1 pipeline:

Parser -> Normalizer -> Categorizer -> Embedder -> Similarity -> Clustering -> Metrics -> Validation -> Insights -> Action Planning -> Policy Engine -> Reporting

The Policy Engine is intentionally downstream of Action Planning.

It controls governance readiness, not analysis behavior.

---

## CLI Usage

```bash
memd analyze memory.json --policy balanced
memd analyze memory.json --policy conservative
memd analyze memory.json --policy aggressive
```

If no policy is provided, Mem-D uses `balanced`.

---

## Enterprise Readiness

The Policy Engine provides:

- deterministic decisions
- explicit matched rules
- explainable outcomes
- configurable governance posture
- machine-readable policy summaries
- separation from execution

Future policy engines or execution systems can consume the report output, but execution remains out of scope for V1.
