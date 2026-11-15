# Submission validation — 2026-11-15

These checks establish artifact consistency and report legibility, not downstream decision benefit. No new model inference, paid calls, held-out cases, reviewer submissions or score changes were performed while preparing this report.

## Evidence and references

- `verify_evidence.py` passes: all historical directory SHA-256 manifests and archive freeze digests verify; 20 cases, ten families and 52 records are independently counted; complete transformed payloads and every headline compression/review count are recomputed.
- The cached pinned Qwen0.5B vocabulary independently recounts **13,680 actual serialized memory sections** across all stored operating points/orders, agreeing with frozen token counts. No character-to-token approximation or inference is used.
- Historical JSON outputs, semantic labels and neutral codes are independently reparsed against unchanged keys. The derived counts reproduce the published findings, including 50/108 code answers correct, 108/108 valid and 16/18 items changing semantic answer. Ten claim groups link the report's empirical statements to source artifacts and units.
- `verify_references.py --cache /tmp/memd-reference-verification` passes for all nine cited papers: primary HTML title/author metadata and PDF title pages, with conference status verified where claimed. Supporting claims and hashes are recorded in the reference audit; later papers are explicitly cited as preprints. No firstness or unverified affiliation claim is made.
- `git diff --quiet 14af8eccc0141450d01981e189a48b72140ce754 -- memd` passes. No inherited production file, gold label, gate rule or historical artifact is changed.

## Automated rendering checks

`check_report.py --check-links` passes. The PDF has **six body pages**, **one reference page**, **three appendix pages**, **ten total pages**, and a **191-word abstract**. It checks US Letter geometry, one-inch DOCX margins, author/abstract consistency, no instructional placeholders, all text bounds, nonblank pages, required appendix/LLM statement and Old Standard TT usage. `pdffonts` confirms embedded fonts. All **13 public HTTP links resolve with status 200**, including nine paper references, the sprint link and repository links. Machine-readable statuses and final PDF/DOCX hashes are in `derived/render-validation.json`; software versions are in `derived/build-environment.json`.

The builder opens the actual current official DOCX export. See `TEMPLATE_COMPLIANCE.md` for the source, format adaptations and metadata distinction. The final delivery's `SHA256SUMS` records this packaging snapshot; it is not a pre-answer study registration.

## Page-by-page visual inspection

All pages were rendered at 1.3× and inspected by the assistant. This is layout inspection, **not independent human semantic review**. Seven final page rasters were byte-identical to their inspected versions (1, 2, 3, 6, 7, 8, 10); updated pages 4, 5 and 9 were inspected again after final edits.

| Page | Inspection |
| --- | --- |
| 1 | Official title rules and linked footnote retained; author/email and missing affiliation visible; abstract/intro fit. |
| 2 | Related work and corpus provenance legible; full inherited baseline included. |
| 3 | Policy, matching, isolation and denominators fit without clipping. |
| 4 | Compression/review plot legible; overlapping annotation removed; captions identify tokenizer and both review denominators. |
| 5 | Model/interface table complete; code-frequency figure legible; validity and decision correctness separated. |
| 6 | Supported/unsupported table, conclusion and repository links fit. |
| 7 | Nine consistent primary-source references with working links; no overwide citation text. |
| 8 | Required limitations/dual-use appendix complete, including personal-data and missing-review disclosure. |
| 9 | Model hashes and logical/physical/reuse table legible; generation settings and adaptive provenance complete. |
| 10 | Six mapping rows legible, header corrected to avoid wrapping; LLM Usage Statement complete. |

## Repository checks actually run

```bash
python research/ai_epistemics_2026/validate_development.py
ruff check research/ai_epistemics_2026
python -m pytest tests research/ai_epistemics_2026/tests -q
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  MEMD_RESEARCH_MODEL_CACHE=/tmp/memd-phase2-hf/hub \
  MEMD_PHASE3B_CACHE=/tmp/memd-phase3-hf/hub \
  python -m pytest research/ai_epistemics_2026/tests -q -rs
ruff check . --output-format concise
git diff --check
```

The dataset validator, research lint and whitespace checks pass. The combined test run, before cache variables were set, reports **550 passed, 11 skipped, two failed**. Nine research skips explicitly required cache variables; repeating the research suite with the existing pinned offline caches gives **116 passed, zero skipped**. These tests exercise tokenizer paths/masks and frozen transformations, not new solver answers. The two remaining optional repository skips concern absent LongMemEval samples. A pytest/AnyIO deprecation warning remains.

The two combined-suite failures are the documented inherited missing fixtures `tests/fixtures/memories.txt` and `tests/fixtures/memories.jsonl` in `tests/test_parser.py::test_load_memory_file_supported_formats`. Whole-repository Ruff still reports **86 findings in thirteen unchanged files**. No fixtures are regenerated, lint suppressed, production code modified or unrelated cleanup performed.

## Outstanding

Affiliation or confirmed independent status for Afnan Khan remains unprovided. The supplied contact is `inbox.afnankhan@gmail.com`. This is the remaining author-metadata requirement before external submission; template access and report rendering are complete. Independent human reviews remain pending as a scientific limitation. No external form submission is performed.
