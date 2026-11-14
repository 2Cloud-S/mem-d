# Phase 2B decision memo

Development only, 2026-11-14. No solver responses or independent human reviews.
The prospective amendment is in [PROTOCOL.md](PROTOCOL.md); it explicitly uses
Phase 2 feasibility knowledge. Existing data, gate rules, and artifacts are unchanged.

1. **Are informative nonzero matches available?** Yes, with a qualification.
   The old shared per-case cap was only 0 or 1 because every tiny store had at
   most one candidate group. It offered no partial selection across stores.
   The new offline corpus ranking supplies 96 similarity-first prefixes across
   six thresholds, plus 18 anchors. All six nonzero gated targets now have
   same-threshold token matches. Only the 0.95 match has different payloads;
   the other five reproduce the gate exactly. This resolves a grid limitation,
   without improving the gate or establishing useful discrimination.

2. **Does mem-d differ from simpler controls?** At 0.45–0.85, no: the full mem-d
   gate, exact deduplication, and similarity-first prefix 2 have byte-identical
   survivor payloads across all 20 cases and identical messages for every shared
   order seed. In particular, 0.55 saves the same 136 actual memory tokens by
   making the same two exact merges. No incremental transformation benefit is
   demonstrated there. At 0.95, the gate additionally merges `m005_1`/`m005_3`,
   keeping `m005_1` and removing `m005_3`, while `m005_2` remains. This is the
   preauthored duplicate-control paraphrase pair, saving **58 extra tokens** over
   exact deduplication (194 versus 136). Its independent semantic audit is pending.
   Similarity-first prefix 3 instead compresses `dev_016`: it keeps the 12 December
   commitment and removes the 14 December commitment. It saves **192 tokens**,
   two fewer than the gate, and differs from the gate in `dev_005`/`dev_016`.
   No prefix of that same-threshold ranking reproduces the gate. The difference
   is observable, but its decision-quality effect has not been measured.

3. **Which comparisons warrant solver evaluation?** After independent semantic
   review, the non-identical 0.95 gate versus prefix-3 control is a candidate
   near-equal-budget comparison; retain exact and full-original anchors. The
   gate-versus-exact contrast isolates its one additional paraphrase merge,
   with unequal compression disclosed. Do not spend separate calls comparing
   identical gate/exact/control messages at 0.45–0.85. Share/reuse identical
   inputs under frozen model settings rather than attribute stochastic output
   differences to gating. New paired execution and analysis must use the frozen
   corpus-point IDs; this phase prepares comparisons, not solver integration.

4. **Which conclusions remain unsupported?** Improved decisions, semantic safety,
   calibrated discrimination, generalization, and deployable per-store budget
   performance remain unsupported. The control is an offline corpus allocation,
   not a deployable query-blind policy. At 0.95 the signed control-minus-gate token
   residual is **−2**, absolute gap **2**, or **0.06079 percentage points** of the
   3,290-token original budget and **1.03%** of the gate's 194-token savings.
   The predeclared absolute tolerance is 65.8 tokens: permissive relative to these
   small savings, although the actual match is much closer. More review is not
   better discrimination: the gate reviews 17/19 groups at 0.55 and 3/6 at 0.95,
   plus review recommendations covering 46/52 and 23/52 original memories,
   respectively. Simple controls have no review mechanism. Do not infer safety
   from those counts or equate them with measured human review time.

5. **What needs human review?** The reviewer-only packet contains **29 distinct
   actual fixed-medoid proposals**, deduplicated from 90 candidate occurrences,
   including accepted and vetoed transformations. Two humans should judge them
   independently using the neutral rubric, then adjudicate disagreements. The
   template is entirely unfilled and review remains pending. These are variants
   of 20 development cases in ten families, not 29 independent scenarios.
   Reviewers must receive only the reviewer directory, without this memo, source
   dataset, comparisons, or evaluator mapping. Public fictional content can still
   be recognized; blinding is procedural. Assistant artifact inspection is not
   independent human semantic validation.

No paid APIs, new safeguards, held-out cases, production changes, or decision
improvement claims are included. The inherited workflow defect and repository
check failures remain separately documented in the research README.
