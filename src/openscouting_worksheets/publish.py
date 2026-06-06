"""Incremental site build for GitHub Pages.

Builds a PDF for every active badge's latest revision, but only rebuilds the
ones whose inputs changed since the previous run (tracked by a content hash in
build-manifest.json). Unchanged PDFs are carried over from the prior build,
which the CI restores from cache. Also emits an index.html listing every
workbook with its git last-changed date and a link to the PDF.
"""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

from . import builder
from . import cli

MANIFEST_NAME = "build-manifest.json"
INDEX_NAME = "index.html"


def _pdf_name(slug: str) -> str:
    return "-".join(p.capitalize() for p in slug.split("-")) + ".pdf"


def _global_hash(base_dir: Path) -> str:
    """Hash of inputs that affect every PDF: generator code, shared text, assets.

    A change to any of these invalidates all badges, forcing a full rebuild.
    """
    h = hashlib.sha256()
    roots = [base_dir / "src", base_dir / "shared", base_dir / "assets"]
    files = sorted(
        p for root in roots if root.exists()
        for p in root.rglob("*") if p.is_file() and p.suffix != ".pyc"
    )
    for p in files:
        h.update(p.relative_to(base_dir).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def _badge_hash(yaml_path: Path, emblem: Path, global_hash: str,
                draft: bool = False) -> str:
    h = hashlib.sha256()
    h.update(global_hash.encode())
    # Draft vs release produce different PDFs from identical source, so the
    # mode is part of the cache key — toggling it forces every badge to rebuild.
    h.update(b"draft" if draft else b"release")
    h.update(yaml_path.read_bytes())
    if emblem.exists():
        h.update(emblem.read_bytes())
    return h.hexdigest()


def build_site(base_dir: Path, output_dir: Path, draft: bool = False) -> dict:
    """Incrementally build all active workbooks + index into output_dir."""
    worksheets_dir = base_dir / "worksheets"
    output_dir.mkdir(parents=True, exist_ok=True)

    prior_path = output_dir / MANIFEST_NAME
    prior = json.loads(prior_path.read_text()) if prior_path.exists() else {}
    global_hash = _global_hash(base_dir)

    manifest: dict[str, str] = {}
    rows = []
    built = reused = 0

    for d in cli._badge_dirs(worksheets_dir):
        slug = d.name
        yml = cli._latest_yaml(d)
        badge = builder.load_badge(yml)
        emblem = base_dir / "badges" / slug / f"{slug}.png"
        h = _badge_hash(yml, emblem, global_hash, draft)
        pdf_name = _pdf_name(slug)
        pdf_path = output_dir / pdf_name

        if prior.get(slug) == h and pdf_path.exists():
            reused += 1
        else:
            builder.build(yml, pdf_path, base_dir=base_dir, draft=draft)
            built += 1

        manifest[slug] = h
        updated = builder._git_last_modified(yml) or builder._today_iso()
        rows.append({
            "name": badge.badge.name,
            "pdf": pdf_name,
            "updated": updated,
            "revision": (badge.badge.requirements_revision or "")[:4],
        })

    rows.sort(key=lambda r: r["name"].lower())
    (output_dir / INDEX_NAME).write_text(_render_index(rows))
    prior_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return {"built": built, "reused": reused, "total": len(rows)}


def _render_index(rows: list[dict]) -> str:
    items = "\n".join(
        f'      <tr>'
        f'<td class="name"><a href="{html.escape(r["pdf"])}">'
        f'{html.escape(r["name"])}</a></td>'
        f'<td class="rev">{html.escape(r["revision"])}</td>'
        f'<td class="date">{html.escape(r["updated"])}</td>'
        f'</tr>'
        for r in rows
    )
    return _INDEX_TEMPLATE.format(count=len(rows), rows=items)


_INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenScouting Merit Badge Workbooks</title>
<style>
  :root {{
    --green: #1B4332; --amber: #F59E0B; --muted: #6B7280;
    --line: #E5E7EB; --bg: #FAFAFA;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font: 16px/1.5 -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
         color: #111; background: var(--bg); }}
  header {{ background: var(--green); color: #fff; padding: 2rem 1.5rem 1.6rem;
            border-bottom: 4px solid var(--amber); }}
  header h1 {{ margin: 0; font-size: 1.6rem; letter-spacing: .2px; }}
  header p {{ margin: .4rem 0 0; color: #cfe3da; font-size: .95rem; }}
  main {{ max-width: 860px; margin: 0 auto; padding: 1.5rem; }}
  .controls {{ display: flex; gap: 1rem; align-items: center; margin-bottom: 1rem; }}
  #q {{ flex: 1; padding: .6rem .8rem; border: 1px solid var(--line); border-radius: 8px;
        font-size: 1rem; }}
  .count {{ color: var(--muted); font-size: .9rem; white-space: nowrap; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff;
           border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }}
  th, td {{ text-align: left; padding: .7rem .9rem; border-bottom: 1px solid var(--line); }}
  th {{ font-size: .72rem; text-transform: uppercase; letter-spacing: .06em;
        color: var(--muted); background: #fff; position: sticky; top: 0; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #F1F5F4; }}
  td.name a {{ color: var(--green); font-weight: 600; text-decoration: none; }}
  td.name a:hover {{ text-decoration: underline; }}
  td.rev, td.date {{ color: var(--muted); font-variant-numeric: tabular-nums;
                     white-space: nowrap; font-size: .92rem; }}
  footer {{ max-width: 860px; margin: 0 auto; padding: 1.5rem; color: var(--muted);
            font-size: .82rem; }}
  footer a {{ color: var(--green); }}
</style>
</head>
<body>
<header>
  <h1>OpenScouting Merit Badge Workbooks</h1>
  <p>Fillable PDF worksheets to organize your notes as you work toward each badge.</p>
</header>
<main>
  <div class="controls">
    <input id="q" type="search" placeholder="Filter badges&hellip;" autocomplete="off">
    <span class="count"><span id="shown">{count}</span> of {count}</span>
  </div>
  <table>
    <thead>
      <tr><th>Badge</th><th>Requirements</th><th>Updated</th></tr>
    </thead>
    <tbody id="list">
{rows}
    </tbody>
  </table>
</main>
<footer>
  &copy; OpenScouting &middot; Released under CC BY-SA 4.0 &middot;
  Requirements &copy; Scouting America, used with permission. &middot;
  <a href="https://github.com/openscouting/workbooks">Source &amp; issues</a>
</footer>
<script>
  const q = document.getElementById('q');
  const rows = [...document.querySelectorAll('#list tr')];
  const shown = document.getElementById('shown');
  q.addEventListener('input', () => {{
    const t = q.value.trim().toLowerCase();
    let n = 0;
    for (const r of rows) {{
      const hit = r.textContent.toLowerCase().includes(t);
      r.style.display = hit ? '' : 'none';
      if (hit) n++;
    }}
    shown.textContent = n;
  }});
</script>
</body>
</html>
"""
