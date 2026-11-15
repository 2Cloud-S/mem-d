# Prospective resource fallback — 2026-11-15, before forced-choice answers

The initial constrained-JSON trial is preserved, not repaired or rerun. Its
pre-answer source is commit `8703c6b` (including the unchanged calibration keys).
The first ten short Qwen submissions took roughly 45–50 seconds each. This
projects beyond the frozen 600-second calibration and 1,500-second development
budgets. The broad regex/token filtering is impractical for this bounded CPU
experiment. This decision uses operational latency before inspecting calibration
decision scores; no new study responses have been collected. Let the initial
trial reach its frozen deadline and record all planned items and failures.

This explicitly amends the original one-interface limit: **at most two interfaces**,
the abandoned constrained JSON trial plus one strict forced-choice interface.
Do not try another prompt/interface after this fallback. The JSON SmolLM2 and
larger-model trials are not executed; document that resource-based decision.
Test both original models on the forced-choice calibration, and try the one
predeclared 1.5B fallback only if neither original model qualifies. Maximum four
model/interface trial pairs in the entire phase, three unique models. No selection
uses a gate advantage. No paid inference or new safeguards are authorized.

## Changed measurement target

Return exactly one of the three offered labels, **without JSON or explanation**.
The common system prompt is frozen in `harness.forced_choice.SYSTEM`. A token
trie containing all three labels' canonical tokenizer encodings masks illegal
tokens through the documented Transformers `prefix_allowed_tokens_fn`. EOS is
allowed only after a complete label. Every label remains reachable; none is
selected by the harness. No evaluator data enters the trie, transport or prompt.

This measures **forced-choice decision correctness**, not joint JSON/explanation
compliance. No explanations are collected in this bounded phase. Explanation
support is unavailable, not assumed correct or supplied by another model. Human
semantic audits of the memory proposals remain separately pending. Strict parsing
requires the entire raw decoded text to equal one offered label; no stripping,
alias mapping or repair. Invalid/truncated outputs still count as errors;
infrastructure retains identical retries and paired exclusions.

Freeze all 18 unchanged calibration items/keys, interface code, native chat
templates, exact weights, dependencies and settings before new execution.
Eligibility remains 95% validity and 80% accuracy over all 18 items, hence
18 valid and at least 15 correct. One calibration run per model in this interface.
The simple assistant-authored keys are independent of mem-d outcomes, not human
annotation or a broad capability benchmark. No study cases enter calibration.

Use the same CPU float32 / two-thread / greedy settings and generation seeds,
but cap output at **24 tokens** (all canonical label encodings plus EOS fit),
with 4,096 total tokens. Preserve the original model identities, resource
deadlines, conditional escalation rule and retry limits in `forced-choice-lock.json`.
No GPU is required for the cached models. Record every model trial or non-attempt.

Only qualifying models receive the full frozen 20-case, three-order, four-condition
comparison at 0.95. Retain all denominators, recompute tokenizer-specific matching,
freeze the same nearest prefix 3 before answers, and preserve exact within-block
identity reuse. Transformations/gating/labels never change. Analyze with the same
family weighting and bootstrap, reporting format validity separately. The old
JSON parser remains the default for old experiments; an explicit parser argument
selects the forced-choice measurement only for this new experiment. Default
strict historical scoring must continue to reproduce every old score exactly.

No further interface or model selection may follow development treatment effects.
No untouched cases are generated. After feasibility, propose the smallest useful
untouched descriptive study with explicit calls, CPU time, reviewer work, and
limitations; do not scale the old uninterpretable measurement or claim power.
