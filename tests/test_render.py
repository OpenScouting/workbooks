"""Smoke tests: schema validates and the PDF builds with fillable widgets."""

from pathlib import Path

import pytest

from openscouting_worksheets import builder

REPO = Path(__file__).resolve().parent.parent
# Versioned layout: latest <year>.yaml in the badge's worksheet directory.
BADGE = sorted((REPO / "worksheets" / "camping").glob("*.yaml"))[-1]


def test_camping_loads():
    badge = builder.load_badge(BADGE)
    assert badge.badge.name == "Camping"
    assert len(badge.requirements) == 10


def test_camping_builds(tmp_path):
    out = tmp_path / "Camping.pdf"
    builder.build(BADGE, out, base_dir=REPO)
    assert out.exists()
    assert out.stat().st_size > 30_000


def test_pdf_has_form_fields(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    out = tmp_path / "Camping.pdf"
    builder.build(BADGE, out, base_dir=REPO)
    reader = pypdf.PdfReader(str(out))
    fields = reader.get_fields() or {}
    # Cover sheet plus a slew of requirement fields — should be well over 50
    assert len(fields) > 50
    # Spot-check a few names we know we generate
    names = set(fields.keys())
    assert "scout_name" in names
    assert "troop_number" in names
    assert any(n.startswith("req_1a") for n in names)
    assert any("hypothermia" in n.lower() for n in names)


def test_draft_watermark_present_only_in_draft(tmp_path):
    """Draft builds stamp DRAFT on the page; release builds don't."""
    pypdf = pytest.importorskip("pypdf")

    def page1_text(draft):
        out = tmp_path / f"Camping-{draft}.pdf"
        builder.build(BADGE, out, base_dir=REPO, draft=draft)
        return pypdf.PdfReader(str(out)).pages[0].extract_text() or ""

    assert "DRAFT" in page1_text(True)
    assert "DRAFT" not in page1_text(False)


def test_draw_area_renders_without_form_field(tmp_path):
    """A draw_area is a blank canvas: it draws a box but registers no widget."""
    pypdf = pytest.importorskip("pypdf")
    yaml_text = (
        "badge:\n"
        "  name: Test\n"
        "  slug: test\n"
        "requirements:\n"
        "  - id: '1'\n"
        "    prompt: Sketch your design.\n"
        "    field: { type: draw_area, height: 4 }\n"
        "  - id: '2'\n"
        "    prompt: Describe it.\n"
        "    field: { type: text_box, lines: 3 }\n"
    )
    src = tmp_path / "test.yaml"
    src.write_text(yaml_text)
    out = tmp_path / "Test.pdf"
    builder.build(src, out, base_dir=REPO)
    reader = pypdf.PdfReader(str(out))
    fields = reader.get_fields() or {}
    # The text_box (req_2) is fillable; the draw_area (req_1) is not.
    assert any(n.startswith("req_2") for n in fields)
    assert not any(n.startswith("req_1") for n in fields)


def test_shared_header_fields_are_linked(tmp_path):
    """Scout name & troop number widgets across pages share one logical field."""
    pypdf = pytest.importorskip("pypdf")
    out = tmp_path / "Camping.pdf"
    builder.build(BADGE, out, base_dir=REPO)
    reader = pypdf.PdfReader(str(out))
    af = reader.trailer["/Root"]["/AcroForm"].get_object()
    top_fields = af["/Fields"]
    # No duplicate top-level field names — postprocess merged them
    from collections import Counter
    name_counts = Counter(str(f.get_object().get("/T", "")) for f in top_fields)
    duplicates = {n: c for n, c in name_counts.items() if c > 1}
    assert duplicates == {}, f"unmerged duplicates: {duplicates}"
    # scout_name should now have many child widgets (one per page)
    scout = next(f.get_object() for f in top_fields
                 if str(f.get_object().get("/T", "")) == "scout_name")
    assert len(scout.get("/Kids", [])) >= 10
