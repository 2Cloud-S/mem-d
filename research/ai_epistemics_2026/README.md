# AI × Epistemics Research Sprint — Phase 1

**Working title:** “When AI Forgets the Caveat: Evaluating Decision-Preserving
Memory Deduplication.”

This directory contains a [research protocol](PROTOCOL.md) and
[20 synthetic development cases](development.jsonl), not experimental results.
**No downstream experiment has run.** No held-out cases, model outcomes,
production-memory changes, or dashboard are included. The study is not
submission-ready; the outcome and novelty remain open.

## Provenance and inherited components

- Recorded preexisting baseline:
  [`14af8eccc0141450d01981e189a48b72140ce754`](https://github.com/2Cloud-S/mem-d/commit/14af8eccc0141450d01981e189a48b72140ce754).
- Remote sprint head and local HEAD at implementation start on 2026-11-14:
  `14af8eccc0141450d01981e189a48b72140ce754`, branch
  `sprint/ai-epistemics-2026`. The commit was verified as a commit object after
  fetching/cloning the existing branch. There were no subsequent sprint commits
  or unrelated local modifications in this checkout at that point.
- Inherited code: parsing/normalization, embedding backends, cosine/DBSCAN
  clustering, trust, lifecycle/evolution, governance policy, recommendation
  resolution/reporting, read-only structural simulation, workflow planning,
  and their fixture-based evaluations. Source inspection included the root
  AGENTS instructions, README, recommendation engine, runtime contracts,
  data-contract documentation, ADR-001, ADR-002, and recommendation benchmark
  documentation. No nested AGENTS files exist at this baseline.
- The baseline README calls simulation/workflows future work, but
  `memd/pipeline.py`, `memd/simulation.py`, `memd/workflows.py`, and runtime
  contracts already implement read-only projections/planning. These are inherited,
  not sprint contributions. No autonomous execution is introduced.
- Recommendation-fixture accuracy measures conformity to architecture-intended
  rules on supplied evidence. It establishes neither downstream decision benefit
  nor decision-preserving compression. Structural savings are not actual tokens.

New Phase 1 files are `PROTOCOL.md`, `development.jsonl`, this `README.md`, and
`validate_development.py` in this directory. The only change outside the directory
is a short disclosure/link in the root README's recommendation-evaluation section.
Production code, contracts, and benchmark artifacts are unchanged.

The English cases were manually authored by the coding assistant from fictional
scenarios and serialized locally. They were not sampled from deployment data or
produced by an experimental model run. All named people, organizations, products,
events, and source registers in the cases are fictional. Future dates inside
records are part of the fiction, not observations of future events.

## Dataset contract and input isolation

This is a research case format, **not a memory export**. Do not give the complete
JSONL file to `memd analyze`, a merge model, or a downstream solver. Existing
parsers can retain unknown keys as metadata, so passing whole cases risks leaking
gold annotations even if the top-level key names look separate.

| Location | Fields and purpose |
| --- | --- |
| Top level | `schema_version` (`1.0`), unique `case_id`, `family_id`, `category`, `split` (`development`), `input`, `evaluator_only` |
| `input` | `memories`, `question`, `decision_criteria`, `answer_options` |
| Each memory | Globally unique opaque `id`, `content`, fictional `source`, UTC `timestamp`; no unrestricted metadata field |
| `evaluator_only` | `acceptable_answer_labels`, `rationale`, `decisive_evidence_ids`, `must_survive`, `merge_safety` |
| Each required detail | Unique `detail_id`, semantic `description`, supporting `evidence_ids` |
| Merge safety | `operation`, `candidate_memory_ids`, `judgment` (`safe`/`unsafe`), `rationale` |

All cases offer all three answer labels in the same order: `proceed`,
`do_not_proceed`, `insufficient_evidence`. Offering a label is not gold disclosure.
Actual acceptable labels belong exclusively in `evaluator_only`.

For the future harness, explicitly construct allowlisted payloads, for example:

```python
from copy import deepcopy

# case has already passed validation. Do not pass case itself to any model.
merge_input = [
    {key: record[key] for key in ("id", "content", "source", "timestamp")}
    for record in case["input"]["memories"]
]
solver_input = {
    "memories": deepcopy(transformed_memories),  # same four allowed record fields
    "question": case["input"]["question"],
    "decision_criteria": case["input"]["decision_criteria"],
    "answer_options": list(case["input"]["answer_options"]),
}
```

Never send gold labels, rationales, evidence IDs, required details, safety
judgments, case/category/family bookkeeping, or recommendation explanations to
the downstream solver. Merge policies also must not see questions or criteria.
Enforce isolation in tests before the future harness runs models; field
validation alone cannot prove that future prompt-building code is leak-free.

Evidence references are evaluator pointers, not lists of records that must all
remain verbatim. Several IDs may redundantly support one description, or jointly
support it. Audit preservation of the **description's meaning**, not survival of
every referenced ID. A retained duplicate can preserve the detail completely.
Decision criteria remain unchanged in every condition and are not counted as
memory content retained by a merge.

The independent safety annotation concerns **arbitrary single-record replacement
of the specified group**, with all other records held fixed. It is independent
of mem-d predictions. `unsafe` indicates that a representative can lose a
required distinction; it does not label every possible medoid or faithful summary
unsafe. Actual transformations need their own audit. In `dev_011`, either original
singleton can still support an insufficient-evidence answer, although a required
stock/estimate distinction is lost: detail loss and decision error are separate
outcomes. In `dev_015`, redundant uncertainty notes are safe to collapse while
the separate decisive approval must remain.

## Composition, families, and author review

There are five cases per category, 52 memory records, and 37 required-detail
annotations. The labels comprise ten `proceed`, four `do_not_proceed`, and six
`insufficient_evidence` cases. Six annotated candidate groups are interchangeable;
fourteen are not. These are **dataset properties**, not measured system results.

Ten scenario families pair `dev_001`–`dev_005` with `dev_006`–`dev_010`, and
`dev_011`–`dev_015` with `dev_016`–`dev_020`, respectively. Each pair shares an
underlying scenario setup. Count ten development families, not twenty independent
observations. Future held-out families must be structurally distinct; changing
names, numbers, wording, or timestamps is not a valid split. No held-out material
is authored here. English phrasing varies; multilingual coverage is not claimed.

Every case received an assistant author review on 2026-11-14 against its actual
serialized memories, criteria, label, evidence references, surviving details,
and safety scope. The review balanced decisive evidence across first/later
records and ID positions and removed criteria-only claims from memory-retention
annotations. This is **not independent human validation**. Labels below summarize
that review, not any model predictions.

| Case | Family | Gold decision | Review finding |
| --- | --- | --- | --- |
| dev_001 | 01 | proceed | Identical sandbox approvals preserve scope. |
| dev_002 | 02 | proceed | Identical availability notices include a harmless cupboard exception. |
| dev_003 | 03 | proceed | Paraphrased purchasing approval and 48/50 price/cap; inventory distractor irrelevant. |
| dev_004 | 04 | do_not_proceed | Duplicate prohibitions are safe to compress despite rejecting the action. |
| dev_005 | 05 | proceed | All three paraphrases contain validation and clearance for S8. |
| dev_006 | 01 | do_not_proceed | Explicit production negation overrides apparent readiness. |
| dev_007 | 02 | proceed | Manager's scoped reopening permits the requested club/time. |
| dev_008 | 03 | proceed | Sample classification activates the higher cap; 80 is within 100. |
| dev_009 | 04 | proceed | Signed staging exception enables the planned environment. |
| dev_010 | 05 | do_not_proceed | Pending validation explicitly blocks pruning; storage pressure is no exception. |
| dev_011 | 06 | insufficient_evidence | Estimated arrival and confirmed stock are not a delivery commitment. |
| dev_012 | 07 | proceed | Signed QA approval governs; an observer's guess has no veto. |
| dev_013 | 08 | proceed | Approved 11:00 booking governs over an unapproved 10:00 draft. |
| dev_014 | 09 | do_not_proceed | Purchasing denial governs over an individual's preference. |
| dev_015 | 10 | proceed | K2 approval survives; duplicate uncertainty concerns a separate document. |
| dev_016 | 06 | insufficient_evidence | Equal-authority commitments conflict across the deadline; recency does not settle them. |
| dev_017 | 07 | insufficient_evidence | Opposed signed results for the same build have no correction or ranking. |
| dev_018 | 08 | insufficient_evidence | Conflicting approved starts have no cancellation or precedence. |
| dev_019 | 09 | insufficient_evidence | Approval and denial remain active with equal authority. |
| dev_020 | 10 | insufficient_evidence | Same-time approval and hold remain unresolved; negation does not win by default. |

## Validation and repository checks

From the repository root:

```bash
python research/ai_epistemics_2026/validate_development.py
python -m ruff check research/ai_epistemics_2026
python -m ruff check .
python -m pytest
git diff --check
```

The validator uses only the standard library and accepts an optional JSONL path.
It exits nonzero on invalid JSON, duplicate keys, nonstandard constants, blank
records, wrong totals, missing/unknown fields, invalid labels/timestamps, duplicate
IDs, broken evidence references, invalid family/category pairing, non-development
splits, or structural annotation leakage into public input/memory fields. It
cannot establish semantic truth, independent family identity, or label correctness;
those require review.

Checks performed on 2026-11-14 with Python 3.12.14, pytest 9.2.0, and Ruff 0.17.5:

- Dataset validation passed: 20 cases; five per category; ten paired families;
  unique IDs and valid evidence links; strict field separation.
- All 52 public memory records satisfy the inherited `MemoryRecord` contract;
  inherited normalization preserves their IDs, content, sources, and timestamps.
- Twenty temporary negative checks passed: sixteen structural/leakage mutations
  and four malformed/duplicate-key/blank/nonstandard-constant JSONL inputs were
  correctly rejected. No mutation fixtures were added to production data.
- New research Python code passes Ruff. `git diff --check` passes.
- Full repository Ruff reports **86 existing findings** across thirteen files;
  every flagged file is unchanged from the baseline. No lint suppression or
  unrelated cleanup is introduced.
- Full pytest: **443 passed, 2 skipped, 2 failed**. The same counts and failures
  reproduce in a detached checkout of the baseline. Both failures are
  `test_load_memory_file_supported_formats`, for missing baseline files
  `tests/fixtures/memories.txt` and `tests/fixtures/memories.jsonl`.

These checks validate artifacts and inherited behavior, not downstream utility.
Existing benchmark output files were not regenerated.

## Next implementation step and remaining issues

Build the external disposable-copy harness described in the protocol. First test
input allowlists, source immutability, fixed-medoid equivalence, gate veto
preservation, actual backend detection, token serialization, invalid responses,
and family-paired analysis without making model calls. Pin model/tokenizer
revisions and dependencies before execution, then run development only. Freeze
policies before generating or accessing later held-out families.

Independent human review, broader family coverage, downstream-model feasibility,
power/sample-size planning, and a refreshed novelty assessment remain open.
Existing lint/missing-fixture problems remain repository limitations. The close
related work means the defensible contribution must be established empirically,
not asserted from this protocol or from the existing fixture scores.
