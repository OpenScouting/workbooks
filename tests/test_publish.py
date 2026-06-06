"""Tests for the incremental-publish logic and index rendering.

The full 140-badge site build is slow and exercised in CI; here we cover the
pure pieces: filename derivation, hash determinism (the basis of incremental
rebuilds), and index HTML generation.
"""

from pathlib import Path

from openscouting_worksheets import publish

REPO = Path(__file__).resolve().parent.parent


def test_pdf_name_titlecases_segments():
    assert publish._pdf_name("camping") == "Camping.pdf"
    assert publish._pdf_name("small-boat-sailing") == "Small-Boat-Sailing.pdf"


def test_global_hash_is_stable_and_sensitive(tmp_path):
    base = tmp_path
    (base / "src").mkdir()
    (base / "shared").mkdir()
    (base / "src" / "a.py").write_text("x = 1\n")
    h1 = publish._global_hash(base)
    h2 = publish._global_hash(base)
    assert h1 == h2                      # deterministic
    (base / "src" / "a.py").write_text("x = 2\n")
    assert publish._global_hash(base) != h1   # sensitive to code changes


def test_badge_hash_changes_with_content(tmp_path):
    yml = tmp_path / "2024.yaml"
    emblem = tmp_path / "x.png"
    yml.write_text("badge: a")
    emblem.write_bytes(b"PNG")
    g = "globalhash"
    h1 = publish._badge_hash(yml, emblem, g)
    assert h1 == publish._badge_hash(yml, emblem, g)        # stable
    yml.write_text("badge: b")
    assert publish._badge_hash(yml, emblem, g) != h1        # yaml change
    yml.write_text("badge: a")
    emblem.write_bytes(b"PNG2")
    assert publish._badge_hash(yml, emblem, g) != h1        # emblem change


def test_badge_hash_distinguishes_draft_and_release(tmp_path):
    yml = tmp_path / "2024.yaml"
    emblem = tmp_path / "x.png"
    yml.write_text("badge: a")
    emblem.write_bytes(b"PNG")
    g = "globalhash"
    release = publish._badge_hash(yml, emblem, g, draft=False)
    draft = publish._badge_hash(yml, emblem, g, draft=True)
    assert release != draft        # toggling mode forces a rebuild


def test_render_index_lists_rows_and_links():
    rows = [
        {"name": "Camping", "pdf": "Camping.pdf", "updated": "2026-06-06", "revision": "2024"},
        {"name": "Cooking", "pdf": "Cooking.pdf", "updated": "2025-01-02", "revision": "2025"},
    ]
    html = publish._render_index(rows)
    assert 'href="Camping.pdf"' in html
    assert ">Camping<" in html
    assert "2026-06-06" in html
    assert "OpenScouting Merit Badge Workbooks" in html
    # live-filter script + search box present
    assert 'id="q"' in html and "addEventListener" in html
    # release index carries no draft warning banner (the CSS class is always
    # defined; the banner element and its text are what's conditional)
    assert "DRAFT PREVIEW" not in html
    assert 'role="alert"' not in html


def test_draft_index_has_prominent_warning():
    rows = [{"name": "Camping", "pdf": "Camping.pdf", "updated": "2026-06-06",
             "revision": "2024"}]
    html = publish._render_index(rows, draft=True)
    assert "draft-banner" in html
    assert "DRAFT PREVIEW" in html
    assert 'class="draft"' in html        # header switches to alert styling
    assert 'href="../"' in html           # links back to the release site
