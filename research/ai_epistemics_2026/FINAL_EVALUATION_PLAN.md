# Untouched evaluation plan — Phase 3 proposal

This is a resource-capped proposal informed by exploratory development feasibility,
not an assertion of sufficient statistical power or submission readiness. No
held-out cases have been generated or accessed in this phase. Pilot findings and
runtime estimates are recorded in [PILOT_RESULTS.md](PILOT_RESULTS.md).

The completed pilot has zero family-level variance for gate versus exact and
gate versus similarity-first in both models. Qwen reaches a strict-format floor;
SmolLM2's only gain over originals is a format change in one family, equally
achieved by exact deduplication. **Precise sample-size/power estimation is
unavailable from this pilot.** Before accessing untouched evaluation, validate
a prospectively amended common output interface and more capable model choices
on development format checks. Target at least 95% structurally valid responses
in each condition, without selecting models by a favorable gate effect. Preserve
the old pilot scoring; stop held-out execution until the interface is feasible.

## Target, effect of interest, and interpretation

- Target **100 independently authored and reviewed scenario families**, two
  related cases each: 200 cases. The family, not the case, order, model, or audit
  packet, is the resampling unit. Conservatively merge families sharing a generator
  or underlying causal setup; do not manufacture 100 units through renamed templates.
- Minimum effect of interest: **5 percentage points absolute reduction in
  family-weighted decision error** for existing mem-d versus the label-blind
  matched similarity-first control at 0.95. Report gate/exact and all original-memory
  paired changes as well. This is an absolute error difference, not a relative
  percentage of a small baseline error count.
- A practical positive result also requires positive compression and disclosure
  of the achieved budget, residual token gap, and review burden. Predeclare a
  5% memory-token compression target as a practical benchmark; if unreachable,
  report that limitation rather than delete evidence or tune the gate. Do not
  restrict analysis to original-correct cases or families where mem-d merges.
- Freeze the number of families before answers. The target of 100 is a pragmatic
  annotation/resource allocation, **not** a pilot-derived power guarantee. Ten
  correlated development families, especially contrasts with zero variance or
  isolated nonzero families, cannot support a precise sample-size estimate.
  Report inconclusive intervals honestly; do not extend the sample after viewing
  favorable or unfavorable held-out results without a new untouched evaluation.

## Untouched content and independent labels

Plan eight to 24 records per case, with four to twelve meaningful distractors
where compatible with the task. Include related but irrelevant entities, versions,
sources, and events, rather than filler copied solely to increase token counts.
Include exact duplicates and useful paraphrases as well as harmful consolidation
opportunities; the policy must face real compression opportunities.

Use new relational/causal setups, not renamed release permissions, ribbon delivery
commitments, room-start disputes, lamp purchase approvals, or snapshot-clearance
templates from development. Candidate mechanism areas include unit/bundle
equivalence in hobby inventory, referential binding across document handoffs,
explicit cancellation and state reversions, conjunctive or quorum requirements,
spatial constraints in layout tasks, provenance retractions, multi-item dependency
chains, and relative-time validity windows. These are design areas, not generated
cases or guarantees of independent family identity.

Before running mem-d, set coverage quotas of 50 cases each for duplicates,
exceptions, uncertainty/attribution, and unresolved contradictions. Balance
action-permitting, action-rejecting, and insufficient-evidence outcomes where
the fictional evidence supports them. Do not filter families using mem-d approval,
similarity, or solver success. An author who has not inspected pilot failure
examples should construct evidence/criteria; two independent humans should verify
labels and family boundaries before any held-out model responses. Disclose author
exposure to the development study and any unavoidable overlap.

Record family-generation provenance and reject paraphrases of development
templates for split integrity. Reject or repair genuinely ambiguous labels only
before the evaluation freeze, with reasons preserved independently of policy
predictions. Never relabel after model answers or use internal mem-d rules as truth.

## Frozen comparisons and analysis

Use original, exact, unchanged gate, and the offline corpus-level similarity-first
control. Primary threshold remains 0.95, selected adaptively in development and
fixed prospectively for this new evaluation. Other thresholds may have
transformation-only diagnostics; no answer-dependent threshold selection.

For each pinned solver tokenizer, enumerate corpus prefixes and select the nearest
gate budget using the existing integer-token matching rule, shorter-prefix tie-break,
and inclusive two-percentage-point tolerance. Freeze selections before answers.
Report absolute gaps and gap/gate-savings ratios; a nominal match can still be
unpersuasive at tiny savings. If no informative nonzero match exists, keep and
report the unmatched result. This remains an offline corpus allocation, not a
deployable per-store policy.

Use three paired order seeds and two genuinely distinct model families. Prefer
models of at least approximately 3B parameters for external validity if hardware
permits; freeze exact identities before held-out generation/response access.
The tiny CPU pilot models are feasibility evidence, not a substitute for broader
capability coverage. Choose models for resources and independent capability
considerations, never for an observed gating advantage. Benchmark resource
requirements on development data before the final freeze, without tuning policies
or selecting models by favorable treatment effects.

Freeze code, data/family manifest, policies, medoids, tokenizer-specific budgets,
prompts/chat templates, generation settings, strict output handling, response reuse,
attempt/exclusion policy, semantic audit rubric, and analysis. Preserve all 200
cases in planned denominators. Average orders within cases and cases within
families, then equally weight families. Report per-model paired bootstrap intervals
using 10,000 family resamples, raw introduced/rescued counts, exclusions, invalid
outputs, case examples, and concentration in individual families. Zero variance
does not prove equivalence. Model/order repeats and reused answers are not new
independent evidence. Distinguish correct labels from supported explanations.

Collect two independent blinded semantic audits of actual medoid proposals,
including vetoes, with immutable separate submissions before adjudication. Keep
assistant/model inspection separate. Final semantic-safety conclusions require
real reviews, even if exploratory solver accuracy differs.

## Calls, resources, and stop/go criteria

With 200 cases × 3 orders × 4 conditions × 2 model families, plan **4,800 logical
observations**. Within-block byte-identity reuse can reduce first attempts, but
budget conservatively for **4,800 physical first attempts** and at most **14,400
attempts** including two infrastructure retries. Never deduplicate planned orders
or count response reuse as extra evidence. At 256 new tokens/attempt the first-attempt
ceiling is 1,228,800 output tokens; at a 4,096-token total context limit the prompt
ceiling is 18,432,000 input tokens. Retries can triple those upper bounds. Larger
record sets may require a larger predeclared context window; do not silently
truncate or exclude long cases.

The current environment provides two CPU cores of quota, 8 GiB RAM, no GPU, and
limited scratch disk. It supports only the small sequential pilot economically.
Measured **physical** generation time was 12.17 seconds/request for Qwen and
5.32 for SmolLM2. At 2,400 first attempts per model, that is approximately 11.7
CPU wall-hours combined at the same short workload without reuse. Transferring
the pilot's 30% physical/logical ratio would give about 3.5 hours, but that reuse
ratio cannot be assumed for new cases. Eight-to-24-record inputs increase prefill;
reserve an illustrative one to three CPU days for the small-model workload and
measure throughput first. These are not GPU or larger-model benchmarks.
For two larger instruction families, reserve at least a 16 GiB GPU or a separately
validated quantized/CPU deployment, roughly 16 GiB host RAM and 15–25 GiB disk
for weights, caches and artifacts. Measure throughput before committing to a
wall-time budget; no paid provider spending is authorized by this plan.

Annotation is substantial: 400 independent case-label reviews at an illustrative
five minutes each are about 33 reviewer-hours, plus case authoring, proposal
audits, and adjudication. These are planning assumptions, not observed timings.
Proceed only after independent reviews, qualified family provenance, sufficient
compute/storage, and a complete pre-answer freeze. Otherwise reduce claims or
obtain resources before accessing the untouched evaluation, rather than silently
substituting mock outputs or publishing a power claim unsupported by the pilot.
