# Bounded feasibility submission

[Report PDF](report.pdf) · [editable DOCX](report.docx) · [Markdown](report.md) · [abstract](abstract.txt) · [submission details](SUBMISSION_DETAILS.md)

The report organizes the existing evidence around control equivalence, achieved compression, review burden and measurement validity. It introduces no new trials, labels, safeguards or production changes. The frozen evidence ends at `255b73fd3986844ea17292e1e8c27776a77cc9a3`; the inherited production baseline is `14af8eccc0141450d01981e189a48b72140ce754`. No independent human semantic reviews or untouched evaluation exist.

`report-source.md` is the editable authoring source. `build_report.py` expands its table/reference markers from verified artifact counts and bibliography, producing `report.md` and `report.docx`. It opens the **actual exported official template**, retains its title rules, footnote and abstract shell, removes instructional content/unused authors, and adds the report. The source Markdown's explicit page breaks are applied to following headings so they do not create blank pages. Only the author's provided name/email are used; affiliation is outstanding.

To reproduce the content and figures without model execution:

```bash
python research/ai_epistemics_2026/submission/verify_evidence.py
python research/ai_epistemics_2026/submission/make_figures.py
python research/ai_epistemics_2026/submission/build_report.py
soffice --headless --convert-to pdf \
  --outdir research/ai_epistemics_2026/submission \
  research/ai_epistemics_2026/submission/report.docx
python research/ai_epistemics_2026/submission/check_report.py --check-links
```

The evidence script checks historical SHA-256 manifests and internal freeze digests, independently parses frozen responses against original keys, compares complete payloads, and derives all plot/table counts. If the original pinned Qwen0.5 tokenizer is still cached, it independently recounts 13,680 serialized memory sections; otherwise it explicitly reports reliance on frozen integer counts. It never downloads weights, performs inference or changes historical artifacts. `derived/claim-ledger.json` links headline claims to evidence and defines their units; `derived/metrics.json` is the numerical figure/table input.

`make_figures.py` uses Matplotlib, with PNG/PDF/SVG exports; no image generation is used. There are no independent-sample confidence intervals for repeated mappings. Plot labels identify memory tokens and review denominators. `references/REFERENCE_AUDIT.md` and its JSON identify primary URLs, authors, publication status, supporting claims and retrieved-version hashes. All nine cited papers were checked against primary HTML and PDF title pages on 2026-11-15. To repeat that check after retrieving the listed primary HTML/PDF files into a local cache:

```bash
python research/ai_epistemics_2026/submission/verify_references.py \
  --cache /path/to/primary-source-cache
```

Cache names are the first field of `verify_references.py`'s `SPECS`, followed by `.html` or `_pdf.pdf`. Primary PDFs are not redistributed. Re-fetching a newer version may legitimately change source hashes; inspect it before replacing the verified bibliography.

Build requirements are recorded in [build-environment.json](derived/build-environment.json). The build used Python 3.12, python-docx, Matplotlib, NumPy, PyMuPDF, lxml and tokenizers, plus Pandoc and LibreOffice. Install the three bundled Old Standard TT font files locally and refresh the font cache before rendering. They come from Google Fonts' `ofl/oldstandardtt` directory under the included OFL license. The DOCX preserves the template's US Letter geometry and one-inch margins; the PDF embeds its fonts. PDF binary identity is not promised across office versions or build timestamps; numerical counts and source content are deterministic.

Validation includes artifact/token recounts, primary-reference checks, research tests/lint, PDF bounds/links/font checks and inspection of every rendered page. See [validation record](VALIDATION.md). The repository's inherited missing parser fixtures and existing lint findings remain unchanged; test success is not decision-benefit evidence.

This is a bounded exploratory report, with adaptive decisions disclosed. The next evidential task is genuine independent review of the 29 existing blinded proposals, preserving separate reviewer submissions. Model experimentation is finished. No external submission or main-branch merge is performed.
