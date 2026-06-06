"""Tests for the CLI's version-resolution and retired-skip logic."""

from pathlib import Path

from openscouting_worksheets import cli

REPO = Path(__file__).resolve().parent.parent
WORKSHEETS = REPO / "worksheets"


def test_latest_yaml_picks_highest_year(tmp_path):
    d = tmp_path / "demo"
    d.mkdir()
    (d / "2016.yaml").write_text("x")
    (d / "2024.yaml").write_text("x")
    (d / "2009.yaml").write_text("x")
    assert cli._latest_yaml(d).stem == "2024"


def test_latest_yaml_empty_dir(tmp_path):
    assert cli._latest_yaml(tmp_path) is None


def test_real_camping_latest_is_2024():
    assert cli._latest_yaml(WORKSHEETS / "camping").stem == "2024"


def test_badge_dirs_skip_raw_and_retired():
    active = {d.name for d in cli._badge_dirs(WORKSHEETS)}
    everything = {d.name for d in cli._badge_dirs(WORKSHEETS, include_retired=True)}
    # raw/ is never a badge dir
    assert "raw" not in active and "raw" not in everything
    # the known retired badge is excluded from active but present in the full set
    assert "citizenship-in-society" in everything
    assert "citizenship-in-society" not in active
    # and active is exactly everything minus the retired one(s)
    assert active < everything


def test_retired_detection():
    cis = cli._latest_yaml(WORKSHEETS / "citizenship-in-society")
    assert cli._is_retired(cis) is True
    camping = cli._latest_yaml(WORKSHEETS / "camping")
    assert cli._is_retired(camping) is False
