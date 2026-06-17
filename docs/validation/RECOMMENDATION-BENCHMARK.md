# Recommendation Benchmark (V0.6 Phase 3)

## Purpose

This benchmark measures the **quality of Mem-D V0.6 recommendation outputs** (the `MemoryResolution.resolvedAction` produced by `plan_recommendations()`), using the labeled gold fixture:

- `tests/fixtures/recommendation_gold.json`

Recommendation quality is decision-oriented: it validates whether Mem-D applies the architecture-defined rules (precedence, conflict resolution, trust/policy gating) correctly.

## Evaluation methodology

### Evaluation unit

**Primary unit:** `MemoryResolution`.

Each gold case defines `expectedResolutions` as a map of `memoryId → expected outcome`. The benchmark compares:

- predicted `MemoryResolution.resolvedAction` against expected `resolvedAction`
- predicted `MemoryResolution.role` against expected `role` (when present)
- predicted `MemoryResolution.conflictDetected` against expected `conflictDetected` (when present)
- optional `suppressedActions` against expected `suppressedActions` (when present in future gold updates)

**Secondary unit:** group-scoped `Recommendation` records are not the metric source for accuracy; they remain for reporting.

### Conflict cases

Conflict resolution accuracy is computed on conflict-tagged cases (currently those with `id` prefix `conflict_`, and cases where gold expectations include `conflictDetected: true`).

Scope note (ADR-002 alignment): ADR-002 documents broader conflict *scenario classes*; this benchmark intentionally counts only explicitly conflict-labeled fixture cases for the conflict-accuracy denominator to keep the metric stable and auditable across fixture revisions. Broader scenario coverage remains represented in overall/per-action accuracy.

### Metrics computed

1. **Overall accuracy**
   - Definition: fraction of evaluated memory resolutions that match expected `resolvedAction`.
2. **Per-action accuracy**
   - Strata: `merge`, `archive`, `review`, `keep`
3. **Conflict resolution accuracy**
   - Case-level pass rate on conflict-tagged cases.
4. **Distribution metrics (diagnostic only)**
   - Counts of predicted resolution categories for drift awareness.

## Artifacts

- JSON: `examples/benchmarks/recommendation_evaluation.json`
- Markdown: `examples/benchmarks/recommendation_evaluation.md`

## Current results (from repository run)

From `recommendation_evaluation.md`:

- **Overall accuracy:** `1.0000 (22/22)`
- **Per-action accuracy:** merge/archive/review/keep all `1.0000`
- **Conflict resolution accuracy:** `1.0000 (3/3)`

## Interpretation guidance

- A perfect score means Mem-D applies the **architecture-intended mapping** from the supplied gold evidence payloads to the expected resolved actions.
- Distribution metrics are useful for posture checks (e.g. review dominance), but **they are not quality metrics**.

## Limitations

- Gold cases are synthetic and fixture-scoped; this benchmark validates rule application, not production-world performance.
- Coverage expands as recommendation capabilities evolve; new rule paths require new gold cases (ADR-002 discipline).

## Reproduction steps

Run:

```bash
python scripts/run_recommendation_evaluation.py
```

This writes:

- `examples/benchmarks/recommendation_evaluation.json`
- `examples/benchmarks/recommendation_evaluation.md`

