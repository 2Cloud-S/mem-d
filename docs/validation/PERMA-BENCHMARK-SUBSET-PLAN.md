# PERMA Benchmark Subset Plan

Date: 2026-06-17

Status: Plan (no code / no gitignore / audit-only)

Goal: Design the smallest reproducible PERMA benchmark subset that preserves Mem-D V0.6 benchmark reproducibility.

---

## Current benchmark dependencies

### Benchmark runner and evaluation path (already in repo)

For the Mem-D “PERMA benchmark” path, reproducibility depends on:

- `scripts/run_perma_benchmark.py`
  - deterministic conversion from PERMA metadata → Mem-D memory export JSONL
- `memd/benchmarks/workflow.py`
  - runs dataset audit → Mem-D analysis → writes baseline + audit artifacts
- `memd/dataset_quality.py` and `memd/pipeline.py`
  - audit + analysis mechanics (existing, not PERMA dataset-dependent beyond the generated export)
- Reporting/serialization:
  - `memd/benchmarks/baseline.py`, `memd/benchmarks/workflow.py`

### PERMA dataset files directly consumed by `run_perma_benchmark.py`

From code inspection of `scripts/run_perma_benchmark.py`, the conversion step reads only:

- `datasets/perma/profile/<user-id>/profile.json`
- `datasets/perma/profile/<user-id>/tasks.json`

No other PERMA dataset directories are required to generate the Mem-D memory export used for the benchmark.

---

## Which files are actually consumed by `run_perma_benchmark.py`

### Required to run the conversion step for a given `--user-id`

For a user `U`, the runner requires:

- `datasets/perma/profile/U/profile.json`
- `datasets/perma/profile/U/tasks.json`

The script:

- sorts `affinities` domains and fields
- sorts `tasks` entries by key
- renders string content deterministically from those JSON structures

### Required to reproduce the rest of Mem-D benchmark artifacts

The benchmark pipeline consumes the generated export JSONL and then runs:

- dataset quality audit (`audit_external_datasets([input_path])`)
- Mem-D analysis (`analyze_file(...)`)
- baseline rendering (`render_baseline_markdown(...)`)

Those steps depend on the generated export JSONL, which in turn depends only on `profile.json` + `tasks.json`.

### Unnecessary for conversion + Mem-D analysis reproducibility

These directories are not read by `run_perma_benchmark.py` for the Mem-D benchmark export path:

- `datasets/perma/tasks/**`
- `datasets/perma/evaluation/**`
- `datasets/perma/WildChat-1M/**`
- `datasets/perma/**` other users’ `profile/<other-user-id>/...` (unless you run those users)
- `datasets/perma/.cache/**` (tooling cache)

---

## Minimum reproducible dataset

To reproduce the currently published PERMA benchmark evidence based on the default benchmark user (`user108`), commit only the following PERMA files:

- `datasets/perma/README.md` (license + dataset structure context)
- `datasets/perma/.gitattributes` (dataset attribute metadata)
- `datasets/perma/profile/user108/profile.json`
- `datasets/perma/profile/user108/tasks.json`

Files required for the directories themselves (implied by the committed files above):

- `datasets/perma/profile/user108/` must exist (via committed files)

---

## Recommended benchmark users

### Primary (recommended for v0.6, based on existing evidence)

- `user108`

Reason:

- the only committed PERMA baseline evidence in `examples/benchmarks/` is `perma_user108.baseline.md`
- code default `--user-id` in `scripts/run_perma_benchmark.py` is `user108`

### Optional (future expansion)

The PERMA dataset currently contains additional users under `datasets/perma/profile/`. If maintainers want reproducibility for more benchmark users later, they can extend the subset by committing:

- `datasets/perma/profile/<other-user>/profile.json`
- `datasets/perma/profile/<other-user>/tasks.json`

No additional PERMA directories are required for those extra users.

---

## Estimated repository size after reduction

Measured on current workspace for the minimal v0.6 subset files:

- `datasets/perma/README.md`: ~5.3 KB
- `datasets/perma/.gitattributes`: ~5.7 KB
- `datasets/perma/profile/user108/profile.json`: ~52.2 KB
- `datasets/perma/profile/user108/tasks.json`: ~73.0 KB

Total minimal subset size:

- **~0.133 MB** (139,488 bytes)

Current full PERMA dataset footprint (measured previously, including cache):

- ~845 MB (2,496 files)

Estimated dataset reduction impact:

- from **~845 MB** → **~0.133 MB** for the committed PERMA benchmark source subset

---

## Reproducibility impact

### Determinism preserved for the PERMA→Mem-D export

Because `run_perma_benchmark.py`:

- reads only `profile.json` and `tasks.json`
- sorts domains and tasks keys before rendering

the generated Mem-D memory export JSONL is deterministic given those files.

### Determinism for Mem-D analysis remains “as existing”

Mem-D analysis reproducibility still depends on existing factors (embedding model selection, threshold settings, and any model nondeterminism).

However, with the subset committed, the PERMA input side (the export generation) is reproducible from a clone.

---

## Migration strategy

This plan is audit/documentation-only; no moving or deletion occurs here. If maintainers decide to adopt subset commit strategy, a minimal migration approach is:

1. Commit the minimal subset files listed above.
2. Keep `examples/benchmarks/perma_user108.baseline.md` and associated benchmark evidence docs aligned with the rerun command (`python scripts/run_perma_benchmark.py --user-id user108`).
3. Optionally document (in a future ops doc) that additional users require committing their `profile/<user>/profile.json` and `tasks.json`.
4. For full upstream PERMA retention:
   - keep the remainder of `datasets/perma/` available externally (download step),
   - or keep it uncommitted locally for researchers who need full upstream context.

No code changes are required for this migration.

---

## Risks

### Dataset representativeness risk

The minimal subset commits only the profile/tasks metadata used to create Mem-D memory exports. It does not preserve:

- full PERMA raw dialogue/task inputs (`datasets/perma/tasks/**`)
- MCQ/intermediate evaluation metadata (`datasets/perma/evaluation/**`)
- style-source slices (`WildChat-1M/**`)

This is acceptable for the Mem-D benchmark export path, but maintainers should avoid claiming the repo contains the full upstream PERMA benchmark protocol.

### Future feature drift risk

If later code starts reading from `datasets/perma/tasks/**` or `datasets/perma/evaluation/**` for Mem-D benchmark correctness, the subset would need expansion.

Mitigation:

- keep this subset plan as an explicit contract
- update the plan if benchmark code starts consuming additional PERMA directories

---

## Final recommendation (Mem-D v0.6)

Choose:

**B. Commit a reproducible benchmark subset only**

Concretely, commit only:

- `datasets/perma/README.md`
- `datasets/perma/.gitattributes`
- `datasets/perma/profile/user108/profile.json`
- `datasets/perma/profile/user108/tasks.json`

and treat everything else under `datasets/perma/` as optional external corpus material (downloaded as needed).

---

## Explicit required-vs-unnecessary file list (summary)

### Required (to reproduce the Mem-D PERMA benchmark for user108)

- `datasets/perma/README.md`
- `datasets/perma/.gitattributes`
- `datasets/perma/profile/user108/profile.json`
- `datasets/perma/profile/user108/tasks.json`

### Unnecessary (for reproducing the Mem-D benchmark export + audit/analyze/baseline)

- `datasets/perma/tasks/**`
- `datasets/perma/evaluation/**`
- `datasets/perma/WildChat-1M/**`
- `datasets/perma/.cache/**`
- other users under `datasets/perma/profile/<user>/**` (unless you run those users)

