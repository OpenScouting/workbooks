# OpenScouting Worksheets

YAML-driven generator for fillable PDF merit badge workbooks, published under the
OpenScouting banner. A shared Python template wraps each badge's content with
OpenScouting branding, page chrome, and AcroForm fillable fields, so every PDF
looks identical across the whole catalogue.

## Repository layout

Two parallel source trees, deliberately separated:

```
badges/                      # MERIT BADGE SOURCE (the facts)
  <slug>/
    <year>.md                # official requirements, one file per revision
    <slug>.png               # official badge emblem
  MANIFEST.md                # catalogue index (142 badges, status, URLs)

worksheets/                  # WORKBOOK SOURCES (our layer on top)
  <slug>/
    <year>.yaml              # workbook definition, one per revision

shared/                      # reusable reference text (Leave No Trace, Outdoor Code, ...)
assets/                      # OpenScouting branding (logo, fonts)
src/openscouting_worksheets/ # the generator
```

The highest `<year>` in each directory is the current revision. PDFs are built
from the latest year only; older years are kept for change-tracking and can be
built explicitly by path. Retired badges carry `status: retired` and are skipped
by `build-all`.

## Quick start

This project uses [mise](https://mise.jdx.dev) to pin Python and run tasks.
Install mise once (`curl https://mise.run | sh`), then:

```bash
mise install            # one-time: installs Python 3.11 and creates .venv
mise run check          # validate + build all PDFs + run tests
```

Individual tasks:

```bash
mise run build camping  # build one badge's latest revision -> dist/Camping.pdf
mise run build-all      # build every active badge -> dist/
mise run validate       # schema-validate every worksheet without rendering
mise run test           # pytest only
mise tasks              # list everything
```

Each task auto-installs deps on first run (cached on `pyproject.toml`).
Prefer raw Python? `pip install -e '.[test]'` then call the `worksheets` CLI:

```bash
worksheets build worksheets/camping -o dist/Camping.pdf
worksheets build-all worksheets/ -o dist/
worksheets validate worksheets/
```

## Adding or revising a merit badge

1. Add the requirement source under `badges/<slug>/<year>.md`.
2. Author `worksheets/<slug>/<year>.yaml` following the conventions in
   `.claude/skills/badge-yaml/SKILL.md`. `worksheets/camping/2024.yaml` is the
   canonical worked example covering every field type.
3. Run `mise run validate` then `mise run build <slug>` to preview.
4. Open a PR. CI validates the schema on every push.

### Field type vocabulary

| Type             | What it produces                                              |
|------------------|---------------------------------------------------------------|
| `text_field`     | Single-line fillable text input                               |
| `text_box`       | Multi-line fillable text area (`lines:` controls height)      |
| `checkbox`       | Single checkbox with inline label                             |
| `checklist`      | A group of labeled checkboxes (stays together on the page)    |
| `labeled_rows`   | Left-column labels with right-column fillable boxes           |
| `table`          | Grid of fillable cells, optional column headers               |
| `repeated_block` | Repeat a sub-template N times (e.g., 4 tent types, 7 meals)   |
| `pair_grid`      | Two side-by-side titled tables (e.g., Internal/External pack) |
| `callout`        | Boxed informational text (no field)                           |

## Architecture

- `schema.py` — Pydantic models for the YAML grammar
- `fields.py` — one ReportLab `Flowable` per field type (visuals + AcroForm widgets)
- `template.py` — OpenScouting cover, header/footer, info card, styles
- `builder.py` — walks the schema and assembles the PDF
- `postprocess.py` — merges duplicate-named widgets (e.g. the Scout's Name field on every page)
- `cli.py` — the `worksheets` command

Visual changes (colors, fonts, cover design) are made once in `template.py` and
apply to every badge.

## Licensing

Workbook layout and code: © OpenScouting, released under CC BY-SA 4.0.
Merit badge requirements: © Scouting America, used with permission.
