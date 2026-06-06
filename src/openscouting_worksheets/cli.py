"""Command-line entry point: `worksheets build|build-all|validate`.

Badges use a versioned layout: badges/<slug>/<year>.yaml, where the highest
year is the current revision. PDFs are built from the latest year only; older
years are kept for change-tracking and can be built explicitly by path.
"""

from __future__ import annotations

import re
from pathlib import Path

import click
import yaml

from . import builder
from . import schema as S


def _year_of(path: Path) -> int:
    m = re.match(r"(\d{4})", path.stem)
    return int(m.group(1)) if m else -1


def _latest_yaml(badge_dir: Path) -> Path | None:
    """The highest-year <year>.yaml in a badge directory (current revision)."""
    yamls = sorted(badge_dir.glob("*.yaml"), key=_year_of)
    return yamls[-1] if yamls else None


def _is_retired(yaml_path: Path) -> bool:
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    return (data.get("badge", {}) or {}).get("status") == "retired"


def _badge_dirs(badges_dir: Path, include_retired: bool = False) -> list[Path]:
    """Per-badge directories under badges/ (skips raw/, dotfiles, retired)."""
    dirs = sorted(
        d for d in badges_dir.iterdir()
        if d.is_dir() and d.name != "raw" and not d.name.startswith(".")
        and any(d.glob("*.yaml"))
    )
    if include_retired:
        return dirs
    return [d for d in dirs if not _is_retired(_latest_yaml(d))]


def _all_yamls(badges_dir: Path) -> list[Path]:
    return sorted(badges_dir.glob("*/*.yaml"))


@click.group()
@click.version_option()
def main() -> None:
    """OpenScouting worksheet generator."""


@main.command()
@click.argument("target", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), required=True,
              help="Output PDF path.")
def build(target: Path, output: Path) -> None:
    """Build a PDF from a badge.

    TARGET may be a badge directory (builds its latest year) or a specific
    <year>.yaml file.
    """
    if target.is_dir():
        yml = _latest_yaml(target)
        if yml is None:
            raise click.ClickException(f"No <year>.yaml found in {target}")
    else:
        yml = target
    builder.build(yml, output)
    click.echo(f"Built {output} (from {yml})")


@main.command("build-all")
@click.argument("badges_dir", type=click.Path(exists=True, file_okay=False,
                                              path_type=Path))
@click.option("-o", "--output-dir", type=click.Path(path_type=Path),
              required=True, help="Output directory for PDFs.")
def build_all(badges_dir: Path, output_dir: Path) -> None:
    """Build the latest revision of every badge in BADGES_DIR to PDFs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dirs = _badge_dirs(badges_dir)
    if not dirs:
        raise click.ClickException(f"No badge directories found in {badges_dir}")
    skipped = len(_badge_dirs(badges_dir, include_retired=True)) - len(dirs)
    for d in dirs:
        yml = _latest_yaml(d)
        # Title-case each slug segment for the filename (camping -> Camping).
        out = output_dir / (
            "-".join(p.capitalize() for p in d.name.split("-")) + ".pdf")
        builder.build(yml, out)
        click.echo(f"Built {out}")
    if skipped:
        click.echo(f"Skipped {skipped} retired badge(s).")


@main.command()
@click.option("-o", "--output-dir", type=click.Path(path_type=Path),
              default="dist", help="Site output directory (default: dist).")
def publish(output_dir: Path) -> None:
    """Incrementally build all active workbooks + index.html for GitHub Pages.

    Only badges whose inputs changed since the last run are rebuilt; unchanged
    PDFs are reused from output_dir (restored from CI cache between runs).
    """
    from . import publish as _publish
    base_dir = Path.cwd()
    stats = _publish.build_site(base_dir, output_dir)
    click.echo(
        f"Published {stats['total']} workbooks "
        f"({stats['built']} built, {stats['reused']} reused) to {output_dir}"
    )


@main.command()
@click.argument("badges_dir", type=click.Path(exists=True, file_okay=False,
                                              path_type=Path))
def validate(badges_dir: Path) -> None:
    """Validate every <year>.yaml in every badge directory."""
    errors = 0
    for yml in _all_yamls(badges_dir):
        try:
            data = yaml.safe_load(yml.read_text(encoding="utf-8"))
            S.Badge.model_validate(data)
            click.echo(f"OK  {yml}")
        except Exception as exc:
            errors += 1
            click.echo(f"ERR {yml}: {exc}", err=True)
    if errors:
        raise click.ClickException(f"{errors} file(s) failed validation")


if __name__ == "__main__":
    main()
