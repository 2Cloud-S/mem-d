# Memory transformation review

Review the before/after evidence in each packet independently. The cases are
fictional. Record IDs are local aliases; record text, source, and time are
preserved. All other supplied information is available to interpret the question.
Use the explicit decision criteria and the fixed query time, not today's date.

Please do not consult the source repository, prior reviews, algorithms, or answer
keys while reviewing. Submit only the completed response template with your neutral
reviewer ID and `review_type` set to `independent_human` if that description is
accurate. Automated or assistant-authored review must instead identify itself as
`assistant`; it does not satisfy independent human review. Leave uncertain issues
explicit rather than guessing.

For every audit ID, inspect the complete original and proposed survivor records:

1. **Decision-relevant information lost:** answer `yes`, `no`, or `uncertain`.
   Has evidence needed to justify the specified decision disappeared, become
   inaccessible, or become misleading? A smaller record count is not itself loss.
   A redundant duplicate may be removed without changing any relevant information.
   Conversely, preserving similar wording can still erase a critical qualifier.
2. **Meaning changes:** separately mark `scope_changed`, `negation_changed`,
   `certainty_changed`, `attribution_changed`, and `time_changed` as `yes`, `no`,
   or `uncertain`. Consider the meaning of the surviving evidence as a whole,
   including lost source relationships or unresolved alternatives. Do not mark a
   change solely because an identical date/source or repeated word was deleted.
   Scope includes entity, environment, version, exception, and permission boundaries.
   Certainty includes tentative versus verified claims; attribution includes who
   asserted or authorized a claim; time includes validity, not just logging order.
3. **Justified decision:** briefly state `original_justified_decision` and
   `proposed_justified_decision`, then mark `justified_decision_changed` as `yes`,
   `no`, or `uncertain`. Compare what follows from the stated criteria, not what
   an AI might guess. Preserve justified uncertainty when evidence is unresolved.
   A lost detail need not change this particular decision, so these judgments
   can legitimately differ. A robust new summary is not proposed here: inspect
   only the actual survivor records shown.
4. **Ambiguity and scorability:** mark `ambiguous` and `unscorable` as `yes` or
   `no`. Ambiguous means multiple interpretations remain materially plausible;
   unscorable means the provided criteria/evidence cannot support a defensible
   judgment. Explain the missing information; use `uncertain` for affected fields.
   A case whose correct decision is insufficient evidence is not automatically
   unscorable: that may be the defensible decision under its explicit criteria.
5. **Rationale:** cite the local record aliases and the specific lost, retained,
   or changed evidence. State why that evidence matters under the decision criteria.
   One to four concrete sentences are enough; record both favorable and unfavorable
   observations. Do not reconstruct an omitted caveat using outside knowledge.

All judgment fields start null; none are prefilled. Set top-level `status` to
`completed` only after filling each packet, or `partial` if leaving packets pending.
Two reviewers should work separately, without discussion or access to each other's
responses. Retain both original responses. A later adjudicator should record
agreements, disagreements, and resolutions separately; do not overwrite independent
judgments. No completed human review is asserted by distributing this material.
