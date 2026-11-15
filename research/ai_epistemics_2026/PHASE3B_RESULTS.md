# Phase 3B — constrained interface and bounded development experiment

This is a separate exploratory experiment following the unconstrained Phase 3
pilot. The dated [plan](PHASE3B_PLAN.md) and [protocol amendment](PROTOCOL.md#phase-3b-common-interface-amendment-2026-11-15-before-new-answers)
were recorded before new answers. Historical responses, scores, gate rules,
gold labels, candidate transformations and production behavior are unchanged.
Threshold 0.95 remains selected from development transformation differences,
not independently preregistered. Human reviews remain pending.

## Frozen-pilot diagnosis, without retrospective repair

Replaying both pinned native chat templates confirms that every actual submitted
prompt preserves the intended system instruction: return exactly `answer_label`
and `justification`, choose one offered label, and provide a nonempty evidence-based
justification. All 480 stored logical requests use that instruction. All 144
physical prompt renderings/token hashes match their frozen manifests and actual
submissions; neither template drops the system instruction. The schema was
specified correctly. These small models did not reliably follow it.

| Historical model | Condition | Invalid / 60 | Valid | Valid but wrong / valid | Correct / 60 |
| --- | --- | ---: | ---: | ---: | ---: |
| Qwen2.5-0.5B | Original | 60 | 0 | N/A | 0 |
| Qwen2.5-0.5B | Exact | 60 | 0 | N/A | 0 |
| Qwen2.5-0.5B | Similarity-first | 57 | 3 | 3 / 3 | 0 |
| Qwen2.5-0.5B | Gate | 60 | 0 | N/A | 0 |
| SmolLM2-360M | Original | 31 | 29 | 15 / 29 | 14 |
| SmolLM2-360M | Exact | 28 | 32 | 15 / 32 | 17 |
| SmolLM2-360M | Similarity-first | 25 | 35 | 18 / 35 | 17 |
| SmolLM2-360M | Gate | 28 | 32 | 15 / 32 | 17 |

Qwen has 237/240 invalid outputs (233 wrong-key objects and four non-JSON
outputs); SmolLM2 has 112/240 invalid outputs, all non-JSON. The remaining
three Qwen and 63 SmolLM2 errors are valid-but-wrong decisions. Thus schema
failure is substantial, but does not account for all substantive mistakes.
No prose labels were inferred, aliases normalized, responses repaired, or old
strict scores replaced. There are zero historical paired exclusions.
`historical-diagnostic.json` preserves these counts and source freeze hashes.

## Fixed interface and eligibility checks

The common interface is the unchanged prompt with a pinned LM Format Enforcer
token constraint, using Transformers' documented `prefix_allowed_tokens_fn`.
It permits all three labels and both field orders, rejects extra/missing/duplicate
keys, and requires a nonempty printable ASCII justification. Quotes/backslashes,
Unicode and multiline explanations are outside this version's explanation format.
This avoids unsupported regex/JSON-escape combinations in the pinned parser;
it does not insert an answer or evidence rationale. Explanation support remains
a separate unscored outcome. Constraints can still end incomplete at a deadline
or token limit, so strict parsing is retained.

Primary backend documentation and implementation links are in the pre-answer
plan. Before inference, actual parser/tokenizer/Transformers masking tests passed:
all labels are reachable with both real tokenizers, premature EOS is masked,
bad keys/empty strings are rejected, and parser state is fresh per submission.
No mock output is used as empirical evidence.

Calibration items and answer keys were defined before execution, six per label,
independently of mem-d and study outcomes. They are assistant-authored and not
independently human validated. The simple tests check interface/capability
eligibility, not general reasoning. Per-model pre-answer freezes include all
18 items/keys, schema, source, prompts, model assets, settings and dependencies.
Eligibility requires 18/18 structurally valid and at least 15/18 correct answers,
equivalent to the frozen 95% / 80% thresholds for this small denominator.
Maximum one interface and three predefined model trials; no prompt optimization
or selection by a favorable gate effect is allowed.

## Operational fallback and calibration outcomes

The initial Qwen JSON trial reached the 600-second budget: 14 physical inference
attempts, 28 logged attempt records including unsubmitted budget-exhausted
retries, 13 complete valid outputs and five planned items ending in infrastructure
failure. Only 4/18 planned decisions were correct; 9/13 valid answers were wrong.
Its 596.63 seconds of physical generation and roughly 45–50 seconds per short
complete answer made this constraint impractical within the frozen budgets.
This was an operationally unsuccessful trial, not evidence of a useful reasoning
interface. Every item, raw response and attempted retry remains in its archive.

The [prospective fallback plan](PHASE3B_FORCED_CHOICE_PLAN.md) was written before
inspecting that trial's decision scores or collecting new study answers. It
explicitly amends the one-interface limit to two. No SmolLM2 or larger-model JSON
inference was run; the prepared SmolLM2 request freeze is retained as unexecuted.
The original JSON implementation/calibration source is preserved in commit
`8703c6b`; its source hashes reproduce the archived preparation exactly.
The JSON source hashes were frozen before calls; that commit captured the
unchanged files during the initial run, rather than timestamping them before
its first answer. The forced-choice source commit and manifests precede all
forced-choice answers. These are local provenance records, not an external
preregistration.

The single fallback interface returns **only an exact offered label**. A small
tokenizer-derived trie permits every label and EOS only after completion, using
the same documented Transformers callback. This avoids unconstrained output
repair and the broad JSON-regex traversal. The fixed prompt, trie and settings
were committed at `eee2cec` before its answers. No prompt/label/interface tuning
follows these results. All 18 calibration items/keys remain unchanged.

This changes the measurement target to forced-choice decision correctness.
Explanations are **not collected**, so supported/unsupported explanation counts
are unavailable; they are not assumed correct. Default historical strict JSON
scoring still reproduces both old pilots exactly. The forced-choice parser is
explicitly selected only for new runs and rejects whitespace, aliases, prose and
JSON. It never repairs an output or chooses a gold label.

| Attempted interface / model | Planned | Structurally valid | Correct | Eligible | Physical generation time |
| --- | ---: | ---: | ---: | --- | ---: |
| Constrained JSON / Qwen2.5-0.5B | 18 | 13 | 4 | no | 596.63 s |
| Forced choice / Qwen2.5-0.5B | 18 | 18 | 5 | no | 29.67 s |
| Forced choice / SmolLM2-360M | 18 | 18 | 6 | no | 26.41 s |
| Forced choice / Qwen2.5-1.5B | 18 | 18 | 8 | no | 96.33 s |

The forced interface resolves format compliance for both original models but
neither reaches 15/18 decision correctness. Qwen chooses `proceed` 12 times,
`do_not_proceed` six times, and never `insufficient_evidence`; SmolLM2 chooses
`proceed` on all 18. The latter is a one-label baseline on this balanced calibration,
not a capable eligible solver. There are no forced-choice infrastructure failures,
truncations or retries in those trials. Neither model receives study questions.
These are failures of the particular model/interface combinations; model
capability, greedy token/label bias and interface sensitivity are not isolated.

The only predeclared larger fallback, Qwen2.5-1.5B-Instruct at
`989aa7980e4cf806f80c7fef2b1adb7bc71aa306`, downloaded successfully and ran on the
same CPU/8-GiB environment. Its exact weights, tokenizer and dependencies are in
the pre-answer manifest. All three actual tokenizer paths were checked before
execution. It produced 18/18 valid outputs but only 8/18 correct, with ten
valid-but-wrong decisions and no infrastructure failures, truncations or retries.
A GPU was not necessary to execute it; physical execution is not the blocker.
It selected `proceed` sixteen times and `do_not_proceed` twice. None of the three
forced-choice models selected `insufficient_evidence`, although the actual trie
tests verify that label is reachable. All therefore miss the six missing-evidence
calibration items. This concentration warrants independent review of label/interface
bias before assuming that simply adding parameters resolves the measurement.

**No model/interface combination qualifies. Inference stops at the declared
trial limit. No development rerun was prepared or submitted.** The accuracy
requirement is 15/18, not satisfied by 5/18, 6/18 or 8/18. No thresholds were
weakened and no prompts, labels or calibration keys were optimized after those
scores. This is a decision-eligibility failure of the tested combinations,
not evidence of general reasoning incapacity or a result about mem-d. In
particular, model size, canonical tokenization, greedy label priors and prompt
sensitivity are not disentangled. No new solver comparison, tokenizer-matched
development run, introduced/rescued error rate or family effect is available.
Prior development compression/review findings remain historical, not new results.

There were four actual model/interface trial pairs, involving three unique models:
one constrained JSON trial, then three fixed forced-choice calibrations. Each
retains all 18 planned items; the same items are not independent replications.
The 68 actual inference calls and 82 logged attempt records are retained, including
the JSON deadline failure and unsubmitted exhausted-budget retries. Forced-choice
calibration alone has 54/54 valid outputs; this is not proof of validity on longer
study prompts. No paid APIs, additional models, new study answers, or held-out
cases were used. The attempted model identities and every non-attempt are recorded
in `trials.json`, including the prepared-but-unexecuted JSON SmolLM2 run.

## What is supported, and the next report task

The bounded experiment establishes that the fixed trie can enforce label syntax
on these calibration inputs at feasible CPU latency. It **does not establish a
usable decision solver**, mem-d benefit, semantic safety, explanation support,
or generalization. Format validity must not be presented as scientific success
on the decision-preservation research question. All new explanations are uncollected;
the old JSON explanations remain unscored. No independent human semantic review
or agreement measurement has been completed.

The next report task is to obtain two independent blinded human reviews of the
existing actual-medoid packets, import each unchanged submission separately, and
write a bounded feasibility/negative-finding account alongside the historical
control-equivalence/compression findings. The precise inference blocker is the
lack of a model/interface combination meeting the frozen accuracy threshold
within this trial budget, **not the absence of a GPU**. A future inference phase
needs independent review of the label/interface behavior and an independently
chosen capable solver under a new bounded amendment; more RAM, a verified CPU
quantization backend, or separately authorized inference may broaden choices.
No spending or further trials are authorized by this report.

[SMALL_EVALUATION_PLAN.md](SMALL_EVALUATION_PLAN.md) gives a conditional 24-family /
48-case descriptive design: 576 logical observations per qualified model and a
provisional CPU-day budget, plus independent review. It is not executed or powered.
Do not author that evaluation until eligibility is resolved. The proposed 200-case
evaluation is not generated. An ineligible measurement should not be scaled.

## Artifacts and validity checks

[artifacts/phase3b-development-2026-11-15/](artifacts/phase3b-development-2026-11-15/)
retains all preparation, response, execution and eligibility freezes, actual
requests/native renderings, raw decoded responses and generated IDs, attempts,
usage/latency and score rows. Readable manifests, eligibility/execution summaries,
trial ledger, historical diagnostic, documentation hashes, source replay commits
and checksums accompany the full archives. No weights are redistributed.

The complete regression suite has 543 passed, two skipped and the same two
inherited missing parser-fixture failures; all 100 research tests pass. Research
lint is clean; repository lint retains 86 findings in thirteen unchanged files.
Actual parser/trie/Transformers masking paths, annotation isolation, strict
non-normalizing parsing, eligibility denominators, and exact old-score
recomputation are checked. Actual development preparation also rejects the failed
1.5B calibration before producing study requests. Source/config hashes, all
archive freezes, native prompt/response provenance, and historical-artifact/gold/
production immutability are verified separately. Test fixtures are explicitly
synthetic and contribute no empirical statistics to this report.
