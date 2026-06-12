# Memory Evolution Audit V1

Status: Active

Purpose:

Detect evidence that memories change over time and identify patterns of memory evolution.

This audit is diagnostic only. It does not modify memories, categorization, clustering, or governance actions.

---

## Evolution Types

Memory Evolution Audit analyzes memories for:

1. **Contradictions** — conflicting states about the same topic, such as database technology changes.
2. **Preference changes** — preference memories that appear to stop or replace a prior choice.
3. **Superseding memories** — newer decision-like memories that may replace older ones.
4. **Stale facts** — temporary or time-bound memories that may no longer be valid.
5. **Status transitions** — planned → in progress → completed style progressions.

---

## Outputs

`validation.memoryEvolutionAudit` includes:

- `contradictionCount`
- `preferenceChangeCount`
- `supersededMemoryCount`
- `staleMemoryCandidates`
- `statusTransitionCandidates`
- `evolutionConfidence`

Each detected case includes:

- involved memories
- evidence
- confidence
- explanation

---

## Reporting

The audit appears in:

- JSON validation output
- Markdown `### Memory Evolution Audit`
- Terminal summary when evolution signals are present

---

## Success Criteria

The audit should help answer:

"How often do memories evolve over time, and what kinds of evolution occur?"
