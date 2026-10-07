"""
document_utils.py – python-docx helper utilities for BRD formatting.
"""
from __future__ import annotations

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


def add_heading(doc: Document, text: str, level: int = 1) -> None:
    """Add a heading with consistent styling."""
    doc.add_heading(text, level=level)


def add_paragraph(doc: Document, text: str, bold: bool = False) -> None:
    """Add a styled paragraph."""
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = bold


def add_bullet_list(doc: Document, items: list[str], label: str = "") -> None:
    """Add a labelled bullet list. Skips if list is empty."""
    if not items:
        doc.add_paragraph("Not specified", style="Normal")
        return
    for item in items:
        if item and str(item).strip():
            doc.add_paragraph(str(item).strip(), style="List Bullet")


def add_table_section(
    doc: Document,
    headers: list[str],
    rows: list[list[str]],
) -> None:
    """Add a formatted table with headers."""
    if not rows:
        doc.add_paragraph("Not specified")
        return

    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"

    # Header row
    hdr_cells = table.rows[0].cells
    for i, header in enumerate(headers):
        hdr_cells[i].text = header
        run = hdr_cells[i].paragraphs[0].runs[0]
        run.bold = True

    # Data rows
    for row_data in rows:
        row_cells = table.add_row().cells
        for i, cell_text in enumerate(row_data):
            row_cells[i].text = str(cell_text or "")


def add_page_break(doc: Document) -> None:
    """Insert a page break."""
    doc.add_page_break()


def set_footer(doc: Document, text: str) -> None:
    """Set footer text on all sections."""
    for section in doc.sections:
        footer = section.footer
        footer.paragraphs[0].text = text
        footer.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
