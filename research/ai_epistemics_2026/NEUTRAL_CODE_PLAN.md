# One neutral-code diagnostic — 2026-11-15, before new answers

Continue from `8cd4ca705f2340aa519ebead897f484d49d450bb`. The user's new request
authorizes exactly this diagnostic and a conditional development rerun, superseding
the previous phase's stop rule for this scope only. All historical files/scores,
production behavior, gate rules, gold labels and calibration keys remain intact.
This exploratory interface diagnostic reuses the existing eighteen calibration
items. They are not untouched validation or 108 independent scenarios.

## Frozen diagnostic

- Use only cached `Qwen/Qwen2.5-1.5B-Instruct` revision
  `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`. No model downloads or paid inference.
- The common system prompt and explicit user-payload `answer_code_mapping` live
  in `harness/neutral_codes.py`. Evidence, questions, criteria, answer options
  and query time are unchanged from the previous calibration. No gold, category,
  rationale, gate disposition or evaluator metadata enters generation.
- Codes are A/B/C. Verify all are distinct single tokens at **each actual native
  generation boundary**, with unchanged prompt prefix and exact decode. Mask all
  but those three IDs at the first step, then permit only EOS. If this fails,
  stop without substituting codes. Output is exactly one code, no explanation.
- Define permutations P1–P6 by `itertools.permutations` of the fixed semantic
  tuple `(proceed, do_not_proceed, insufficient_evidence)`. Zip each tuple to
  `(A, B, C)` in that order. Display the complete mapping in every user prompt.
  Decode only through that prompt's frozen mapping, never through gold.
- Enumerate all eighteen item IDs in sorted order, all six permutations per item,
  then shuffle the 108 requests once using Python `random.Random(20261115)`.
  Every item/permutation is submitted once. No response reuse across items or
  permutations, no selection of a best mapping, no replacement trials.
- CPU float32, two Torch threads, deterministic algorithms, eval/inference mode,
  native pinned chat template, greedy decoding, generation seed 2026, two new
  tokens maximum (code + EOS), 4,096 total tokens. Torch 2.6.0+cpu and Transformers
  4.57.1, complete dependency/asset hashes in the pre-answer manifest.
- Runtime cap 1,200 seconds/model execution, 60 seconds/submission, checked between
  native steps. At most two identical infrastructure retries; no retry for a wrong
  decision or invalid output. Keep raw outputs, generated IDs, requests, statuses,
  retries, timing and usage. Freeze responses before scoring.
- Structural validity requires normal completion and decoded text exactly A, B
  or C (no stripping/repair). Invalid/truncated and infrastructure-failed items
  are not correct. All **108 planned** pairs remain in eligibility denominators.
  Require at least 95% valid and 80% correct: **103 valid and 87 correct**.
  Also require a complete real response/attempt record. No post-answer threshold
  changes or extra eligibility filters. If it fails, stop model experimentation.

Report valid/invalid/infrastructure counts, overall correctness, code and decoded
semantic distributions, every permutation's correct/18, every gold semantic
class's correct/36, and the confusion matrix. For each item retain six codes,
decoded answers and correctness indicators. Report semantic changes and code
changes across mappings, coverage and missing outputs; comparisons only among
valid answers have explicit denominators. Report correct insufficient-evidence
selection and false abstentions separately. Do not treat repeated items or
within-item pair comparisons as independent evidence or compute a powered claim.

This removes unequal canonical label lengths from the *decision step*, but code
priors and mapping comprehension can remain. Mapping sensitivity is an interface
finding. Any difference from the old pilot also changes instructions/answer
representation; it cannot isolate tokenization alone as the cause of old failures.
No explanation validation, mem-d benefit or general model incapacity follows.

## Conditional development policy, fixed now

Only if the aggregate eligibility rule passes, prepare the existing twenty
development cases at 0.95 with original, exact, frozen matched similarity-first
prefix 3 and unchanged mem-d. Recompute all tokenizer-specific token points,
requiring prefix 3 still nearest within the existing inclusive two-percentage-point
tolerance. Freeze all actual requests, matching and reuse before answers.

Sort the sixty `(case_id, order_seed)` pairs, using the twenty original IDs and
seeds 2026/2027/2028 only. Make a list of permutation indices `0..5` repeated ten
times, shuffle it with `random.Random(20261116)`, and zip to the sorted pairs.
Thus each mapping appears exactly ten times. This schedule reads no labels,
categories, families, audits, recommendations or answers. Use the same mapping
within each four-condition block, and the existing shared memory permutations
and condition-execution randomization. Freeze that schedule before study answers.

Use the same code interface, model, generation and per-submission settings, with
a separate 1,200-second execution cap. All 240 logical requests remain planned;
only byte-identical **complete requests** within one case/model/order block can
share a real response. Mapping is part of request bytes. No reuse across planned
orders or cases. Keep the owner mapping and physical attempts. No prompt or mapping
optimization after diagnostic results. Failed or unavailable budget matching is
reported without collecting unmatched study answers.

Use the existing equal-family paired analysis and 10,000 family bootstrap draws,
with strict code decoding through each frozen request mapping. Unresolved
infrastructure excludes the entire paired block, with complete denominators
reported; context overflow/invalid/truncation remain errors. Report original
accuracy, introduced/rescued counts, gate versus both controls, case/family
concentration, token savings, residuals and review burden. Ten development
families and adaptively chosen 0.95 support exploratory findings only. Code-only
answers supply no independent explanation validation. Human semantic audits remain
pending. No held-out cases or further model/interface trials are allowed.

## Report handoff

After execution, separate control identity, compression/review, interface findings,
genuine downstream decision evidence and pending human audits in an evidence
table. Outline a 4–8-page report around supported results, disclosing adaptive
decisions, provisional novelty and small correlated data. Passing tests is not
scientific impact. If this diagnostic fails, recommend a bounded feasibility
report; do not scale the ineligible measurement or generate a new evaluation.
