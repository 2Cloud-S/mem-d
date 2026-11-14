# When AI Forgets the Caveat

## Evaluating Decision-Preserving Memory Deduplication

**Status:** Phase 1 protocol and synthetic development material, 2026-11-14.
No downstream experiment has run. This is not a preregistration of completed
experiments or a submission-ready empirical study. Novelty is provisional.

## 1. Problem, audience, and contribution

Semantically similar memories can disagree about permission, scope, certainty,
source authority, or time. Replacing them with one representative may erase a
detail that changes a later decision. Conversely, retaining every record wastes
context when the records really are interchangeable.

For developers operating agent memory and researchers studying consolidation,
the research question is: **Can mem-d identify memory merges that damage
downstream decisions while still allowing useful compression?** The proposed
contribution is a transparent, paired evaluation of an existing recommendation
gate against decisions grounded in explicit fictional evidence, with compression
and review burden reported together. It is not a new consolidation algorithm.

Falsifiable expectations for later evaluation:

- **H1 (decision preservation):** existing mem-d gating has lower mean paired
  decision-error change than ungated semantic merging at comparable achieved
  compression. Equal or greater error contradicts the directional expectation;
  inability to reach comparable compression leaves that comparison unestablished.
- **H2 (useful compression):** gating saves a positive number of actual memory
  tokens on genuine duplicate controls while preserving their required details.
  Refusing all merges, nonpositive savings, or detail loss contradicts this claim.
- **H3 (diagnostic discrimination, exploratory):** the gate vetoes a larger
  fraction of independently unsafe candidate transformations than safe ones.
  Report both denominators and all-veto behavior; perfect rejection of both is
  not useful discrimination. Recommendation confidence is not assumed calibrated.

The null possibilities include no advantage, increased error, useful compression
only in easy cases, and safety bought entirely through inaction. Wide intervals
are inconclusive, not proof of equivalence. The 20 development cases are for
debugging and interpretation, not confirmatory support for these hypotheses.

## 2. Inherited system and sprint boundary

The recorded preexisting baseline and implementation-start sprint head are both
`14af8eccc0141450d01981e189a48b72140ce754`.

Inherited components include parsing and normalization, embedding backends,
cosine/DBSCAN clustering, trust assessment, lifecycle/evolution analysis, policy,
recommendations, reporting, read-only structural simulation, workflow planning,
and their fixture-based evaluations. See `memd/pipeline.py`,
`memd/recommendations.py`, `memd/contracts.py`, and ADR-001/ADR-002. The baseline
root README describes simulation/workflows as future work even though the source
contains them; source inspection establishes what was inherited.

Existing recommendation evaluation checks architecture-intended rule application
to supplied evidence payloads. Its published 22/22 resolution accuracy is **not
evidence that compression improves downstream AI decisions**. Structural
simulation savings likewise are not measured tokenizer savings or answer utility.

New Phase 1 work consists only of this protocol, the development dataset,
provenance/usage documentation, a data validator, and a root README disclosure.
No production contracts, recommendation rules, or source memories change.
Future transformations must run in an **external research harness on disposable
copies**. Do not use inherited simulated active stores as the experimental
conditions: they have different keeper/archive semantics from this protocol.

## 3. Focused related-work check

Primary publication/paper URLs below were opened and checked on 2026-11-14.
This is a focused check, not an exhaustive systematic review. Reported results
in these papers are their authors' findings, not replications by this sprint.

| Primary paper | Overlap and proposed distinction |
| --- | --- |
| Wu et al., [LongMemEval](https://arxiv.org/abs/2410.10813), ICLR 2025; inspected v2 | Tests interactive memory, temporal reasoning, updates, and abstention. We isolate one compression intervention with explicit decision criteria rather than compare complete retrieval systems. |
| Maharana et al., [Evaluating Very Long-Term Conversational Memory of LLM Agents](https://aclanthology.org/2024.acl-long.747/), ACL 2024 | LoCoMo evaluates conversational QA, summarization, and dialogue generation. Our small fictional decision cases target loss of caveats; they do not replace conversational benchmarks. |
| Jiang et al., [LLMLingua](https://aclanthology.org/2023.emnlp-main.825/), EMNLP 2023 | Already studies compression with task performance. Our unit is a memory-record merge and its recommendation gate, rather than token-level prompt compression. |
| Chhikara et al., [Mem0](https://arxiv.org/abs/2504.19413), 2025; inspected v1 | Consolidation and downstream QA/cost comparisons already exist. We hold the representative procedure fixed to test the incremental gate, without claiming a superior memory architecture. |
| Zhang et al., [Useful Memories Become Faulty When Continuously Updated by LLMs](https://arxiv.org/abs/2605.12978), 2026; inspected v2 | Directly examines faulty consolidation and episodic controls. Our narrower intervention is one representative-only deduplication pass, not repeated abstraction over trajectories. |
| Colaco and Lahjouji, [What to Keep, What to Forget](https://arxiv.org/abs/2607.08032), 2026; inspected v1 | Frames compaction through downstream utility under budgets. We operationalize a small record-level comparison; the accuracy/compression tradeoff itself is not new. |
| Annapureddy and Thamatani, [The Epistemics of Agent Memory](https://arxiv.org/abs/2609.33013), 2026; inspected v1 | Studies consolidation quality and governance, including limits of proxy metrics. We directly score specified downstream decisions for a frozen existing mem-d gate; broad epistemic-consolidation novelty is unavailable. |
| Anand et al., [MEMOIR](https://arxiv.org/abs/2611.07631), 2026; inspected v1 | Especially close: judge-gated consolidation screens evidence preservation and measures compression/loss. Our distinction is testing existing deterministic mem-d recommendations, with identical medoid transformations and family-paired decision scoring. Merge screening itself is not novel. |

These overlaps substantially constrain the contribution. A later publication
needs a refreshed search, closer method comparison, and evidence that the narrow
evaluation teaches something beyond existing work. Do not claim firstness.

## 4. Dataset, ground truth, and split

`development.jsonl` contains exactly 20 fictional, manually inspectable English
cases: five genuine duplicates, five decision-changing exceptions (including
negation), five uncertainty/attribution distinctions, and five unresolved
contradictions. Ten scenario families each contribute two related cases. Software
releases, scheduling, purchasing, and other low-risk domains avoid real personal
or high-stakes data. Wording, caveat placement, and record counts vary.

Each case separates `input` from `evaluator_only`. The input contains memory
records compatible with the core MemoryRecord fields, a question, explicit
decision criteria, and answer options. Top-level IDs, family, category, and split
are bookkeeping, not prompt material. Evaluator annotations contain acceptable
labels, rationale, decisive evidence references, required surviving details, and
an independent merge-safety judgment. See the research README for the contract.

Gold answers follow the fictional evidence and stated decision rules, never
mem-d's recommendations. Criteria state authority and precedence explicitly;
record order, recency, repetition, and assertive phrasing confer no authority
unless the case says so. Unresolved contradictions permit
`insufficient_evidence`, which must be justified by the conflicting evidence.
An explicit prohibition is distinguished from missing confirmation. Caveats
sometimes permit the action. A duplicated statement containing “except” can be
safe to compress; a suspicion can remain attributed while an action proceeds.

In the shared solver instructions, establish the fictional query time as the
latest original record timestamp (unchanged across conditions). Interpret
relative dates inside a record against that record's timestamp, and “now” or
“today” in the question against the fixed query time, never the execution clock.

The safety judgment asks whether the annotated candidate records are
interchangeable under **arbitrary single-record replacement**, holding other
records fixed. `unsafe` means at least one choice loses a required distinction;
it does not mean every medoid outcome is unsafe or that a faithful summary is
impossible. A safe judgment applies only to the specified group and case task,
not arbitrary future questions. Candidate annotations are evaluator-only and
must never drive candidate generation. Audit actual transformations separately.

All cases and all ten families are **development**. Category counts and variant
counts are not independent sample sizes. Later held-out data must use new
scenario families (new underlying evidence/decision setups), not renamed or
paraphrased development templates. Conservatively group related causal setups
under one family. Freeze a family manifest before evaluation; document uncertain
family assignments and contamination. Generate no held-out cases in Phase 1.

Author review covers every case's answer, evidence links, authority/scope rules,
and safety judgment. It is not independent human annotation. Independent review
and adjudication remain necessary before stronger claims.

## 5. Planned comparison conditions

Run one simultaneous deduplication pass within each case; never cluster records
across cases. Start every condition from a fresh copy of identical original
records. Preserve source and time fields. The information-preserving reference
means preservation of supplied information, not guaranteed model correctness.

| Condition | Procedure |
| --- | --- |
| Original | Supply all original records, unchanged. |
| Exact | Group records equal in content, source, timestamp, and any other evidence-bearing fields, excluding ID. Keep the lexicographically smallest ID. Do not normalize wording/case/whitespace or discard attribution differences to create matches. |
| Semantic | Embed content using local `BAAI/bge-small-en-v1.5`; cosine DBSCAN with `min_samples=2`, initial threshold `0.55`. For each cluster, keep the member with greatest mean cosine similarity to the other members; exact ties use lexicographic ID. Preserve its original payload, without summarization. Keep unclustered records. |
| Semantic + existing mem-d | Use the identical candidate clusters and medoids. Admit only complete groups passing the gate below; preserve every record of all other groups. |
| Optional later safeguard | Add a separate condition using the same candidates and medoids, against the frozen existing gate. Do not replace or retroactively relabel the existing condition. |

The semantic conditions use the same embedding vectors and raw memberships, so
the only intervention is permission to apply an already-defined transformation.
Use mem-d's existing enrichment/trust/policy/recommendation pipeline on those
records and clusters, with balanced policy and the same threshold. Never inject
gold labels or fabricated HIGH-trust evidence as the recommendation fixture
runner does for rule testing. DBSCAN connectivity may chain dissimilar endpoints;
record this as a potential baseline failure rather than changing clusters by hand.

The gate requires one merge recommendation whose affected ID set equals the
complete cluster; every member must resolve to `merge`, reference that
recommendation, and have consistent one-keeper/rest-removable roles. Require
nonconflicting resolutions and no pending human approval. Missing, duplicate,
partial, inconsistent, review, keep, archive, or approval-required dispositions
veto the entire cluster. Do not execute archive recommendations or resolve
reviews with oracle knowledge. Keep/review/veto preserve records and order.

Use the medoid in both semantic conditions even when mem-d suggests another
keeper: this tests **gating only**, not the full keeper-selection system. Report
keeper disagreement counts. This choice may understate or overstate the utility
of mem-d's complete recommendations and needs a later sensitivity analysis.

Merge policies see **only original memories**, not questions, criteria, gold, or
family/category identifiers. Downstream solvers see only transformed memories,
question, criteria, and all answer options. Exact matching and mem-d normalization
must not rewrite the original payload delivered to solvers. The harness must
map outputs back to unchanged unique IDs and fail if normalization alters IDs
or drops records. Do not silently substitute a different embedding backend:
mem-d currently catches optional-backend failures and falls back to hashing.
Verify the actual backend, pin the model revision, and invalidate fallback runs.

## 6. Outcomes, denominators, and scoring

Require downstream JSON with exactly the two string fields
`{"answer_label": "...", "justification": "..."}` and a nonempty justification.
Allowed labels are `proceed`, `do_not_proceed`, and `insufficient_evidence`.
The primary binary decision error is zero iff a valid single label belongs to
the case's acceptable set; otherwise one. Explanations are audited separately:
an unsupported explanation does not silently change this primary label metric.
Report unsupported abstentions and lucky correct labels in that audit. An
abstention is substantively justified only when its explanation identifies the
specified missing or conflicting evidence.

Invalid JSON, duplicate/extra keys, absent/nonstring/empty fields, unknown/multiple labels,
refusals, and truncation count as decision errors and remain in denominators.
Do not repair outputs with another model or use condition-specific retries.
Infrastructure/transport failures are different: permit at most two identical
retries, retain all attempt logs, and if unresolved exclude the entire matched
case/model/order block from every condition. Report excluded counts and reasons;
never impute a successful answer. Context overflow is a condition failure/error,
not a reason to silently drop an inconvenient condition.

For case c, model m, and paired repetition r, let e(k,c,m,r) be binary error in
condition k. The **primary outcome** is e(k,c,m,r) - e(original,c,m,r).
Average repetitions within case, cases within family, then equally weight
families. Report each downstream model separately; an equally weighted
cross-model average is secondary. Compare gated and ungated paired changes.
Always show full-memory error rates and a transition table: correct→wrong,
wrong→correct, correct→correct, wrong→wrong. Report introduced-error rate over
original-correct blocks and rescue rate over original-wrong blocks, with counts.
Zero eligible blocks means not applicable. Net change can conceal both effects.

| Secondary outcome | Numerator / denominator and handling |
| --- | --- |
| Critical-detail retention | Required details semantically preserved in transformed memory / all annotated required details. Audit scope, negation, certainty, source, and time, without relying on keyword overlap. Average within case/family; also show raw detail counts. Full-memory input is the reference. |
| Actual memory tokens saved | T(original memory serialization) - T(transformed memory serialization), plus that difference / T(original). Count records including displayed IDs, metadata, and delimiters with each downstream model's pinned tokenizer. Report absolute totals, family means, and tokenizer-specific fractions; negative savings are allowed. |
| Unsafe merge rate | Actually executed groups causing required-detail loss or unsupported meaning / all actually executed groups, audited on before/after text. Gold category or the arbitrary-representative safety label is not a substitute. Zero groups: N/A, not 0% unsafe. |
| Review frequency | Candidate groups containing at least one explicit `review` resolution / all semantic candidate groups. Report numerator/denominator, review memories / all original memories, total vetoes, approval-required groups, and unchanged records separately. Zero candidates: N/A. Ungated/exact methods have no review mechanism, which does not imply safety. |

For H3, audit every proposed group’s fixed medoid output, including vetoed
groups. Compare vetoed unsafe / all unsafe proposals against vetoed safe / all
safe proposals. This avoids conditioning discrimination on executed merges only.
Retention and safety audits use evaluator-only detail definitions after outputs
are frozen, preferably blinded to condition and adjudicated by two reviewers.
Missing audits are unscored, disclosed with coverage, never assumed safe.

Memory-token savings are not total inference savings. Separately account for
embedding/gating computation, all model input/output tokens, retries, review
work, latency, and any summarization cost in future extensions. Report offline
construction versus per-question cost and amortization assumptions. Record
counts, mem-d structural savings, and character counts cannot replace tokens.

## 7. Compression, pairing, and uncertainty

Report error versus **achieved** memory-token compression and review burden.
Include every fixed operating point on threshold grid
`[0.45, 0.55, 0.65, 0.75, 0.85, 0.95]`, including zero-compression outcomes;
`0.55` is the initial reference, inherited from mem-d rather than optimized here.
Do not choose favorable thresholds from held-out labels.

At each threshold, order disjoint candidate groups by decreasing mean pairwise
cosine similarity, then sorted member-ID tuple. Evaluate prefixes (including
empty and complete) for each method; gated prefixes apply the gate to every
candidate encountered. All choices are label-blind. Compare points whose
aggregate achieved compression differs by at most two percentage points, within
each tokenizer/model; choose the closest compression, then higher threshold,
then shorter prefix for ties. Report residual mismatch, both operating points,
and full curves, not just selected favorable comparisons. This is compression
matching, not a fitted performance frontier. Thresholds and prefixes define
exploratory comparisons, not independent hypothesis tests.

Original/exact conditions are fixed anchors, not forced to match arbitrary
budgets. If gated/exact methods cannot reach a level, mark it unreachable;
never force unsafe removal, extrapolate an advantage, or interpret all-review
behavior as H1+H2 success. Small stores can make close matching impossible.

For later execution, use three seeded record-order permutations per case
(seeds 2026, 2027, 2028), shared across all conditions. Canonically sort IDs before
clustering, so solver order tests do not change merge membership/medoids. Filter
the shared original permutation to obtain survivor order. Randomize condition
execution order within each case/model/permutation, logging the schedule seed.
Use isolated stateless solver calls: no conversation or cache transfers answers
between conditions. Keep prompts and decoding settings identical across
conditions within a model. Freeze all settings and output limits in a manifest.

Plan two genuinely distinct downstream model families if local hardware and
licenses permit. Select and pin versions in the later harness manifest before
any experiment; a second size of one family does not satisfy this goal. Use
temperature zero where supported, document remaining nondeterminism, and report
single-family feasibility limits instead of making paid calls in this phase.

Use paired 95% percentile bootstrap intervals with 10,000 resamples and seed
2026, sampling **scenario families**, keeping each family's cases, order repeats,
and paired condition outputs together. Recompute ratio statistics from sampled
counts; disclose undefined resamples rather than substituting zeros. With only
ten development families these intervals are unstable diagnostics. Never treat
20 variants, repeated calls, or model conditions as independent evidence.
No power or statistical-significance claim is supported by this development set.

## 8. Reproducibility, freeze, limitations, and ethics

Before later held-out evaluation, freeze and hash: dataset and family manifest,
code commit, existing gate and any new safeguard, thresholds/prefix rules,
embedding revision/backend, dependencies, solver model revisions, prompts,
tokenizers/serialization, seeds, scoring/invalid-output policy, audit rubric,
and analysis script. Complete harness leakage/invariance checks and development
debugging first. Predeclare held-out sample size from family-level pilot variance
and a minimum effect of interest before collecting that evaluation. Document all
subsequent amendments and reruns; policies changed after viewing held-out cases
require a new untouched evaluation, not relabeling the same cases as held-out.

Retain immutable originals, per-condition payloads, candidate/medoid maps,
recommendation evidence, veto reasons, seeds, token counts, raw responses,
operational failures, and audit decisions. Report every category and failures,
not just aggregate gains. Do not publish credentials or private model artifacts.

Limitations include synthetic author bias, small correlated samples, English-only
coverage, explicit decision rules unlike natural tasks, constrained answer labels,
single-pass compression, and a deliberately simple representative baseline.
Full memories can still confuse solvers; token reduction can sometimes improve
answers. One group's safety does not guarantee whole-store or unknown-query
safety. Query-blind gating cannot anticipate every future use. Model versions,
metadata, retrieval, repeated compaction, and distribution shift can change the
result. Independent human review and larger untouched families remain needed.

All scenarios and organizations are fictional and low-risk. Real deployments
raise consent, privacy, data-retention, and source-authority concerns absent here.
Removing attribution or uncertainty can launder a rumor into fact, or selectively
erase inconvenient evidence; the framework could be misused to optimize such
erasure. Preserve original records and provenance, limit claims to evaluated
tasks, and keep human review reversible. High review burden can cause fatigue;
report it rather than equate abstention with a usable system. This sprint grants
no permission to modify production memories or deploy autonomous consolidation.

## Phase 2 implementation clarifications (2026-11-14, before feasibility)

These choices resolve underspecified interfaces before producing any Phase 2
feasibility artifacts or solver responses. They do not change labels, gate rules,
thresholds, or hypotheses. No downstream solver experiment has run.

- Serialize displayed memories as compact JSON with sorted object keys,
  `ensure_ascii=False`, no trailing newline, preserving record order. Count this
  exact array with `add_special_tokens=False`, without truncation. It appears
  verbatim inside the solver's user JSON. Standalone-section tokenization is a
  reproducible memory-budget measure; boundary effects mean it is not a billed
  whole-prompt token delta.
- Use a common prefix cap k across cases: take each case's first min(k, number
  of candidates) groups, with k from zero through the largest case's group count.
  This makes the family-wide operating-point grid explicit without label-driven
  selection of separate budgets for individual cases. Original/exact remain
  fixed anchors, paired separately at each operating point, never pooled as
  extra observations. Freeze compression matches before scoring responses.
- Phase 2 uses the pinned Qwen2.5-0.5B-Instruct **tokenizer only** to check actual
  token feasibility; no Qwen solver or model-family comparison is run. This
  tokenizer choice is not selection of a downstream model for later experiments.
  Missing tokenizers yield null counts, not a character-based proxy.
- Freeze transformation/request files and their SHA-256 digests before permitting
  scoring or gold-bearing audit exports. Keep model payloads separate from
  routing IDs and evaluation metadata. A later transport must return structured
  status metadata (ok, truncated, refusal, context overflow, infrastructure)
  rather than let the scorer guess transport failures from text.
- The research adapter observes the genuine `analyze_file` embedding engine via
  a scoped instrumented subclass. It verifies a pinned local snapshot and that
  the sentence-transformer path actually returned the vectors used by mem-d.
  It does not substitute vectors or alter any upstream evidence, policy,
  recommendation, simulation, or workflow functions. A caught optional-backend
  exception followed by hashing is a fatal invalid run, not a valid condition.

### Post-recommendation pipeline failure (before retrying feasibility)

The first real-embedding preparation attempt stopped without a valid run:
inherited workflow planning raised a `WorkflowItem` validation error after the
genuine recommendation stage had completed. Workflow planning is downstream of
recommendations and has no feedback into the tested gate. The adapter will
observe the genuine report passed into simulation, still attempt the unchanged
simulation/workflow functions, and record any exception raised specifically in
those downstream functions. It may use the captured upstream report for this
recommendation-gate experiment, explicitly marking pipeline completion false.
Embedding, parsing, clustering, trust, policy, or recommendation failures remain
fatal. This isolates the intended intervention without repairing or hiding the
inherited workflow defect. This clarification precedes the retry and any valid
feasibility finding; the aborted attempt is retained as a blocker artifact.

## Phase 2B amendment — corpus budgets and blinded audits

**Recorded 2026-11-14, before constructing Phase 2B operating points.** This
amendment is informed by the Phase 2 development feasibility findings and the
frozen grid diagnosis; it was not preregistered independently of those findings.
No solver responses or independent human audits have been collected. The
original common-per-case-prefix grid and all Phase 2 artifacts remain historical
results without alteration.

### Diagnosis and prospective budget rule

The frozen run has at most one semantic candidate group per case at every
threshold. The common cap k is therefore only zero or one: ungated k=0 selects
nothing, while k=1 selects every case's available group. Gating admits a subset
at k=1 but cannot create intermediate ungated corpus budgets. Lack of nonzero
matches on that grid is not evidence that compression matching is intrinsically
impossible. The gate's actual approvals, refusals, and limited savings are
separate facts and will not be weakened or retuned.

For each existing threshold, reuse the frozen genuine pipeline evidence,
candidate memberships, original payloads, fixed medoids, and gate decisions.
Do not rerun clustering, change similarities, or inject annotations. Validate
the freeze/data hashes and recompute candidate/medoid and gate identities against
the unchanged implementation. Sort all candidate groups across the corpus by
decreasing **unrounded** mean within-group cosine similarity, breaking exact ties
lexicographically by sorted original member-ID tuple, then medoid ID. Original
memory IDs are globally unique, so no case/category/family ordering is needed.
Evaluate every prefix j=0..N of this global order, applying each selected
replacement only inside its original case. Never cluster across cases. This is
an **offline corpus-level similarity-first budget control**, not a deployable
query-blind per-store policy. No randomized control is added.

Original, exact deduplication, and the unchanged full-prefix mem-d gate remain
anchors at each threshold. The primary match for that gate is chosen among all
similarity-first prefixes **at the same threshold**, including zero, using the
smallest absolute aggregate memory-token savings gap, then the smaller prefix
length. Matching uses the pinned tokenizer, original serialization, and all three
shared order seeds. Use integer sums over seeds to avoid rounding ties; report
mean token counts by dividing by three. Require residual compression difference
at most 0.02 of the original corpus token count, inclusively. If no point meets
that rule, report unmatched; no interpolation, forced removal, or cross-threshold
search. Missing actual token counts make matching unavailable. Mark a comparison
nonzero only if **both** points save positive tokens. This tolerance may be
permissive at small savings: report signed and absolute token gaps, percentage
points of original tokens, and gap relative to gate savings, with denominators.
Report every operating point, not just the selected match. These adaptive
development comparisons are not independent scenario observations.

Do not consult categories, gold answers, annotated groups, audits, or downstream
answers for ranking or matching. After selection, compare complete canonical
survivor payloads and all per-case/seed solver-message bytes. Identity is a
reported outcome, **not** a matching tie-break. Compare against exact matching by
payload, not token equality. Report groups/records/cases affected, additional
non-exact merges and incremental savings, unchanged gate review counts and all
veto reasons. Non-exact is a syntactic description, not proof of paraphrase safety.
Report whether any global prefix reproduces the gate as an identity diagnostic,
without substituting such a point for the predeclared token-selected match.
Identical prompts do not warrant separate solver calls to infer an intervention
effect; stochastic differences between identical inputs are not a gate benefit.

### Prospective blinded audit export

Export each actual single-group medoid proposal across all thresholds, accepted
or vetoed, applying it to a fresh original case with all other records preserved.
Deduplicate by byte-identical reviewer content: complete original records,
proposed survivor records, question, decision criteria, and fixed original query
time, after replacing original record IDs with local ordinal aliases. Do not
deduplicate merely by number of deleted records or by old safety annotations.
Sort unique packet hashes, shuffle presentation using fixed seed 20262, and
assign sequential neutral audit IDs. This randomization concerns presentation
only, not budget selection, inference, or independent sample size.

Reviewer files contain only the neutral audit ID and the content above. Hide
condition, threshold, similarity, case/family/category identifiers, gate action,
gold answers, rationales, required-detail annotations, and prior safety labels.
Put packet hashes, original ID mappings, source proposals, and gate provenance
in a separate evaluator-only directory. The public fictional content can still
be recognized by someone who has seen the dataset; blinding is procedural, not
a guarantee against re-identification. Share only the reviewer directory.

Supply a neutral rubric and entirely unfilled response template asking about
decision-relevant loss; scope, negation, certainty, attribution, and time changes;
original/proposed justified decisions and whether they differ; ambiguity or
unscorability; and an evidence-based rationale. Inspect the actual fixed medoid,
not arbitrary replacement or deletion alone. Seek two independent human reviews
before adjudication; do not auto-fill judgments or describe assistant authorship
as independent human review. Human review remains pending in this phase.
