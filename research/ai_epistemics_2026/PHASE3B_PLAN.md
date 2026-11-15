# Phase 3B interface plan — 2026-11-15, before new answers

Continue from `ec1e469f3853344fc00fe6ddd270b2f322b816ae`. Preserve the old
pilot and strict scores; no retrospective normalization or model repair is used.
Threshold 0.95 remains an exploratory development selection based on prior
transformation differences. Five other thresholds reproduce simpler controls.
Human semantic reviews remain pending; no independent validation is implied.

## One common interface and compatibility

Use **one** constrained JSON interface across calibration and every condition,
with the unchanged actual system prompt in `harness.requests.SYSTEM`. Exactly
`answer_label` and `justification` are required, no extra keys, and all three
labels remain possible. `answer-schema.json` is the fixed decoding schema.
Justifications are nonempty printable ASCII, beginning with a nonspace character;
quotes, backslashes, Unicode and multiline explanations are outside this interface.
This restriction avoids the pinned parser's unsupported regex/JSON-escape
combination. It changes explanation surface form, not the three-label target.
No reference answer or substantive rationale is constrained or supplied.

Use `lm-format-enforcer==0.11.3` / `interegular==0.3.3`, through Transformers
4.57.1 `generate(prefix_allowed_tokens_fn=...)`. Greedy generation masks illegal
next tokens; it does not insert gold labels or repair generated answers. A fresh
schema parser/token enforcer is created per submission; tokenizer vocabulary data
alone may be reused. No conversation state transfers between conditions.

Authoritative references checked on 2026-11-15:

- [Transformers 4.57.1 generation API](https://huggingface.co/docs/transformers/v4.57.1/en/main_classes/text_generation)
  documents `prefix_allowed_tokens_fn`; its installed `PrefixConstrainedLogitsProcessor`
  masks disallowed IDs and raises on an empty allowed set.
- [Pinned upstream README](https://github.com/noamgat/lm-format-enforcer/blob/v0.11.3/README.md)
  demonstrates this exact integration and explains token filtering.
- [Pinned Transformers adapter](https://github.com/noamgat/lm-format-enforcer/blob/v0.11.3/lmformatenforcer/integrations/transformers.py)
  implements the callback and tokenizer prefix tree.
- [Pinned JSON parser](https://github.com/noamgat/lm-format-enforcer/blob/v0.11.3/lmformatenforcer/jsonschemaparser.py)
  supports enum/required/properties/pattern, rejects combined pattern and length
  constraints, and explicitly does not support quotes/backslash escaping with
  regex strings. Actual character/token acceptance and the real Transformers
  logits processor must pass tests before model execution; documentation alone
  does not establish compatibility. Token limits/deadlines can still truncate a
  constrained answer; strict parsing remains authoritative.

## Calibration freeze, eligibility, and bounded selection

`interface-calibration.jsonl` has 18 new, straightforward fictional items, six
for each label, separate from all study cases. Answers are defined from evidence
and explicit criteria before inference, without mem-d, not inferred from solver
outputs. They are assistant-authored, **not independently human annotated**.
These are interface calibration, not held-out scientific evaluation. Only
allowlisted input reaches models; keys remain evaluator-only until responses freeze.

Freeze items/keys, schema/interface source, prompts, model assets and dependency
versions in each pre-answer manifest. Run each item once with seed 2026 and a
fixed shuffled presentation. No response reuse or prompt adjustments in calibration.
Require at least **95% structural validity and 80% decision accuracy over all
18 planned items**, counting invalid, truncated, and failed responses as not
correct. With this denominator that means 18 valid and at least 15 correct.
Also require complete real response provenance; infrastructure is not silently
removed. These pragmatic eligibility checks establish no general reasoning claim.

Test both existing models first, without using development treatment effects:
Qwen2.5-0.5B and SmolLM2-360M at their original pinned revisions. If **neither**
passes, attempt only Qwen2.5-1.5B-Instruct at the revision in `interface-lock.json`,
provided disk/RAM fit. This is the predetermined modest CPU-capable escalation,
not selection for a gating advantage. Maximum three models, one calibration run
per model, one interface, no paid calls. Record every trial, including failure or
non-attempt/resource reasons. A second size of Qwen is not another model family.
If any existing model qualifies, do not escalate. If none qualifies, stop inference.

The environment has 8 GiB RAM, two CPU cores of quota, no GPU, and about 4.9 GB
free scratch disk at inspection. Existing full weights are cached. The fallback's
1.54B parameters need approximately 6.18 GB float32 weights plus runtime memory;
public BF16 download is approximately 3.1 GB. CPU feasibility must be checked,
not ruled out solely for lack of a GPU. Provider keys/endpoints checked by presence
are absent; no remote paid inference is authorized.

Keep CPU float32, two threads, greedy decoding, native pinned chat templates,
256 new tokens and 4,096 total tokens. Per-attempt deadline 90 s, at most two
identical infrastructure retries. Model inference budgets: 600 s calibration /
1,500 s development for existing models; 900 / 2,700 s for fallback. Generation
checks deadlines between native steps. No retries for reasoning or format failure.

## Eligible development rerun and reporting

Only eligible models may rerun the existing 20 cases, all ten families, all three
paired orders, and original/exact/frozen matched similarity-first/existing-gate
conditions at 0.95. Recompute every tokenizer-specific prefix point before answers,
requiring frozen prefix 3 to remain nearest and within the unchanged tolerance.
Otherwise record the matching blocker without collecting development answers.
Freeze all requests, complete denominators, matching and within-block reuse first.
Keep the original candidate/medoid/gate/payload functions unchanged. Reuse is only
for byte-identical requests in the same case/model/order block. Physical owners
remain 72/model, logical requests 240/model, with every attempt auditable.

Use unchanged strict scoring, paired infrastructure exclusions and family bootstrap.
Separately report structural validity, valid-but-wrong decisions, full-memory
accuracy, introduced/rescued counts, gate/exact and gate/control, and concentration
in cases/families. Invalid outputs still count as primary errors; also report
decision correctness conditional on validity with explicit denominators, never
silently select a favorable valid-only subset for the primary comparison.
This is a new constrained-inference experiment, not correction of the old pilot.
Explanations remain unscored unless genuinely reviewed; assistant/model inspection
is not independent human review. Memory tokens are not total inference cost.

Do not generate any untouched cases. After seeing interface feasibility, write
a small, realistic report-oriented untouched-study resource proposal, with claims
limited by family count and no unjustified power calculation. Retain independent
reviewer submissions separately through the existing importer.
