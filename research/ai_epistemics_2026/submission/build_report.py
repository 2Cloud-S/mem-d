"""Build the editable report from the actual exported official DOCX template.

No inference is performed. The human-readable Markdown and DOCX share content;
tables and references are expanded from the independently verified evidence.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

HERE = Path(__file__).resolve().parent
TITLE = "Compression Controls and Decision Measurement in Memory Deduplication"
FONT = "Old Standard TT"
METRICS = json.loads((HERE / "derived/metrics.json").read_text())
REFERENCES = json.loads((HERE / "references/verified-references.json").read_text())


def table_content():
    qwen, smol = METRICS["historical_solver"]

    def result(model, condition, text):
        row = model["conditions"][condition]
        return [text, str(row["planned"]), str(row["valid"]), str(row["correct"])]

    outcomes = [
        ["Model / interface / inputs", "N", "Valid", "Correct"],
        result(qwen, "original", "Qwen0.5 / JSON / original, exact, gate"),
        result(qwen, "similarity_first", "Qwen0.5 / JSON / similarity-first"),
        result(smol, "original", "Smol360 / JSON / original"),
        result(smol, "exact", "Smol360 / JSON / exact, gate"),
        result(smol, "similarity_first", "Smol360 / JSON / similarity-first"),
    ]
    for row in METRICS["calibration"]:
        short = (
            "Smol360"
            if "Smol" in row["model"]
            else ("Qwen1.5" if "1.5B" in row["model"] else "Qwen0.5")
        )
        interface = "constrained JSON" if row["interface"] == "json" else "semantic labels"
        outcomes.append(
            [
                f"{short} / {interface} / calibration",
                str(row["planned"]),
                str(row["valid"]),
                str(row["correct"]),
            ]
        )
    row = METRICS["neutral"]
    outcomes.append(
        [
            "Qwen1.5 / neutral codes / calibration",
            str(row["planned"]),
            str(row["valid"]),
            str(row["correct"]),
        ]
    )

    conclusions = [
        ["Supported on these development inputs", "Still unsupported"],
        [
            "Five thresholds reproduce exact/control payloads",
            "Gate superiority or novel consolidation",
        ],
        [
            "0.95 yields a small distinct transformation",
            "Validated semantic safety or decision benefit",
        ],
        [
            "Code interface is mapping-sensitive; eligibility fails",
            "Causal token-bias diagnosis or broad incapacity",
        ],
    ]
    models = [
        ["Role / repository", "Frozen weight revision"],
        ["Embeddings: BAAI/bge-small-en-v1.5", "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"],
        ["Solver: Qwen/Qwen2.5-0.5B-Instruct", "7ae557604adf67be50417f59c2c2f167def9a775"],
        ["Solver: HuggingFaceTB/SmolLM2-360M-Instruct", "a10cc1512eabd3dde888204e902eca88bddb4951"],
        ["Solver: Qwen/Qwen2.5-1.5B-Instruct", "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"],
    ]
    history = [
        ["Historical stage", "Planned logical answers", "Real calls / reuse"],
        ["Original JSON development pilot (two models)", "480 = 2 × 20 × 3 × 4", "144 / 336"],
        [
            "Constrained JSON calibration (Qwen0.5)",
            "18; 5 infrastructure failures",
            "14 calls; 28 attempt-log rows",
        ],
        ["Forced semantic calibration (three models)", "54 = 3 × 18", "54 / 0"],
        ["Neutral-code diagnostic (Qwen1.5)", "108 = 18 × 6", "108 / 0"],
        ["Conditional neutral-code development rerun", "240 proposed; none executed", "0 / 0"],
    ]
    mapping = [["Map", "A means", "B means", "C means", "Correct / 18"]]
    short = {
        "proceed": "proceed",
        "do_not_proceed": "deny",
        "insufficient_evidence": "insufficient",
    }
    for row in METRICS["neutral"]["by_permutation"]:
        mapping.append(
            [f"P{row['permutation']}"]
            + [short[row["mapping"][code]] for code in "ABC"]
            + [str(row["correct"])]
        )
    return {
        "TABLE_OUTCOMES": outcomes,
        "TABLE_CONCLUSIONS": conclusions,
        "TABLE_MODELS": models,
        "TABLE_HISTORY": history,
        "TABLE_MAPPING": mapping,
    }


def markdown_table(rows):
    return "\n".join(
        ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * len(rows[0])) + " |"]
        + ["| " + " | ".join(row) + " |" for row in rows[1:]]
    )


def ref_text(ref):
    return (
        f"[{ref['id']}] {', '.join(ref['authors'])}. {ref['year']}. "
        f"{ref['title']}. {ref['venue_or_version']}. "
    )


def set_font(run, size=11, bold=None, italic=None):
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor(0, 0, 0)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is not None:
        fonts.set(qn("w:eastAsia"), FONT)


def hyperlink(paragraph, text, url, size=11):
    link = OxmlElement("w:hyperlink")
    rid = paragraph.part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    link.set(qn("r:id"), rid)
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    fonts = OxmlElement("w:rFonts")
    fonts.set(qn("w:ascii"), FONT)
    fonts.set(qn("w:hAnsi"), FONT)
    props.append(fonts)
    size_xml = OxmlElement("w:sz")
    size_xml.set(qn("w:val"), str(int(size * 2)))
    props.append(size_xml)
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "244D64")
    props.append(color)
    run.append(props)
    text_xml = OxmlElement("w:t")
    text_xml.text = text
    run.append(text_xml)
    link.append(run)
    paragraph._p.append(link)


def inlines(paragraph, nodes, size=11, bold=False, italic=False):
    for node in nodes:
        kind, val = node["t"], node.get("c")
        if kind == "Str":
            set_font(paragraph.add_run(val), size, bold, italic)
        elif kind in {"Space", "SoftBreak"}:
            set_font(paragraph.add_run(" "), size, bold, italic)
        elif kind == "LineBreak":
            paragraph.add_run().add_break()
        elif kind in {"Strong", "Emph"}:
            inlines(paragraph, val, size, bold or kind == "Strong", italic or kind == "Emph")
        elif kind == "Code":
            # Font continuity avoids overwide hashes/IDs in the manuscript.
            set_font(paragraph.add_run(val[1]), size, bold, italic)
        elif kind == "Link":
            text = inline_text(val[1])
            hyperlink(paragraph, text, val[2][0], size)
        elif kind == "Quoted":
            set_font(paragraph.add_run("“"), size, bold, italic)
            inlines(paragraph, val[1], size, bold, italic)
            set_font(paragraph.add_run("”"), size, bold, italic)
        else:
            raise ValueError(f"Unsupported inline: {kind}")


def inline_text(nodes):
    parts = []
    for n in nodes:
        if n["t"] == "Str":
            parts.append(n["c"])
        elif n["t"] in {"Space", "SoftBreak"}:
            parts.append(" ")
        elif n["t"] == "Code":
            parts.append(n["c"][1])
    return "".join(parts)


def add_table(doc, rows, key):
    table = doc.add_table(rows=0, cols=len(rows[0]))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    widths = {
        "TABLE_OUTCOMES": [4.65, 0.55, 0.65, 0.65],
        "TABLE_CONCLUSIONS": [3.45, 3.05],
        "TABLE_MODELS": [3.2, 3.3],
        "TABLE_HISTORY": [2.9, 1.95, 1.65],
        "TABLE_MAPPING": [0.6, 1.5, 1.5, 1.5, 1.4],
    }[key]
    for col, width in zip(table.columns, widths, strict=True):
        col.width = Inches(width)
    for index, row in enumerate(rows):
        cells = table.add_row().cells
        trpr = table.rows[-1]._tr.get_or_add_trPr()
        trpr.append(OxmlElement("w:cantSplit"))
        if index == 0:
            trpr.append(OxmlElement("w:tblHeader"))
        for cell, text, width in zip(cells, row, widths, strict=True):
            cell.width = Inches(width)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.line_spacing = 1
            size = 9 if key in {"TABLE_OUTCOMES", "TABLE_HISTORY", "TABLE_MODELS"} else 9.5
            set_font(p.add_run(text), size, bold=index == 0)
            if index == 0:
                shade = OxmlElement("w:shd")
                shade.set(qn("w:fill"), "EBF0F1")
                cell._tc.get_or_add_tcPr().append(shade)
        if index == 0:
            for cell in cells:
                cell.paragraphs[0].paragraph_format.keep_with_next = True
    # Keep all rows of these small tables on one page.
    for row in table.rows[:-1]:
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.keep_with_next = True


def prepare_template(abstract):
    doc = Document(HERE / "template/official-template.docx")
    shell = doc.tables[0]
    body = doc._element.body
    for child in list(body):
        if child is not shell._tbl and child.tag != qn("w:sectPr"):
            body.remove(child)
    title = next(p for p in shell.cell(0, 0).paragraphs if "PROJECT TITLE" in p.text)
    for p in list(shell.cell(0, 0).paragraphs):
        if not p.text:
            p._p.getparent().remove(p._p)
    title.paragraph_format.space_before = Pt(10)
    title.paragraph_format.space_after = Pt(12)
    for run in title.runs:
        if "PROJECT TITLE" in run.text:
            run.text = TITLE
            set_font(run, 20, bold=True)
    cell = shell.cell(1, 0)
    author_grid = cell.tables[0]._tbl
    p = OxmlElement("w:p")
    author_grid.addprevious(p)
    author_grid.getparent().remove(author_grid)
    from docx.text.paragraph import Paragraph

    author = Paragraph(p, cell)
    author.alignment = WD_ALIGN_PARAGRAPH.CENTER
    author.paragraph_format.space_after = Pt(3)
    for index, text in enumerate(
        ["Afnan Khan", "inbox.afnankhan@gmail.com", "Affiliation not provided"]
    ):
        if index:
            author.add_run().add_break()
        set_font(author.add_run(text), 10 if index else 11, bold=index == 0)
    abstract_p = cell.tables[0].cell(0, 0).paragraphs[0]
    abstract_p.clear()
    abstract_p.paragraph_format.line_spacing = 1
    abstract_p.paragraph_format.space_after = Pt(0)
    set_font(abstract_p.add_run(abstract), 10)
    for section in doc.sections:
        section.page_width, section.page_height = Inches(8.5), Inches(11)
        section.top_margin = section.bottom_margin = Inches(1)
        section.left_margin = section.right_margin = Inches(1)
        footer = section.footer.paragraphs[0]
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_font(footer.add_run(""), 9)
        field = OxmlElement("w:fldSimple")
        field.set(qn("w:instr"), "PAGE")
        footer._p.append(field)
    normal = doc.styles["normal"]
    normal.font.name, normal.font.size = FONT, Pt(11)
    normal.paragraph_format.line_spacing = 1.08
    normal.paragraph_format.space_after = Pt(6)
    for name, size in [("Heading 2", 14), ("Heading 3", 13)]:
        style = doc.styles[name]
        style.font.name, style.font.size, style.font.bold = FONT, Pt(size), True
        style.paragraph_format.space_before = Pt(8)
        style.paragraph_format.space_after = Pt(5)
        style.paragraph_format.line_spacing = 1.1
    props = doc.core_properties
    props.title, props.author = TITLE, "Afnan Khan"
    props.subject = "Model Epistemics & Decision-Making Evals"
    props.comments = "Built from the official Apart Research template, retrieved 2026-11-15."
    return doc


def main():
    source = (HERE / "report-source.md").read_text()
    abstract = (HERE / "abstract.txt").read_text().strip()
    assert 150 <= len(abstract.split()) <= 250
    tables = table_content()
    expanded = source
    for key, rows in tables.items():
        expanded = expanded.replace("{{" + key + "}}", markdown_table(rows))
    refs_md = "\n\n".join(ref_text(r) + r["primary_url"] for r in REFERENCES)
    expanded = expanded.replace("{{REFERENCES}}", refs_md)
    assert "{{" not in expanded
    (HERE / "report.md").write_text(expanded)
    ast = json.loads(
        subprocess.check_output(
            ["pandoc", "-f", "markdown-implicit_figures", "-t", "json"], input=source.encode()
        )
    )
    doc = prepare_template(abstract)
    pending_break = False
    for block in ast["blocks"]:
        kind, val = block["t"], block.get("c")
        if kind == "RawBlock" and "PAGE_BREAK" in val[1]:
            pending_break = True
        elif kind == "Header":
            level, _, nodes = val
            p = doc.add_paragraph(style="Heading 2" if level == 1 else "Heading 3")
            p.paragraph_format.page_break_before = pending_break
            pending_break = False
            inlines(p, nodes, size=14 if level == 1 else 13, bold=True)
        elif kind in {"Para", "Plain"}:
            text = inline_text(val)
            macro = re.fullmatch(r"\{\{(\w+)\}\}", text)
            if macro:
                if macro[1] == "REFERENCES":
                    for ref in REFERENCES:
                        p = doc.add_paragraph()
                        p.paragraph_format.space_after = Pt(9)
                        set_font(p.add_run(ref_text(ref)), 10)
                        hyperlink(p, ref["primary_url"], ref["primary_url"], 10)
                else:
                    add_table(doc, tables[macro[1]], macro[1])
            elif len(val) == 1 and val[0]["t"] == "Image":
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.keep_with_next = True
                p.add_run().add_picture(str(HERE / val[0]["c"][2][0]), width=Inches(6.5))
            else:
                p = doc.add_paragraph()
                caption = len(val) == 1 and val[0]["t"] == "Emph"
                if caption:
                    p.paragraph_format.line_spacing = 1
                    p.paragraph_format.space_after = Pt(6)
                inlines(p, val, size=9 if caption else 11)
        else:
            raise ValueError(f"Unsupported block: {kind}")
    doc.save(HERE / "report.docx")
    print(
        json.dumps(
            {
                "abstract_words": len(abstract.split()),
                "source": "report-source.md",
                "template": "template/official-template.docx",
                "outputs": ["report.md", "report.docx"],
                "inference_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
