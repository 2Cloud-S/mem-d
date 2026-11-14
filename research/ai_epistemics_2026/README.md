# AI × Epistemics Research Sprint — Phases 1–3

**Working title:** “When AI Forgets the Caveat: Evaluating Decision-Preserving
Memory Deduplication.”

This directory contains a [research protocol](PROTOCOL.md),
[20 synthetic development cases](development.jsonl), and an external Phase 2
harness with development compression-feasibility artifacts.
Phase 3 adds an exploratory local downstream pilot; see [PILOT_PLAN.md](PILOT_PLAN.md)
and [PILOT_RESULTS.md](PILOT_RESULTS.md) for its scope and findings. The Phase 1–2B
sections below are historical delivery records: their statements about no solver
calls describe their own phase. No held-out cases, production-memory changes,
or dashboard are included. The study is not submission-ready; broader decision
benefit, semantic safety, and novelty remain open.

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

## Phase 1 handoff (historical)

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

## Phase 2 harness and commands

Phase 2 starts from `6df6d250c859cb0826973e2497ba754772c06a3c` on the same sprint
branch. The dataset, production modules, inherited tests/fixtures, benchmark
outputs, and existing gate policies are unchanged. New implementation lives in
`harness/`, with offline validity tests in `tests/test_validity.py`, model locks,
dependency instructions, and the artifacts linked below. Protocol clarifications
are dated and explained in the final section of [PROTOCOL.md](PROTOCOL.md).

Architecture:

- `transform.py` constructs memory allowlists, fixed medoids, exact groups, and
  whole-group gate decisions. Gated/ungated conditions share one candidate list.
- `backend.py` loads pinned local snapshots, verifies the actual sentence-transformer
  path, and observes genuine `memd.pipeline.analyze_file` output. The adapter
  receives only original records. Every call uses a new disposable input file;
  originals and solver survivor payloads remain unchanged.
- `requests.py` constructs stateless, allowlisted solver messages with the fixed
  original query time and shared seeded survivor ordering. Routing metadata is
  outside `request`; a transport receives only `row["request"]`.
- `runner.py` prepares thresholds/prefixes, freezes transformations and requests,
  then makes category-based feasibility summaries and an unscored audit template.
  It never calls a solver. The frozen response state explicitly records zero
  collected responses; there are no fake response files in feasibility artifacts.
- `artifacts.py` records content hashes, source files, dependencies, model assets,
  configurations, and seeds. `execution.py` defines the future transport boundary,
  identical infrastructure retries, response freezing, and strict parsing.
- `analysis.py` scores only after request/response freezes verify; it propagates
  infrastructure exclusions to every condition in a paired block, weights cases
  within families, and resamples families together for intervals and ratios.
  It also provides a paired gated-minus-semantic contrast. Model/revision and
  operating points are analyzed separately, never pooled as independent samples.

Install the repository development dependencies, then the optional local-model
dependencies in a virtual environment:

```bash
python -m pip install -e '.[dev]'
python -m pip install 'torch==2.6.0+cpu' --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r research/ai_epistemics_2026/requirements-phase2.txt
```

Prepare the pinned snapshots and model-ready messages (downloads are public
model assets, not solver calls):

```bash
python -m research.ai_epistemics_2026.harness dry-run \
  --cache /tmp/memd-research-cache --download --output /tmp/memd-development-run
```

For a cached, network-independent rerun, use a new output directory:

```bash
HF_HUB_OFFLINE=1 python -m research.ai_epistemics_2026.harness dry-run \
  --cache /tmp/memd-research-cache --output /tmp/memd-development-replay
```

The CLI refuses to overwrite runs. `--without-tokenizer` explicitly yields null
token counts. Without a cached embedding snapshot, offline preparation fails
explicitly; hashing cannot silently substitute for real embeddings. An invalid
preparation creates `blocked.json`, not a valid feasibility report.

No solver is selected in this phase: manifests use `UNASSIGNED` identities and
real transport execution rejects them. A later preparation can supply both
`--solver-model` and `--solver-revision` before the freeze. The messages are
provider-neutral; an adapter must translate the fixed temperature/output limit
without changing prompts and supply structured status metadata. No provider
adapter, credentials, paid API, or solver-execution CLI is bundled. The pinned
tokenizer must be aligned with any future solver before claiming its token cost.

For later **real** responses, the offline interfaces are:

```bash
python -m research.ai_epistemics_2026.harness import-responses \
  --run /tmp/future-pinned-run --responses /tmp/future-real-responses.jsonl
python -m research.ai_epistemics_2026.harness score --run /tmp/future-pinned-run
```

Each response envelope must have `request_id`, `status`, `text`, `attempts`, and
`provenance`. Attempts retain status/text and optional diagnostic messages; only
infrastructure failures permit retries (at most two). Final status/text must match
the last attempt, and every frozen request must have exactly one envelope. Status
is `ok`, `truncated`, `refusal`, `context_overflow`, or `infrastructure`.
`Transport.submit` receives a fresh copy of only the model/messages request.
Synthetic transports declare `synthetic_test_fixture` and exist only in tests;
the CLI rejects their import/publication. Strict parsing never repairs answers.
No response import or decision-scoring command was run for development feasibility.

## Development-only compression feasibility (2026-11-14)

The real local embedding check **completed**. Immutable model locks are in
[model-lock.json](model-lock.json):

- Embeddings: `BAAI/bge-small-en-v1.5` at
  `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`, CPU SentenceTransformer, 384 dimensions,
  one Torch thread. Every returned vector set was verified against the actual
  parent sentence-transformer path; hashing fallback was not used.
- Tokenizer only: `Qwen/Qwen2.5-0.5B-Instruct` at
  `7ae557604adf67be50417f59c2c2f167def9a775`. No Qwen generation weights or solver
  calls were needed. Tokens count compact displayed memory JSON with IDs/source/time,
  no special tokens or truncation; they are not total inference cost.

The corpus has 52 records and 3,290 memory-section tokens. The five duplicate
controls have 12 records and 766 such tokens. Table entries use the full candidate
prefix at each threshold (k=1 here); all empty prefixes and exact/original anchors
remain in the machine-readable artifacts. Token savings below are actual counts
averaged over the three shared order seeds; the seeds yielded equal totals here.

| Threshold | Candidate groups | Ungated executed / records removed / tokens saved | Gated executed / records removed / tokens saved | Gated duplicate-control groups / records removed / tokens saved | Review / approval groups | Flagged conflict / other-only veto groups |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.45 | 20 | 20 / 31 / 1,900 | 2 / 2 / 136 | 2 / 2 / 136 | 18 / 18 | 0 / 0 |
| 0.55 | 19 | 19 / 28 / 1,727 | 2 / 2 / 136 | 2 / 2 / 136 | 17 / 17 | 0 / 0 |
| 0.65 | 19 | 19 / 23 / 1,410 | 2 / 2 / 136 | 2 / 2 / 136 | 17 / 17 | 0 / 0 |
| 0.75 | 17 | 17 / 18 / 1,094 | 2 / 2 / 136 | 2 / 2 / 136 | 15 / 15 | 0 / 0 |
| 0.85 | 9 | 9 / 10 / 613 | 2 / 2 / 136 | 2 / 2 / 136 | 7 / 7 | 0 / 0 |
| 0.95 | 6 | 6 / 6 / 377 | 3 / 3 / 194 | 3 / 3 / 194 | 3 / 3 | 0 / 0 |

At every threshold exact deduplication removes two records in two duplicate
controls, saving 136 tokens. Original removes nothing. At 0.55 the gate's record
reduction is **2/52 (3.85%)**, while its token compression is **136/3,290 (4.13%)**;
these measures are distinct. At 0.95 they are **3/52 (5.77%)** and
**194/3,290 (5.90%)**. On duplicate controls, gated savings are 136/766 (17.75%)
through 0.85, and 194/766 (25.33%) at 0.95. There are zero keeper disagreements in
this development run; test fixtures cover disagreement explicitly.

These are positive but limited compression findings. The gate compresses the
exact duplicate controls `dev_001`/`dev_002`; at 0.95 it additionally merges
`m005_1`/`m005_3`, a paraphrase pair in a duplicate control. It does not refuse all
compression. At 0.55, however, it refuses all three paraphrased duplicate-control
groups (`dev_003`–`dev_005`). Their genuine evidence shows mixed heuristic
categories, no dominant category, multiple-concept audit judgments, Medium trust
0.6, and taxonomy/over-clustering review. These are observed inherited signals,
not fabricated trust or an assessment that those controls are truly unsafe.

Review/approval counts overlap: every vetoed group here contains review
dispositions and approval-required recommendations. Additional nonexclusive
integrity reasons, such as no merge recommendation or no keeper, are consequences
of those review dispositions. “Conflict” counts only explicit mem-d conflict
flags; zero does **not** mean the fictional evidence has no contradictions.
Review frequency uses all semantic candidate groups, with separate prefix-specific
counts; semantic/exact conditions have no human-review mechanism. The artifact
tables include raw reasons, untouched records, family-mean compression fractions,
and token-specific compression matching.

**No positive-compression point matches ungated compression within the protocol's
two-percentage-point tolerance on this common-prefix grid.** Only zero-compression
points match. The smallest nonzero ungated compression is 377/3,290 (11.46%),
above the gate's maximum 5.90%. Do not infer a matched-compression decision benefit
or interpolate one. No labels, thresholds, policies, or records were adjusted to
improve this finding. Critical-detail retention, unsafe-merge rate, explanation
quality, and downstream decision error remain unscored, pending independent audits
and real solver responses.

### Inherited workflow blocker and auditable artifacts

The first attempt aborted on inherited workflow validation. Under the documented
pre-retry protocol clarification, the adapter now observes genuine upstream
recommendations and records downstream failure without changing those functions.
Of 120 case/threshold pipeline calls, four fail after recommendations:
`dev_009`, `dev_013`, `dev_015` at 0.45; `dev_015` at 0.55. All are workflow
`WorkflowItem` validation errors. A direct call to the unchanged pipeline in a
detached baseline checkout reproduces the `dev_015` error with the same pinned
real embedding model. This remains a production issue, not a research fix.

Artifacts are under [artifacts/phase2-development-2026-11-14/](artifacts/phase2-development-2026-11-14/):
`manifest.json`, `feasibility.json`, the initial `initial-blocker.json`,
`SHA256SUMS`, and a compressed `run.tar.gz`. The archive contains 240 transformation
rows, 2,880 unsubmitted requests, manifests/freezes, a zero-response state, and an
**unscored evaluator-only** audit template. It contains no model weights, solver
responses, or synthetic decision statistics. Never hand the archive/audit template
to a solver; use only an individual allowlisted request payload.

The run manifest records the Phase 1 parent commit plus SHA-256 hashes of the
then-uncommitted Phase 2 code/configuration and all model asset files. The present
commit carries that source; the archive is not claimed to have been generated from
a clean already-committed checkout. This avoids a circular artifact/commit hash.

Verify and inspect the committed run without downloading models:

```bash
cd research/ai_epistemics_2026/artifacts/phase2-development-2026-11-14
sha256sum -c SHA256SUMS
mkdir -p /tmp/memd-phase2-inspect
tar -xzf run.tar.gz -C /tmp/memd-phase2-inspect
cd /path/to/mem-d
python - <<'PY'
from pathlib import Path
from research.ai_epistemics_2026.harness.artifacts import verify
directory = Path('/tmp/memd-phase2-inspect/phase2-run')
verify(directory)
verify(directory, 'audit.freeze.json')
PY
```

### Phase 2 checks and next task

Checks actually run: 40 focused offline validity tests pass; research Ruff passes;
the unchanged 20-case dataset validator passes; all frozen artifact checksums
verify. Repeated real local preparations reproduce byte-identical transformation
and request files. Tests cover all required veto/isolation/backend/token/response/
pairing/family failure modes, including hand-calculated family means and bootstrap
endpoints. Synthetic test statistics are not exported as experimental findings.

Combined repository/research pytest: **483 passed, 2 skipped, 2 failed**. The two
failures remain the missing baseline TXT/JSONL parser fixtures described above.
Repository Ruff still has **86 preexisting findings** in thirteen unchanged
files; no suppression or unrelated fixture/benchmark changes were made. The newly
observed downstream workflow defect is recorded separately from those suite failures.

The next task is to independently audit the actual executed and vetoed medoid
outputs, and resolve the lack of comparable nonzero compression **before** a
confirmatory solver comparison. Any expanded budget grid or matching procedure
requires an explicit prospective protocol amendment, not a favorable retrofit.
Then pin distinct downstream model families and matching tokenizers, integrate
real transports, and freeze a new development run before collecting responses.
This phase ends with no solver calls, paid APIs, held-out generation, new
safeguard, or decision-benefit claim.

## Phase 2B: corpus budgets, incremental value, and pending audits

Phase 2B continues from `489e3ddeb97afa2ed250d83ba3a2a8c3adb3ef8d`. Read the
[decision memo](PHASE2B_MEMO.md) for the five conclusions and next decisions.
The prospective [protocol amendment](PROTOCOL.md#phase-2b-amendment--corpus-budgets-and-blinded-audits)
was recorded before generating these comparisons. It is informed by development
feasibility, not an independent preregistration. The Phase 2 grid/findings above
and its archived artifacts are preserved as historical results.

Diagnosis: the frozen candidate-count histogram has only zero/one groups per
case at every threshold. Consequently the historical shared cap 0 selects none
and cap 1 selects every available group across stores before gating. Its lack
of nonzero compression matches was partly a coarse-grid limitation. The gate's
refusals and limited savings remain separate observations.

New modules, without changing the existing gate/transform/prompt implementation:

- `harness/budgets.py`: global similarity ordering, all corpus prefixes, actual
  token matching, byte identity, and review-burden accounting. Ranking uses only
  frozen group similarities and original IDs; matching uses only actual token
  sums and prefix length. No categories, gold, audit judgments, or answers enter
  either choice. This is an **offline corpus-level budget control**, not a
  deployable query-blind per-store policy. No cross-case clustering is performed.
- `harness/blind_audits.py`: unique fixed-medoid proposals, neutral record aliases
  and audit IDs, a reviewer-only packet/template, and separate evaluator mapping.
- `harness/phase2b.py`: verifies the historical freezes, data and committed code
  hashes; checks unchanged candidates, medoids, gate outputs and payloads; then
  runs tokenization locally. It reuses genuine frozen pipeline evidence and
  does not rerun embeddings or alter recommendations. Selection freezes before
  identity checks and audit export. The inherited workflow failures remain in
  source provenance; nothing repairs or suppresses them.

For each threshold the gate's full-prefix output is matched to the nearest
similarity-first global prefix at that same threshold, minimizing the absolute
token-savings gap and then shorter prefix length. Every prefix, including zero,
is retained. Integer sums over three order seeds avoid rounding ties. The
inclusive tolerance is two percentage points of the original corpus token budget;
missing counts make matching unavailable, and unmatched points remain unmatched.
Identity, safety, categories, and answers do not break matching ties. No random
budget control, interpolation, or cross-threshold selection is introduced.

All six matches are nonzero, but five have **identical** transformed payloads:

| Threshold | Candidates | Gate groups / records / cases; tokens saved | Similarity prefix; groups / records / cases; tokens saved | Absolute token gap | Gate identical to exact / selected control | Review / approval groups |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| 0.45 | 20 | 2 / 2 / 2; 136 | 2; 2 / 2 / 2; 136 | 0 | yes / yes | 18 / 18 |
| 0.55 | 19 | 2 / 2 / 2; 136 | 2; 2 / 2 / 2; 136 | 0 | yes / yes | 17 / 17 |
| 0.65 | 19 | 2 / 2 / 2; 136 | 2; 2 / 2 / 2; 136 | 0 | yes / yes | 17 / 17 |
| 0.75 | 17 | 2 / 2 / 2; 136 | 2; 2 / 2 / 2; 136 | 0 | yes / yes | 15 / 15 |
| 0.85 | 9 | 2 / 2 / 2; 136 | 2; 2 / 2 / 2; 136 | 0 | yes / yes | 7 / 7 |
| 0.95 | 6 | 3 / 3 / 3; 194 | 3; 3 / 3 / 3; 192 | 2 | no / no | 3 / 3 |

Exact deduplication is a primary anchor at **every threshold**: two groups, two
records, two cases affected, and 136 memory tokens saved. Original saves zero.
All identity statements compare complete survivor bytes and all 60 case/seed
solver-message payloads, not merely token totals. At 0.55 the gate adds no
transformation beyond exact matching or similarity prefix 2. Higher review burden
does not establish better discrimination; these controls have no review mechanism.
Vetoed groups equal the review counts here, with zero explicit conflict flags;
nonexclusive reason counts are preserved in `comparisons.json` and source evidence.
Review recommendations also apply to memories outside selected candidate groups:
the reviewed-memory counts are **48, 46, 43, 36, 27, 23 out of 52**, respectively,
over the six increasing thresholds. These are recommendation frequencies, not
observed human review time, and are reported separately from candidate-group rates.

At 0.95, mem-d adds only the `m005_1`/`m005_3` paraphrase merge over exact matching,
removing `m005_3` for **58 incremental tokens**. The selected simple control instead
merges `m016_1`/`m016_2`, keeping `m016_1`. Both remove three records across three
cases overall, but their payloads differ in `dev_005` and `dev_016`. The control
saves 56 tokens over exact deduplication. Its signed residual relative to mem-d is
−2 tokens: an absolute 2/3,290 = **0.06079 percentage points**, or 2/194 = **1.03%**
of the gate savings. The allowed 0.02 × 3,290 = **65.8-token** gap would have been
permissive at this scale; the actual selected gap is reported rather than hidden
behind the tolerance. No same-threshold global prefix reproduces the gate at 0.95.
All 114 operating points (96 global prefixes plus 18 anchors) are published,
including their token totals, groups, records, affected cases, and payload hashes.
These development points are not independent observations and establish no
downstream decision improvement or independent semantic safety result.

### Reproduce Phase 2B without embeddings or solvers

Use the Phase 2 archive extraction instructions above to obtain an intact
`phase2-run` directory. Install the same dependencies and pinned tokenizer cache
as Phase 2, then run:

```bash
HF_HUB_OFFLINE=1 python -m research.ai_epistemics_2026.harness.phase2b \
  --source /tmp/memd-phase2-inspect/phase2-run \
  --cache /tmp/memd-research-cache --output /tmp/memd-phase2b-run
```

The cache needs the pinned Qwen tokenizer, whose asset hashes must match Phase 2.
There is no model-download option in this replay command. Missing/mismatched
assets fail explicitly. The output directory must be new. No embeddings, source
memories, prior artifacts, labels, recommendations, or solver responses are generated
or changed. Actual tokenization uses the unchanged display serialization and seeds.

The new run is archived at
[artifacts/phase2b-development-2026-11-14/](artifacts/phase2b-development-2026-11-14/).
It includes readable `comparisons.json`, `operating-points.json`, `matching.json`,
`rankings.json`, `manifest.json`, audit directories, `SHA256SUMS`, and `run.tar.gz`.
The archive includes the complete `points.jsonl` survivor payloads and selection/
analysis freezes. Source hashes record the Phase 2 parent plus new worktree code,
protocol, and rubric. Preserve the historical source freeze separately.

Run `sha256sum -c SHA256SUMS` in that artifact directory. After extracting the new
archive, verify `selection.freeze.json` and `analysis.freeze.json` in its root,
then the default `freeze.json` separately in `reviewer/` and `evaluator-only/`,
using `harness.artifacts.verify`. `child-freezes.json` records the audit-directory
freeze digests. These checks detect artifact edits, not reviewer agreement.

### Blinded semantic audit handoff — human review pending

Share **only `reviewer/`**, not this README/memo, source dataset, comparisons,
rankings, or `evaluator-only/`. Its files are:

- `packets.json`: 29 unique actual proposals from 90 threshold/group occurrences,
  with originals, proposed survivors, question/criteria, fixed query time, and
  neutral audit IDs. Original record IDs become local aliases. Identical reviewer
  content is deduplicated before presentation is shuffled with seed 20262.
- `rubric.md`: the [neutral rubric](AUDIT_RUBRIC.md) asks for relevance loss,
  scope/negation/certainty/attribution/time changes, justified-decision changes,
  ambiguity/unscorability, and a short evidence-based rationale. It explicitly
  distinguishes meaningful loss from removal of redundant copies.
- `response-template.json`: every judgment and rationale is null; reviewer ID
  and review type are also null. Status is pending. Nothing is assistant-prefilled.
- `freeze.json`: hashes of those three reviewer files before review.

The separate `evaluator-only/audit-map.json` links neutral audit IDs to original
IDs, thresholds, candidate medoids/similarities, and gate provenance. It includes
accepted and vetoed proposals; three unique proposals have accepted provenance
and 26 have vetoed provenance. No such metadata appears in reviewer files.
The 29 proposals come from 20 cases in ten families; do not treat them as 29
independent scenarios. Identical proposals are not sent repeatedly, while distinct
medoids/groupings of one case remain reviewable variants. Public fictional content
can still permit recognition, so blinding is procedural and reviewers should avoid
the source repository. Two actual people must review independently before
adjudication; no human review has yet been completed or solicited by the harness.
Assistant inspection checked packet completeness and fixed-survivor fidelity,
without filling responses or claiming independent semantic judgments.

### Phase 2B validation and next task

Research checks: **55 tests pass** (40 inherited research validity tests plus
15 Phase 2B tests), including actual pinned-tokenizer integration. Tests cover
ranking/ties, label-independent matching, inclusive token tolerance and residuals,
unmatched/missing-token cases, unchanged frozen candidates/medoids/gate outputs,
full-byte identity, and deduplicated blinded exports. Two fresh preparations
reproduce the same point, matching, identity, and audit files byte-for-byte.
Research lint, unchanged dataset validation, freeze/checksum checks, and diff
checks pass. Combined repository/research suite: **498 passed, 2 skipped, 2 failed**.
The same two inherited parser failures concern missing TXT/JSONL fixtures.
Repository lint still has **86 preexisting findings** in thirteen unchanged files.
Baseline fixtures and workflow behavior are not repaired or suppressed in this phase.

Next obtain two independent blinded semantic reviews. Only then consider the
non-identical 0.95 gate/control contrast and the incremental gate/exact comparison,
with full-original anchors and frozen paired execution settings. Separate solver
calls for identical 0.45–0.85 prompts cannot establish a gating contribution.
Safety, decision benefit, and generalization remain unmeasured. No downstream
solver calls, paid APIs, held-out cases, safeguards, or production changes occur.

## Phase 3: bounded real local pilot and genuine review import

Phase 3 continues from `5da79b3ad282eda44c96e7da250c440294089996`. The dated
[protocol amendment](PROTOCOL.md#phase-3-exploratory-pilot-amendment-2026-11-14-before-solver-answers)
and [pilot plan](PILOT_PLAN.md) were written before collecting answers. They
prospectively allow exploratory development calls while independent human review
is pending. Threshold 0.95 was selected from pre-answer transformation differences,
not solver outcomes; the comparison is not an independent confirmatory preregistration.

The experiment remains external. Production code, gate rules, gold labels,
earlier prompts, and all prior frozen artifacts are unchanged. `local_solver.py`
provides a CPU Transformers transport with explicit allowlists, pinned local
weights, native chat templates, stateless calls, greedy decoding, and structured
status/usage/latency logs. `pilot.py` freezes tokenizer-specific matching, requests,
and within-block reuse before execution. `pilot_analysis.py` uses existing strict
parsing, paired exclusions, equal-family metrics and bootstrap intervals. It
exports a separate **unscored** explanation-support audit; correct answer labels
do not establish valid explanations.

Model selection and limits are in [pilot-lock.json](pilot-lock.json), recorded
before answers. The two instruction families are Qwen2.5-0.5B-Instruct and
SmolLM2-360M-Instruct, with immutable revisions. The old Qwen tokenizer-only cache
was not treated as a selected or cached solver. Full generation weights were
downloaded publicly into a new cache. No configured provider credentials or
remote inference endpoint were found; no paid calls are authorized or used.
Both tokenizers are checked before responses: frozen similarity-first prefix 3
must remain the nearest eligible match under the existing rule. See the results
for tokenizer-specific budgets and residuals rather than transferring Qwen counts
to another family.

### Prepare and run a fresh pilot

Use the existing Phase 2 dependencies. Download only pinned public snapshots into
a separate cache (this does not execute inference):

```bash
HF_HUB_DISABLE_XET=1 python - <<'PY'
import json
from pathlib import Path
from research.ai_epistemics_2026.harness.backend import snapshot
lock = json.loads(Path('research/ai_epistemics_2026/pilot-lock.json').read_text())
for model in lock['models']:
    snapshot(model, Path('/tmp/memd-phase3-cache'), True)
PY
```

Extract the preserved Phase 2 and Phase 2B archives into a scratch parent, giving
`phase2-run` and `phase2b-run`, then prepare each family in a new directory:

```bash
HF_HUB_OFFLINE=1 python -m research.ai_epistemics_2026.harness.pilot prepare \
  --source /tmp/sources/phase2-run --source2b /tmp/sources/phase2b-run \
  --cache /tmp/memd-phase3-cache --family Qwen2.5 --output /tmp/new-qwen-pilot
HF_HUB_OFFLINE=1 python -m research.ai_epistemics_2026.harness.pilot run \
  --run /tmp/new-qwen-pilot
python -m research.ai_epistemics_2026.harness.pilot_analysis --run /tmp/new-qwen-pilot
```

Use `--family SmolLM2` and a separate output directory for the second family;
run sequentially on constrained hardware. Preparation records full asset/code/data
hashes, dependencies, rendered prompts, generation settings, 240 planned logical
requests, and 72 physical request owners/model. It makes no solver calls. The
four conditions each retain all 20 cases and three order seeds. The `prefix`
field is paired stratum 3; the gate remains its unchanged full anchor.

Reuse occurs only inside one case/model/order block for byte-identical requests,
in the frozen randomized condition schedule. Repetitions are never deduplicated
across cases, order seeds or families. The freeze contains `reuse-plan.json`;
responses mark reused attempts and retain their owner. Physical submissions log
the actual request, rendered prompt/hash, generated token IDs, raw decoded output,
latency, usage, statuses and retries. Usage/latency totals sum physical attempts,
not repeated logical copies. These counts are local token/compute observations,
not monetary cost savings.

Each model has a 20-minute inference budget and 60-second per-submission deadline,
with one native generation step of deadline slack. No output repair, alternate
model, JSON-constrained generation, or label editing occurs. Invalid/truncated
outputs remain decision errors. Infrastructure failures get at most two identical
retries; one failed condition excludes the entire matched block, with all planned
denominators retained in the report. Context overflow is an error, not a silently
removed case. Refusing to overwrite started runs prevents accidental hidden reruns.

### Import actual independent human reviews

Only after a person has completed a copy of the original reviewer template:

```bash
python -m research.ai_epistemics_2026.harness.review_import \
  --packets research/ai_epistemics_2026/artifacts/phase2b-development-2026-11-14/reviewer \
  --submission /path/to/completed-review.json --output /tmp/independent-reviews
```

The command verifies the original packet freeze, validates exact audit IDs and
fields, completed/explicitly partial status, judgment choices, and nonempty rationales.
It preserves original submission bytes plus provenance under a neutral reviewer
ID, with its own freeze. It never fills forms, overwrites packets, merges reviewers,
or performs adjudication. Two reviewers must use separate IDs and submissions.
`review_type` distinguishes self-declared `independent_human` from `assistant`;
structural validation cannot verify a person's identity or independence. The
researcher must establish that provenance separately. No completed independent
human submission has been imported in this phase. Semantic-safety outcomes and
inter-reviewer agreement remain pending.

See [PILOT_RESULTS.md](PILOT_RESULTS.md) for counts, original-memory errors,
introduced/rescued errors, contrasts, failures, invalid outputs and exclusions.
See [FINAL_EVALUATION_PLAN.md](FINAL_EVALUATION_PLAN.md) for the proposed untouched
family allocation, minimum effect, call/resource budgets and limits of pilot-based
power estimates. No held-out cases are generated or accessed here. A functioning
adapter and passing tests alone do not establish a competitive research contribution.

### Phase 3 validation and archive checks

```bash
MEMD_RESEARCH_MODEL_CACHE=/path/to/preserved-phase2-cache HF_HUB_OFFLINE=1 \
  python -m pytest tests research/ai_epistemics_2026/tests -q
ruff check research/ai_epistemics_2026
python research/ai_epistemics_2026/validate_development.py
```

All **69 research tests** pass, including fourteen new transport, provenance,
reuse, paired-contrast, and reviewer-import tests. Tests generate only explicitly
synthetic fixtures. The combined suite has **512 passed, two skipped, two failed**;
the failures are the same inherited missing TXT/JSONL parser fixtures. Whole-repository
Ruff retains 86 findings in thirteen unchanged files; research lint is clean.
No fixture repair, inherited lint suppression, or benchmark regeneration occurred.

The [Phase 3 artifact directory](artifacts/phase3-development-2026-11-14/) contains
readable per-model manifests, matching grids, execution summaries and analyses,
plus full compressed runs. Run `sha256sum -c SHA256SUMS` from that directory.
Extract `qwen/run.tar.gz` and `smol/run.tar.gz` into scratch directories to obtain
`qwen-run/` and `smol-run/`. For each extracted run, verify `freeze.json`,
`responses.freeze.json`, `execution.freeze.json`, and `analysis.freeze.json`
with `harness.artifacts.verify`. The archives preserve the original preparation,
response, execution, and scoring freezes without model weights. Actual requests,
rendered prompts, raw responses, generated IDs, and reuse provenance are included.
Every frozen source/config hash still matches the delivered code. All prior
artifacts, development labels, gate/transform code and production behavior remain
unchanged. See the pilot results for the strict-score limitations and next task.
