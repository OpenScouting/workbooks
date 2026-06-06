"""OpenScouting visual identity: page chrome, cover, fonts, colors.

Volunteers never touch this file. One redesign here = every badge restyled.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    PageTemplate,
)

from .schema import Badge


# Conventions for brand assets. Drop files at these paths and they render
# automatically. Until then the chrome falls back to text placeholders.
LOGO_FILENAME = "openscouting-logo.png"
BADGE_DIR = "badges"

# Public home for the workbook catalogue (shown + linked on the cover).
SITE_URL = "https://openscouting.github.io/workbooks/"
SITE_LABEL = "openscouting.github.io/workbooks"


PAGE_W, PAGE_H = letter
MARGIN_L = 0.7 * inch
MARGIN_R = 0.7 * inch
MARGIN_T = 1.0 * inch         # body pages: room for 2-row header
COVER_MARGIN_T = 0.75 * inch  # cover: single-row chrome, can sit tighter
MARGIN_B = 0.7 * inch

# OpenScouting brand palette. Used sparingly as text/rule color — no large
# filled bands, so printed pages use minimal toner.
BRAND_PRIMARY = colors.HexColor("#1B4332")   # deep forest green
BRAND_ACCENT = colors.HexColor("#F59E0B")    # warm amber
BRAND_MUTED = colors.HexColor("#6B7280")     # neutral gray
BRAND_RULE = colors.HexColor("#1F2937")      # near-black hairline for chrome


def make_styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("BadgeEyebrow", parent=s["BodyText"],
                         fontName="Helvetica-Bold", fontSize=8,
                         textColor=BRAND_MUTED, alignment=0,
                         spaceBefore=8, spaceAfter=4, leading=10))
    s.add(ParagraphStyle("BadgeTitle", parent=s["Heading1"],
                         fontName="Helvetica-Bold", fontSize=34,
                         textColor=BRAND_PRIMARY, alignment=0,
                         spaceAfter=0, leading=38))
    s.add(ParagraphStyle("BadgeSubtitle", parent=s["Heading2"],
                         fontName="Helvetica", fontSize=13,
                         textColor=BRAND_MUTED, alignment=0,
                         spaceAfter=8, leading=16))
    s.add(ParagraphStyle("BadgeDescription", parent=s["BodyText"],
                         fontSize=10, leading=14, alignment=0,
                         textColor=colors.black,
                         spaceBefore=4, spaceAfter=0))
    s.add(ParagraphStyle("Disclaimer", parent=s["BodyText"],
                         fontSize=9, leading=12, alignment=0,
                         textColor=BRAND_MUTED, spaceAfter=4))
    s.add(ParagraphStyle("CoverInfoLabel", parent=s["BodyText"],
                         fontSize=10, leading=14,
                         textColor=BRAND_MUTED))
    s.add(ParagraphStyle("CoverMeta", parent=s["BodyText"],
                         fontSize=8, leading=11, alignment=1,
                         textColor=BRAND_MUTED, spaceBefore=8))

    # Requirement styles, by depth
    s.add(ParagraphStyle("Req0Intro", parent=s["BodyText"],
                         fontSize=12, leading=15, fontName="Helvetica-Bold",
                         textColor=BRAND_PRIMARY,
                         spaceBefore=14, spaceAfter=6, keepWithNext=1))
    s.add(ParagraphStyle("Req0Prompt", parent=s["BodyText"],
                         fontSize=11, leading=14, fontName="Helvetica-Bold",
                         spaceBefore=14, spaceAfter=4, keepWithNext=1))
    s.add(ParagraphStyle("Req1Prompt", parent=s["BodyText"],
                         fontSize=10, leading=13,
                         leftIndent=18, spaceBefore=8, spaceAfter=4,
                         keepWithNext=1))
    s.add(ParagraphStyle("Req2Prompt", parent=s["BodyText"],
                         fontSize=10, leading=13,
                         leftIndent=36, spaceBefore=6, spaceAfter=4,
                         keepWithNext=1))
    s.add(ParagraphStyle("ReqNote", parent=s["BodyText"],
                         fontSize=9, leading=11,
                         leftIndent=18, textColor=BRAND_MUTED, spaceAfter=4,
                         keepWithNext=1))
    s.add(ParagraphStyle("FieldLabel", parent=s["BodyText"],
                         fontSize=9, leading=11,
                         leftIndent=18, spaceAfter=2,
                         textColor=BRAND_MUTED, keepWithNext=1))
    s.add(ParagraphStyle("RepeatedIndex", parent=s["BodyText"],
                         fontSize=10, leading=13, fontName="Helvetica-Bold",
                         leftIndent=18, spaceBefore=6, spaceAfter=2,
                         textColor=BRAND_PRIMARY, keepWithNext=1))
    s.add(ParagraphStyle("CalloutText", parent=s["BodyText"],
                         fontSize=9.5, leading=13))

    # Reference-page styles
    s.add(ParagraphStyle("RefTitle", parent=s["Heading1"],
                         fontName="Helvetica-Bold", fontSize=18,
                         textColor=BRAND_PRIMARY, spaceBefore=4, spaceAfter=10))
    s.add(ParagraphStyle("RefHeading", parent=s["Heading2"],
                         fontName="Helvetica-Bold", fontSize=12,
                         textColor=BRAND_PRIMARY, spaceBefore=10, spaceAfter=6))
    s.add(ParagraphStyle("RefBody", parent=s["BodyText"],
                         fontSize=10, leading=13, spaceAfter=6))
    s.add(ParagraphStyle("RefBullet", parent=s["BodyText"],
                         fontSize=10, leading=13,
                         leftIndent=14, bulletIndent=2, spaceAfter=2))
    return s


class WorkbookDoc(BaseDocTemplate):
    """The document template owning chrome for cover + body pages."""

    def __init__(self, filename: str, badge: Badge,
                 asset_dir: Path | None = None, **kw):
        super().__init__(
            filename,
            pagesize=letter,
            leftMargin=MARGIN_L,
            rightMargin=MARGIN_R,
            topMargin=MARGIN_T,
            bottomMargin=MARGIN_B,
            title=f"{badge.badge.name} Merit Badge Workbook",
            author="OpenScouting",
            subject=f"{badge.badge.name} merit badge workbook",
            **kw,
        )
        self.badge = badge
        self.asset_dir = asset_dir
        logo = (asset_dir / LOGO_FILENAME) if asset_dir else None
        self.logo_path = logo if logo and logo.exists() else None

        body_frame = Frame(
            MARGIN_L, MARGIN_B,
            PAGE_W - MARGIN_L - MARGIN_R,
            PAGE_H - MARGIN_T - MARGIN_B,
            id="body", showBoundary=0,
        )
        cover_frame = Frame(
            MARGIN_L, MARGIN_B,
            PAGE_W - MARGIN_L - MARGIN_R,
            PAGE_H - COVER_MARGIN_T - MARGIN_B,
            id="cover", showBoundary=0,
        )
        self.addPageTemplates([
            PageTemplate(id="cover", frames=[cover_frame],
                         onPage=self._draw_cover_chrome),
            PageTemplate(id="body", frames=[body_frame],
                         onPage=self._draw_body_chrome),
        ])

    # ----- chrome -----
    #
    # Both page templates use the same minimal-ink approach: dark text on a
    # white background, a single hairline rule, no filled color bands. Color
    # is reserved for the brand accent (a short amber tab on the rule) which
    # uses negligible toner when printed.

    def _draw_cover_chrome(self, canvas: Canvas, doc) -> None:
        canvas.saveState()
        # OpenScouting logo (or text wordmark fallback) on the left, the public
        # catalogue URL (clickable) on the right.
        self._draw_brand_mark(canvas,
                              x=MARGIN_L, y=PAGE_H - 0.52 * inch,
                              height=20, wordmark_size=14)
        url_y = PAGE_H - 0.45 * inch
        canvas.setFillColor(BRAND_PRIMARY)
        canvas.setFont("Helvetica-Bold", 10)
        url_w = canvas.stringWidth(SITE_LABEL, "Helvetica-Bold", 10)
        url_x = PAGE_W - MARGIN_R - url_w
        canvas.drawString(url_x, url_y, SITE_LABEL)
        canvas.linkURL(SITE_URL, (url_x, url_y - 2, url_x + url_w, url_y + 10),
                       relative=0, thickness=0)
        self._draw_chrome_rule(canvas, PAGE_H - 0.62 * inch)
        self._draw_footer(canvas, doc, footer_text=(
            "© OpenScouting · CC BY-SA 4.0 · "
            "Requirements © Scouting America, used with permission."
        ))
        canvas.restoreState()

    def _draw_body_chrome(self, canvas: Canvas, doc) -> None:
        canvas.saveState()
        # Minimal header: just Scout's Name + Troop fields. OpenScouting
        # branding and badge identity live in the footer instead, so the
        # top of every body page is dedicated to identifying *whose* work
        # it is rather than what publication this is.
        field_y = PAGE_H - 0.50 * inch
        self._draw_header_field(
            canvas, label="Scout's Name:", name="scout_name",
            x_start=MARGIN_L, y=field_y, field_w=260,
        )
        # Right-anchor the Troop block so the field's right edge lines up
        # with the chrome divider rule below.
        troop_field_w = 55
        troop_label_w = canvas.stringWidth("Troop:", "Helvetica", 9)
        troop_x_start = (PAGE_W - MARGIN_R) - troop_label_w - 4 - troop_field_w
        self._draw_header_field(
            canvas, label="Troop:", name="troop_number",
            x_start=troop_x_start, y=field_y, field_w=troop_field_w,
        )
        self._draw_chrome_rule(canvas, PAGE_H - 0.72 * inch)
        self._draw_footer(
            canvas, doc,
            footer_text=f"OpenScouting · {self.badge.badge.name} Merit Badge Workbook",
        )
        canvas.restoreState()

    # ----- chrome helpers -----

    def _draw_brand_mark(self, canvas: Canvas, *, x: float, y: float,
                         height: float, wordmark_size: float) -> float:
        """Render the OpenScouting logo if available, else the text wordmark.

        Returns the width consumed so callers can lay out beside it.
        """
        if self.logo_path:
            img = ImageReader(str(self.logo_path))
            iw, ih = img.getSize()
            width = height * (iw / ih)
            canvas.drawImage(img, x, y, width=width, height=height,
                             mask="auto", preserveAspectRatio=True)
            return width
        canvas.setFillColor(BRAND_PRIMARY)
        canvas.setFont("Helvetica-Bold", wordmark_size)
        text = "OpenScouting"
        canvas.drawString(x, y + height * 0.2, text)
        return canvas.stringWidth(text, "Helvetica-Bold", wordmark_size)

    def _draw_chrome_rule(self, canvas: Canvas, y: float) -> None:
        """Single hairline divider + short amber accent tab."""
        canvas.setStrokeColor(BRAND_RULE)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN_L, y, PAGE_W - MARGIN_R, y)
        canvas.setStrokeColor(BRAND_ACCENT)
        canvas.setLineWidth(1.6)
        canvas.line(MARGIN_L, y, MARGIN_L + 28, y)

    def _draw_footer(self, canvas: Canvas, doc, *, footer_text: str) -> None:
        rule_y = 0.55 * inch
        canvas.setStrokeColor(BRAND_MUTED)
        canvas.setLineWidth(0.3)
        canvas.line(MARGIN_L, rule_y, PAGE_W - MARGIN_R, rule_y)
        canvas.setFillColor(BRAND_MUTED)
        canvas.setFont("Helvetica", 8)
        if footer_text:
            canvas.drawString(MARGIN_L, 0.35 * inch, footer_text)
        canvas.drawRightString(PAGE_W - MARGIN_R, 0.35 * inch,
                               f"Page {doc.page}")

    def _draw_header_field(self, canvas: Canvas, *, label: str, name: str,
                           x_start: float, y: float, field_w: float) -> float:
        """Inline labeled fillable field for the body-page header.

        Draws a borderless AcroForm widget with an underline beneath. The
        chrome divider sits well below these underlines so the two no
        longer visually merge. Shared field name syncs across pages.

        Returns the x coordinate of the field's right edge.
        """
        canvas.setFillColor(colors.black)
        canvas.setFont("Helvetica", 9)
        canvas.drawString(x_start, y + 3, label)
        label_w = canvas.stringWidth(label, "Helvetica", 9)
        field_x = x_start + label_w + 4
        field_h = 13
        canvas.acroForm.textfield(
            name=name, tooltip=label.rstrip(":"),
            x=field_x, y=y, width=field_w, height=field_h,
            borderWidth=0,
            fillColor=colors.transparent,
            textColor=colors.black,
            forceBorder=False,
            relative=False,
            maxlen=80,
        )
        canvas.setStrokeColor(BRAND_RULE)
        canvas.setLineWidth(0.6)
        canvas.line(field_x, y - 1, field_x + field_w, y - 1)
        return field_x + field_w


# ---------- Cover info card --------------------------------------------------
#
# Polished bordered card with sectioned Scout/Counselor info. Lives in the
# template module so every badge's cover gets the same look — volunteers
# don't author it, they just inherit it.

class CoverInfoCard(Flowable):
    """A bordered info card with Scout-info and Counselor-info sections."""

    # Row tuples are (label, field_name) or (label, field_name, weight).
    # Weights are relative within a row; default 1 each (equal columns).
    SECTIONS = (
        ("SCOUT INFORMATION", (
            (("Name", "scout_name", 6),
             ("Troop", "troop_number", 2),
             ("Date", "date_started", 3)),
        )),
        ("MERIT BADGE COUNSELOR", (
            (("Name", "counselor_name"),),
            (("Phone", "counselor_phone", 1), ("Email", "counselor_email", 2)),
        )),
    )

    PAD_X = 18
    PAD_TOP = 11
    PAD_BOTTOM = 11
    SECTION_HEAD_H = 18
    SECTION_GAP = 4
    ROW_H = 19
    LABEL_GAP = 6
    COL_GAP = 18
    FIELD_H = 13

    def wrap(self, avail_w, avail_h):
        self.width = avail_w
        total_rows = sum(len(rows) for _, rows in self.SECTIONS)
        total_heads = len(self.SECTIONS) * self.SECTION_HEAD_H
        total_gaps = (len(self.SECTIONS) - 1) * self.SECTION_GAP
        body_h = total_rows * self.ROW_H + total_heads + total_gaps
        self.height = body_h + self.PAD_TOP + self.PAD_BOTTOM
        return self.width, self.height

    def draw(self):
        c = self.canv
        # Card outline
        c.saveState()
        c.setStrokeColor(BRAND_RULE)
        c.setLineWidth(0.6)
        c.roundRect(0, 0, self.width, self.height, 5, stroke=1, fill=0)
        c.restoreState()

        inner_x = self.PAD_X
        inner_w = self.width - 2 * self.PAD_X
        y = self.height - self.PAD_TOP

        for i, (heading, rows) in enumerate(self.SECTIONS):
            if i > 0:
                y -= self.SECTION_GAP
            self._draw_section_heading(c, heading, inner_x, y, inner_w)
            y -= self.SECTION_HEAD_H
            for row in rows:
                self._draw_row(c, row, inner_x, y, inner_w)
                y -= self.ROW_H

    def _draw_section_heading(self, c, text, x, y, width):
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(BRAND_PRIMARY)
        c.drawString(x, y - 11, text)
        # Subtle full-width divider with a short amber accent
        c.setStrokeColor(BRAND_RULE)
        c.setLineWidth(0.3)
        c.line(x, y - 16, x + width, y - 16)
        c.setStrokeColor(BRAND_ACCENT)
        c.setLineWidth(1.4)
        accent_w = c.stringWidth(text, "Helvetica-Bold", 10)
        c.line(x, y - 16, x + accent_w, y - 16)

    def _draw_row(self, c, row, x, y, width):
        n_cols = len(row)
        available = width - self.COL_GAP * (n_cols - 1)
        weights = [(item[2] if len(item) >= 3 else 1) for item in row]
        total = sum(weights)
        col_widths = [available * (w / total) for w in weights]
        baseline = y - 13
        cx = x
        for j, item in enumerate(row):
            label, name = item[0], item[1]
            self._draw_field(c, label, name, cx, baseline, col_widths[j])
            cx += col_widths[j] + self.COL_GAP

    def _draw_field(self, c, label, name, x, baseline, width):
        # Left-aligned label so narrow columns aren't dominated by a fixed
        # label gutter (Troop only needs ~30pt of label width).
        c.setFont("Helvetica", 9)
        c.setFillColor(BRAND_MUTED)
        label_w = c.stringWidth(label, "Helvetica", 9)
        c.drawString(x, baseline, label)
        field_x = x + label_w + self.LABEL_GAP
        field_w = max(width - label_w - self.LABEL_GAP, 10)
        field_y = baseline - 3
        c.acroForm.textfield(
            name=name, tooltip=label,
            x=field_x, y=field_y, width=field_w, height=self.FIELD_H,
            borderWidth=0,
            fillColor=colors.transparent,
            textColor=colors.black,
            forceBorder=False,
            relative=True,
            maxlen=120,
        )
        c.setStrokeColor(BRAND_MUTED)
        c.setLineWidth(0.5)
        c.line(field_x, field_y - 1, field_x + field_w, field_y - 1)


# ---------- Reusable visual primitives ---------------------------------------

class AccentRule(Flowable):
    """Hairline divider with a short amber accent tab — same vocabulary as
    the section heads in the info card. Use it anywhere on the cover to
    add subtle structure without filling areas with color.
    """

    def __init__(self, accent_w: float = 40, height: float = 8):
        super().__init__()
        self.accent_w = accent_w
        self.height = height

    def wrap(self, avail_w, avail_h):
        self.width = avail_w
        return self.width, self.height

    def draw(self):
        c = self.canv
        y = self.height / 2
        c.setStrokeColor(BRAND_RULE)
        c.setLineWidth(0.3)
        c.line(0, y, self.width, y)
        c.setStrokeColor(BRAND_ACCENT)
        c.setLineWidth(1.5)
        c.line(0, y, min(self.accent_w, self.width), y)


# ---------- Badge artwork (cover) -------------------------------------------

class BadgeArtwork(Flowable):
    """Render the badge artwork on the cover, or a dashed placeholder.

    Pass `image_path=None` to force the placeholder regardless of file
    existence (useful for testing). Otherwise pass the resolved path; the
    flowable will use the image if it exists on disk, or a dashed circular
    placeholder labeled with the expected filename so a contributor knows
    what to drop in.
    """

    def __init__(self, image_path: Path | None, badge_name: str,
                 expected_filename: str = "<slug>.png",
                 size: float = 1.4 * inch, align: str = "left"):
        super().__init__()
        self.image_path = (image_path if image_path
                           and Path(image_path).exists() else None)
        self.badge_name = badge_name
        self.expected_filename = expected_filename
        self.size = size
        self.align = align  # "left" or "center"

    def wrap(self, avail_w, avail_h):
        self.width = avail_w
        self.height = self.size
        return self.width, self.height

    def draw(self):
        c = self.canv
        if self.align == "center":
            x = (self.width - self.size) / 2
        elif self.align == "right":
            x = self.width - self.size
        else:
            x = 0
        cx = x + self.size / 2
        if self.image_path:
            img = ImageReader(str(self.image_path))
            c.drawImage(img, x, 0, width=self.size, height=self.size,
                        mask="auto", preserveAspectRatio=True)
        else:
            radius = self.size / 2
            c.saveState()
            c.setStrokeColor(BRAND_PRIMARY)
            c.setLineWidth(1.5)
            c.setDash(4, 3)
            c.circle(cx, radius, radius - 2, stroke=1, fill=0)
            c.setDash()
            c.setFillColor(BRAND_PRIMARY)
            c.setFont("Helvetica-Bold", 9)
            c.drawCentredString(cx, radius + 4, "BADGE ARTWORK")
            c.setFillColor(BRAND_MUTED)
            c.setFont("Helvetica", 8)
            c.drawCentredString(cx, radius - 8,
                                f"drop {self.expected_filename}")
            c.restoreState()
