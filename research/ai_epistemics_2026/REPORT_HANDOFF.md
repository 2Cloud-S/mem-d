# Sprint report handoff — evidence boundaries

This handoff supports a short research/feasibility report, not a claim of a new
consolidation algorithm or a submission-ready result. The original title remains
provisional: “When AI Forgets the Caveat: Evaluating Decision-Preserving Memory
Deduplication.” The narrower contribution is a controlled examination of an
existing gate, useful compression, simpler controls, and the validity of its
downstream measurement. Mem-d still analyzes source memories without editing them.

## Evidence table

| Evidence | Observations and independent units | What it establishes / what remains unknown |
| --- | --- | --- |
| Transformation/control equivalence | On 20 development cases in ten families, gate outputs at 0.45, 0.55, 0.65, 0.75 and 0.85 are byte-identical to exact deduplication and the token-matched similarity-first control. At 0.95, gate adds the dev_005 paraphrase pair over exact, while the matched control instead replaces the dev_016 conflicting pair. | Five thresholds cannot show a gating contribution through identical solver prompts. At 0.95 the intervention differs; that alone establishes neither safety nor decision benefit. [Phase 2B memo](PHASE2B_MEMO.md). |
| Compression and review | Historical 0.95 counts with the pinned Qwen0.5B tokenizer: original 3,290 memory tokens; exact saves 136, gate 194, matched control 192. Exact removes two groups/records in two cases; gate/control each remove three in three cases. Gate/control residual is two tokens. Review affects 3/6 candidate groups and 23/52 original memories; three approval-required vetoes, no explicit conflict flags. | Positive, limited development compression and recommendation burden. Gate adds 58 memory tokens over exact. These are not total inference savings, measured reviewer time, or semantic-discrimination results. The offline corpus-budget control is not a deployable per-store policy. |
| Interface/calibration | Phase 3B semantic-label scores were 5/18, 6/18 and 8/18. The new cached-Qwen1.5B code diagnostic has 108/108 valid but 50/108 correct (87 required), B chosen 84/108, and semantic changes in 16/18 items. Every mapping/class is reported in [the readout](NEUTRAL_CODE_RESULTS.md). | This establishes mapping sensitivity in the tested interface, not mem-d benefit or the cause of old failures. Eighteen reused items are not 108 independent or untouched scenarios. Token/label priors, mapping comprehension and capability are not isolated. |
| Genuine downstream decisions | Historical Phase 3: Qwen0.5B has 0/60 strict-correct per condition; SmolLM2 has 14/60 original and 17/60 in every compression condition. All three Smol rescues are one case's prose-to-JSON change, equally achieved by exact. No Phase 3B or neutral-code development rerun qualifies. | Genuine calls exist, but the historical score gain is a format change and supplies no incremental mem-d advantage. The failed code diagnostic blocks further study inference; there are no new paired decision effects, introduced/rescued counts or family contrasts to report. |
| Human semantic audits | Twenty-nine unique actual medoid proposals from ninety threshold/group occurrences were exported, with accepted and vetoed provenance hidden. Zero independent human submissions or adjudications are complete. Source labels/author checks are assistant-authored. | Semantic retention, actual unsafe-merge rates, approval discrimination and explanation support are not independently validated. Old arbitrary-representative annotations do not label each fixed medoid. Code-only answers contain no explanation to validate. |

The table deliberately distinguishes transformed-payload facts, resource proxies,
model observations, and missing human evidence. Recommendation-fixture accuracy
(22/22 under internal rules) belongs in inherited-system context, not as downstream
decision evidence. See [NEUTRAL_CODE_PLAN.md](NEUTRAL_CODE_PLAN.md) for the new
diagnostic's prospective limits and conditional development policy.

## Feasible 4–8-page outline

A six-page body and optional one-page reproducibility appendix are sufficient:

1. **Question and contribution (0.75 page).** Define decision-preserving memory
   compression and intended developer/research users. State the unknown outcome
   and narrow evaluation contribution. Explicitly separate inherited mem-d from
   sprint protocol/data/harness work. Avoid claiming firstness or a new safeguard.
2. **Intervention and controls (0.75 page).** Explain original, exact, fixed medoid,
   genuine mem-d gating and the corpus-level similarity budget. Hold candidate
   clusters, medoids and source payloads fixed. Show whole-group veto preservation
   and explain why approval/review burden does not itself show discrimination.
3. **Design and epistemic ground truth (one page).** Describe twenty fictional
   development cases, ten families and evaluator isolation. Define primary paired
   error, original-memory failures, valid-but-wrong errors, introduced/rescued
   denominators, tokenizer-specific compression and paired infrastructure exclusions.
   Report family bootstrap limits. Disclose that gold and audit material lack
   independent human validation; all calibration is reused development material.
4. **Compression/control findings (0.75 page).** Use the historical operating-point
   table, payload identities, incremental paraphrase merge, absolute token gaps,
   review denominators and all-veto limitations. Preserve the original coarse grid
   and explain its zero/one-prefix gap before the adaptive corpus-budget amendment.
5. **Measurement diagnostic (one page).** Show semantic token sequences and the
   first-token branch, without treating the mechanism as proof of cause. Present
   the neutral-code aggregate, six permutation rows, class counts, code preference
   and within-item changes. No best-mapping selection, pseudo-independent 108-case
   claim or conflation of format validity with reasoning. Explain that new prompts
   and mapping comprehension also differ from the old interface.
6. **Decision evidence and limits (0.75 page).** If qualification permits a new
   pilot, show per-condition counts and family-paired contrasts, with case/family
   concentration, original errors and exact-control comparisons. Otherwise state
   why no new decision comparison was run. Keep supported and unsupported claims
   explicit. Explain why code-only responses supply no explanation audit.
7. **Related work, ethics and report decision (one page).** The protocol's primary
   papers already constrain novelty: consolidation/compaction and downstream utility
   are established topics. The distinction is evaluating this existing deterministic
   gate with controlled replacements and controls. Refresh the focused primary-work
   search before external submission; no exhaustive novelty claim is supported.
   Discuss synthetic author bias, tiny correlated data, one checkpoint in the
   code diagnostic, adaptive design, missing reviews, distribution shift and the
   dual use of erasing attribution/caveats. End with the justified next step.

The optional appendix lists immutable model/tokenizer revisions, source/data hashes,
generation settings, exact schedules, invalid-output policy, response reuse and
archive verification. Full prompts/raw responses stay in the auditable repository;
test counts are engineering checks, not scientific results.

## Adaptive decisions to disclose

The dataset and policies are development work, not independent preregistration.
The corpus-prefix budget control followed the coarse-grid feasibility finding;
0.95 was selected because its transformations differed before solver answers.
The first real pilot exposed schema failures. The JSON constraint trial hit its
budget, leading to a prospectively documented forced-choice fallback. Its low
calibration scores motivated inspection of canonical label tokens. The user then
authorized one neutral-code diagnostic, frozen before its answers. These steps
are legitimate exploratory development when disclosed, not a confirmatory sequence.
No gold, gate rule, prior score or historical artifact is rewritten after outcomes.

## Handoff status

**Finalize as a bounded feasibility study. Do not proceed to a small new evaluation
with the current solver/interface.** The diagnostic fails the frozen aggregate
threshold despite full syntax validity; model experimentation stops. A suggested
report title is “Compression Controls and Decision Measurement in Memory
Deduplication,” which matches the evidence better than implying a demonstrated
caveat-forgetting decision effect.

The strongest contribution is the transparent control-equivalence/compression
appraisal plus a concrete measurement failure exposed by counterbalanced codes.
Make no novelty claim for counterbalancing or tokenization effects themselves.
This is a useful bounded negative/feasibility account, not evidence of scientific
impact merely because the harness works. Independent human audits remain pending;
obtain the two blinded submissions and preserve them separately before semantic
claims. No held-out cases or 200-case evaluation are generated. A future new
evaluation requires a separately authorized, prospectively frozen adequate
measurement and human-reviewed new families; this handoff authorizes no more
solver, prompt or checkpoint trials.
