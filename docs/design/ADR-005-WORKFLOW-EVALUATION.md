# ADR-005: Workflow Evaluation

## Status

Status: Accepted: 2026-06-23
Target: V0.8 Phase 4
Date: 2026-06-23

This ADR defines evaluation architecture only. It does not implement Phase 4,
create fixtures, create evaluator code, change workflow planning behavior, or
authorize workflow execution.

### Audit disposition

The V0.8 ADR-005 architecture audit returned `NOT APPROVED` with four medium
findings and three low findings. This revision resolves them as follows:

| Finding | Disposition in this ADR |
| --- | --- |
| M1: aggregate-status and blocker-catalog coverage was not normative | Adds mandatory coverage tables for every aggregate status and every V0.8 blocker code. `UNSUPPORTED_ACTION` and `STALE_EVIDENCE` are explicitly dispositioned for planner version `"2"` as reserved/not production-emittable and must not be manufactured with invalid contracts. |
| M2: safety cardinality and effect boundaries were underspecified | Requires every safety property to have `checksTotal >= 1`, `checksPassed`, `passed`, and failure details. Defines bounded CI instrumentation for `no_effects`, immutability, determinism, idempotence, atomic decisions, plan-ID stability, and step/operation preservation. |
| M3: checkpoint key encoding and primary-metric assignment were ambiguous | Defines checkpoint identity as a canonical encoded tuple, validates rendered display IDs separately, rejects collisions and duplicate IDs, and adds a closed `checkpointType -> primaryMetric` mapping. |
| M4: invalid-fixture representation was incomplete | Adds explicit evaluation states. Invalid fixtures return all metric names with `accuracy: null`, `passed: 0`, `total: 0`, fixture failures, and `gatePassed: false`. |
| L1: some controls were implied rather than required | Makes overlap controls, warning-scope unaffected controls, and immutability/effect sentinel checks mandatory. |
| L2: provenance partial versus complete mode was implicit | Adds explicit `matchMode: "partial" | "complete"` for provenance expectations. |
| L3: JSON/Markdown semantic equivalence was unspecified | Requires both artifacts to render from one normalized result object; Markdown checks compare required rendered sections against that source object rather than treating Markdown as ground truth. |

ADR-005 remains Proposed until a new independent architecture audit approves the
hardened text.

## Context

ADR-004 defines a deterministic, read-only workflow planning layer with two
separate transformations:

```python
plan_workflows(...)
apply_workflow_decisions(...)
```

V0.8 Phases 1-3 have implemented and independently verified the contracts,
planner, pipeline attachment, JSON and Markdown serialization, terminal output,
and CLI integration. The implemented planner version is `"2"`. Initial planning
occurs after simulation, and operator decisions are a pure transformation of a
plan rather than execution.

Unit and integration tests establish implementation assurance, but they do not
provide an independent aggregate correctness authority for workflow planning.
Recommendation evaluation cannot fill that role because it ends at
recommendation resolution. Simulation evaluation cannot fill it because it ends
at dry-run store projection. Workflow evaluation must independently determine
whether upstream outputs are packaged into the correct items, review routes,
blockers, operations, ordered steps, aggregate state, evidence, identities, and
decision transitions.

External Hugging Face validation is useful design and regression evidence. It
shows review-heavy and keep-heavy real-data postures, but it has no labeled
workflow outcomes and therefore cannot score workflow correctness.

The current unrelated repository baselines remain outside this ADR: the missing
`tests/fixtures/memories.txt`, four existing E501 findings in `memd/reports.py`,
the cosmetic singular grammar issue in Markdown truncation, and digest evidence
references for conflicting duplicate payloads.

## Decision

Mem-D will add an independent, fixture-driven workflow evaluation layer in V0.8
Phase 4. It will evaluate both workflow transformations separately:

1. Initial planning evaluation invokes `plan_workflows()` and evaluates only
   planner-generated state. Every item must have operator status `none`,
   `decisionsFingerprint` must be empty, and the plan must never be
   `ready_for_execution`.
2. Decision application evaluation starts from a validated initial plan, invokes
   `apply_workflow_decisions()` with labeled decision batches, and evaluates
   transitions, cumulative operator state, aggregate status, identity stability,
   and preservation invariants.

Workflow correctness means exact conformance to ADR-004 and the implemented V0.8
contracts for a labeled input: correct construction, routing, blocking,
operation intent, ordering, status derivation, summary, provenance, identity
relationships, and decision transitions. It does not mean that executing the
plan would improve a memory store, that an operator agrees with a recommendation,
or that any action has occurred.

The benchmark gate passes only when:

```text
evaluationStatus == scored
every quality metric == 1.0
every safety property passes
failures == []
gatePassed == true
```

Diagnostics cannot rescue a quality, fixture, artifact, evaluator, or safety
failure.

## Goals and Non-Goals

### Goals

- Define one exclusive workflow-correctness authority.
- Define exact, auditable checkpoint formulas without denominator inflation.
- Evaluate item construction, review routing, blockers, operations, steps,
  aggregate status, summary, provenance, identities, and decisions.
- Validate the H1-H7 readiness boundary with non-vacuous positive and negative
  controls.
- Make every safety invariant a hard release gate with non-zero observations.
- Produce deterministic, reproducible JSON and Markdown evidence with no network
  dependency.
- Preserve separate metric namespaces for recommendation, simulation, and
  workflow evaluation.

### Non-Goals

Workflow evaluation does not evaluate or introduce:

- action execution or memory mutation;
- persistence of plans or decisions;
- scheduling, retries, rollback, or background work;
- file writes by the planner or decision transformer;
- external side effects or external orchestration;
- interactive or UI approval workflows;
- recommendation correctness, simulation correctness, or external-data accuracy;
- threshold tuning or planner behavior changes during evaluation.

The future benchmark runner may write its requested benchmark artifacts under
`examples/benchmarks/`. That is evaluator output, not planner behavior or
workflow execution.

## Ground-Truth Authority

`tests/fixtures/workflow_gold.json` is the sole authority for workflow planning
correctness.

Authority is deliberately separated by layer:

| Authority | Evaluates | Does not evaluate |
| --- | --- | --- |
| `tests/fixtures/recommendation_gold.json` | Recommendation resolution | Workflow planning |
| `tests/fixtures/simulation_gold.json` | Simulation projection | Workflow planning |
| `tests/fixtures/workflow_gold.json` | Workflow planning and decision application | Recommendation or simulation quality |

Additional evidence has narrower roles:

- Existing unit and integration tests are implementation assurance, not gold
  correctness.
- External Hugging Face validation is non-gating regression and limitation
  evidence, not workflow ground truth.
- Generated benchmark JSON and Markdown report results; they are not labels and
  must never be read back as expected outcomes.
- ADR-004 and the workflow contracts define semantics. The gold fixture encodes
  focused examples of those semantics. A disputed label requires explicit
  architecture disposition, not silent fixture adjustment.

## Evaluation Scope

The evaluation layer covers:

- workflow item construction;
- item action and planner status;
- review requirements, review subtypes, primary review queues, and secondary
  review queues;
- policy decision preservation and aggregation;
- blocker construction, blocker scope, and blocker references;
- structured operations;
- step ordering, sequence, membership, and dependencies;
- aggregate status and H1-H7 readiness;
- summary counts and structural delta;
- evidence and provenance completeness;
- deterministic plan, item, blocker, and step identities;
- decision transitions and cumulative `decisionsFingerprint`;
- safety invariants.

It excludes action execution, persistence, scheduling, retries, rollback,
external side effects, and approval UX.

## Gold Fixture Schema

The fixture has a top-level `fixtureVersion`, an optional human-readable
`description`, and `cases`. Each case has this conceptual shape:

```json
{
  "caseId": "safe_merge",
  "description": "Trusted merge with keeper and removable member",
  "input": {
    "builder": "safe_merge",
    "overrides": {}
  },
  "planningOptions": {"includeKeep": false},
  "operatorDecisions": [
    {"batchId": "approve_merge", "decisions": []}
  ],
  "expected": {
    "initial": {},
    "decisionStages": [],
    "identityAssertions": [],
    "safetyProperties": [],
    "diagnostics": {}
  }
}
```

### Required exact fields

Every case requires:

- unique `caseId` and non-empty `description`;
- deterministic input report specification;
- explicit `planningOptions`;
- `expected.initial` with expected workflow items, review routes, blockers,
  operations, step order and dependencies, aggregate status, summary, and
  provenance expectations relevant to the case;
- expected identity relations;
- expected safety properties.

Every decision case additionally requires ordered operator decision batches and
one expected transition stage per batch. A stage identifies the prior plan, the
decision batch, expected resulting operator states, expected aggregate status,
expected fingerprint relationship, and any expected unchanged structures.
Expected atomic failure stages specify the exception category and unchanged-plan
assertion.

Exact expected structures use stable semantic keys such as recommendation IDs,
memory IDs, blocker codes/scopes, and operation contents. They do not use array
positions as identity.

### Optional expected fields and partial blocks

A case may omit dimensions that it is not designed to label. Omission means "not
a quality checkpoint," never "accept any value" for a safety invariant.

Partial expected blocks are allowed only when the expanded fixture schema
explicitly declares:

- the expected block path;
- `matchMode`;
- the checkpoint type;
- the primary metric;
- the fields compared;
- whether unexpected sibling fields are ignored or rejected.

Unknown expected fields fail fixture validation before scoring. A partial block
cannot weaken any safety gate, non-vacuity rule, aggregate-status expectation, or
identity relation.

### Provenance match modes

Every provenance expectation must declare:

```json
{"matchMode": "partial"}
```

or:

```json
{"matchMode": "complete"}
```

`partial` compares only the labeled provenance fields and still requires all
labeled references to resolve. `complete` requires exact closure: every expected
plan and item evidence reference is present, no unexpected provenance reference
is present, item evidence is a subset of plan evidence, and warning scope is
preserved. Dedicated provenance closure cases default to `complete`.

### Relational identity assertions

Identity expectations should normally be relations rather than literal hashes:

- `isLowercaseSha256(path)`;
- `equal(runA.path, runB.path)` for identical input;
- `notEqual(base.path, changed.path)` for safety-relevant changes;
- `equal(ordered.path, permuted.path)` for canonically unordered input;
- `equal(initial.workflowPlanId, decided.workflowPlanId)`;
- `notEqual(stage1.decisionsFingerprint, stage2.decisionsFingerprint)` when the
  cumulative operator state changes.

Literal complete hashes are permitted only when the case documents a stability
reason, such as detecting an intentional canonicalization contract change across
planner versions.

### Diagnostic-only expectations

The optional `expected.diagnostics` block may label expected distribution buckets
for artifact tests. Its checkpoints are excluded from every quality denominator,
from `checkpointCount`, and from `gatePassed`.

### Deterministic fixture builders

The JSON fixture should name small, reviewed structured builders plus explicit
overrides rather than duplicate full `AnalysisReport` payloads. Builders must be
pure, local, versioned with the evaluator, and deterministic. The expanded input
must be available in failure output or reproducible from `caseId`, fixture
version, builder name, and overrides.

Builders may construct input `AnalysisReport` objects only. They must not:

- call `plan_workflows()` to generate expected values;
- call `apply_workflow_decisions()` to generate expected values;
- derive expectations from actual planner output;
- compute expected aggregate statuses using production helpers;
- compute expected routing using production planner logic;
- import committed benchmark artifacts as labels;
- import evaluator comparison helpers to synthesize expected structures.

Builders may compute stable IDs only when the expectation is explicitly defined
as relational or generated by this ADR. Builders must not bypass production
contracts with invalid enum values, `model_construct()` shortcuts, or other
invalid objects to manufacture planner outputs.

### Normative fixture coverage matrix

The initial fixture should remain readable, approximately 15-20 focused cases,
but the following coverage is mandatory. Cases may cover multiple rows.

| Coverage area | Mandatory coverage |
| --- | --- |
| Plan archetypes | Empty plan, all-keep plan, review-only plan, all-deferred plan, all-rejected plan, integrity-blocked plan, mixed-blocked plan, mixed-blocked-review plan, and ready-for-execution positive case |
| Structural actions | Safe merge, safe archive, keeper/removable validation, archive target validation, and keep-never-removes validation |
| Policy states | Approved policy, requires-review policy, blocked policy, unresolved existing policy action, and missing source action |
| Review routing | Every review subtype and every primary queue at least once |
| Conflicts | Recommendation conflict and archive/merge structural overlap conflict, with an unrelated unaffected control item |
| Simulation warnings | Recommendation-scoped warning, memory-scoped warning, unscoped warning, and unrelated-item unaffected control |
| Missing inputs | Missing simulation, missing keeper, and orphan merge warning |
| Duplicates | Byte-equivalent duplicate recommendation normalization and conflicting duplicate recommendation integrity case |
| Integrity | Plan-level input integrity blocker and evidence closure |
| Decisions | Partial approval, complete structural approval, all rejected, all deferred, review acknowledgment, invalid batch atomicity, and multi-call cumulative fingerprint |
| Readiness | H1-H7 negative boundary controls and at least one positive `ready_for_execution` control |
| Identity | Repeated planning, reordered input invariance, safety-relevant mutation inequality, stable plan ID across decisions, and cumulative decision fingerprint changes |

### Aggregate-status coverage

Every ADR-004 aggregate status must have at least one exact
`aggregate_status` checkpoint unless this table explicitly defers it. No
aggregate status is deferred for V0.8 Phase 4.

| Aggregate status | Mandatory fixture pattern |
| --- | --- |
| `integrity_blocked` | Input integrity failure, missing source action, unscoped duplicate-removal warning, or conflicting duplicate recommendation |
| `empty` | No workflow items after planning |
| `all_keep` | All items are keep/retain-only work |
| `all_blocked` | All actionable items are blocked |
| `mixed_blocked_review` | At least one blocked item and at least one unresolved review item |
| `mixed_blocked` | At least one blocked item and at least one non-review non-blocked item |
| `rejected` | All actionable items rejected after decisions |
| `deferred` | All actionable items deferred after decisions |
| `ready_for_execution` | Approved eligible structural work in full planning mode with H1-H7 all true |
| `partially_approved` | Some approved structural work remains while another actionable item is unresolved or not terminal |
| `approved` | All actionable items approved but readiness is false because no executable structural chain exists |
| `requires_review` | At least one unresolved review item and no earlier aggregate status applies |
| `proposed` | Proposed actionable work with no review, blocker, terminal decision, or readiness condition applying |

### Blocker-code coverage

Every V0.8 blocker code must be covered or explicitly dispositioned below.
Planner version `"2"` must not manufacture reserved blockers through invalid
inputs.

| Blocker code | V0.8 disposition | Mandatory evaluation treatment |
| --- | --- | --- |
| `POLICY_BLOCKED` | Production-positive | At least one positive blocker checkpoint and one decision-atomicity safety check |
| `MISSING_SIMULATION` | Production-positive | At least one positive blocker checkpoint in degraded/recommendations-only planning |
| `MISSING_KEEPER` | Production-positive | At least one positive blocker checkpoint on merge without keeper evidence |
| `ORPHAN_MERGE_NO_KEEPER` | Production-positive | At least one positive blocker checkpoint for orphan merge warning |
| `DUPLICATE_REMOVAL_SKIPPED` | Production-positive | At least one recommendation-scoped, memory-scoped, and unscoped coverage path |
| `INPUT_INTEGRITY` | Production-positive | At least one plan-level integrity blocker and readiness suppression check |
| `UNSUPPORTED_ACTION` | Reserved/not production-emittable with closed V0.8 action enum | Required absence check; no invalid enum/model bypass; if ADR-004 later makes it reachable, this row must become production-positive before acceptance of that change |
| `STALE_EVIDENCE` | Reserved/not production-emittable in planner version `"2"` | Required absence check; no synthetic planner output; if a future planner emits it, fixture, metrics, and ADR expectations must be reviewed together |

### Review subtype and queue coverage

Every V0.8 review subtype and every primary queue must appear at least once in a
`review_routing` checkpoint. The expanded fixture must fail validation if any
listed subtype or queue is absent.

| Coverage kind | Required values |
| --- | --- |
| Review subtypes | General, unknown category, low trust, lifecycle, lifecycle alternate, lifecycle mixed, conflict, policy review, simulation safety, missing simulation, and warning-related review subtypes defined by the V0.8 contracts |
| Primary queues | General review, unknown category, low trust, lifecycle, conflict, policy, and simulation safety queues defined by the V0.8 routing table |

If the exact enum spelling changes in contracts, the fixture validator must read
the contract enum and fail until this table and the fixture are updated together.

### Focused case inventory

The recommended initial fixture inventory is:

| Case | Required coverage |
| --- | --- |
| 1. `empty_workflow` | Empty aggregate; zero structural items; not ready |
| 2. `all_keep_modes` | All keep with `includeKeep` false and true; retain only; no removal |
| 3. `safe_merge` | Keeper/removable roles, merge operation, dependencies, complete structural approval |
| 4. `safe_archive` | Archive target, operation, approval, ready boundary |
| 5. `review_routing_matrix` | General, unknown category, low trust, lifecycle, lifecycle alternate, lifecycle mixed |
| 6. `defer_and_non_structural_boundaries` | Defer; all deferred; all rejected; approved non-structural work; never ready without structural work |
| 7. `policy_matrix` | Approved, requires review, blocked, unresolved policy action |
| 8. `missing_source_action` | Missing action reference fails closed and differs from unresolved policy |
| 9. `structural_conflict_overlap` | Recommendation conflict and archive/merge memory overlap route to conflict review, plus non-overlap and unrelated-item controls |
| 10. `missing_simulation_and_keeper` | Recommendations-only mode, missing simulation, missing keeper, orphan merge warning |
| 11. `duplicate_removal_warning_scopes` | Warning scoped by recommendation, by memory, unscoped warning integrity failure, and unrelated-item controls |
| 12. `duplicate_recommendation_ids` | Byte-equivalent collapse and conflicting variants with digest evidence refs |
| 13. `integrity_blocked_workflow` | Input integrity blocker, zero structural readiness, evidence closure |
| 14. `mixed_blocked_aggregates` | All blocked, mixed blocked, mixed blocked review, policy-block preservation |
| 15. `partial_approval` | Approved structural plus unresolved item; `partially_approved` |
| 16. `decision_terminal_states` | Complete structural approval, all rejected, all deferred, review acknowledgment semantics |
| 17. `h1_h7_boundary_matrix` | One positive and one negative perturbation for every H1-H7 predicate |
| 18. `identity_and_order_invariance` | Repeated planning, reordered inputs, safety-relevant mutations, cumulative multi-call decisions |

If implementation planning cannot retain auditability with 18 composite cases, it
may split matrices into 15-20 readable cases. It may not drop a mandatory
coverage dimension.

## Quality Metrics

### Common metric contract

For metric `M`, let `C_M` be the set of quality checkpoint encoded tuples whose
primary metric is `M`:

```text
M.accuracy = count(c in C_M where c passed) / count(C_M)
```

Every quality metric denominator must be greater than zero in a valid gold
fixture. A zero denominator is a fixture-validation failure before scoring. It is
never reported as `1.0`, never omitted, and never repaired by diagnostics.

For `evaluationStatus == scored`, every metric reports:

```json
{"accuracy": 1.0, "passed": 10, "total": 10}
```

For `evaluationStatus == fixture_invalid` or `evaluator_error`, every metric
name is still present and reports:

```json
{"accuracy": null, "passed": 0, "total": 0}
```

For scored failures, metrics report actual passed and total counts. All
comparisons are exact after canonical normalization defined by this ADR.

### Required failure record

Every failed checkpoint emits at least:

```text
kind
caseId
checkpointId
checkpointTuple
checkpointType
primaryMetric
phase
semanticKey
expected
actual
message
```

`phase` is `initial` or a deterministic decision-stage ID. Large values may be
represented by canonical digests plus a bounded readable diff, provided the
failure remains reproducible from the fixture and source code.

### Metric denominator table

| Metric | Exact checkpoint source | Denominator construction | Numerator construction | Zero denominator | Required non-zero | Phase scored | Partial blocks | Failure recording |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `overallWorkflowAccuracy` | All expanded quality checkpoints from every primary metric | Count of unique quality checkpoint encoded tuples; safety and diagnostics excluded | Count of those unique tuples whose assigned primary checkpoint passed | Fixture invalid before scoring | Yes; `overallWorkflowAccuracy.total == checkpointCount` | Initial and decision | Inherits each checkpoint's rule | One failure per failed primary checkpoint |
| `itemConstructionAccuracy` | `expected.initial.items` and labeled decision-stage item-state expectations with `checkpointType: item_construction` | One checkpoint per semantic item construction obligation, including expected presence or absence | Passed when the complete labeled item obligation matches exactly | Fixture invalid | Yes | Initial and decision when item operator state is labeled | Allowed only for schema-declared item fields; safety-relevant fields may not be partial | Exact item failure with item semantic key |
| `reviewRoutingAccuracy` | `expected.*.reviewRoutes` with `checkpointType: review_routing` | One checkpoint per item route obligation | Passed when required flag, subtype set, primary queue, complete queue refs, and labeled escalation signals match | Fixture invalid | Yes | Initial and decision if route preservation is labeled | No partial route credit; route is one composite obligation | Exact route failure with route semantic key |
| `blockerAccuracy` | `expected.*.blockers` and required absence entries with `checkpointType: blocker` | One checkpoint per expected blocker presence or required absence | Passed when code, scope, source, memory/recommendation refs, overridability, item links, and message if labeled match | Fixture invalid | Yes | Initial and decision if blocker preservation is labeled | Message may be omitted; structured blocker fields may not be partial unless schema-declared | Exact blocker failure, including absent/unexpected distinction |
| `operationAccuracy` | `expected.*.operations` with `checkpointType: operation` | One checkpoint per complete structured operation obligation | Passed when operation type, keeper, removables, archive targets, review targets, recommendation IDs, and forbidden-field emptiness match | Fixture invalid | Yes | Initial and decision preservation | No partial operation credit | Exact operation failure with canonical operation key |
| `stepOrderingAccuracy` | `expected.*.steps` with `checkpointType: step_ordering` | One checkpoint per semantic ordered step list and dependency graph for a plan or item scope | Passed when semantic step keys, gap-free sequence, membership, and exact dependency edge set match | Fixture invalid | Yes | Initial and decision preservation | No; order/dependency graph is atomic per scope | Exact step-order failure with expected/actual ordered keys |
| `aggregateStatusAccuracy` | `expected.*.aggregateStatus` with `checkpointType: aggregate_status` | One checkpoint per initial plan or decision-stage aggregate expectation | Passed when aggregate enum matches exactly | Fixture invalid | Yes | Initial and decision | No | Exact aggregate failure with stage key |
| `summaryConsistencyAccuracy` | `expected.*.summary` with `checkpointType: summary_consistency` | One checkpoint per full summary expectation and recomputation scope | Passed when full count maps, totals, queue counts, blocker count, keep count, structural delta, and recomputation from plan contents match | Fixture invalid | Yes | Initial and decision | No for count maps in labeled summary blocks | Exact summary failure plus recomputation mismatch if applicable |
| `provenanceAccuracy` | `expected.*.provenance` with `checkpointType: provenance` | One checkpoint per provenance expectation block | Passed according to declared `matchMode`; all refs resolve, item refs are scoped, warning scope is preserved | Fixture invalid | Yes | Initial and decision if provenance preservation is labeled | Yes only when `matchMode: partial`; `complete` rejects unexpected provenance | Exact provenance failure with match mode |
| `decisionTransitionAccuracy` | `expected.decisionStages` transition blocks with `checkpointType: decision_transition` | One checkpoint per valid transition or expected atomic-error stage | Passed when changed/unchanged operator states, planner status, aggregate status, atomic error outcome, plan immutability, preserved structures, and cumulative resulting decision state match | Fixture invalid | Yes | Decision only | No; a transition stage is atomic | Exact transition failure with batch/stage key |
| `identityDeterminismAccuracy` | `expected.identityAssertions` with `checkpointType: identity` | One checkpoint per explicit equality, inequality, shape, order-invariance, mutation, plan-ID, or fingerprint relation | Passed when the relation evaluates exactly | Fixture invalid | Yes | Initial and decision | No | Exact relation failure with compared paths and relation |

An atomic expected object counts as one checkpoint only when partial correctness
would not be independently meaningful. For example, a complete operation is one
checkpoint; it does not earn partial credit for a correct keeper with incorrect
removables. Review routing uses one checkpoint per item route because primary
and secondary queues jointly define the route.

Every dimension metric is release-gating. Safety properties are evaluated
separately and do not enter quality numerators or denominators.

## Unique Checkpoint Accounting

### Canonical identity

Each quality checkpoint has one canonical encoded tuple:

```json
["caseId", "phase", "checkpointType", "semanticKey"]
```

The encoded tuple is serialized using canonical JSON:

- UTF-8;
- array of exactly four strings;
- no insignificant whitespace;
- object key sorting where objects appear inside a semantic key payload;
- JSON string escaping for all separators and control characters.

The human-readable display ID may render the same tuple as:

```text
{caseId}::{phase}::{checkpointType}::{semanticKey}
```

The rendered ID is for reports only. The canonical JSON tuple is the identity
used for duplicate detection and counting.

### Component rules

- `caseId` must be a fixture-declared stable string.
- `phase` must be `initial` or a fixture-declared decision-stage ID such as
  `after_batch_1`.
- `checkpointType` must be in the closed mapping below.
- `semanticKey` must be deterministic fixture data. It may include structured
  JSON rendered canonically, but it must not include generated planner IDs as
  the only distinguishing element.

The fixture validator rejects:

- duplicate canonical encoded tuples;
- duplicate rendered display IDs;
- unknown checkpoint types;
- checkpoint types missing a primary metric;
- any checkpoint assigned to more than one primary metric;
- semantic keys that cannot be reproduced before planner execution;
- run-dependent hidden checkpoints added by evaluator code.

### Closed primary-metric mapping

| Checkpoint type | Primary metric |
| --- | --- |
| `item_construction` | `itemConstructionAccuracy` |
| `review_routing` | `reviewRoutingAccuracy` |
| `blocker` | `blockerAccuracy` |
| `operation` | `operationAccuracy` |
| `step_ordering` | `stepOrderingAccuracy` |
| `aggregate_status` | `aggregateStatusAccuracy` |
| `summary_consistency` | `summaryConsistencyAccuracy` |
| `provenance` | `provenanceAccuracy` |
| `decision_transition` | `decisionTransitionAccuracy` |
| `identity` | `identityDeterminismAccuracy` |

`overallWorkflowAccuracy` has no direct checkpoint type. It is calculated from
the set union of all quality checkpoints assigned to the ten dimension metrics.

### Overall accounting

```text
checkpointCount = count(unique quality checkpoint encoded tuples)
overallWorkflowAccuracy.total == checkpointCount
overallWorkflowAccuracy.passed == count(unique passing quality checkpoint encoded tuples)
```

Safety checks use a separate namespace, such as:

```json
["caseId", "phase", "safety", "property"]
```

Safety checks never enter `checkpointCount`, `overallWorkflowAccuracy`, or any
dimension metric denominator. Diagnostic metrics are likewise excluded from all
quality denominators.

## Exactness and Identity Validation

### Exact comparison

The following are compared exactly:

- actions, planner/operator statuses, policy decisions, and queues;
- blocker codes, scopes, sources, overridability, and references;
- operation targets and forbidden empty fields;
- semantic step order, membership, and dependencies;
- evidence and simulation references;
- all summary counts and `estimatedStructuralDelta`;
- aggregate status and decision results.

Collections whose contract is order-insensitive are normalized by sorting their
canonical semantic values before comparison. Step order and dependency direction
are semantic and are never sorted away. No float tolerance is introduced because
workflow outputs under evaluation are structurally exact. If a future workflow
contract adds floats, a later ADR amendment must define their semantics before
they can become quality checkpoints.

Unexpected elements fail exact complete-collection checkpoints. Partial expected
blocks compare only schema-allowlisted fields, but safety checks still enforce
global invariants.

### Generated identity

Generated IDs are validated primarily by relations:

- every expected hash-shaped ID is lowercase hexadecimal with exactly 64
  characters;
- identical reports and options produce byte-identical initial plans and equal
  IDs;
- canonical reordering of unordered upstream collections does not change IDs;
- safety-relevant changes to memory content, recommendation semantics,
  resolutions, policy, simulation events/warnings, options, or planner version
  change the relevant plan identity;
- byte-equivalent duplicate recommendations collapse deterministically;
- conflicting duplicate recommendations fail closed and retain deterministic
  digest evidence references;
- `workflowPlanId` does not change when decisions are applied;
- `decisionsFingerprint` is empty on an initial plan;
- `decisionsFingerprint` represents the cumulative resulting operator state of
  all items, is stable on repeated equivalent application, and changes whenever
  that cumulative state changes.

Decision batches are evaluated sequentially as well as independently. The
fingerprint after batch two is compared to the complete resulting item state,
not merely to batch two's input records.

## Safety Gates

Safety evaluation is independent of quality scoring. Every property below is a
hard gate. One failure makes `gatePassed == false` regardless of metric values.

Each safety property result must contain:

```json
{
  "passed": true,
  "checksPassed": 1,
  "checksTotal": 1,
  "failures": []
}
```

`checksTotal` must be at least `1` for every safety property. A missing property,
zero checks, skipped checks, or an unexecuted precondition is a fixture or
evaluator failure before the gate can pass.

| Safety property | Required assertion | Required instrumentation or control |
| --- | --- | --- |
| `source_report_immutability` | Canonical source `AnalysisReport` is unchanged after planning and decision evaluation | Snapshot source report, memories, recommendations, simulation report, policy/action data before and after; include a harness self-test or sentinel proving mutation would be detected |
| `deterministic_planning` | Identical input and options produce byte-identical initial plans and IDs | Run at least two fresh equivalent inputs; compare canonical serialized outputs |
| `idempotent_repeated_planning` | Repeated planning has no accumulated state and yields the same result | Re-run in the same process on fresh equivalent source objects; result must equal first run |
| `initial_never_ready` | Initial plan is never `ready_for_execution`; planner status is initial, operator statuses are none, fingerprint empty | Check every initial plan, including structurally eligible cases |
| `zero_structural_never_ready` | Empty, all-keep, review-only, all-rejected, and all-deferred zero-structural plans cannot become ready | Include zero-structural negative cases and one structural positive control |
| `policy_blocked_remains_blocked` | Policy-blocked items retain a non-overridable blocker and cannot become structurally eligible | Include attempted decision on policy-blocked item and approved-policy control |
| `unresolved_policy_requires_review` | Existing source actions with unresolved policy differ from missing actions and route to review | Include unresolved existing source action and missing-action contrast |
| `missing_source_action_fails_closed` | Missing referenced actions produce integrity blocking and no structural readiness | Include missing source action with integrity blocker and no structural steps |
| `keep_never_removes` | Keep items never contain merge/archive removal intent or become eligible | Include both `includeKeep` modes and merge/archive controls |
| `merge_keeper_removable_safety` | Merge has exactly one keeper, at least one distinct removable, and neither archive nor review targets | Include valid merge and missing-keeper/orphan controls |
| `integrity_suppresses_readiness` | Any input integrity failure yields `integrity_blocked`, no executable structural chain, and no readiness | Include equivalent valid structural control where feasible |
| `simulation_warnings_visible_scoped` | Warnings remain visible; recommendation-scoped and memory-scoped warnings affect only matching items; unscoped duplicate-removal warning fails closed | Include unrelated-item unaffected control for scoped warnings |
| `structural_overlap_conflict_review` | Archive/merge overlap routes implicated items to conflict review and withholds their structural steps | Include non-overlap control and unrelated structural item that remains unaffected |
| `blocked_decisions_atomic` | Any decision batch targeting a blocked or non-overridable item fails wholly and leaves the plan byte-identical | Include mixed batch with at least one otherwise valid decision plus one blocked target |
| `decision_preserves_steps_operations` | Decision application changes operator-derived fields only; step identities, order, dependencies, and operations are unchanged | Compare canonical pre/post steps and operations after a valid state-changing decision |
| `plan_id_stable_across_decisions` | `workflowPlanId` is unchanged by every valid or rejected decision application | Compare initial, valid decision, and atomic-error stages |
| `cumulative_decision_fingerprint` | Fingerprint exactly represents cumulative resulting operator state and is order-independent for equivalent decision sets | Include at least one multi-call decision case and an equivalent cumulative-state comparison |
| `no_effects` | Planning and decisions perform no execution, persistence, source/file writes, network calls, or external effects within the bounded CI harness | Instrument planner/decision call boundary for filesystem writes, network/socket calls, subprocess/process launches, action execution APIs, persistence/scheduling APIs, and source object mutation |

### Bounded `no_effects` scope

`no_effects` is a bounded CI assertion, not a claim about every conceivable
operating-system side effect. The required boundary is the execution of
`plan_workflows()` and `apply_workflow_decisions()`.

Within that boundary:

- no filesystem writes are allowed;
- no network or socket calls are allowed;
- no subprocess or process-launch calls are allowed;
- no action execution APIs may be called;
- no persistence or scheduling APIs may be called;
- no input `AnalysisReport`, source memories, recommendations, simulation
  report, policy data, or action data may be mutated.

The evaluation runner may write only its benchmark artifacts under
`examples/benchmarks/`, and only after evaluation has produced the normalized
result. Artifact writes are outside the planner/decision call boundary.

## H1-H7 Readiness Boundary

Readiness cannot pass by vacuity. The fixture must include at least one positive
`ready_for_execution` case where H1-H7 are all true and at least one isolated
negative-control case for every gate.

| Gate | Field or condition checked | Required fixture pattern | Why violation prevents readiness | Failure record |
| --- | --- | --- | --- | --- |
| H1 | Plan contains at least one structural item with executable structural operation | Start from a ready structural plan, then remove or suppress all structural items while resolving non-structural work | No structural work exists to execute | `safety` and `aggregate_status` failure identifying missing structural item |
| H2 | Every structural item is eligible and approved | Leave exactly one structural item unapproved or ineligible while other gates remain true | Structural work has not been approved or is not safe to hand off | Failure identifies the structural item and unmet eligibility/approval field |
| H3 | Every non-structural actionable item is operator-resolved | Leave one review/defer/keep-style actionable item unresolved while structural work is approved | Non-structural actionable work remains pending | Failure identifies unresolved non-structural item |
| H4 | No unresolved review remains | Add or preserve one item requiring review without acknowledgment/resolution | Human review remains open | Failure identifies review subtype and queue |
| H5 | No blocked item remains | Add one item-level blocker without adding a plan-level blocker where production construction allows isolation | Blocked work cannot be handed off | Failure identifies blocked item and blocker code |
| H6 | No plan-level blocker remains | Add one plan-level blocker while items are otherwise eligible and resolved | Plan-wide integrity or safety condition blocks handoff | Failure identifies plan-level blocker |
| H7 | Planning mode is `full` | Use `recommendations_only` mode with otherwise approved structural-looking work | Degraded planning lacks simulation-backed structural readiness | Failure identifies planning mode |

For H5 and H6, if ordinary production inputs naturally trigger both predicates,
the fixture must document the closest production-valid isolation and the
evaluator must record which predicate is being checked. Invalid object
construction may not be used to force impossible planner states.

## Diagnostic Metrics

The evaluator reports, but never gates on:

- workflow status distribution;
- review queue distribution, counting primary and all-membership views
  separately;
- blocker distribution by code and scope;
- planning-mode distribution;
- structural operation distribution;
- review-to-structural ratio, with zero-structural cases reported explicitly
  rather than divided by zero;
- average workflow items per case;
- average steps per case;
- integrity-blocked case count.

Diagnostics carry `diagnosticOnly: true`. They cannot add quality checkpoints,
change thresholds, suppress failures, or override a quality, fixture, evaluator,
artifact, or safety gate.

## Evaluation API

Phase 4 should provide a dedicated API following the established recommendation
and simulation patterns without copying their assumptions blindly:

```python
def evaluate_workflows(
    gold_path: Path | None = None,
) -> WorkflowEvaluationResult:
    """Evaluate workflow planning only; perform no workflow execution."""
```

The evaluator should:

1. load and validate the fixture;
2. validate non-vacuity requirements before scoring;
3. expand deterministic input builders;
4. construct a fresh source report per run;
5. evaluate initial planning;
6. apply labeled decision stages to validated initial plans;
7. evaluate quality checkpoints and safety properties separately;
8. collect diagnostic distributions;
9. return one normalized conceptual result;
10. serialize artifacts only in the runner layer.

Planned Phase 4 files are:

```text
memd/benchmarks/workflow_evaluation.py
tests/fixtures/workflow_gold.json
tests/test_workflow_evaluation.py
scripts/run_workflow_evaluation.py
examples/benchmarks/workflow_evaluation.json
examples/benchmarks/workflow_evaluation.md
docs/validation/WORKFLOW-BENCHMARK.md
docs/validation/V0.8-PHASE4-WORKFLOW-EVALUATION-IMPLEMENTATION.md
```

This ADR creates none of them.

## Benchmark Result Contract

The conceptual serialized result contains:

```json
{
  "benchmark": "workflow_evaluation",
  "evaluationStatus": "scored",
  "fixtureVersion": "...",
  "plannerVersion": "2",
  "caseCount": 0,
  "checkpointCount": 0,
  "qualityMetrics": {},
  "diagnosticMetrics": {"diagnosticOnly": true},
  "safetyResults": {"passed": false, "properties": {}, "failures": []},
  "failures": [],
  "gatePassed": false,
  "groundTruthAuthority": "tests/fixtures/workflow_gold.json",
  "diagnosticOnly": false
}
```

### Result states

| `evaluationStatus` | Meaning | Metric representation | `gatePassed` |
| --- | --- | --- | --- |
| `scored` | Fixture valid, evaluator completed, quality and safety checks executed | Actual `accuracy`, `passed`, and `total` for all eleven metrics | True only if every metric is `1.0`, every safety property passes, artifacts if generated succeeded, and `failures == []` |
| `fixture_invalid` | Fixture failed schema, non-vacuity, duplicate, unknown-field, or checkpoint validation before scoring | All metric names present with `accuracy: null`, `passed: 0`, `total: 0` | False |
| `evaluator_error` | Evaluator failed unexpectedly before producing scored checkpoint results | All metric names present with `accuracy: null`, `passed: 0`, `total: 0` | False |
| `scored_failure` | Fixture valid and scoring completed, but one or more quality checkpoints failed | Actual scored metrics | False |
| `safety_failure` | Quality may have scored, but one or more safety gates failed | Actual scored metrics when available | False |
| `artifact_generation_failure` | Evaluation result existed, but required artifact generation or semantic-equivalence validation failed | Actual scored metrics when available | False |

`gatePassed` must short-circuit to `false` unless `evaluationStatus == "scored"`
and all quality, safety, failure-list, and artifact clauses pass. A result may
include a more specific failure kind while keeping the top-level
`evaluationStatus` as the earliest decisive state; the serialized `failures`
list must make the distinction explicit.

`qualityMetrics` contains all eleven metric names, each with `accuracy`,
`passed`, and `total`. `overallWorkflowAccuracy.total` equals `checkpointCount`
and counts unique quality checkpoints only. `safetyResults` has no accuracy
contribution.

Failures contain checkpoint failures, fixture-validation failures,
evaluator-error failures, safety failures, and artifact failures with explicit
`kind` values. Workflow fields stay under the workflow namespace.
Recommendation and simulation metrics must not be copied into `qualityMetrics`,
averaged with workflow scores, or renamed as workflow accuracy.

The initial architecture-compliance threshold is:

```text
evaluationStatus == scored
every quality metric == 1.0
every safety property passes
failures == []
gatePassed == true
```

The fixture is intentionally small, synthetic, and focused. A perfect score
means conformance to architecture-defined behavior on those labeled cases. It is
not a claim of production-world accuracy, operator utility, or external-dataset
performance. External validation findings remain limitations and regression
context.

## Artifact Requirements

Phase 4 commits:

```text
examples/benchmarks/workflow_evaluation.json
examples/benchmarks/workflow_evaluation.md
```

Both artifacts must include:

- all quality metrics with numerators and denominators;
- complete safety results with `checksPassed`, `checksTotal`, and failures;
- diagnostic distributions marked diagnostic-only;
- failed checkpoint details, or an explicit empty failure list;
- fixture version, planner version, case count, and checkpoint count;
- `evaluationStatus` and `gatePassed`;
- the exact reproduction command;
- the statement that `workflow_gold.json` is the sole workflow ground truth;
- a planning-only disclaimer stating that no action was executed, persisted, or
  externally applied.

The JSON artifact is machine-readable and authoritative for the recorded run.
The Markdown artifact is a faithful human-readable rendering of the same
normalized result object. CI must render JSON and Markdown from the same result
dictionary and test required Markdown sections and values against that source
object; Markdown is not parsed as a second source of truth. Volatile timestamps,
absolute machine paths, and platform-specific separators must not make committed
artifacts drift.

## CI Requirements

CI must enforce:

1. deterministic fixture loading and builder expansion;
2. duplicate `caseId`, duplicate canonical checkpoint tuple, and duplicate
   rendered checkpoint-ID rejection;
3. required-field, enum, expected-field, unknown-field, checkpoint-type, and
   primary-metric validation;
4. non-vacuity validation before scoring;
5. non-zero denominator and metric arithmetic validation;
6. exact unique-checkpoint accounting and
   `overallWorkflowAccuracy.total == checkpointCount`;
7. every quality metric at `1.0`;
8. every safety property present with `checksTotal >= 1` and passing
   independently of quality scores;
9. bounded `no_effects` instrumentation for planner and decision calls;
10. source report immutability snapshots;
11. deterministic JSON and Markdown artifact generation and checked-in artifact
    regression;
12. artifact semantic-equivalence validation from one normalized result object;
13. agreement between test and runner results;
14. no network dependency or external-data download;
15. local, deterministic inference/builders only;
16. no threshold tuning based on observed failures;
17. no modification, monkeypatching, or alternate implementation of planner
    behavior by the evaluator;
18. explicit planner-version mismatch failure unless the fixture and
    architecture expectations are intentionally reviewed together.

Tests may inject controlled clocks or filesystem/network sentinels to validate
the evaluator boundary, but must call the production planner and decision
transformer for scored behavior.

## Relationship to Existing ADRs

```text
ADR-001 -> Recommendation Layer
ADR-002 -> Recommendation Evaluation
ADR-003 -> Simulation Evaluation
ADR-004 -> Workflow Planning Architecture
ADR-005 -> Workflow Evaluation
```

Each evaluation layer owns a separate gold authority and metric namespace.
Recommendation evaluation answers whether recommendations match recommendation
labels. Simulation evaluation answers whether dry-run projections match
simulation labels. Workflow evaluation answers whether planning and decision
application match workflow labels.

Neither ADR-002 nor ADR-003 replaces ADR-005. ADR-005 consumes their verified
outputs as input specifications without re-scoring those layers. ADR-005 also
does not amend ADR-004 planning semantics. Where completed Phase 2 and Phase 3
hardening clarified implementation--planner version `"2"`, warning scoping,
structural overlap routing, missing versus unresolved source actions, digest
evidence for conflicting duplicates, and cumulative decision-state
fingerprinting--the gold fixture evaluates that verified V0.8 behavior.

## Risks and Limitations

| Risk or open question | Recommended default |
| --- | --- |
| Fixture size versus combinatorial coverage | Keep 15-20 focused cases; use readable matrices and pairwise boundary perturbations rather than an exhaustive cross-product |
| Checkpoint overlap and denominator inflation | One canonical encoded tuple and one primary quality dimension per semantic obligation; set union once for overall |
| Relational versus literal identity expectations | Prefer relational assertions; hardcode full hashes only with a documented cross-version stability reason |
| Partial expected blocks | Allow only schema-declared partial blocks; require complete safety evaluation globally and make omitted quality fields visible in expanded fixture metadata |
| Decision-transition representation | Use ordered batches with an expected stage after each batch, including atomic-error stages and cumulative-state fingerprints |
| Provenance depth | Require explicit `matchMode`; use complete closure in dedicated provenance cases rather than duplicating entire reports everywhere |
| Planner-version changes invalidating expectations | Fail on version mismatch; review architecture, fixture, evaluator, and artifacts together; never auto-rebaseline |
| Reserved blocker codes | Treat `UNSUPPORTED_ACTION` and `STALE_EVIDENCE` as required absence checks for planner version `"2"`; do not manufacture unreachable outputs |
| Safety sentinel limits | State bounded CI scope; require harness self-tests; do not overclaim global absence of effects |
| Evaluation helper duplication | Share small canonical comparison/reporting utilities only when semantics are identical; keep workflow checkpoint definitions workflow-specific |
| Test/runner drift | Both call the same public evaluation API; CI compares runner artifacts to the returned normalized result |
| External validation remains non-gating | Preserve it as diagnostic regression context with no workflow labels or pass/fail influence |
| Small-fixture overconfidence | State architecture-compliance scope in every artifact and release document; do not claim production-world accuracy |
| Composite cases becoming opaque | Require primary-purpose descriptions and expanded checkpoint listings; split a matrix when failures cannot be understood locally |
| Exact blocker messages becoming brittle | Match codes and structured scope by default; match full messages only when wording is intentionally contractual |
| Builder drift hiding label changes | Review builders as fixture code, expose expanded inputs on failure, and forbid builders from calling planner output to derive expectations |
| Invalid-fixture reporting divergence | Use the required `evaluationStatus` states and `accuracy: null`, `passed: 0`, `total: 0` representation |

The initial fixture cannot establish empirical usefulness on arbitrary memory
exports. It establishes exact architectural conformance for V0.8 planning.

## Acceptance Criteria

ADR-005 may move from Proposed to Accepted when:

- every metric formula, denominator, numerator, zero-denominator behavior, and
  phase boundary is unambiguous;
- every quality metric has mandatory non-zero fixture coverage;
- checkpoint identity, semantic-key construction, collision rejection, and
  primary-metric assignment are deterministic;
- `overallWorkflowAccuracy.total == checkpointCount` is defined and enforced;
- every safety gate is explicit, independently gating, and non-vacuous;
- H1-H7 readiness boundaries have positive and negative controls;
- `workflow_gold.json` is the exclusive workflow-correctness authority;
- normative fixture coverage includes every aggregate status, every V0.8
  blocker disposition, every review subtype, and every primary queue;
- the fixture schema and deterministic builder restrictions are implementable;
- invalid fixtures, evaluator errors, scored failures, safety failures, and
  artifact failures have distinct result representations;
- exact and relational identity validation is deterministic;
- initial planning and decision application are separately specified;
- cumulative decision fingerprint semantics are explicit;
- artifact and CI requirements are defined;
- no action execution, persistence, scheduling, rollback, external side effects,
  or approval UX semantics are introduced;
- an independent architecture audit approves this ADR.

## V0.8 Release Gate

V0.8 release requires all of the following:

- ADR-004 Accepted;
- ADR-005 Accepted;
- Phase 1 workflow contracts verified;
- Phase 2 workflow planner verified;
- Phase 3 pipeline and reporting integration verified;
- Phase 4 workflow evaluation implemented;
- `tests/fixtures/workflow_gold.json` committed;
- all eleven workflow quality metrics equal `1.0` with non-zero denominators;
- `overallWorkflowAccuracy.total == checkpointCount`;
- every workflow safety property present, non-vacuous, and passing;
- no evaluation failures and `gatePassed == true`;
- workflow benchmark JSON and Markdown artifacts committed;
- independent Phase 4 audit complete;
- V0.8 release-readiness audit complete;
- the known unrelated parser-fixture and Ruff baselines explicitly dispositioned
  without being hidden or misattributed to workflow evaluation.

External validation may inform limitations and future fixture additions, but it
cannot satisfy or waive this gate.

## Consequences

### Positive

- Workflow planning gains an independent correctness authority before V0.8
  certification.
- Initial planning and operator decision behavior cannot mask one another.
- Unique checkpoint accounting makes a perfect score auditable rather than
  inflated by repeated assertions.
- Exact structural comparisons and relational hash tests detect both semantic
  regressions and accidental canonicalization drift.
- Safety remains an absolute, non-vacuous gate even when aggregate quality scores
  look good.
- Artifacts communicate conformance, limitations, and the planning-only
  boundary.

### Negative

- The fixture, builders, evaluator, artifacts, and planner version must evolve in
  lockstep when workflow semantics intentionally change.
- Perfect-score gating makes any ambiguous expectation immediately blocking and
  requires architecture disposition rather than threshold relaxation.
- Approximately 15-20 focused cases cannot cover the full combinatorial space.
- Provenance, checkpoint accounting, safety sentinels, and identity relations add
  evaluator complexity beyond ordinary field comparison.
- Reserved blocker dispositions must be revisited if ADR-004 or the planner
  later makes those blockers reachable.

These costs are accepted because workflow plans package safety-sensitive future
handoff intent. V0.8 must prove that packaging is correct before claiming release
readiness, while remaining strictly non-executing.
