# PERMA Dataset Distribution Review

Date: 2026-06-17  
Scope: distribution strategy for `datasets/perma/` under benchmark artifact policy

---

## Dataset inventory

Top-level structure observed under `datasets/perma/`:

- `.cache/` (local HuggingFace cache metadata and download markers)
- `profile/` (per-user profile and task metadata JSON)
- `tasks/` (per-user task corpora, raw dialogues, timelines, large `input_data_*` JSON)
- `evaluation/` (per-user evaluation metadata under `meta/overall/*.json`)
- `WildChat-1M/` (style-source JSON slices)
- `README.md`, `.gitattributes`, `.DS_Store`

Representative benchmark dependency path:

- `scripts/run_perma_benchmark.py` currently requires:
  - `datasets/perma/profile/<user>/profile.json`
  - `datasets/perma/profile/<user>/tasks.json`

It does not currently require `tasks/` or `evaluation/` to execute the Mem-D benchmark export path, but those directories are part of the upstream PERMA dataset package.

---

## Total size and file counts

Measured on current workspace:

- **All files (including cache):**
  - `2,496 files`
  - `886,051,524 bytes` (~845 MB)
- **Non-cache files (`datasets/perma/.cache/**` excluded):**
  - `1,247 files`
  - `885,920,835 bytes` (~844.9 MB)

Directory-level footprint (from prior audit measurements):

- `tasks/`: ~874,550,338 bytes
- `evaluation/`: ~5,205,770 bytes
- `profile/`: ~1,418,194 bytes
- `WildChat-1M/`: ~4,729,153 bytes
- `.cache/`: ~130,689 bytes

Interpretation: repository impact is dominated by `tasks/`.

---

## Reproducibility requirements

From policy and existing benchmark docs:

- `BENCHMARK-ARTIFACT-POLICY.md` classifies `datasets/perma/**` as source assets for reproducibility.
- `PERMA-IMPLEMENTATION-STATUS.md` and `BENCHMARK-EVIDENCE-SUMMARY.md` establish a reproducible command:
  - `python scripts/run_perma_benchmark.py --user-id user108`
- Current script implementation consumes only `profile/<user>/profile.json` and `profile/<user>/tasks.json` for Mem-D benchmark export generation.

Therefore:

- **Strict clone-and-run reproducibility for current Mem-D PERMA benchmark** requires at least the relevant `profile/` user files.
- Full upstream PERMA package reproducibility requires the entire dataset bundle (including `tasks/`, `evaluation/`, and `WildChat-1M/`).

---

## Licensing / redistribution assessment (if discoverable)

From `datasets/perma/README.md`:

- Declared license: **Apache-2.0**

Implication:

- Redistribution appears permitted under Apache-2.0 terms, but repository maintainers should still verify:
  - provenance of included subcomponents
  - whether all packaged files are covered uniformly by the declared license
  - practical hosting/storage policy constraints for large binary/text corpora

No legal advice is provided here; this is a technical policy assessment.

---

## Repository impact assessment

Committing full PERMA dataset into this repo would add:

- ~845 MB additional tracked content
- ~2.5k files
- substantial clone/fetch overhead
- higher repo maintenance burden (history growth, review friction, CI checkout time)

Given Mem-D v0.6 scope and existing benchmark approach (published benchmark artifacts + reproducible scripts), this is high-cost relative to immediate benchmark utility.

---

## Benchmark needs assessment

For Mem-D v0.6 benchmark needs:

- Required:
  - reproducible benchmark command for at least one user (`user108`)
  - committed benchmark evidence artifacts and interpretation docs
- Not strictly required (for current script path):
  - full `tasks/` and `evaluation/` trees
  - entire `WildChat-1M/` source slices

Conclusion:

- Current benchmark runner’s functional minimum is small (profile subset),
- while full dataset inclusion is much larger than current operational need.

---

## Full dataset vs subset tradeoffs

### Option A — Commit full PERMA dataset (~845 MB, 2,496 files)

**Pros**

- Maximum in-repo reproducibility and transparency
- No external acquisition dependency
- Preserves entire upstream package context

**Cons**

- Large repository bloat and long-term maintenance cost
- Increases clone, fetch, and contributor onboarding burden
- Mismatch with v0.6 benchmark operational minimum

### Option B — Commit reproducible benchmark subset only

**Pros**

- Preserves clone-and-run reproducibility for Mem-D benchmark command
- Drastically lower repository impact
- Aligns with practical benchmark requirements in v0.6

**Cons**

- Requires explicit subset contract/documentation
- Not equivalent to full upstream PERMA package availability
- Must define and enforce subset integrity over time

### Option C — Keep PERMA external and document acquisition steps

**Pros**

- Minimal repository size impact
- Clear separation of source data and benchmark code
- Common pattern for large external datasets

**Cons**

- Fresh-clone reproducibility depends on external download availability
- Requires robust acquisition docs + validation checks
- Higher friction for contributors running PERMA benchmark locally

---

## Recommendation for Mem-D v0.6

## Recommended choice: **B — Commit a reproducible benchmark subset only**

Reasoning:

1. It best balances policy intent (“reproducible from clone”) with repository sustainability.
2. The current v0.6 PERMA benchmark pipeline only needs profile-level files for export generation.
3. Full-dataset commit cost is high relative to benchmark value for current Mem-D scope.
4. External-only strategy (C) weakens out-of-the-box reproducibility unless acquisition/docs are made mandatory and continuously validated.

Suggested v0.6 distribution posture:

- Keep/commit only the minimal PERMA files needed for deterministic benchmark generation (at least default user benchmark path).
- Treat full upstream PERMA as an optional external corpus with explicit acquisition documentation.
- Keep cache/temp content ignored (`datasets/perma/.cache/`, OS artifacts).

---

## Practical decision notes

- This review is **audit + recommendation only**; no subset was created and no ignore rules were changed.
- If maintainers choose B, they should define a formal subset manifest (paths + checksums) in a follow-up policy/ops document.
- If maintainers choose C instead, reproducibility claims in benchmark docs should be adjusted to “reproducible after dataset acquisition.”

