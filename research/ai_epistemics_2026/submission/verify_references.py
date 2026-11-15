"""Verify cited bibliography against retrieved primary HTML and PDF title pages."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import fitz
from lxml import html

HERE = Path(__file__).resolve().parent
SPECS = [
    (
        "longmemeval",
        "https://arxiv.org/abs/2410.10813",
        2025,
        "ICLR 2025",
        "Published as a conference paper at ICLR 2025",
        (
            "Evaluates extraction, multi-session and temporal reasoning, updates and abstention"
            " in long-term interactive memory."
        ),
        "Abstract; five abilities",
    ),
    (
        "locomo",
        "https://aclanthology.org/2024.acl-long.747/",
        2024,
        "ACL 2024 (Long Papers), 13851–13870",
        "Proceedings of the 62nd Annual Meeting",
        (
            "LoCoMo evaluates long conversational memory using question answering, "
            "summarization and multimodal dialogue tasks."
        ),
        "Abstract",
    ),
    (
        "llmlingua",
        "https://aclanthology.org/2023.emnlp-main.825/",
        2023,
        "EMNLP 2023, 13358–13376",
        "Proceedings of the 2023 Conference",
        "Prompt compression and task-performance trade-offs are established research topics.",
        "Abstract; budget controller and token-level compression",
    ),
    (
        "mem0",
        "https://arxiv.org/abs/2504.19413",
        2025,
        "arXiv:2504.19413 (preprint version)",
        None,
        (
            "A memory architecture extracts, consolidates and retrieves information and "
            "evaluates downstream QA."
        ),
        "Abstract",
    ),
    (
        "prior_2605",
        "https://arxiv.org/abs/2605.12978",
        2026,
        "arXiv:2605.12978 (preprint version)",
        None,
        (
            "Studies faulty continuously consolidated memories and an episodic-retention "
            "control; compaction harm is not a new hypothesis here."
        ),
        "Abstract",
    ),
    (
        "prior_2607",
        "https://arxiv.org/abs/2607.08032",
        2026,
        "arXiv:2607.08032 (preprint version)",
        None,
        "Frames memory compaction as retaining downstream utility under a resource budget.",
        "Abstract",
    ),
    (
        "prior_2609",
        "https://arxiv.org/abs/2609.33013",
        2026,
        "arXiv:2609.33013 (preprint version)",
        None,
        (
            "Separates consolidation quality and governance, and reports a negative external-"
            "validity result for its quality score."
        ),
        "Primary abstract; not independently replicated by this submission",
    ),
    (
        "prior_2611",
        "https://arxiv.org/abs/2611.07631",
        2026,
        "arXiv:2611.07631 (preprint version)",
        None,
        (
            "MEMOIR already combines judge-gated consolidation screening with a memory "
            "lifecycle; merge gating is not claimed novel."
        ),
        "Abstract and opening description",
    ),
    (
        "mcq",
        "https://arxiv.org/abs/2309.03882",
        2024,
        "ICLR 2024",
        "Published as a conference paper at ICLR 2024",
        (
            "Documents option-ID selection/token bias and studies permutation-based debiasing; "
            "the present diagnostic is not a novel discovery of that effect."
        ),
        "Abstract",
    ),
]


def normalized(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--cache", type=Path, default=Path("/tmp/memd-reference-verification"))
    args = cli.parse_args()
    verified = []
    for index, (name, url, year, venue, venue_proof, claim, location) in enumerate(SPECS, 1):
        page = args.cache / (name + ".html")
        pdf = args.cache / (name + "_pdf.pdf")
        tree = html.fromstring(page.read_bytes())
        title = tree.xpath('//meta[@name="citation_title"]/@content')[0]
        authors = tree.xpath('//meta[@name="citation_author"]/@content')
        # ArXiv metadata uses family-name, given-name; ACL already uses display order.
        authors = [" ".join(a.split(", ")[::-1]) if ", " in a else a for a in authors]
        doc = fitz.open(pdf)
        first = doc[0].get_text()
        assert normalized(title) in normalized(first), (name, "PDF title mismatch")
        for author in authors:
            assert normalized(author.split()[-1]) in normalized(first[:2500]), (name, author)
        if venue_proof:
            assert venue_proof in first, (name, "venue not verified")
        abstract_nodes = tree.xpath('//*[contains(@class,"abstract")]')
        abstract = " ".join(abstract_nodes[0].text_content().split()) if abstract_nodes else ""
        assert abstract
        verified.append(
            {
                "id": index,
                "title": title,
                "authors": authors,
                "year": year,
                "venue_or_version": venue,
                "primary_url": url,
                "primary_pdf_url": tree.xpath('//meta[@name="citation_pdf_url"]/@content')[0],
                "retrieved_date": "2026-11-15",
                "primary_html_sha256": hashlib.sha256(page.read_bytes()).hexdigest(),
                "primary_pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
                "verified_against": "primary HTML metadata and PDF first page",
                "claim_supported": claim,
                "support_location": location,
                "short_support_excerpt": " ".join(abstract.removeprefix("Abstract:").split()[:18]),
                "publication_status_note": "Venue verified on primary PDF"
                if venue_proof
                else "ArXiv version cited; no peer-reviewed venue claimed",
            }
        )
    out = HERE / "references"
    out.mkdir(exist_ok=True)
    (out / "verified-references.json").write_text(
        json.dumps(verified, indent=2, ensure_ascii=False) + "\n"
    )
    lines = [
        "# Primary-reference audit",
        "",
        (
            "Retrieved 2026-11-15. Titles and author lists were checked against primary HTML "
            "metadata and PDF title pages. Conference status is claimed only where the primary "
            "PDF states it. Other cited versions are identified as arXiv preprints. No paper's "
            "reported numerical results are presented as this sprint's results."
        ),
        "",
    ]
    for ref in verified:
        lines += [
            f"## [{ref['id']}] {ref['title']}",
            "",
            ", ".join(ref["authors"]) + f" ({ref['year']}). {ref['venue_or_version']}.",
            "",
            f"Primary source: {ref['primary_url']}",
            "",
            f"Supports: {ref['claim_supported']}",
            f"Location: {ref['support_location']}. Verification: {ref['publication_status_note']}.",
            "",
        ]
    lines += [
        "## Scope",
        "",
        (
            "All nine research papers cited by the report were verified; none is carried "
            "forward solely because it appeared in an earlier protocol. No firstness claim is "
            "made. The report does not cite unverified author affiliations or infer Afnan "
            "Khan's affiliation from other authors. Paper PDFs/HTML are cached locally for "
            "verification rather than redistributed with the submission. SHA-256 hashes "
            "identify retrieved versions in the JSON ledger."
        ),
        "",
    ]
    (out / "REFERENCE_AUDIT.md").write_text("\n".join(lines))
    print(
        f"Verified {len(verified)} cited research papers "
        "against primary metadata and PDF title pages."
    )


if __name__ == "__main__":
    main()
