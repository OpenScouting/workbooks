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
