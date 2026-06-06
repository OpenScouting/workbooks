---
name: badge-yaml
description: Convert Scouting America merit badge requirements into an OpenScouting workbook YAML file at badges/<slug>.yaml. Use when a contributor pastes the official requirement text (or supplies a scouting.org URL) and wants a ready-to-build workbook YAML.
---

# Generating merit badge YAML files

This skill turns raw requirement text into an OpenScouting workbook YAML matching the schema in `src/openscouting_worksheets/schema.py`. The canonical reference is `badges/camping.yaml` — when a structural decision isn't covered here, mirror what camping does.

## Workflow

1. Identify the badge slug. It matches the URL path on Scouting.org: `https://www.scouting.org/merit-badges/<slug>/`. Examples: `camping`, `first-aid`, `citizenship-in-the-nation`, `nuclear-science`.
2. If the user pasted text, use it. If they only gave a name/URL, fetch the official page with WebFetch.
3. Walk the requirements top-down, picking the right field type for each (see vocabulary below).
4. Write the YAML to `badges/<slug>.yaml`.
5. Validate the schema: `mise run validate`.
6. Build a preview: `worksheets build badges/<slug>.yaml -o dist/<Name>.pdf`.
7. Spot-check the rendered PDF before declaring done — title block correct, every requirement present, no orphaned text, no fields oversized for their content.

## Top-level structure

```yaml
badge:
  name: <Title Case Badge Name>            # "First Aid", "Citizenship in the Nation"
  slug: <kebab-case>                       # must match the scouting.org URL slug
  requirements_revision: "YYYY-MM-DD"      # date the official requirements were last revised
  # workbook_version: optional; defaults to today's build date when omitted
  description: >
    1–3 sentence summary in OpenScouting's own voice. Do NOT lift this from
    the official pamphlet. Describe what the badge is about and why a Scout
    might pursue it.

requirements:
  - id: "1"
    intro: "Do the following:"             # bolded section header for multi-child reqs
    children:
      - id: "1a"
        prompt: <official wording, verbatim>
        field: { ... }
  - id: "2"
    prompt: <official wording>             # use `prompt:` when the req itself has a field
    field: { ... }
  # ...

reference_pages:                            # OPTIONAL — only include when the badge
  - title: ...                              # cites a standing reference (e.g., LNT,
    body: shared/<file>.md                  # Outdoor Code, Wilderness Use Policy).
```

## Field-type vocabulary

| Type             | Use it for                                                                                |
|------------------|--------------------------------------------------------------------------------------------|
| `text_box`       | Multi-line written response. Set `lines:` (3–12 typical).                                  |
| `text_field`     | Single-line input. Rare in body content; mostly used inside `repeated_block` sub-templates. |
| `checkbox`       | One attestation checkbox with a label.                                                     |
| `checklist`      | A group of related checkboxes that should stay together on the page. **Always prefer this over multiple sibling `checkbox` children** — siblings can split across pages, a checklist can't. |
| `labeled_rows`   | Left-column labels with right-column writing areas. Use when a requirement enumerates discrete items (first aid for X/Y/Z, list of skills to demonstrate). |
| `table`          | Grid for free-form lists (gear lists, food lists, camping log entries). Set `rows`, `cols`, optional `headers`. |
| `repeated_block` | "Describe N of these" patterns (4 tent types, 3 stoves, 7 meals). Each iteration renders as label-left/field-right rows numbered 1..N. |
| `pair_grid`      | Two side-by-side titled comparison tables (internal vs external frame packs, etc.).         |
| `callout`        | Boxed informational note with no fillable field. Use sparingly — only when OpenScouting needs to flag something that isn't in the official text (e.g., the Cooking-MB no-double-counting reminder in Camping). |

## Numbering and ID conventions

- Top-level requirements use the official number: `id: "1"`, `id: "10"`.
- Sub-requirements append the letter: `id: "1a"`, `id: "10f"`.
- Sub-sub-requirements append the number: `id: "8a1"`, `id: "8a2"`.
- **Continuation IDs** for splitting a long requirement into multiple fill-in sections use a hyphenated suffix: `id: "1b-prep"`, `id: "5a-warm"`, `id: "8c-menus"`. The renderer's heuristic suppresses the displayed label for hyphenated suffixes, so the prompt text stands on its own.
- All IDs must be unique within the document (Pydantic validates this).

## Patterns for common requirement shapes

### Long requirement with multiple distinct prompts

When one official requirement has 2+ distinct things to write about, split into siblings with continuation IDs. Each gets its own field:

```yaml
- id: "1b"
  prompt: "Discuss with your counselor why it is important to be aware of weather conditions before and during your camping activities."
  field: { type: text_box, lines: 6 }
- id: "1b-prep"
  prompt: "Tell how you can prepare should the weather turn bad during your campouts."
  field: { type: text_box, lines: 6 }
```

### "Pick one of the following" options

Use `checklist`, NOT separate sibling `checkbox` children. The checklist is one flowable and won't split across pages:

```yaml
- id: "3"
  prompt: "Make a written plan for an overnight trek and show how to get to your camping spot using a topographical map and one of the following:"
  field:
    type: checklist
    items:
      - "Compass"
      - "GPS receiver"
      - "Smartphone with a GPS app"
```

### Enumerated first-aid / item list

Use `labeled_rows`:

```yaml
- id: "1c"
  prompt: "Show that you know first aid for the following:"
  field:
    type: labeled_rows
    lines_each: 2
    labels: [Hypothermia, Frostbite, "Heat reactions", Dehydration, ...]
```

### "Describe N types of X"

Use `repeated_block`. The template defines sub-fields that repeat N times:

```yaml
- id: "6a"
  prompt: "Describe the features of four types of tents, when and where they could be used."
  field:
    type: repeated_block
    count: 4
    template:
      - { label: "Type",        type: text_field }
      - { label: "Features",    type: text_box, lines: 3 }
      - { label: "When to use", type: text_box, lines: 2 }
      - { label: "Where to use",type: text_box, lines: 2 }
```

### Side-by-side comparison

Use `pair_grid`:

```yaml
- id: "6d-pair"
  field:
    type: pair_grid
    left_title: "Internal Frame Pack"
    right_title: "External Frame Pack"
    col_headers: ["Advantages", "Disadvantages"]
    rows: 5
```

### Meals / repeating compound entries

`repeated_block` is the right tool. For Camping req 8c (2 breakfasts + 3 lunches + 2 suppers), use `count: 7`:

```yaml
- id: "8c-menus"
  prompt: "Give recipes and make a food list for your patrol. Plan two breakfasts, three lunches, and two suppers. Label each row with the meal."
  field:
    type: repeated_block
    count: 7
    template:
      - { label: "Meal",     type: text_field }
      - { label: "Food list", type: text_box, lines: 4 }
      - { label: "Recipes",  type: text_box, lines: 6 }
```

### Checklist of nights / events to log

Use `table` with descriptive headers:

```yaml
- id: "9a"
  prompt: "Camp for at least 20 nights at designated Scouting activities..."
  field:
    type: table
    headers: ["Date(s)", "Location", "Nights", "Notes"]
    rows: 6
    cols: 4
```

## Line-count heuristics for `text_box`

| Question shape                  | `lines:`           |
|---------------------------------|--------------------|
| Short concept ("Explain X")     | 4–6                |
| Multi-part explanation          | 6–8                |
| Plan / story / process          | 8–12               |
| Per-item rows in labeled_rows   | 2–3 (`lines_each`) |

Err small. Text boxes now split across page boundaries, so a writer who needs more room continues onto the next page — but an oversized empty box wastes printable space.

## Style rules

- **No em-dashes (—) in any user-facing text.** Use `.`, `:`, or `;` instead.
- **Don't lift text from the pamphlet** for the workbook's `description` or disclaimers. The official requirement *prompts themselves* should match Scouting America's wording verbatim — they're the requirements. Everything else is OpenScouting's own copy.
- Use straight quotes (`"`, `'`), not curly (`"`, `'`).
- Inline hyperlinks use ReportLab Paragraph markup. Quote the whole YAML value with single quotes when the string contains double quotes:
  ```yaml
  notes:
    - 'See the <a href="https://example.org/foo.pdf" color="#1B4332"><b>Planning Worksheet</b></a> for a template.'
  ```
- Naming: "Boy Scouts of America" / "BSA" → **"Scouting America"**. "Webelos" stays (still the current Cub Scouts rank).
- Drop resource lists (videos, supporting PDFs) unless they're genuinely useful in the workbook context. The official page already lists them; the workbook should focus on writing space, not link curation. The Scout Planning Worksheet link in Camping req 3 is a good exception — it's a working aid the Scout fills in alongside the workbook.

## Reference pages

Include `reference_pages` only when the official requirements cite a standing reference. Reuse shared files where possible:

- `shared/leave-no-trace.md` — the 7 LNT principles
- `shared/outdoor-code.md` — the Outdoor Code
- `shared/wilderness-use-policy.md` — Scouting America Wilderness Use Policy

```yaml
reference_pages:
  - title: "Outdoor Ethics"
    columns:
      - title: "The Principles of Leave No Trace"
        body: shared/leave-no-trace.md
      - title: "The Outdoor Code"
        body: shared/outdoor-code.md
```

Add new shared files when multiple badges will reference the same boilerplate. Single-use boilerplate can go inline as `body: |\n  <text>` instead.

## What NOT to do

- Don't put separate sibling `checkbox` children when they form a "pick one" or "do all of these" group — use `checklist`.
- Don't paraphrase the official requirement prompt. Match wording exactly.
- Don't add the OpenScouting cover info (Scout name, counselor info) to per-badge YAML — that lives in `template.CoverInfoCard` and is rendered automatically on every cover.
- Don't include the BSA-style "this workbook may not be required" disclaimer — that lives in the cover template too.
- Don't put `requirements_revision` in the future or unknown. Use the revision date Scouting America publishes on the badge page (often shown as "Revised YYYY").

## Final pre-flight checklist

Before declaring a new badge YAML done:

- [ ] `slug` matches `https://www.scouting.org/merit-badges/<slug>/`
- [ ] `requirements_revision` set to the official revision date
- [ ] Every official requirement appears, in order, with matching wording
- [ ] Top-level requirement IDs are `"1"` through `"N"` (strings, even when numeric)
- [ ] Pick-one or do-all-of-these groups use `checklist`, not sibling checkboxes
- [ ] No em-dashes anywhere
- [ ] `mise run validate` passes
- [ ] `worksheets build badges/<slug>.yaml -o dist/<Name>.pdf` succeeds
- [ ] Spot-check pages 1, 2, and any with `repeated_block` / `pair_grid` / `table`
