"""Render reference pages (Wilderness Use Policy, Outdoor Code, etc.).

Supports a single-body page or a two-column layout. Body content can be inline
text or a path to a markdown file in `shared/` for cross-badge reuse.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from .schema import ReferencePage
from .template import MARGIN_L, MARGIN_R, PAGE_W


def _resolve_body(body: str, base_dir: Path) -> str:
    """Inline text, or read from disk if it looks like a relative path."""
    if "\n" not in body and body.strip().endswith(".md") and len(body) < 200:
        candidate = base_dir / body.strip()
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    return body


def _render_markdown_ish(text: str, styles) -> list[Flowable]:
    """Tiny subset of Markdown: paragraphs, '-' bullets, **bold**, *italic*.

    Enough for the standard Scouting America boilerplate (LNT, Outdoor Code).
    """
    out: list[Flowable] = []
    for block in _split_blocks(text):
        block = block.strip()
        if not block:
            continue
        lines = [ln.rstrip() for ln in block.splitlines()]
        if all(ln.lstrip().startswith(("- ", "* ", "• ")) for ln in lines):
            for ln in lines:
                bullet = ln.lstrip()[2:].strip()
                out.append(Paragraph(
                    _inline_format(bullet), styles["RefBullet"],
                    bulletText="•",
                ))
        else:
            paragraph = " ".join(ln.strip() for ln in lines)
            out.append(Paragraph(_inline_format(paragraph), styles["RefBody"]))
    return out


def _split_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    cur: list[str] = []
    for line in text.splitlines():
        if line.strip() == "":
            if cur:
                blocks.append("\n".join(cur))
                cur = []
        else:
            cur.append(line)
    if cur:
        blocks.append("\n".join(cur))
    return blocks


def _inline_format(text: str) -> str:
    """Translate **bold** and *italic* into ReportLab Paragraph markup."""
    import re
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    return text


def build_reference_pages(
    pages: list[ReferencePage], styles, base_dir: Path,
) -> list[Flowable]:
    out: list[Flowable] = []
    for i, page in enumerate(pages):
        if i > 0:
            out.append(PageBreak())
        if page.title:
            out.append(Paragraph(page.title, styles["RefTitle"]))

        if page.body:
            body_text = _resolve_body(page.body, base_dir)
            out.extend(_render_markdown_ish(body_text, styles))

        if page.columns:
            usable_w = PAGE_W - MARGIN_L - MARGIN_R
            gap = 16
            col_w = (usable_w - gap) / len(page.columns)
            cells = []
            for col in page.columns:
                cell: list[Flowable] = []
                if col.title:
                    cell.append(Paragraph(col.title, styles["RefHeading"]))
                cell.extend(_render_markdown_ish(
                    _resolve_body(col.body, base_dir), styles
                ))
                cells.append(cell)
            t = Table(
                [cells],
                colWidths=[col_w] * len(page.columns),
                hAlign="LEFT",
            )
            t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), gap),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            out.append(Spacer(1, 6))
            out.append(t)
    return out
