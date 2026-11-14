# Phase 3 development pilot plan — recorded before solver execution

2026-11-14. Starting commit: `5da79b3ad282eda44c96e7da250c440294089996`.
This is exploratory. Threshold 0.95 was selected because pre-answer development
transformation analysis found different payloads; five other thresholds reproduce
simpler controls. Human semantic review remains pending. The dated protocol
amendment permits exploratory calls before review, without claiming semantic safety.

Use all 20 existing cases and order seeds 2026/2027/2028. Four conditions at 0.95:
original, exact, frozen similarity-first prefix 3, and existing mem-d gating.
Keep every planned denominator (60 observations/condition/model; ten families).
Freeze a separate per-model manifest, requests, tokenizer-specific matching grid,
and within-block reuse mapping before execution. No generation for calibration,
prompt tuning, or response-format repair occurs before or during this pilot.

Resource inspection found two CPU cores of cgroup quota, 8 GiB memory, about
6 GiB free disk, no GPU, no generation model cache, and no configured provider
credentials/endpoints. Torch 2.6.0+cpu and Transformers 4.57.1 are installed.
Only public model downloads and local inference will be used; no paid calls.
Download weights into a new Phase 3 cache, preserving Phase 2 tokenizer caches.

Explicit model selections (not an inference from the old tokenizer cache):

| Family | Repository | Immutable revision |
| --- | --- | --- |
| Qwen2.5 | Qwen/Qwen2.5-0.5B-Instruct | 7ae557604adf67be50417f59c2c2f167def9a775 |
| SmolLM2 | HuggingFaceTB/SmolLM2-360M-Instruct | a10cc1512eabd3dde888204e902eca88bddb4951 |

Run sequentially on CPU in float32, two Torch threads, eval/inference mode,
deterministic algorithms, each repository's pinned chat template, greedy decoding
(`do_sample=False`), 256 new tokens maximum, 4,096 total tokens maximum, and model
EOS/padding settings. Use the paired order seed as the generation seed even
though greedy decoding does not sample. No JSON-constrained decoding or lexical
answer extraction is added. Strict existing response parsing determines validity.

For each tokenizer, rerun the complete 0.95 corpus budget curve without labels.
Require frozen prefix 3 to remain the nearest token match within two percentage
points. Report all actual counts and residual tokens. If it fails, stop that
model before answers and report the blocker; no answer-driven reselection.

Reuse only byte-identical requests inside a case/model/order block, in the frozen
randomized condition schedule. Do not reuse across planned repetitions. Expected
maximum first attempts: 240 logical requests but 72 physical requests per model;
at most 216 attempts with infrastructure retries. Across two families: 480 logical
observations, 144 first attempts, at most 432 attempts. Bound each model to 20
minutes of inference and each attempt to 60 seconds (one native step of slack).
Model loading/downloading are separate. Budget exhaustion leaves planned requests
with explicit infrastructure statuses and whole-block exclusions, not silent drops.
The un-retried generation ceiling is 18,432 new tokens/model; actual usage and
timing will be measured. Runtime precision is unknown before execution.

Freeze raw responses and physical-submission provenance before scoring. Never
change labels after answers. Score every condition with the existing family
weighting and paired bootstrap. Report raw counts, invalid outputs, exclusions,
original-correct→wrong and original-wrong→correct transitions, gate/exact and
gate/control contrasts, case-level failures, and concentration in individual
families. Reuse does not enlarge the sample. Memory-section token savings are
distinct from chat-template input usage and total inference compute/cost.

Explanations remain available for audit, with semantic support unscored until
reviewed. Any assistant-authored example commentary must say so. Two genuine
independent human submissions remain pending; the importer must validate and
preserve them separately, without fabricating agreement or filling blank forms.

After feasibility, propose an untouched family-based evaluation size, a minimum
effect of interest, call counts, and resources. Treat zero or unstable pilot
variance as inadequate for precise power estimation. No held-out generation or
access is part of this phase, and tests alone establish no publication strength.
