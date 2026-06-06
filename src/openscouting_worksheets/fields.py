"""Custom ReportLab Flowables that render each field type.

Each Flowable both draws its own visuals (labels, table grids, callout boxes)
AND registers fillable AcroForm widgets on the canvas at the same position.
Coordinates are local to the Flowable's bounding box (relative=True), so
ReportLab's layout engine still owns page flow / pagination.
"""

from __future__ import annotations

import re

from reportlab.lib import colors
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Flowable, Paragraph


# Visual constants. Tweak here, not per-field.
LINE_HEIGHT = 18          # vertical units of one text-box line
TEXT_FIELD_HEIGHT = 16
CHECKBOX_SIZE = 10
LABEL_COL_WIDTH = 95      # for labeled_rows; left label column width
RULE_INSET = 0            # horizontal inset of rules from field edge
BORDER_COLOR = colors.HexColor("#9CA3AF")   # neutral gray
FILL_COLOR = colors.HexColor("#FAFAFA")     # very light gray (single-line fields)
RULE_COLOR = colors.HexColor("#CBD5E1")     # soft gray for writing rules
HEADER_COLOR = colors.HexColor("#1B4332")   # OpenScouting forest green
CALLOUT_FILL = colors.HexColor("#FFF8E1")
CALLOUT_BORDER = colors.HexColor("#F59E0B")


def _slug(s: str) -> str:
    """Slugify a label into a valid AcroForm field name fragment."""
    out = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    return out or "field"


def _text_widget(c: Canvas, name: str, x: float, y: float, w: float, h: float,
                 *, multiline: bool = False, lined: bool = False,
                 tooltip: str | None = None,
                 line_height: float = LINE_HEIGHT) -> None:
    """Place an AcroForm text field, optionally with ruled writing lines.

    When `lined=True` (multi-line text boxes), horizontal rules are drawn
    behind the field at `line_height` intervals. The form widget is given a
    transparent fill so rules remain visible whether the field is empty or
    filled in.
    """
    if lined:
        # Draw N-1 separator rules between the N writing slots; the box's
        # own top and bottom border serve as the outermost rules. So for
        # 5 lines we draw 4 rules at line_height intervals from the top,
        # leaving a full slot of headroom against each border.
        c.saveState()
        c.setStrokeColor(RULE_COLOR)
        c.setLineWidth(0.4)
        n_lines = max(int(round(h / line_height)), 1)
        for i in range(1, n_lines):
            ry = y + h - i * line_height
            c.line(x + RULE_INSET, ry, x + w - RULE_INSET, ry)
        c.restoreState()
        fill = colors.transparent
    else:
        fill = FILL_COLOR
    c.acroForm.textfield(
        name=name,
        tooltip=tooltip or name,
        x=x, y=y, width=w, height=h,
        borderWidth=0.5,
        borderColor=BORDER_COLOR,
        fillColor=fill,
        textColor=colors.black,
        forceBorder=True,
        fieldFlags="multiline" if multiline else "",
        relative=True,
    )


def _checkbox_widget(c: Canvas, name: str, x: float, y: float,
                     *, tooltip: str | None = None) -> None:
    c.acroForm.checkbox(
        name=name,
        tooltip=tooltip or name,
        x=x, y=y, size=CHECKBOX_SIZE,
        borderWidth=0.5,
        borderColor=BORDER_COLOR,
        fillColor=colors.white,
        forceBorder=True,
        relative=True,
    )


# ---------- text_field ----------

class TextFieldFlowable(Flowable):
    def __init__(self, name: str):
        super().__init__()
        self.name = name

    def wrap(self, avail_w, avail_h):
        self.width = avail_w
        self.height = TEXT_FIELD_HEIGHT
        return self.width, self.height

    def draw(self):
        _text_widget(self.canv, self.name, 0, 0, self.width, self.height)


# ---------- text_box ----------

class TextBoxFlowable(Flowable):
    def __init__(self, name: str, lines: int = 5):
        super().__init__()
        self.name = name
        self.lines = lines

    def wrap(self, avail_w, avail_h):
        self.width = avail_w
        self.height = LINE_HEIGHT * self.lines
        return self.width, self.height

    def split(self, avail_w, avail_h):
        """Allow the text box to split across pages.

        If the whole box doesn't fit, draw as many lines as possible on the
        current page and continue with the remaining lines on the next. Both
        pieces share the same AcroForm name, so postprocess.merge_duplicate_fields
        will collapse them into a single logical field with two widgets that
        sync values across pages.
        """
        if avail_h >= self.lines * LINE_HEIGHT:
            return [self]
        max_lines = int(avail_h / LINE_HEIGHT)
        # Need at least two writing lines on the current page to justify a
        # split — one orphan line at the bottom looks awkward.
        if max_lines < 2:
            return []
        first = TextBoxFlowable(self.name, lines=max_lines)
        rest = TextBoxFlowable(self.name, lines=self.lines - max_lines)
        return [first, rest]

    def draw(self):
        _text_widget(self.canv, self.name, 0, 0, self.width, self.height,
                     multiline=True, lined=True)


# ---------- checkbox ----------

class CheckboxFlowable(Flowable):
    def __init__(self, name: str, label: str = ""):
        super().__init__()
        self.name = name
        self.label = label
        self._label_lines: list[str] = []

    def wrap(self, avail_w, avail_h):
        self.width = avail_w
        text_x = CHECKBOX_SIZE + 6
        text_w = max(self.width - text_x, 50)
        self._label_lines = _wrap_text(
            self.label, text_w, self.canv if hasattr(self, "canv") else None,
            font="Helvetica", size=10,
        )
        line_count = max(len(self._label_lines), 1)
        self.height = max(CHECKBOX_SIZE, line_count * 12) + 4
        return self.width, self.height

    def draw(self):
        c = self.canv
        # Checkbox aligns to the top line of the label
        y_top = self.height
        _checkbox_widget(c, self.name, 0, y_top - CHECKBOX_SIZE - 2,
                         tooltip=self.label or self.name)
        if self.label:
            c.setFont("Helvetica", 10)
            c.setFillColor(colors.black)
            text_x = CHECKBOX_SIZE + 6
            for i, line in enumerate(self._label_lines):
                c.drawString(text_x, y_top - 12 - i * 12, line)


# ---------- checklist ----------

class ChecklistFlowable(Flowable):
    def __init__(self, name_prefix: str, items: list[str]):
        super().__init__()
        self.name_prefix = name_prefix
        self.items = items
        self._wrapped: list[list[str]] = []

    def wrap(self, avail_w, avail_h):
        self.width = avail_w
        text_x = CHECKBOX_SIZE + 6
        text_w = max(self.width - text_x, 50)
        self._wrapped = [
            _wrap_text(item, text_w, None, font="Helvetica", size=10)
            for item in self.items
        ]
        self.height = sum(max(len(w), 1) * 12 + 4 for w in self._wrapped)
        return self.width, self.height

    def draw(self):
        c = self.canv
        y = self.height
        text_x = CHECKBOX_SIZE + 6
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.black)
        for item, lines in zip(self.items, self._wrapped):
            row_h = max(len(lines), 1) * 12 + 4
            _checkbox_widget(c, f"{self.name_prefix}_{_slug(item)[:30]}",
                             0, y - CHECKBOX_SIZE - 2, tooltip=item)
            for i, line in enumerate(lines):
                c.drawString(text_x, y - 12 - i * 12, line)
            y -= row_h


# ---------- labeled_field (single row, used inside repeated_block) ----------

class LabeledFieldFlowable(Flowable):
    """A single row: label on the left, fillable field on the right.

    Used inside `repeated_block` sub-templates so each numbered instance
    renders as a tidy form (Type / Features / When / Where) instead of
    a stack of label-then-field pairs.

    The label is right-aligned in its column so its colon sits flush against
    the field's left edge, regardless of label length.
    """

    LABEL_FIELD_GAP = 6   # pts between label colon and field's left border

    def __init__(self, name: str, label: str, lines: int = 1,
                 label_col_width: float = LABEL_COL_WIDTH,
                 left_indent: float = 0):
        super().__init__()
        self.name = name
        self.label = label
        self.lines = lines
        self.label_col_width = label_col_width
        self.left_indent = left_indent
        self._label_lines: list[str] = []

    def wrap(self, avail_w, avail_h):
        self.width = avail_w
        self._label_lines = _wrap_text(
            self.label, self.label_col_width, None,
            font="Helvetica", size=10,
        )
        label_h = max(len(self._label_lines), 1) * 12
        field_h = self.lines * LINE_HEIGHT
        self.height = max(label_h, field_h)
        return self.width, self.height

    def draw(self):
        c = self.canv
        label_right = self.left_indent + self.label_col_width
        text_x = label_right + self.LABEL_FIELD_GAP
        text_w = self.width - text_x
        field_h = self.lines * LINE_HEIGHT
        field_y = self.height - field_h
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.black)
        for i, line in enumerate(self._label_lines):
            # First label line baseline sits inside the first writing slot.
            line_y = self.height - 12 - i * 12
            suffix = ":" if i == len(self._label_lines) - 1 else ""
            text = line + suffix
            tw = c.stringWidth(text, "Helvetica", 10)
            c.drawString(label_right - tw, line_y, text)
        multi = self.lines > 1
        _text_widget(c, self.name, text_x, field_y, text_w, field_h,
                     multiline=multi, lined=multi, tooltip=self.label)


# ---------- labeled_rows ----------

class LabeledRowsFlowable(Flowable):
    def __init__(self, name_prefix: str, labels: list[str], lines_each: int = 2):
        super().__init__()
        self.name_prefix = name_prefix
        self.labels = labels
        self.lines_each = lines_each

    def wrap(self, avail_w, avail_h):
        self.width = avail_w
        row_h = self.lines_each * LINE_HEIGHT + 6
        self.height = len(self.labels) * row_h
        return self.width, self.height

    def draw(self):
        c = self.canv
        row_h = self.lines_each * LINE_HEIGHT + 6
        text_x = LABEL_COL_WIDTH
        text_w = self.width - LABEL_COL_WIDTH
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.black)
        for i, label in enumerate(self.labels):
            y_top = self.height - i * row_h
            field_h = row_h - 6
            field_y = y_top - row_h + 3
            c.drawString(0, y_top - 12, f"{label}:")
            multi = self.lines_each > 1
            _text_widget(c, f"{self.name_prefix}_{_slug(label)}",
                         text_x, field_y, text_w, field_h,
                         multiline=multi, lined=multi, tooltip=label)


# ---------- table ----------

class TableFlowable(Flowable):
    def __init__(self, name_prefix: str, rows: int, cols: int,
                 headers: list[str] | None = None):
        super().__init__()
        self.name_prefix = name_prefix
        self.rows = rows
        self.cols = cols
        self.headers = headers

    def wrap(self, avail_w, avail_h):
        self.width = avail_w
        header_h = 14 if self.headers else 0
        self.height = header_h + self.rows * LINE_HEIGHT
        return self.width, self.height

    def draw(self):
        c = self.canv
        col_w = self.width / self.cols
        y_top = self.height
        if self.headers:
            c.setFont("Helvetica-Bold", 9)
            c.setFillColor(colors.black)
            for j, h in enumerate(self.headers):
                c.drawString(j * col_w + 3, y_top - 11, h)
            y_top -= 14
        for i in range(self.rows):
            for j in range(self.cols):
                x = j * col_w
                y = y_top - (i + 1) * LINE_HEIGHT
                _text_widget(c, f"{self.name_prefix}_r{i}_c{j}",
                             x, y, col_w, LINE_HEIGHT,
                             tooltip=f"row {i + 1} col {j + 1}")


# ---------- pair_grid ----------

class PairGridFlowable(Flowable):
    def __init__(self, name_prefix: str, left_title: str, right_title: str,
                 col_headers: list[str], rows: int = 5):
        super().__init__()
        self.name_prefix = name_prefix
        self.left_title = left_title
        self.right_title = right_title
        self.col_headers = col_headers
        self.rows = rows

    def wrap(self, avail_w, avail_h):
        self.width = avail_w
        # title row + header row + N data rows
        self.height = 16 + 14 + self.rows * LINE_HEIGHT
        return self.width, self.height

    def draw(self):
        c = self.canv
        gap = 14
        group_w = (self.width - gap) / 2
        sub_cols = len(self.col_headers)
        cell_w = group_w / sub_cols
        for g_idx, (title, side) in enumerate(
            [(self.left_title, "L"), (self.right_title, "R")]
        ):
            gx = g_idx * (group_w + gap)
            # Group title
            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(HEADER_COLOR)
            c.drawString(gx, self.height - 12, title)
            # Sub-column headers
            c.setFont("Helvetica-Bold", 9)
            c.setFillColor(colors.black)
            for j, h in enumerate(self.col_headers):
                c.drawString(gx + j * cell_w + 3, self.height - 16 - 11, h)
            # Data cells
            for i in range(self.rows):
                for j in range(sub_cols):
                    x = gx + j * cell_w
                    y = self.height - 16 - 14 - (i + 1) * LINE_HEIGHT
                    _text_widget(c, f"{self.name_prefix}_{side}_r{i}_c{j}",
                                 x, y, cell_w, LINE_HEIGHT)


# ---------- callout ----------

class CalloutFlowable(Flowable):
    """Boxed informational text (no form field)."""

    def __init__(self, text: str, style):
        super().__init__()
        self.text = text
        self.style = style
        self._para: Paragraph | None = None
        self._pad = 10

    def wrap(self, avail_w, avail_h):
        self._para = Paragraph(self.text, self.style)
        inner_w = avail_w - 2 * self._pad
        _, ph = self._para.wrap(inner_w, avail_h)
        self.width = avail_w
        self.height = ph + 2 * self._pad
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.saveState()
        c.setFillColor(CALLOUT_FILL)
        c.setStrokeColor(CALLOUT_BORDER)
        c.setLineWidth(1)
        c.roundRect(0, 0, self.width, self.height, 4, stroke=1, fill=1)
        c.restoreState()
        self._para.drawOn(c, self._pad, self._pad)


# ---------- internal: a tiny word wrapper for raw-canvas labels ----------

def _wrap_text(text: str, max_w: float, canvas_obj, font: str, size: int) -> list[str]:
    """Greedy word wrap using stringWidth — for labels drawn directly on canvas."""
    if not text:
        return []
    from reportlab.pdfbase.pdfmetrics import stringWidth
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        candidate = " ".join(cur + [w])
        if stringWidth(candidate, font, size) <= max_w or not cur:
            cur.append(w)
        else:
            lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines
