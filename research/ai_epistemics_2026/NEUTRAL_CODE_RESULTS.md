# Neutral-code diagnostic — completed 2026-11-15

**The solver fails aggregate eligibility: 50/108 correct, with 108/108 valid
outputs. No development rerun is executed. Finalize a bounded feasibility study;
do not proceed to a new evaluation with this measurement.**

The diagnostic finds strong output-code preference and mapping sensitivity in
this interface. It does not establish that token bias caused the previous
failures, that mem-d improves decisions, or that the model is generally incapable.
There are eighteen reused calibration items, each evaluated under six mappings,
not 108 independent scenarios or untouched validation.

## Frozen design and execution

The [plan](NEUTRAL_CODE_PLAN.md), chronological protocol amendment, interface,
settings, scoring, eligibility and conditional development schedule were committed
at `02d3322` before answers. The separate run manifest freezes all 108 requests,
execution order, calibration keys, native prompt renderings, model assets and
dependencies before execution. These are local provenance records, not an
independently preregistered confirmatory study.

Only the already cached `Qwen/Qwen2.5-1.5B-Instruct` revision
`989aa7980e4cf806f80c7fef2b1adb7bc71aa306` was used. No checkpoint was downloaded.
CPU float32, two Torch threads, deterministic algorithms, native pinned template,
greedy decoding, generation seed 2026, two new tokens and 4,096 total tokens were
fixed. Every actual prompt boundary verifies A/B/C as distinct single tokens
(IDs 32/33/34); all three are permitted, followed only by EOS 151645.
The complete public code-to-label mapping appears in every prompt. Evidence,
questions, criteria, answer options and query time are unchanged. No gold enters
the transport or constraint. All six mappings per item were shuffled once with
seed 20261115; no response reuse or best-mapping selection occurred.

All **108 real calls** ended normally at EOS: no infrastructure failures, retries,
truncations, context overflows or missing usage. Actual usage was 30,756 input
tokens and 216 generated tokens (code plus EOS); physical generation latency
totaled 600.98 seconds. Download/model-load/preparation time is outside that sum.
These are operational observations, not memory-compression or inference-cost
savings. Responses and execution records were frozen before scoring.

Eligibility was fixed at at least **103/108 valid and 87/108 correct**. Validity
passes; accuracy is 50/108 (46.3%), with 58 valid-but-wrong decisions. No thresholds
or mappings are changed after results. The actual development-preparation guard
rejects this failed diagnostic before model loading or creating study requests.
No further model experimentation is performed.

## Every mapping and semantic class

All eighteen outputs per mapping are valid. The complete predeclared mapping grid:

| Mapping | A means | B means | C means | Correct / planned |
| --- | --- | --- | --- | ---: |
| P1 | proceed | do_not_proceed | insufficient_evidence | 11 / 18 |
| P2 | proceed | insufficient_evidence | do_not_proceed | 10 / 18 |
| P3 | do_not_proceed | proceed | insufficient_evidence | 6 / 18 |
| P4 | do_not_proceed | insufficient_evidence | proceed | 8 / 18 |
| P5 | insufficient_evidence | proceed | do_not_proceed | 6 / 18 |
| P6 | insufficient_evidence | do_not_proceed | proceed | 9 / 18 |

Class results and confusion counts include all 36 planned pairs per class:

| Gold semantic class | Predicted proceed | Predicted do_not_proceed | Predicted insufficient_evidence | Correct / planned |
| --- | ---: | ---: | ---: | ---: |
| proceed | 29 | 3 | 4 | 29 / 36 |
| do_not_proceed | 16 | 11 | 9 | 11 / 36 |
| insufficient_evidence | 15 | 11 | 10 | 10 / 36 |

Overall decoded semantic distribution: `proceed` 60/108, `do_not_proceed` 25/108,
`insufficient_evidence` 23/108. Insufficient evidence is selected correctly for
10/36 missing-evidence pairs, with 13 false abstentions among the 23 predictions.
These label counts do not establish supported abstention explanations: none
were collected. No class or mapping is selected to replace aggregate eligibility.

## Code preference and within-item changes

Output codes are **A 19/108, B 84/108, C 5/108**. All six outputs are valid for
every item, so coverage is complete for the following denominators:

- **16/18 items change decoded semantic answer** across mappings despite identical
  evidence, question and criteria; only two preserve the semantic answer in all six.
- **11/18 change output code**; seven emit B under every mapping, which makes their
  decoded meaning change as B's assigned label changes.
- `interface_02` (confirmed zero markers, request one) emits B six times. Its decoded
  answers are deny/insufficient/proceed/insufficient/proceed/deny, correct 2/6.
- `interface_03` (unknown bolt count) also emits B six times, correct 2/6. Different
  evidence requirements do not alter those six raw codes for these two items.
- `interface_07` (both checks pass) and `interface_13` (confirmed empty bin) emit
  A/A/B/C/B/C: they preserve `proceed` correctly across all six mappings. The
  observation therefore does not support universal mapping incapacity.

Full per-item codes, decoded labels and correctness flags are published. A fixed
code independent of mapping would score 2/6 per item under this balanced design;
it cannot meet eligibility. The observed behavior is not wholly constant-code:
some outputs track meaning, while many decisions depend on the mapping. The
diagnostic is not a statistical test with 108 independent units, and no powered
or generalization claim is made from it.

## What this does and does not establish

[LABEL_TOKEN_INSPECTION.md](LABEL_TOKEN_INSPECTION.md) establishes that the old
semantic-label trie branches only at the first token; all remaining pieces are
forced. That is a plausible measurement concern, not proof of its causal role.
Single-token codes remove unequal output-path lengths at the decision step but
retain code priors and require mapping comprehension. The new instructions and
answer representation differ from the old interface. Comparing their aggregate
scores cannot isolate tokenization alone as the cause of old errors.

The new empirical finding is **interface sensitivity under a controlled mapping
change**, with poor aggregate eligibility on these reused items. It supplies no
new mem-d decision comparison. No new introduced/rescued errors, family contrasts,
memory-token savings or review effects are measured in this diagnostic. Historical
transformation/compression findings remain separately labeled. All old scores,
artifacts, production behavior, gate rules and labels are preserved.

Independent human semantic audits remain pending: zero actual human submissions
have been imported. Code-only answers provide no explanation validation. The
next report step is independent review of the frozen actual-medoid packets and
the bounded evidence/limitations account in [REPORT_HANDOFF.md](REPORT_HANDOFF.md).
Do not generate the proposed small or 200-case evaluation, try another mapping,
revise the prompt, or download another checkpoint in this phase. No further
inference was needed to reject development preparation.

## Audit and reproducibility

[artifacts/phase3c-neutral-codes-2026-11-15/](artifacts/phase3c-neutral-codes-2026-11-15/)
contains the token inspection, readable manifest/analysis/execution summary and
the complete diagnostic archive. The archive retains actual submitted requests,
native renderings, raw outputs/generated IDs, attempts, frozen keys, score rows,
and preparation/response/execution/analysis freezes. Check `SHA256SUMS`, extract
the archive into scratch, and verify every freeze with `harness.artifacts.verify`.
Model weights are not redistributed. Source/data hashes identify the pre-answer
code, calibration and exact cached assets.

Validation replayed all 108 actual native prompts and code/EOS token traces and
independently recomputed every score from raw codes and frozen mappings/keys.
All four extracted freezes and source hashes match; sentinel annotations leave
the entire request grid identical. Historical checksums, labels, gate and production
files remain unchanged. Regression checks retain the documented missing-fixture
and inherited lint failures; details are in `validation.json` and the research
README. These checks support auditability, not scientific impact.
