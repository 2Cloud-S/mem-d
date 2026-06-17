# PERMA Gitignore Changes

Date: 2026-06-17  
Scope: minimal `.gitignore` updates for PERMA content not required by Mem-D benchmark reproducibility

---

## Current PERMA size

Measured from `datasets/perma/`:

- Files: `2,496`
- Total size: `886,051,524 bytes` (`~845.005 MB`)

---

## Rules added

Added to `.gitignore`:

```gitignore
# PERMA dataset content not required for Mem-D benchmark reproducibility (user108)
datasets/perma/tasks/
datasets/perma/evaluation/
datasets/perma/WildChat-1M/
```

No rules were removed in this change.

---

## Files/directories newly ignored

Newly ignored PERMA directories:

- `datasets/perma/tasks/`
- `datasets/perma/evaluation/`
- `datasets/perma/WildChat-1M/`

Validated examples:

- `datasets/perma/tasks/user108/input_data_c.json`
- `datasets/perma/evaluation/user108/meta/overall/MD-task-11_1.json`
- `datasets/perma/WildChat-1M/Australia_labeled_checked.json`

All are matched by the newly added explicit path rules.

---

## Justification for each ignore rule

### `datasets/perma/tasks/`

- Not read by `scripts/run_perma_benchmark.py` for the current Mem-D export path.
- Large footprint contributor; not needed for reproducing published `user108` Mem-D benchmark.
- Safe because benchmark-relevant consumed files are under `datasets/perma/profile/user108/`.

### `datasets/perma/evaluation/`

- Not consumed by the Mem-D benchmark export runner.
- Contains upstream PERMA protocol metadata, but not required for Mem-D’s current benchmark generation path.
- Ignoring reduces dataset sprawl without hiding required Mem-D benchmark inputs.

### `datasets/perma/WildChat-1M/`

- Not read by `run_perma_benchmark.py`.
- Source context for upstream PERMA dataset construction, but unnecessary for Mem-D benchmark reproduction.
- Explicit path ignore avoids broad/pervasive patterns.

---

## Files intentionally kept trackable

Required files for published user108 benchmark reproducibility remain trackable:

- `datasets/perma/README.md`
- `datasets/perma/.gitattributes`
- `datasets/perma/profile/user108/profile.json`
- `datasets/perma/profile/user108/tasks.json`

Also intentionally left trackable:

- `datasets/perma/profile/` (other users), so future user additions can be made intentionally.

---

## Benchmark reproducibility verification

### Required files must NOT be ignored

Ran:

```bash
git check-ignore -v datasets/perma/profile/user108/profile.json
git check-ignore -v datasets/perma/profile/user108/tasks.json
```

Result:

- No output (not ignored), as required.

### Required files remain visible to Git

Ran:

```bash
git status --short -- \
  datasets/perma/profile/user108/profile.json \
  datasets/perma/profile/user108/tasks.json \
  datasets/perma/tasks \
  datasets/perma/evaluation \
  datasets/perma/WildChat-1M
```

Result:

- `profile.json` and `tasks.json` appear as untracked (`??`) and remain visible to Git.
- Ignored directories (`tasks`, `evaluation`, `WildChat-1M`) do not appear in status output.

---

## Risk assessment

### Low risk

- Rules are explicit path-based, not broad wildcards.
- No entire `datasets/perma/` ignore was added.
- Required benchmark input files are still trackable.

### Residual risk

- Ignoring `tasks/` and `evaluation/` assumes benchmark logic stays as currently implemented (profile-driven export only).  
  If future benchmark logic begins consuming those directories, ignore rules must be revisited.

### Mitigation

- Keep `PERMA-BENCHMARK-SUBSET-PLAN.md` as the reproducibility contract.
- Re-audit ignore rules whenever `scripts/run_perma_benchmark.py` input dependencies change.

