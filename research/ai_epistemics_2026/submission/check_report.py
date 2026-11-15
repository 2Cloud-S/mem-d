"""Check the rendered submission, optionally resolving its public HTTP links."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import fitz
import requests
from docx import Document

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def link_status(url):
    try:
        response = requests.get(url, timeout=30)
        return {"url": url, "status": response.status_code, "final_url": response.url}
    except requests.RequestException as error:
        return {"url": url, "error_type": type(error).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-links", action="store_true")
    parser.add_argument("--render-dir", type=Path, default=Path("/tmp/memd-submission-pages"))
    args = parser.parse_args()
    abstract = (HERE / "abstract.txt").read_text().strip()
    assert 150 <= len(abstract.split()) <= 250
    doc = Document(HERE / "report.docx")
    for section in doc.sections:
        assert abs(section.page_width.inches - 8.5) < 0.01
        assert abs(section.page_height.inches - 11) < 0.01
        assert all(
            abs(getattr(section, x).inches - 1) < 0.01
            for x in ("top_margin", "bottom_margin", "left_margin", "right_margin")
        )
    assert doc.core_properties.author == "Afnan Khan"
    assert doc.tables[0].cell(1, 0).tables[0].cell(0, 0).text.strip() == abstract
    pdf = fitz.open(HERE / "report.pdf")
    pages = [page.get_text() for page in pdf]
    references_page = next(i for i, text in enumerate(pages) if "\nReferences\n" in text)
    assert references_page == 6 and len(pdf) == 10
    text = "\n".join(pages)
    for required in (
        "inbox.afnankhan@gmail.com",
        "Independent Researcher, Pakistan",
        "Limitations and Dual-Use / Ethical Considerations",
        "LLM Usage Statement",
    ):
        assert required in text, required
    for forbidden in (
        "PROJECT TITLE",
        "Author name 1",
        "Summarize your project",
        "How to use this template",
        "{{TABLE",
        "[Link to GitHub",
        "Affiliation not provided",
    ):
        assert forbidden not in text, forbidden
    args.render_dir.mkdir(parents=True, exist_ok=True)
    links, page_checks = set(), []
    for index, page in enumerate(pdf):
        assert page.rect == fitz.Rect(0, 0, 612, 792)
        assert len(page.get_text().split()) > 30, (index, "blank or near-blank page")
        out_of_bounds = [
            w for w in page.get_text("words") if not page.rect.contains(fitz.Rect(w[:4]))
        ]
        assert not out_of_bounds, (index, out_of_bounds)
        fonts = sorted({font[3] for font in page.get_fonts()})
        assert any("OldStandardTT" in font for font in fonts)
        for link in page.get_links():
            if link.get("uri", "").startswith("http"):
                links.add(link["uri"])
        page.get_pixmap(matrix=fitz.Matrix(1.3, 1.3)).save(
            args.render_dir / f"page-{index + 1:02d}.png"
        )
        page_checks.append(
            {
                "page": index + 1,
                "words": len(page.get_text().split()),
                "text_within_page": True,
                "fonts": fonts,
            }
        )
    refs = json.loads((HERE / "references/verified-references.json").read_text())
    assert all(ref["primary_url"] in links for ref in refs)
    statuses = []
    if args.check_links:
        with ThreadPoolExecutor(max_workers=6) as pool:
            statuses = list(pool.map(link_status, sorted(links)))
    result = {
        "pdf_pages": len(pdf),
        "body_pages": references_page,
        "reference_pages": 1,
        "appendix_pages": 3,
        "abstract_words": len(abstract.split()),
        "public_http_links": len(links),
        "link_checks": statuses,
        "page_checks": page_checks,
        "pdf_sha256": sha(HERE / "report.pdf"),
        "docx_sha256": sha(HERE / "report.docx"),
        "remaining_metadata": None,
        "manual_visual_inspection": "See VALIDATION.md; not inferred by this script",
        "inference_calls": 0,
    }
    (HERE / "derived/render-validation.json").write_text(json.dumps(result, indent=2) + "\n")
    dependencies = {
        name: importlib.metadata.version(name)
        for name in (
            "python-docx",
            "matplotlib",
            "numpy",
            "PyMuPDF",
            "lxml",
            "requests",
            "tokenizers",
        )
    }
    versions = {
        cmd: subprocess.check_output([cmd, "--version"], text=True).splitlines()[0]
        for cmd in ("pandoc", "soffice")
    }
    (HERE / "derived/build-environment.json").write_text(
        json.dumps(
            {
                "python": platform.python_version(),
                "dependencies": dependencies,
                "tools": versions,
                "font": "Old Standard TT (bundled OFL files)",
                "platform": platform.platform(),
            },
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "body_pages",
                    "pdf_pages",
                    "abstract_words",
                    "public_http_links",
                    "remaining_metadata",
                )
            },
            indent=2,
        )
    )
    if args.check_links:
        failures = [row for row in statuses if row.get("status") != 200]
        print(json.dumps({"http_link_failures": failures}, indent=2))
        assert not failures, "Public link access failed; inspect recorded statuses"


if __name__ == "__main__":
    main()
