# Workflow Benchmark

## Purpose

The workflow benchmark provides independent V0.8 Phase 4 evidence for workflow
planning correctness. It evaluates:

```python
plan_workflows(...)
apply_workflow_decisions(...)
```

It does not execute workflow actions, persist decisions, schedule work, mutate
source memories, or score external datasets.

## Ground Truth Authority

The sole workflow correctness authority is:

```text
tests/fixtures/workflow_gold.json
```

Recommendation gold evaluates recommendation correctness only. Simulation gold
evaluates simulation correctness only. External validation remains non-gating
regression context and does not provide workflow labels.

## Fixture Format

The fixture contains metadata, deterministic builder names, planning options,
initial expectations, decision-stage expectations, identity assertions, safety
expectations, and diagnostic expectations.

Fixture builders construct input `AnalysisReport` objects only. They do not call
`plan_workflows()`, `apply_workflow_decisions()`, production aggregate helpers,
or production routing logic to derive labels.

Review subtype non-vacuity is satisfied only by scored
`review_routing` checkpoints. Metadata-only coverage does not satisfy subtype
coverage. Planner-version-specific reserved subtypes must be listed as explicit
fixture dispositions rather than counted as scored output.

## Checkpoint Accounting

Each quality checkpoint has a canonical tuple:

```json
["caseId", "phase", "checkpointType", "semanticKey"]
```

`checkpointCount` is the count of unique quality checkpoint tuples.
`overallWorkflowAccuracy.total` must equal `checkpointCount`. Safety and
diagnostic checks are excluded from quality denominators.

## Metrics

The benchmark reports eleven release-gating metrics:

- `overallWorkflowAccuracy`
- `itemConstructionAccuracy`
- `reviewRoutingAccuracy`
- `blockerAccuracy`
- `operationAccuracy`
- `stepOrderingAccuracy`
- `aggregateStatusAccuracy`
- `summaryConsistencyAccuracy`
- `provenanceAccuracy`
- `decisionTransitionAccuracy`
- `identityDeterminismAccuracy`

Every quality metric must have a non-zero denominator and equal `1.0` for the
gate to pass.

## Safety Gates

Safety gates are hard-gating and non-vacuous. Each safety result includes
`passed`, `checksPassed`, `checksTotal`, and failures.

The benchmark covers source immutability, decision input plan immutability,
deterministic and idempotent planning, initial-not-ready behavior,
zero-structural readiness prevention, policy and missing-action fail-closed
behavior, keep safety, merge safety, integrity readiness suppression, warning
scope, structural overlap conflict review, decision atomicity, step/operation
preservation, plan ID stability, cumulative decision fingerprints, and bounded
`no_effects`.

The bounded `no_effects` guard is limited to CI-observable boundaries:
network/process attempts and Python-level filesystem writes during pure
evaluator calls. Benchmark artifact writes are performed only by the runner.

## H1-H7 Readiness Validation

The fixture includes a positive `ready_for_execution` case and negative
boundaries for H1-H7:

- H1: structural work exists.
- H2: structural work is eligible and approved.
- H3: non-structural actionable work is resolved.
- H4: no unresolved review remains.
- H5: no item-level blocker remains.
- H6: no plan-level blocker remains.
- H7: planning mode is `full`.

Readiness cannot pass by vacuity.

## Artifact Generation

Artifacts:

```text
examples/benchmarks/workflow_evaluation.json
examples/benchmarks/workflow_evaluation.md
```

Both artifacts are rendered from the same normalized result object and exclude
timestamps, machine-specific paths, external service data, and network-derived
data.

## Reproduce

```bash
python scripts/run_workflow_evaluation.py
```

## Known Limitations

The fixture is intentionally synthetic and architecture-focused. A perfect score
means conformance to V0.8 workflow planning semantics on the labeled fixture; it
is not a claim of production-world operator utility.

Reserved blocker codes `UNSUPPORTED_ACTION` and `STALE_EVIDENCE` are required
absence checks for planner version `"2"` because the current validated planner
does not emit them from production-valid inputs.
