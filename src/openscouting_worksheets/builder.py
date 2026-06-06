"""Orchestrate: load YAML → validate → assemble Flowables → render PDF."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml
from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from . import fields as F
from . import schema as S
from .postprocess import merge_duplicate_fields
from .reference_pages import build_reference_pages
from .template import (
    AccentRule,
    BadgeArtwork,
    CoverInfoCard,
    WorkbookDoc,
    make_styles,
)


def load_badge(path: Path) -> S.Badge:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return S.Badge.model_validate(data)


def _find_repo_root(start: Path) -> Path:
    """Walk up from a worksheet YAML path to the repo root.

    The root holds the sibling source trees: badges/ (merit badge source +
    emblems), shared/ (reusable text), assets/ (OpenScouting branding).
    """
    for parent in [start, *start.parents]:
        if (parent / "badges").is_dir() or (parent / "shared").is_dir():
            return parent
    return start.parent.parent


def build(badge_path: Path, output_path: Path,
          base_dir: Path | None = None) -> None:
    """Build one badge YAML into a PDF at output_path."""
    badge = load_badge(badge_path)
    base_dir = base_dir or _find_repo_root(badge_path)
    asset_dir = base_dir / "assets"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = WorkbookDoc(str(output_path), badge=badge, asset_dir=asset_dir)
    styles = make_styles()

    story: list[Flowable] = []
    built = badge.badge.workbook_version or _git_last_modified(badge_path) \
        or _today_iso()
    story.extend(_build_cover(badge, styles, asset_dir=asset_dir,
                              base_dir=base_dir, built=built))
    # Switch to body chrome for any page that overflows past the cover, but
    # don't force a page break — let requirements flow onto the cover page
    # when there's room. The natural spaceBefore on Req0Intro gives the
    # visual separation between cover content and the first requirement.
    story.append(NextPageTemplate("body"))

    for req in badge.requirements:
        story.extend(_render_requirement(req, styles, depth=0, parent_id=""))

    if badge.reference_pages:
        story.append(PageBreak())
        story.extend(build_reference_pages(badge.reference_pages, styles, base_dir))

    doc.build(story)
    merge_duplicate_fields(output_path)


# ---------- cover ----------

def _build_cover(badge: S.Badge, styles, asset_dir: Path,
                 base_dir: Path, built: str) -> list[Flowable]:
    s = styles
    out: list[Flowable] = []

    # Resolve badge artwork. Search order:
    #   1. Explicit `cover_image` path in the YAML
    #   2. badges/<slug>/<slug>.png  (emblem co-located with the requirement source)
    slug = badge.badge.slug
    candidates = []
    if badge.badge.cover_image:
        candidates.append(base_dir / badge.badge.cover_image)
    candidates.append(base_dir / "badges" / slug / f"{slug}.png")
    cover_image = next((p for p in candidates if p.exists()), candidates[-1])
    expected = f"badges/{slug}/{slug}.png"

    # Inline header: title on the left, small badge artwork on the right.
    # Revision / accent rule / description flow full-width below.
    art_size = 56
    art = BadgeArtwork(cover_image, badge.badge.name,
                       expected_filename=expected, size=art_size,
                       align="right")
    inline_header = Table(
        [[Paragraph(badge.badge.name, s["BadgeTitle"]), art]],
        colWidths=[None, art_size + 14],
    )
    inline_header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    out.append(inline_header)

    out.append(AccentRule(accent_w=50, height=6))
    if badge.badge.description:
        out.append(Paragraph(badge.badge.description,
                             s["BadgeDescription"]))
    out.append(Spacer(1, 14))

    official_url = (
        badge.badge.official_url
        or f"https://www.scouting.org/merit-badges/{badge.badge.slug}/"
    )
    official_display = official_url.replace("https://", "").rstrip("/")
    disclaimer = (
        "Keep your notes here as you work through the requirements and "
        "prepare to meet with your counselor. This is a study aid only. "
        "Your counselor decides how each requirement is verified and is "
        "not obligated to accept this workbook. The official requirements "
        f'live at <a href="{official_url}" color="#1B4332"><b>'
        f"{official_display}</b></a>."
    )
    out.append(Paragraph(disclaimer, s["Disclaimer"]))
    out.append(Spacer(1, 6))
    feedback = (
        "Found an error or have a suggestion for this workbook? File an "
        'issue at <a href="https://github.com/openscouting/workbooks/issues" '
        'color="#1B4332"><b>github.com/openscouting/workbooks</b></a>. '
        "Requirement changes should be reported to Scouting America directly."
    )
    out.append(Paragraph(feedback, s["Disclaimer"]))
    out.append(Spacer(1, 12))

    # Polished info card lives in template.py — its scout_name and
    # troop_number widgets share names with the body-page header so values
    # sync across every page of the workbook.
    out.append(CoverInfoCard())

    meta_bits = []
    if badge.badge.requirements_revision:
        meta_bits.append(
            f"Requirements revised {badge.badge.requirements_revision}"
        )
    meta_bits.append(f"Workbook updated {built}")
    out.append(Spacer(1, 8))
    out.append(Paragraph(" · ".join(meta_bits), s["CoverMeta"]))
    return out


def _today_iso() -> str:
    from datetime import date
    return date.today().isoformat()


def _git_last_modified(path: Path) -> str | None:
    """Date (YYYY-MM-DD) of the last commit that touched `path`.

    This makes the cover's "updated" stamp reflect when the worksheet content
    actually last changed, not when the PDF happened to be built, so identical
    source produces an identical PDF. Returns None outside a git repo or for an
    uncommitted file, so callers can fall back to today's date.
    """
    import subprocess
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", path.name],
            cwd=path.parent, capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    date = out.stdout.strip()
    return date or None


# ---------- requirements ----------

_PROMPT_STYLES = {0: "Req0Prompt", 1: "Req1Prompt", 2: "Req2Prompt"}


def _display_id(req_id: str, parent_id: str) -> str:
    """Display the Scouting-America-style suffix (1 → '1', 1a → 'a', 8a1 → '1').

    Compound IDs used for disambiguation (e.g., '5a-warm', '8c-menus', '3plan')
    are not standard numbering — the suffix is meaningful only as a key, not as
    a label. We suppress the displayed prefix in that case and let the prompt
    text carry the meaning.
    """
    if parent_id and req_id.startswith(parent_id):
        suffix = req_id[len(parent_id):]
    else:
        suffix = req_id
    if suffix and suffix.isalnum() and len(suffix) <= 3:
        return suffix
    return ""


def _render_requirement(req: S.Requirement, styles, depth: int,
                        parent_id: str) -> list[Flowable]:
    out: list[Flowable] = []
    label_suffix = _display_id(req.id, parent_id)
    label = f"<b>{label_suffix}.</b> " if label_suffix else ""

    prompt_style = styles[_PROMPT_STYLES.get(depth, "Req2Prompt")]
    intro_style = styles["Req0Intro"] if depth == 0 else prompt_style

    if req.intro:
        out.append(Paragraph(label + req.intro, intro_style))
    elif req.prompt:
        out.append(Paragraph(label + req.prompt, prompt_style))
    elif label and not req.field and not req.children:
        out.append(Paragraph(label, prompt_style))

    if req.notes:
        for note in req.notes:
            out.append(Paragraph(note, styles["ReqNote"]))

    if req.field is not None:
        out.extend(_render_field(req.field, styles,
                                 name_prefix=f"req_{req.id}",
                                 indent=18 if depth >= 1 else 0))
        out.append(Spacer(1, 6))

    if req.children:
        for child in req.children:
            out.extend(_render_requirement(child, styles,
                                           depth=depth + 1,
                                           parent_id=req.id))
    return out


# ---------- field dispatch ----------

def _wrap_indent(flowable: Flowable, indent: float) -> list[Flowable]:
    """Visually indent a non-paragraph flowable by composing with a Table.

    Cheaper than wrapping in another Frame: we just left-pad by emitting an
    invisible Spacer-style indent via a single-cell table. For the volumes
    here, a simpler approach — emit the flowable directly and rely on the
    parent paragraph's indent — is fine. This helper exists for future use.
    """
    return [flowable]


def _render_field(field: S.FieldDef, styles, name_prefix: str,
                  indent: float) -> list[Flowable]:
    out: list[Flowable] = []

    if isinstance(field, S.RepeatedBlockDef):
        out.extend(_render_repeated(field, styles, name_prefix))
        return out

    if isinstance(field, S.CalloutDef):
        out.append(Spacer(1, 4))
        out.append(F.CalloutFlowable(field.text, styles["CalloutText"]))
        return out

    if isinstance(field, S.TextFieldDef):
        out.append(F.TextFieldFlowable(name=name_prefix))
    elif isinstance(field, S.TextBoxDef):
        out.append(F.TextBoxFlowable(name=name_prefix, lines=field.lines))
    elif isinstance(field, S.CheckboxDef):
        out.append(F.CheckboxFlowable(name=name_prefix, label=field.label or ""))
    elif isinstance(field, S.ChecklistDef):
        out.append(F.ChecklistFlowable(name_prefix=name_prefix, items=field.items))
    elif isinstance(field, S.LabeledRowsDef):
        # Emit one flowable per labeled row so ReportLab can break the list
        # between rows when the whole block won't fit on the current page.
        for label in field.labels:
            sub_name = f"{name_prefix}_{F._slug(label)}"
            out.append(F.LabeledFieldFlowable(
                name=sub_name, label=label, lines=field.lines_each,
            ))
    elif isinstance(field, S.TableDef):
        out.append(F.TableFlowable(
            name_prefix=name_prefix, rows=field.rows, cols=field.cols,
            headers=field.headers,
        ))
    elif isinstance(field, S.PairGridDef):
        out.append(F.PairGridFlowable(
            name_prefix=name_prefix,
            left_title=field.left_title, right_title=field.right_title,
            col_headers=field.col_headers, rows=field.rows,
        ))
    else:  # pragma: no cover — exhaustive via discriminator
        raise ValueError(f"Unknown field type: {type(field).__name__}")
    return out


def _render_repeated(block: S.RepeatedBlockDef, styles,
                     name_prefix: str) -> list[Flowable]:
    """Expand a repeated_block into N copies of its sub-template.

    Each copy is wrapped in KeepTogether so a single instance doesn't break
    across a page boundary (the four-tent block, the seven meal blocks, etc.).
    """
    # Size the label column to fit the widest label in this template, so
    # labels never wrap mid-word. Capped to prevent very long YAML labels
    # from squeezing the field area too narrow.
    from reportlab.pdfbase.pdfmetrics import stringWidth
    max_label_w = max(
        stringWidth(sub.label + ":", "Helvetica", 10)
        for sub in block.template
    )
    label_col = min(max(max_label_w + 2, 70), 160)

    out: list[Flowable] = []
    for i in range(block.count):
        group: list[Flowable] = [
            Paragraph(f"<b>{i + 1}.</b>", styles["RepeatedIndex"]),
        ]
        for sub in block.template:
            sub_name = f"{name_prefix}_{i}_{F._slug(sub.label)}"
            lines = 1 if sub.type == "text_field" else (sub.lines or 2)
            group.append(F.LabeledFieldFlowable(
                name=sub_name, label=sub.label, lines=lines,
                label_col_width=label_col, left_indent=36,
            ))
        out.append(KeepTogether(group))
        out.append(Spacer(1, 4))
    return out
