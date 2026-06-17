# README Accuracy Audit

Date: 2026-06-17  
Scope: independent validation of `README.md` claims against repository state  
Method: code inspection, artifact cross-check, and command execution (audit-only; README not modified)

---

## Verified Claims

### Version and feature presence (capabilities, not version label)

Despite the version-label mismatch documented below, the README’s **capability claims** are largely supported by implemented code:

| README claim | Verification |
| --- | --- |
| Parse JSON, JSONL, CSV, TXT | `memd/parser/loaders.py::load_memory_file` supports `.json`, `.jsonl`, `.csv`, `.txt` |
| Heuristic categorization | `memd/categorization.py` used in `analyze_file` |
| Semantic duplicate clustering (DBSCAN + cosine similarity) | `memd/clustering.py` uses `sklearn.cluster.DBSCAN` |
| Trusted vs unverified compression metrics | `memd/metrics.py::calculate_metrics` |
| Governance action planning | `memd/actions.py::plan_governance_actions` wired in pipeline |
| Recommendation layer (`merge`, `archive`, `review`, `keep`) | `memd/recommendations.py::plan_recommendations`, `resolve_memory_conflicts` |
| Recommendations integrated in pipeline | `memd/pipeline.py` calls `plan_recommendations` after `apply_policy` |
| Recommendations in reports | `memd/reports.py` serializes `recommendations`, `memoryResolutions`, `recommendationSummary` |
| Recommendation evaluation exists | `memd/benchmarks/recommendation_evaluation.py`, `scripts/run_recommendation_evaluation.py`, `tests/test_recommendation_evaluation.py` |
| Read-only / no memory mutation | No write-back paths in pipeline; `AGENTS.md` aligns |
| Output: terminal, JSON, Markdown | `memd/cli/app.py`, `memd/reports.py` |

Evidence sources used by recommendations (README list):

- Governance actions — mapped in `memd/recommendations.py`
- Lifecycle signals — `validation.memoryLifecycle` consumed
- Evolution signals — evolution/lifecycle corroboration paths present
- Trust analysis — cluster trust modifiers and evidence (`cluster_trust`)
- Policy decisions — `policyDecision` / `policy.blocked` modifiers

### Architecture (partial)

The README’s high-level ordering **Governance -> Policy -> Recommendations -> Reporting** matches `memd/pipeline.py`:

```
plan_governance_actions -> apply_policy -> plan_recommendations -> AnalysisReport
```

Recommendations are integrated and evaluation exists as a separate benchmark track.

### Benchmark tracks and commands

All README reproduction commands were validated on 2026-06-17:

| Track | Command | Result |
| --- | --- | --- |
| LongMemEval | `python scripts/run_longmemeval_benchmark.py datasets/evaluation/longmemeval_sample.jsonl` | Exit 0 (~6 min); artifacts written to `examples/benchmarks/` |
| PERMA | `python scripts/run_perma_benchmark.py --user-id user108` | Exit 0; 228 records generated and analyzed |
| Clustering | `python -m memd evaluate-clusters datasets/validation/clustering_quality.json` | Exit 0; JSON metrics returned |
| Lifecycle | `python -m pytest tests/test_lifecycle_evaluation.py -q` | 2 passed |
| Evolution | `python -m pytest tests/test_evolution_evaluation.py -q` | 2 passed |
| Recommendation evaluation | `python scripts/run_recommendation_evaluation.py` | Exit 0; overall/conflict accuracy 1.0000 |

### Benchmark metric highlights

Cross-checked against committed/generated artifacts:

| README highlight | Source artifact | Match |
| --- | --- | --- |
| LongMemEval meaningful rate `35.5%` -> `83.42%` | `examples/benchmarks/longmemeval_sample.baseline.md` | Yes |
| LongMemEval trusted compression `3.44%` | same | Yes |
| PERMA duplicate/compression `59.21%`, trusted `8.77%` | `examples/benchmarks/perma_user108.baseline.md` | Yes |
| PERMA audit verdict `poor_fit` | `examples/benchmarks/perma_user108.audit.raw.md` | Yes |
| Recommendation overall `1.0000 (22/22)` | `examples/benchmarks/recommendation_evaluation.json` | Yes |
| Per-action accuracies (merge/archive/review/keep) | same | Yes |
| Conflict resolution `1.0000 (3/3)` | same | Yes |

### Documentation links

All paths referenced in README were verified to exist:

- Core docs: `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/DECISIONS.md`, `docs/INSIGHTS.md`, `docs/ACTION-PLANNING.md`, `docs/POLICY-ENGINE.md`
- Validation docs: `docs/validation/CATEGORY-AUDIT-V2.md`, `DATASET-QUALITY-AUDIT.md`, `BENCHMARK-WORKFLOW.md`, `BENCHMARK-EVIDENCE-SUMMARY.md`, `CLUSTER-AUDIT.md`, `CLUSTERING.md`
- ADRs and v0.6 reports: `ADR-001`, `ADR-002`, Phase 1/2/3 implementation docs, `V0.6.1-RELEASE-HARDENING.md`
- `AGENTS.md`, `LICENSE`
- Benchmark fixtures/artifacts: `tests/fixtures/recommendation_gold.json`, `datasets/validation/clustering_quality.json`, `examples/benchmarks/recommendation_evaluation.{md,json}`

No broken references found.

### Roadmap accuracy

README correctly states:

- Recommendation generation and evaluation are **current / implemented**
- Simulation, workflow automation, and memory mutation/execution are **not implemented**
- Future layers are described as gated future work

No wording was found that implies Mem-D currently executes memory actions autonomously.

### Design principles

- Local-first, provider-independent core: supported
- Read-only inputs: supported for analysis path
- Explainable outputs: evidence fields on recommendations and validation payloads exist

---

## Inaccurate Claims

### 1. Version label (`v0.6.0`) — **material mismatch**

README states:

- `Version: v0.6.0`

Repository package metadata reports:

- `memd/__init__.py`: `__version__ = "0.1.0"`
- `pyproject.toml`: `version = "0.1.0"`
- CLI: `python -m memd --version` -> `memd 0.1.0`

**Verdict:** README version claim is not supported by package metadata or CLI output.

### 2. Architecture diagram — **conceptual oversimplification**

README diagram:

`Input -> Audit -> Analyze -> Governance -> Policy -> Recommendations -> Reporting`

Actual `analyze_file` pipeline is more granular and does **not** run dataset-quality `audit-dataset` as a first stage. Core flow is:

`parse/normalize -> categorize -> embed -> cluster -> validation audits -> metrics -> insights -> governance -> policy -> recommendations`

Issues:

- **Audit** as a standalone first step conflates two different concepts:
  1. External dataset audit CLI (`memd audit-dataset`) used in benchmark workflows
  2. In-pipeline validation audits (cluster/category/evolution/lifecycle) that occur mid-pipeline
- **Analyze** is not a single module boundary; parsing, categorization, clustering, and validation are distinct implemented stages.

**Verdict:** Directionally useful, but not a faithful representation of implemented pipeline boundaries.

### 3. Benchmark reproducibility prerequisites — **understated**

README lists LongMemEval reproduction without clearly stating that:

- `datasets/evaluation/longmemeval_sample.jsonl` is gitignored and must be acquired locally for fresh clones
- LongMemEval workflow runtime is substantial (~6 minutes in this audit environment)

PERMA reproduction similarly depends on local presence of:

- `datasets/perma/profile/user108/profile.json`
- `datasets/perma/profile/user108/tasks.json`

These may be untracked in some working copies even when present locally.

**Verdict:** Commands are valid where prerequisites exist, but README implies broader out-of-the-box reproducibility than a fresh clone guarantees.

---

## Missing Information

1. **Package version inconsistency** — README v0.6.0 vs package/CLI 0.1.0 is not explained.
2. **Recommendation benchmark scope** — README publishes `1.0000` accuracies without noting:
   - evaluation is on a small synthetic gold fixture (`14` cases, `22` memory resolutions)
   - metrics are regression gates, not production representativeness claims
3. **Lifecycle/evolution benchmark asymmetry** — listed as benchmark tracks, but:
   - no dedicated `scripts/run_*` artifact generators
   - no committed summary artifacts under `examples/benchmarks/` (unlike recommendation/LongMemEval/PERMA)
4. **Linked architecture doc drift** — `docs/ARCHITECTURE.md` remains V1-oriented and does not document the recommendation layer; README still points readers there for architecture context.
5. **Clustering benchmark metrics** — README no longer includes the labelled clustering precision/recall table (not inaccurate, but less complete than prior README and than `BENCHMARK-EVIDENCE-SUMMARY.md`).
6. **PERMA benchmark caveat** — README cites `poor_fit` only indirectly via metrics; it does not state that PERMA path is metadata-derived and intentionally limited (documented elsewhere, absent from README highlights).

---

## Broken References

**None found.**

All README-linked paths resolve to existing files in the repository.

---

## Suggested Corrections

Priority-ordered, README-only guidance (for future maintainers):

1. **Align version labeling**
   - Either bump `pyproject.toml` / `memd/__init__.py` to `0.6.0`, or change README to match current package version and add a release note explaining v0.6 capability milestone vs package semver.

2. **Clarify architecture wording**
   - Replace or annotate the diagram to distinguish:
     - `memd analyze` pipeline stages (parse -> categorize -> cluster -> validation -> governance -> policy -> recommendations -> report)
     - optional benchmark `audit-dataset` step used in LongMemEval/PERMA workflows
   - Avoid presenting dataset audit as mandatory first step of all analysis.

3. **Add benchmark prerequisites**
   - Note LongMemEval input is local/gitignored.
   - Note PERMA requires committed profile subset files for `user108`.
   - Optionally mention expected runtime for LongMemEval workflow.

4. **Scope recommendation quality claims**
   - Add one sentence: metrics are from ADR-002 gold-fixture evaluation (`recommendation_gold.json`), not end-to-end operator validation.
   - Preserve numbers, but avoid implying universal recommendation correctness.

5. **Differentiate benchmark track maturity**
   - Mark lifecycle/evolution as pytest gold-fixture evaluations.
   - Mark LongMemEval/PERMA/recommendation as script-driven artifact benchmarks with published outputs.

6. **Refresh architecture doc link context**
   - Add note that v0.6 recommendation architecture is in ADR-001 / Phase docs, while `docs/ARCHITECTURE.md` is broader V1 baseline documentation.

---

## Marketing vs Reality Assessment

| Area | README posture | Reality check |
| --- | --- | --- |
| Memory intelligence (not just audit) | Positions Mem-D as evidence-based intelligence | Supported by governance + recommendations; still analysis-only |
| Automation / actions | Explicitly says no autonomous actions / no mutation | Accurate |
| Memory management | Does not claim to manage memory | Accurate |
| Recommendation quality | Presents perfect accuracies prominently | Technically true on gold fixture; can overstate real-world readiness without fixture-scope caveat |
| Benchmark coverage | “Currently supported tracks” lists six tracks | All exist, but lifecycle/evolution are test-suite evaluations without published benchmark summaries |
| Product progression | Future simulation/workflows/actions clearly deferred | Accurate |

**Primary overstatement risk:** presenting `1.0000` recommendation accuracies without gold-fixture scope context.

**Secondary risk:** `v0.6.0` branding while tooling reports `0.1.0`.

---

## Final Verdict

**MOSTLY ACCURATE WITH MATERIAL CAVEATS**

The README accurately reflects v0.6 **capabilities** (recommendation generation, pipeline integration, recommendation evaluation, benchmark tracks, and published metric values). Roadmap boundaries and non-execution posture are well aligned with code and `AGENTS.md`.

However, the audit found one **material inaccuracy** (version label mismatch) and several **accuracy gaps** that should be addressed before treating README as fully authoritative:

1. README `v0.6.0` != package/CLI `0.1.0`
2. Architecture diagram oversimplifies/misplaces “Audit” relative to implemented pipeline
3. Benchmark reproduction prerequisites and evaluation-scope caveats are under-documented
4. Recommendation quality metrics are correct but can be misread without gold-fixture context

No broken documentation links were found. No roadmap wording was found that implies implemented execution layers.

**Recommendation:** README is suitable as a v0.6 capability overview after correcting version alignment and adding short scope/prerequisite clarifications. Until then, treat `BENCHMARK-EVIDENCE-SUMMARY.md`, ADR-002, and package metadata as authoritative for version and benchmark-scope claims.
