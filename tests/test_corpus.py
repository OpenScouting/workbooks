"""Corpus-wide checks across all badges and worksheets.

These guard the whole catalogue, not just one sample badge: every worksheet
must validate, every slug must line up with its source directory and emblem,
and the prose-style rules (no em-dashes, no curly quotes) must hold.
"""

import re
from pathlib import Path

import pytest
import yaml

from openscouting_worksheets import schema as S

REPO = Path(__file__).resolve().parent.parent
WORKSHEETS = REPO / "worksheets"
BADGES = REPO / "badges"

ALL_YAMLS = sorted(WORKSHEETS.glob("*/*.yaml"))
BADGE_DIRS = sorted(d for d in BADGES.iterdir()
                    if d.is_dir() and d.name != "raw")


def test_catalogue_is_populated():
    assert len(ALL_YAMLS) >= 140
    assert len(BADGE_DIRS) >= 140


@pytest.mark.parametrize("path", ALL_YAMLS, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_worksheet_validates(path):
    badge = S.Badge.model_validate(yaml.safe_load(path.read_text()))
    # slug matches its directory; filename is the revision year.
    assert badge.badge.slug == path.parent.name
    assert re.fullmatch(r"\d{4}", path.stem)
    assert badge.badge.description, "every badge needs an OpenScouting-voice description"


@pytest.mark.parametrize("path", ALL_YAMLS, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_no_typographic_violations(path):
    text = path.read_text()
    for bad, label in [("—", "em-dash"), ("–", "en-dash"),
                       ("“", "curly-open-quote"), ("”", "curly-close-quote"),
                       ("‘", "curly-open-apostrophe"), ("’", "curly-apostrophe")]:
        assert bad not in text, f"{label} found in {path}"


@pytest.mark.parametrize("badge_dir", BADGE_DIRS, ids=lambda d: d.name)
def test_each_badge_has_source_and_emblem(badge_dir):
    slug = badge_dir.name
    # at least one <year>.md requirement source
    assert any(re.fullmatch(r"\d{4}", p.stem) for p in badge_dir.glob("*.md")), \
        f"{slug}: no <year>.md requirement source"
    # the official emblem, co-located
    assert (badge_dir / f"{slug}.png").exists(), f"{slug}: missing emblem png"


def test_worksheet_and_badge_slugs_align():
    ws = {p.parent.name for p in ALL_YAMLS}
    bd = {d.name for d in BADGE_DIRS}
    # every worksheet has a matching badge source dir
    assert ws <= bd, f"worksheets with no badge source: {ws - bd}"
