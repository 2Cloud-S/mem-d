# Memory Lifecycle Model V1

Status: Active

Purpose:

Infer likely memory lifecycle state from existing Memory Evolution Audit evidence.

This model is diagnostic only. It does not modify memories, change categorization, alter clustering, or affect governance actions.

---

## Lifecycle States

- `Active`
- `Historical`
- `Superseded`
- `Deprecated`
- `Temporary`
- `Completed`

---

## Input

Memory Lifecycle Model V1 uses only `validation.memoryEvolutionAudit`.

It consumes detected evolution relationships and stale memory candidates, including:

- contradictions
- preference changes
- superseded memories
- stale memory candidates
- status transition candidates

---

## Output

`validation.memoryLifecycle` includes:

- `lifecycleCounts`
- `lifecycleTransitions`
- `lifecycleConfidence`
- `memoryLifecycleAssignments`

Each assignment includes:

- memory ID
- content snapshot
- inferred lifecycle state
- confidence
- evidence
- source evolution case
- explanation

---

## Interpretation

Lifecycle states are inferred as follows:

- Contradicted or stopped earlier memories become `Deprecated`; newer memories become `Active`.
- Superseded earlier decisions become `Superseded`; newer decisions become `Active`.
- Older status memories become `Historical`; newer completed status memories become `Completed`.
- Stale temporary memories become `Temporary`; other stale candidates become `Historical`.

If one memory receives multiple lifecycle signals, the model keeps the strongest lifecycle interpretation and preserves alternates for review.

---

## Reporting

The model appears in:

- JSON validation output
- Markdown `### Memory Lifecycle`
- Terminal summary when lifecycle assignments exist

---

## Success Criteria

The model should answer:

"Which memories are still active, which have been superseded, and which are historical?"
