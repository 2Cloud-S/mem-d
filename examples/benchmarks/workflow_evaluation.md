# Workflow Evaluation Benchmark

Reproducible Mem-D V0.8 workflow planning evaluation.

## Ground Truth

`tests/fixtures/workflow_gold.json` is the sole workflow correctness authority.

## Summary

| Metric | Value |
| --- | --- |
| Evaluation status | `scored` |
| Gate passed | True |
| Fixture version | `0.8.0` |
| Planner version | `2` |
| Cases | 34 |
| Checkpoints | 117 |

## Quality Metrics

| Metric | Accuracy | Passed | Total |
| --- | ---: | ---: | ---: |
| overallWorkflowAccuracy | 1.0000 | 117 | 117 |
| itemConstructionAccuracy | 1.0000 | 9 | 9 |
| reviewRoutingAccuracy | 1.0000 | 11 | 11 |
| blockerAccuracy | 1.0000 | 12 | 12 |
| operationAccuracy | 1.0000 | 6 | 6 |
| stepOrderingAccuracy | 1.0000 | 4 | 4 |
| aggregateStatusAccuracy | 1.0000 | 44 | 44 |
| summaryConsistencyAccuracy | 1.0000 | 4 | 4 |
| provenanceAccuracy | 1.0000 | 2 | 2 |
| decisionTransitionAccuracy | 1.0000 | 14 | 14 |
| identityDeterminismAccuracy | 1.0000 | 11 | 11 |

## Safety Gates

| Property | Passed | Checks |
| --- | --- | ---: |
| source_report_immutability | True | 34/34 |
| deterministic_planning | True | 3/3 |
| idempotent_repeated_planning | True | 3/3 |
| initial_never_ready | True | 34/34 |
| zero_structural_never_ready | True | 7/7 |
| policy_blocked_remains_blocked | True | 4/4 |
| unresolved_policy_requires_review | True | 2/2 |
| missing_source_action_fails_closed | True | 1/1 |
| keep_never_removes | True | 2/2 |
| merge_keeper_removable_safety | True | 1/1 |
| integrity_suppresses_readiness | True | 5/5 |
| simulation_warnings_visible_scoped | True | 2/2 |
| structural_overlap_conflict_review | True | 1/1 |
| blocked_decisions_atomic | True | 4/4 |
| decision_preserves_steps_operations | True | 6/6 |
| plan_id_stable_across_decisions | True | 9/9 |
| cumulative_decision_fingerprint | True | 1/1 |
| no_effects | True | 48/48 |

## Diagnostic Metrics

`diagnosticOnly: true`; diagnostics do not affect quality metrics or the gate.

```json
{
  "averageStepsPerCase": 0.8529411764705882,
  "averageWorkflowItemsPerCase": 1.1470588235294117,
  "blockerDistribution": {
    "DUPLICATE_REMOVAL_SKIPPED": 1,
    "INPUT_INTEGRITY": 5,
    "MISSING_KEEPER": 1,
    "MISSING_SIMULATION": 12,
    "ORPHAN_MERGE_NO_KEEPER": 1,
    "POLICY_BLOCKED": 5
  },
  "diagnosticOnly": true,
  "integrityBlockedCaseCount": 5,
  "planningModeDistribution": {
    "full": 11,
    "recommendations_only": 23
  },
  "reviewQueueDistribution": {
    "review:conflict": 1,
    "review:general": 8,
    "review:lifecycle": 2,
    "review:low_trust": 1,
    "review:policy": 2,
    "review:simulation_safety": 3,
    "review:unknown_category": 1
  },
  "reviewToStructuralRatio": 1.8,
  "structuralOperationDistribution": {
    "archive": 3,
    "merge": 7,
    "retain": 1,
    "review": 18
  },
  "workflowStatusDistribution": {
    "all_blocked": 2,
    "all_keep": 2,
    "empty": 1,
    "integrity_blocked": 5,
    "mixed_blocked": 1,
    "mixed_blocked_review": 2,
    "proposed": 8,
    "requires_review": 13
  }
}
```

## Case Results

| Case | Passed | Checkpoints | Initial | Final |
| --- | --- | ---: | --- | --- |
| empty_plan | True | 4/4 | `empty` | `empty` |
| all_keep_summary_only | True | 4/4 | `all_keep` | `all_keep` |
| all_keep_items | True | 6/6 | `all_keep` | `all_keep` |
| safe_merge | True | 11/11 | `proposed` | `ready_for_execution` |
| safe_archive | True | 6/6 | `proposed` | `ready_for_execution` |
| review_only | True | 6/6 | `requires_review` | `approved` |
| policy_requires_review | True | 3/3 | `requires_review` | `requires_review` |
| policy_blocked | True | 5/5 | `all_blocked` | `all_blocked` |
| all_deferred | True | 4/4 | `proposed` | `deferred` |
| all_rejected | True | 3/3 | `requires_review` | `rejected` |
| mixed_blocked | True | 2/2 | `mixed_blocked` | `mixed_blocked` |
| mixed_blocked_review | True | 3/3 | `mixed_blocked_review` | `mixed_blocked_review` |
| missing_source_action | True | 2/2 | `integrity_blocked` | `integrity_blocked` |
| unresolved_policy_action | True | 2/2 | `requires_review` | `requires_review` |
| structural_overlap_conflict | True | 4/4 | `requires_review` | `requires_review` |
| scoped_simulation_warning | True | 4/4 | `requires_review` | `requires_review` |
| unscoped_simulation_warning | True | 2/2 | `integrity_blocked` | `integrity_blocked` |
| duplicate_recommendation_normalization | True | 3/3 | `requires_review` | `requires_review` |
| conflicting_duplicate_integrity | True | 2/2 | `integrity_blocked` | `integrity_blocked` |
| review_subtype_matrix_unknown | True | 2/2 | `requires_review` | `requires_review` |
| review_subtype_matrix_lifecycle_lowtrust | True | 2/2 | `requires_review` | `requires_review` |
| review_subtype_matrix_lifecycle_plain | True | 2/2 | `requires_review` | `requires_review` |
| orphan_merge_missing_keeper | True | 5/5 | `integrity_blocked` | `integrity_blocked` |
| missing_simulation | True | 2/2 | `proposed` | `proposed` |
| h1_no_structural_negative | True | 3/3 | `requires_review` | `approved` |
| h2_unapproved_structural_negative | True | 1/1 | `proposed` | `proposed` |
| h3_unresolved_non_structural_negative | True | 3/3 | `requires_review` | `partially_approved` |
| h4_unresolved_review_negative | True | 3/3 | `requires_review` | `partially_approved` |
| h5_blocked_item_negative | True | 1/1 | `all_blocked` | `all_blocked` |
| h6_plan_blocker_negative | True | 1/1 | `integrity_blocked` | `integrity_blocked` |
| h7_recommendations_only_negative | True | 1/1 | `proposed` | `proposed` |
| invalid_decision_atomicity | True | 3/3 | `proposed` | `proposed` |
| multi_call_decision_fingerprint | True | 6/6 | `mixed_blocked_review` | `mixed_blocked` |
| identity_repeated_run | True | 6/6 | `proposed` | `proposed` |

## Failures

No failures.

## Reproduce

```bash
python scripts/run_workflow_evaluation.py
```

## Planning-Only Disclaimer

Workflow evaluation plans and decision transitions only; no workflow action is executed, persisted, scheduled, or externally applied.
