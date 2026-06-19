# Simulation Benchmark (V0.7 Phase 3)

## Purpose

This benchmark measures the **quality of Mem-D V0.7 simulation outputs** (`SimulationReport` produced by `simulate_recommendations()`), using the labeled gold fixture:

- `tests/fixtures/simulation_gold.json`

Simulation evaluation is **structural and store-composition oriented**. It validates whether the simulation engine correctly projects merge, archive, review, and keep resolutions onto a dry-run memory store — including safety guards, warning emission, explainability completeness, and internal metric consistency.

Simulation evaluation is **independent** from recommendation evaluation (ADR-002). High recommendation accuracy does not imply simulation pass, and vice versa.

## Evaluation methodology

### Ground truth authority

**Only** `tests/fixtures/simulation_gold.json` is used for correctness scoring.

LongMemEval and PERMA exports are **regression guards only** — they detect posture drift but do not supply labeled simulation expected outcomes.

### Evaluation unit

**Primary unit:** atomic **checkpoints** in each gold case `expected` block, plus derived required checks (keeper preservation, explainability refs, metric consistency, safety invariants).

Each checkpoint is pass/fail. Case pass requires all checkpoints for that case to pass.

### Quality metrics (gate pass/fail)

| Metric | Definition |
| --- | --- |
| `overallStructuralAccuracy` | `passedCheckpoints / totalCheckpoints` |
| `mergeProjectionAccuracy` | Merge-scenario checkpoint pass rate |
| `archiveProjectionAccuracy` | Archive-scenario checkpoint pass rate |
| `reviewPreservationAccuracy` | Review-scenario checkpoint pass rate |
| `warningAccuracy` | Warning-scenario checkpoint pass rate |
| `orphanMergeAccuracy` | Case-level pass on orphan scenarios (hard gate: 1.0) |
| `explainabilityAccuracy` | Simulated event explainability checkpoint pass rate |
| `metricConsistencyAccuracy` | Internal `SimulationMetrics` formula checkpoint pass rate |

**Launch threshold:** `1.0` on the current 9-case fixture.

### Diagnostic metrics (never gate)

| Metric | Purpose |
| --- | --- |
| `recommendationUtilizationDistribution` | Per-case utilization rates; posture drift |
| `warningDistribution` | Count by warning code |
| `projectedReductionDistribution` | `memoryCountDelta` and duplicate reduction summary |

Diagnostic metrics are labeled `"diagnosticOnly": true` in artifacts and **must not** affect pass/fail.

## Float tolerance rules

### Exact match

No tolerance. Must match exactly:

- IDs, counts, sets, booleans
- Warning codes, explainability sources, evidence refs
- Actions and structural outcomes

### Tolerance-based floats

| Field | Tolerance |
| --- | --- |
| Percentage fields (`estimatedCompressionGain`, etc.) | ±0.01 |
| Utilization rates | ±0.0001 |

### Inequality guards (regression only)

- `estimatedTrustedCompressionGain <= estimatedCompressionGain + 0.01`
- Monotonic reduction: `memoryCountAfter <= memoryCountBefore`
- Review preservation: review-resolution IDs remain in active store

## Safety validation (release-gating)

Safety properties are evaluated **in addition to** gold structural accuracy. A single safety failure fails evaluation regardless of accuracy score.

| Property | Requirement |
| --- | --- |
| Source immutability | `AnalysisReport` unchanged after simulation |
| Idempotency | Repeated runs yield identical `SimulationReport` and `simulationId` |
| Monotonic reduction | Store size never increases |
| No orphan removal | Every removed ID appears in merge or archive logs |
| Orphan safety | No removal when keeper absent; warning + downgrade |
| Review preservation | Review resolutions never remove memories |
| Duplicate-removal safety | `DUPLICATE_REMOVAL_SKIPPED` on labeled case |

## Artifacts

- JSON: `examples/benchmarks/simulation_evaluation.json`
- Markdown: `examples/benchmarks/simulation_evaluation.md`

## Current results (from repository run)

From `simulation_evaluation.json`:

- **Overall structural accuracy:** `1.0000` (119/119 checkpoints)
- **Per-dimension accuracy:** merge, archive, review, warning, orphan, explainability, metric consistency all `1.0000`
- **Safety:** all properties passed
- **Gate passed:** `true`

## Interpretation guidance

- A perfect score means the simulation engine matches **architecture-defined semantics** on labeled gold inputs.
- Diagnostic distributions are useful for posture monitoring but are **not quality metrics**.
- Structural compression figures in simulation metrics are **estimates only** — not equivalent to LongMemEval or PERMA analyze compression percentages.

## Regression guards

LongMemEval and PERMA guards (when run manually on published exports) check inequality posture only. They are recorded in artifacts under `regressionGuards` with `"diagnosticOnly": true` by default and do not gate Phase 3 completion.

## Limitations

- Gold cases are synthetic and fixture-scoped (9 cases at launch).
- Coverage expands as simulation capabilities evolve; new paths require new gold cases (ADR-003 discipline).
- Regression guards on LongMemEval/PERMA are optional at launch and not ground truth.

## Reproduction steps

Run:

```bash
python scripts/run_simulation_evaluation.py
```

Run evaluation tests:

```bash
python -m pytest tests/test_simulation_evaluation.py -q
```

This writes:

- `examples/benchmarks/simulation_evaluation.json`
- `examples/benchmarks/simulation_evaluation.md`
