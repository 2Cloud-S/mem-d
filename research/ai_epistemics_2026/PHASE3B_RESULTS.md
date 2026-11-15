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

Calibration and development findings follow after their response freezes.
