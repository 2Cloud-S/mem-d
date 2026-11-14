# Phase 3 exploratory development pilot — 2026-11-14

The real local pilot completed, but provides **no observed incremental decision
accuracy benefit from mem-d over either simple control**. Output-format failures
dominate these tiny checkpoints. This is evidence about experimental feasibility
and limitations on these development cases, not a confirmatory result, proof of
equivalence, independent semantic validation, or evidence of broad generalization.

## Design and execution provenance

The dated [amendment](PROTOCOL.md#phase-3-exploratory-pilot-amendment-2026-11-14-before-solver-answers),
[pilot plan](PILOT_PLAN.md), model lock, and both run manifests were recorded and
hashed before collecting answers. The manifests were prepared at 22:07 UTC;
these are local provenance records, not an externally timestamped preregistration.
Threshold 0.95 was selected because development transformation analysis found
non-identical payloads **before viewing solver answers**. Five other thresholds
reproduce simpler controls. Selection is exploratory and informed by development.
The amendment prospectively permits exploratory execution while human reviews
are pending; those reviews remain pending after execution.

All 20 existing cases, ten families, and order seeds 2026/2027/2028 were retained.
Each model has 60 planned observations per condition: original memories, exact
deduplication, frozen matched similarity-first prefix 3, and existing mem-d gate.
The similarity control is an offline corpus allocation, not a deployable per-store
policy. No policies, gold labels, prompts, prior artifacts, or production behavior
were changed after answers. No held-out material or paid API was used.

| Local instruction model | Actual weight revision | Physical calls | Logical observations | Reused within block | Generation time |
| --- | --- | ---: | ---: | ---: | ---: |
| Qwen/Qwen2.5-0.5B-Instruct | `7ae557604adf67be50417f59c2c2f167def9a775` | 72 | 240 | 168 | 875.93 s |
| HuggingFaceTB/SmolLM2-360M-Instruct | `a10cc1512eabd3dde888204e902eca88bddb4951` | 72 | 240 | 168 | 383.06 s |

The second model is a distinct pretrained family, using LlamaForCausalLM rather
than Qwen2ForCausalLM. Both used native pinned chat templates, CPU float32,
two Torch threads, deterministic algorithms, greedy decoding, a 256-new-token
limit, and 4,096 total tokens. Torch was 2.6.0+cpu and Transformers 4.57.1;
manifests include dependency versions and complete weight/tokenizer hashes.
The preexisting tokenizer-only snapshot was not treated as generation weights.

There were **zero retries, infrastructure failures, paired exclusions, context
overflows, or truncated responses**. All 144 physical calls ended at model EOS;
transport success does not imply valid JSON or correct decisions. Every condition
retains 60/60 planned case/order observations per model. Byte-identical requests
share answers only within one case/model/order block, with an explicit frozen
reuse mapping. Orders, reused conditions, and models are not independent families.

Physical input/output usage was 25,317/4,854 tokens for Qwen and 27,540/1,974 for
SmolLM2. Completion counts include generated EOS tokens. No attempts lacked usage.
Generation latency totals exclude downloads, model loading, preparation, and
analysis. Reused logical rows are not counted again in these totals. These are
observed inference counts, not claims of total cost savings by condition.

## Strict decision outcomes and family uncertainty

Invalid outputs count as errors under the unchanged parser. It requires exactly
`answer_label` and a nonempty `justification`, with an offered label. No lexical
repair, second-model repair, or retrospective lenient score was substituted.
Because this pilot is balanced, raw accuracy equals equal-family accuracy;
analysis nevertheless averages orders, then cases, then ten families.

| Model | Condition | Correct / planned | Errors / included | Invalid outputs | Paired error change versus original |
| --- | --- | ---: | ---: | ---: | ---: |
| Qwen | Original | 0 / 60 | 60 / 60 | 60 | 0 |
| Qwen | Exact | 0 / 60 | 60 / 60 | 60 | 0 |
| Qwen | Similarity-first | 0 / 60 | 60 / 60 | 57 | 0 |
| Qwen | Gate | 0 / 60 | 60 / 60 | 60 | 0 |
| SmolLM2 | Original | 14 / 60 | 46 / 60 | 31 | 0 |
| SmolLM2 | Exact | 17 / 60 | 43 / 60 | 28 | −0.05 |
| SmolLM2 | Similarity-first | 17 / 60 | 43 / 60 | 25 | −0.05 |
| SmolLM2 | Gate | 17 / 60 | 43 / 60 | 28 | −0.05 |

Qwen has a strict-score floor: across 240 logical outputs, 233 use `answer`
instead of `answer_label`, four are not JSON, and the three valid schema outputs
are incorrect similarity-control answers to `dev_016`. This says little about
the relative decision-preserving quality of the memory transformations.

For SmolLM2, **all three rescued observations are the three orders of `dev_002`,
family_02**. Original answers already affirm the booking in prose, but violate
the required schema; all three compression methods return valid, correct JSON.
Exact deduplication accounts for the entire strict-score gain. No substantive
reasoning improvement or incremental mem-d benefit is established by that gain.
The other 19 cases have unchanged error indicators across conditions. Invalid
outputs remain failures even when assistant inspection finds plausible prose.

Against original memories, each compression condition introduces 0/14 errors
among SmolLM2's originally correct observations and rescues 3/46 originally wrong
observations. For Qwen, introduced error is **undefined (0 originally correct)**,
and rescued error is 0/60. These denominators include order repetitions, not
independent scenarios. There are no infrastructure exclusions in either model.

For both models, gate versus exact and gate versus similarity-first have zero
error difference in every one of the ten families, with zero sample variance.
Their 10,000-resample paired family bootstrap intervals are [0, 0]; the Qwen
floor and small pilot make these degenerate intervals unsuitable for an
equivalence claim or precise sample-size calculation. SmolLM2's compression
versus original interval is [−0.15, 0] in absolute error units, driven entirely
by one family and output formatting. Full transition counts, resamples with
undefined denominators, case errors, and intervals are in the frozen analysis files.

## Actual memory compression and review burden

Matching was recomputed and frozen separately for each tokenizer before answers.
All seven similarity-prefix points plus the three anchors at 0.95 are exported
in each `token-matching.json`; the original frozen prefix 3 remains the nearest
eligible match for both models. Counts below are corpus memory tokens averaged
over the three shared orders, not full prompt tokens or total inference cost.

| Tokenizer | Original tokens | Exact saved | Gate saved | Similarity-first saved | Absolute gate/control gap | Allowed gap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen | 3,290 | 136 | 194 | 192 | 2 | 65.8 |
| SmolLM2 | 3,436 | 143 | 207 | 203 | 4 | 68.72 |

Residual control-minus-gate savings are −2 and −4 tokens, respectively: 0.06079
and 0.11641 percentage points of the original budgets, or 1.03% and 1.93% of gate
savings. The two-percentage-point tolerance would be permissive at these small
savings; the actual gaps are disclosed. Exact removes two groups/records across
two cases; gate and control each remove three groups/records across three cases.
Gate adds only the `dev_005` paraphrase merge over exact, saving an incremental
58 Qwen or 64 SmolLM2 tokens. The control instead replaces the conflicting
`dev_016` pair with its fixed 12-December medoid. Payloads differ even though
strict decision error indicators do not.

The unchanged gate requests review for 3/6 candidate groups and 23/52 original
memory records at 0.95. The three vetoed groups require approval; no explicit
conflict flag is present. These are recommendation frequencies, not measured
reviewer time or proof of discrimination. Semantic safety and critical-detail
retention remain unscored pending actual independent review of the proposals.

## Case-level inspection and limits

The following are **assistant inspections of frozen responses**, not independent
human audit judgments. The complete raw texts and requests remain in the archives.

- `dev_001`, Qwen original, seed 2026: the rationale correctly describes sandbox
  approval, but the JSON key is `answer`; the unchanged parser scores an error.
- `dev_002`, SmolLM2 original, seed 2026: “Yes, we can book Cedar room at 11:00 on
  10 December without using its cupboard.” Exact returns valid JSON with label
  `proceed`. This illustrates the format-only source of all three rescues.
- `dev_005`, SmolLM2 gate, seed 2026: raw answer “Yes” is invalid. This format
  failure prevents that checkpoint from discriminating the added paraphrase merge.
- `dev_016`, Qwen original, seed 2026: the rationale falsely treats 14 December
  as within a 12-December deadline; it also uses the wrong JSON key. Similarity-first
  returns valid `proceed` based on its surviving 12-December record. Both are
  incorrect against the original unresolved evidence (`insufficient_evidence`).
  This illustrates why original-memory errors must be separated from merge errors;
  record loss alone does not establish an introduced solver error.

Correct labels do not establish supported explanations. Every explanation-support
field in the post-freeze audit exports is null. No person has completed an
independent semantic review, and no inter-reviewer agreement is claimed. The
importer now validates actual completed or partial submissions while preserving
each reviewer's raw bytes separately; unit fixtures are explicitly synthetic.

## What follows

The strongest supported claim is that bounded, reproducible local execution,
tokenizer-specific matching, within-block reuse, and strict family-based scoring
are feasible. This pilot supplies **no observed incremental accuracy advantage**
for mem-d over simpler controls; its tiny models and schema failures prevent a
credible broad decision-benefit or safety claim. Equal scores do not establish
equivalent transformations. Prior transformation findings remain limited to
the development corpus.

Before untouched evaluation, obtain the two pending blinded human reviews and
validate a prospectively specified common output interface on development data
with more capable, distinct solvers. Any prompt/schema-interface change must be
amended before new responses and must preserve this pilot unchanged. Do not
select models or cases by a favorable gate effect.

[FINAL_EVALUATION_PLAN.md](FINAL_EVALUATION_PLAN.md) proposes 100 new independent
families / 200 cases, a five-percentage-point minimum effect of interest, and
4,800 logical observations across two families and three orders. This is a
resource-based proposal, not a powered design inferred from zero pilot variance.
No held-out cases were generated or accessed. Compute, reviewer availability,
and a usable solver/output interface remain prerequisites.

## Auditable artifacts

[artifacts/phase3-development-2026-11-14/](artifacts/phase3-development-2026-11-14/)
contains per-model readable manifests, matching grids, execution summaries and
analyses, plus complete `run.tar.gz` archives and checksums. Archives retain
pre-answer requests/rendered prompts/reuse plans, actual physical submissions,
raw responses/generated token IDs, scored rows, unfilled explanation audits, and
the preparation/response/execution/analysis freezes. Resource inspection and
pending human-review status are separate root artifacts. Model weights are not
redistributed; their immutable public identities and asset hashes are recorded.

Validation completed: all 69 research tests passed within the combined suite
(512 passed, two skipped, two inherited parser failures for missing
`tests/fixtures/memories.txt` and `memories.jsonl`). Research Ruff passed;
repository Ruff retains 86 findings in thirteen unchanged files. Dataset validation,
all historical/new checksums, all four extracted freezes per pilot, source/config
hashes, 480 request hashes/allowlists, 144 actual-submission/reuse records, independent
score recomputation, and production/gold/historical-artifact immutability checks
passed. No inherited fixture, lint rule, or benchmark artifact was changed.
