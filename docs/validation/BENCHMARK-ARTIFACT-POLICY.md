# Benchmark Artifact Policy

Status: Active (analysis-only policy; no `.gitignore` changes applied yet)

Purpose: classify Mem-D benchmark outputs and define what belongs in Git versus local-only storage.

Scope inspected:

- `examples/benchmarks/`
- `scripts/` (`run_longmemeval_benchmark.py`, `run_perma_benchmark.py`, `preprocess_longmemeval.py`, `benchmark_10k.py`)
- `docs/validation/` and `docs/benchmarks/`
- `memd/benchmarks/` (`artifacts.py`, `workflow.py`, `baseline.py`)

Canonical artifact names are defined in `memd/benchmarks/artifacts.py`.

---

## Classification model

Every benchmark-related file should be classified into exactly one category:

| Class | Definition | Typical Git treatment |
| --- | --- | --- |
| **1. Source Asset** | Inputs required to reproduce benchmarks: datasets, fixtures, scripts, templates | **Commit** (unless too large for repo policy) |
| **2. Published Evidence** | Human-readable evidence intended for documentation readers | **Commit** |
| **3. Reproducible Generated Artifact** | Machine-generated pipeline output fully reproducible from source assets + scripts | **Ignore** (regenerate locally) |
| **4. Temporary Output** | Scratch, logs, one-off experiments, non-canonical intermediates | **Ignore** |

Decision rule (from benchmark retention practice):

- **Commit** when human-readable, published evidence, hard to reconstruct from history alone, and intended for documentation readers.
- **Ignore** when machine-generated, fully reproducible, primarily consumed by code, and large or accumulative.

When uncertain: document a recommendation and request maintainer approval before changing `.gitignore`.

---

## Artifact pattern policy

| Pattern | Class | Commit | Ignore | Reason |
| --- | --- | :---: | :---: | --- |
| `datasets/validation/*.json` | Source Asset | Yes | No | Labelled evaluation ground truth (e.g. `clustering_quality.json`); small, required for `evaluate-clusters` |
| `datasets/evaluation/*.jsonl` | Source Asset | No | Yes | Large local benchmark exports (LongMemEval); reproducible from external source; gitignored today |
| `datasets/perma/**` | Source Asset | Yes* | No* | PERMA benchmark input data; required for `run_perma_benchmark.py` (*currently blocked — see findings) |
| `datasets/real/*.json`, `datasets/memories.json` | Source Asset | Yes | No | Committed sample/realistic memory corpora for manual analysis |
| `tests/fixtures/*.json` | Source Asset | Yes | No | Gold evaluation fixtures (`evolution_gold.json`, `lifecycle_gold.json`) |
| `tests/fixtures/*.jsonl` | Source Asset | Yes | No | Small deterministic benchmark/preprocess test inputs |
| `tests/fixtures/memories.{json,csv}` | Source Asset | Yes | No | Parser contract fixtures |
| `scripts/run_*_benchmark.py` | Source Asset | Yes | No | Reproducible benchmark entrypoints |
| `scripts/preprocess_longmemeval.py` | Source Asset | Yes | No | Deterministic preprocessing step |
| `memd/benchmarks/**` | Source Asset | Yes | No | Benchmark orchestration library |
| `examples/benchmarks/BENCHMARK-BASELINE.md` | Source Asset | Yes | No | Baseline section template (not generated output) |
| `examples/benchmarks/README.md` | Source Asset | Yes | No | Artifact layout and run instructions |
| `{stem}.baseline.md` | Published Evidence | Yes | No | One-page published benchmark summary; primary GitHub evidence |
| `{stem}.audit.raw.md` | Published Evidence | Yes | No | Human-readable dataset quality audit (raw) |
| `{stem}.audit.cleaned.md` | Published Evidence | Yes | No | Human-readable dataset quality audit (cleaned) |
| `{stem}.preprocess-report.md` | Published Evidence | Yes | No | Human-readable preprocessing evidence (LongMemEval) |
| `docs/benchmarks/*.md` | Published Evidence | Yes | No | Curated benchmark reports (e.g. `LONGMEMEVAL-BENCHMARK.md`) |
| `docs/validation/BENCHMARK-*.md` | Published Evidence | Yes | No | Workflow, evidence summary, gap analysis, interpretation guides |
| `docs/validation/PERMA-*.md` | Published Evidence | Yes | No | PERMA status and interpretation evidence |
| `docs/validation/V0.5.1-*.md` | Published Evidence | Yes | No | Release-scope audit and reproducibility status |
| `{stem}.audit.raw.json` | Published Evidence | Yes | No | Small machine-readable audit snapshot; complements `.md` evidence |
| `{stem}.audit.cleaned.json` | Published Evidence | Yes | No | Small machine-readable cleaned-audit snapshot |
| `{stem}.preprocess-report.json` | Published Evidence | Yes | No | Small preprocessing metrics JSON |
| `{stem}.analysis.md` | Reproducible Generated Artifact | No | Yes | Large full analyze report (~33KB–93KB+); reproducible via `memd analyze` |
| `{stem}.analysis.json` | Reproducible Generated Artifact | No | Yes | Very large analyze payload (PERMA ~428KB; LongMemEval ~38MB); reproducible |
| `{stem}.cleaned.jsonl` | Reproducible Generated Artifact | No | Yes | Large cleaned export; reproducible via preprocess step |
| `{stem}.input.jsonl` | Reproducible Generated Artifact | No | Yes | PERMA-generated memory export; reproducible via `run_perma_benchmark.py` |
| `{stem}.*-eval.json` / `*-eval.md` | Reproducible Generated Artifact | No | Yes | Optional clustering evaluation output; reproducible via `evaluate-clusters` |
| `clustering_quality.cluster-eval.*` | Reproducible Generated Artifact | No | Yes | Same as above |
| `*.log`, `scratch/`, `tmp/` | Temporary Output | No | Yes | Non-canonical scratch and logs |
| `report.json`, `report.md` (repo root) | Temporary Output | No | Yes | Ad-hoc local analyze outputs |
| `benchmark_10k.py` runtime output | Temporary Output | No | Yes | Performance smoke only; not published evidence |

---

## Current repository state (review snapshot)

### Tracked published evidence (good)

- `examples/benchmarks/longmemeval_sample.{baseline,audit.*.md,preprocess-report.*}`
- `examples/benchmarks/longmemeval_sample.audit.{raw,cleaned}.json`
- `examples/benchmarks/perma_user108.baseline.md`
- `docs/validation/*` benchmark docs
- `docs/benchmarks/LONGMEMEVAL-BENCHMARK.md`

### Present locally, correctly ignored

- `longmemeval_sample.analysis.{json,md}` (~38MB / ~332KB)
- `longmemeval_sample.cleaned.jsonl` (~739KB)
- `perma_user108.analysis.{json,md}`
- `perma_user108.input.jsonl`

### Inconsistencies / risks

| Issue | Evidence | Risk |
| --- | --- | --- |
| Stem-specific PERMA audit ignores | `.gitignore` lines 109–111 ignore only `perma_user108.audit.*.json` | Inconsistent with LongMemEval audit JSON policy; new stems need manual entries |
| Bare `perma` ignore rule | `.gitignore:147` matches `datasets/perma/**` | **Entire PERMA dataset treated as gitignored**; conflicts with PERMA benchmark reproducibility from clone |
| Global `*.jsonl` | `.gitignore:122` | Blocks all untracked JSONL, including new fixture exports; tracked fixtures remain only because already committed |
| Duplicate `*.analysis.json` rules | Lines 85 and 108 | Redundant; harder to maintain |
| PERMA audit markdown untracked | `perma_user108.audit.{raw,cleaned}.md` show as `??` | Published evidence exists but not yet committed; JSON counterparts explicitly ignored by stem-specific rules |
| `benchmark_10k.py` not in artifact policy | Script writes no canonical artifacts | Low risk; document as non-evidence performance smoke |

---

## Per-pipeline artifact map

### LongMemEval (`scripts/run_longmemeval_benchmark.py`)

| Artifact | Class | Commit | Ignore |
| --- | --- | :---: | :---: |
| Raw dataset (`datasets/evaluation/*.jsonl`) | Source Asset | No | Yes |
| `{stem}.audit.raw.{md,json}` | Published Evidence | Yes | No |
| `{stem}.preprocess-report.{md,json}` | Published Evidence | Yes | No |
| `{stem}.cleaned.jsonl` | Reproducible Generated | No | Yes |
| `{stem}.audit.cleaned.{md,json}` | Published Evidence | Yes | No |
| `{stem}.analysis.{md,json}` | Reproducible Generated | No | Yes |
| `{stem}.baseline.md` | Published Evidence | Yes | No |

### PERMA (`scripts/run_perma_benchmark.py`)

| Artifact | Class | Commit | Ignore |
| --- | --- | :---: | :---: |
| `datasets/perma/**` | Source Asset | Yes | No |
| `{stem}.input.jsonl` | Reproducible Generated | No | Yes |
| `{stem}.audit.raw.{md,json}` | Published Evidence | Yes | No |
| `{stem}.audit.cleaned.{md,json}` | Published Evidence | Yes* | No* |
| `{stem}.analysis.{md,json}` | Reproducible Generated | No | Yes |
| `{stem}.baseline.md` | Published Evidence | Yes | No |

\*For PERMA, cleaned audit equals raw audit (no preprocessing step). Both should follow the same retention policy as LongMemEval audit artifacts.

### Clustering evaluation (`memd evaluate-clusters`)

| Artifact | Class | Commit | Ignore |
| --- | --- | :---: | :---: |
| `datasets/validation/clustering_quality.json` | Source Asset | Yes | No |
| `examples/benchmarks/*-eval.{json,md}` | Reproducible Generated | No | Yes |

---

## Maintainer decision guide

```text
Is it a script, fixture, template, or small labelled dataset?
  -> Source Asset -> commit

Is it human-readable evidence for docs/README readers?
  -> Published Evidence -> commit

Is it large analyze output or regenerated JSONL?
  -> Reproducible Generated Artifact -> ignore

Is it scratch/log/ad-hoc?
  -> Temporary Output -> ignore
```

Never add ignore rules for: benchmark scripts, fixtures, validation docs, baseline markdown, or small audit/preprocess JSON without explicit maintainer approval.

---

## Recommended `.gitignore` updates (proposal only — not applied)

These are recommendations for maintainer review. **Do not apply automatically.**

### 1. Replace bare `perma` with a scoped dataset path

```gitignore
# Local PERMA dataset cache only (if needed)
datasets/perma/.cache/
```

**Justification:** Current rule `perma` (line 147) incorrectly ignores `datasets/perma/README.md` and the full PERMA dataset tree. PERMA benchmarking requires `datasets/perma/profile/` and related inputs. A bare `perma` pattern is unsafe and prevents clone-and-run reproducibility.

**Maintainer decision required:** whether `datasets/perma/` itself should be committed (large) or documented as a manual download step.

---

### 2. Remove stem-specific PERMA audit JSON ignores

Remove:

```gitignore
perma_user108.analysis.json
perma_user108.audit.raw.json
perma_user108.audit.cleaned.json
```

**Justification:** These create inconsistent policy versus LongMemEval (whose audit JSON is committed). Existing scoped rules already cover analysis JSON:

```gitignore
examples/benchmarks/*.analysis.json
```

Audit JSON files are small (~3–9KB) and serve as machine-readable published evidence alongside markdown.

---

### 3. Add explicit PERMA generated-input ignore

```gitignore
examples/benchmarks/*.input.jsonl
```

**Justification:** PERMA runner writes `{stem}.input.jsonl` to `examples/benchmarks/`. Global `*.jsonl` already ignores it, but an explicit examples-scoped rule documents intent and survives future relaxation of global `*.jsonl`.

---

### 4. Consolidate duplicate global analysis ignores

Keep one canonical block:

```gitignore
# Large reproducible analyze outputs (any path)
*.analysis.json
*.analysis.md
```

Remove duplicate `*.analysis.json` entry at line 108.

**Justification:** Reduces maintenance drift; behavior unchanged.

---

### 5. Narrow global `*.jsonl` to evaluation/generated paths (optional, high-impact)

Proposed replacement:

```gitignore
datasets/evaluation/
examples/benchmarks/*.cleaned.jsonl
examples/benchmarks/*.input.jsonl
```

And remove or relax global:

```gitignore
*.jsonl
```

**Justification:** Global `*.jsonl` blocks new committed fixtures under `tests/fixtures/` unless force-added. Narrowing to known large-export locations preserves fixture commit safety.

**Maintainer decision required:** confirm no other JSONL paths need tracking.

---

### 6. Add explicit cluster-eval ignore (already present; keep documented)

```gitignore
examples/benchmarks/*-eval.json
examples/benchmarks/*-eval.md
```

**Justification:** Already in `.gitignore`; retain as canonical reproducible evaluation output policy.

---

## Files to commit now (policy recommendation, not an action)

Based on current working tree:

| File | Recommendation |
| --- | --- |
| `examples/benchmarks/perma_user108.audit.raw.md` | Commit (Published Evidence) |
| `examples/benchmarks/perma_user108.audit.cleaned.md` | Commit (Published Evidence) |
| `examples/benchmarks/perma_user108.audit.raw.json` | Commit after removing stem-specific ignore (Published Evidence) |
| `examples/benchmarks/perma_user108.audit.cleaned.json` | Commit after removing stem-specific ignore (Published Evidence) |

Do not commit: `perma_user108.analysis.*`, `perma_user108.input.jsonl`, `longmemeval_sample.analysis.*`, `longmemeval_sample.cleaned.jsonl`.

---

## Related documents

- [BENCHMARK-WORKFLOW.md](BENCHMARK-WORKFLOW.md)
- [BENCHMARK-EVIDENCE-SUMMARY.md](BENCHMARK-EVIDENCE-SUMMARY.md)
- [PERMA-BENCHMARK-INTERPRETATION.md](PERMA-BENCHMARK-INTERPRETATION.md)
- [examples/benchmarks/README.md](../../examples/benchmarks/README.md)
- Cursor rule: `.cursor/rules/benchmark-artifact-retention.mdc`
