"""Post-processing pass on the generated PDF.

ReportLab's `canvas.acroForm.textfield` emits one independent field per call,
so a widget repeated across pages (e.g., the Scout's Name field in the header)
ends up as N sibling fields in `/AcroForm/Fields`, all sharing the same `/T`.
PDF readers vary in how they handle that — most merge by name, some don't.

This module rewrites duplicate-name fields into the spec-compliant form: a
single parent field with `/Kids` pointing to the per-page widget annotations.
That guarantees value synchronisation in every reader.
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    NameObject,
    TextStringObject,
)


# Field-level keys that should live on the parent dictionary (and be stripped
# from the kid widgets) when we merge duplicates.
_FIELD_LEVEL_KEYS = ("/FT", "/T", "/TU", "/Ff", "/V", "/DV", "/MaxLen", "/Q",
                     "/DA", "/DR")


def merge_duplicate_fields(pdf_path: Path) -> None:
    """Rewrite the PDF so widgets sharing a name link to a single field."""
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter(clone_from=reader)

    root = writer.root_object
    af_ref = root.get("/AcroForm")
    if af_ref is None:
        return
    af = af_ref if isinstance(af_ref, DictionaryObject) else af_ref.get_object()

    raw_fields = af.get("/Fields")
    if not raw_fields:
        return
    fields = raw_fields if isinstance(raw_fields, ArrayObject) else raw_fields.get_object()

    by_name: dict[str, list] = {}
    for ref in fields:
        obj = ref.get_object()
        name = str(obj.get("/T", ""))
        by_name.setdefault(name, []).append(ref)

    merged: list = []
    changed = False
    for name, refs in by_name.items():
        if len(refs) == 1:
            merged.append(refs[0])
            continue
        changed = True
        merged.append(_collapse(writer, name, refs))

    if not changed:
        return

    af[NameObject("/Fields")] = ArrayObject(merged)
    with open(pdf_path, "wb") as fh:
        writer.write(fh)


def _collapse(writer: PdfWriter, name: str, refs: list):
    """Build a parent field for `name` and reparent each widget as a kid."""
    first = refs[0].get_object()
    parent = DictionaryObject()
    for key in _FIELD_LEVEL_KEYS:
        if key in first:
            parent[NameObject(key)] = first[key]
    parent[NameObject("/T")] = TextStringObject(name)

    parent_ref = writer._add_object(parent)

    kids = ArrayObject()
    for ref in refs:
        kid = ref.get_object()
        # Strip field-level keys that now belong to the parent.
        for key in _FIELD_LEVEL_KEYS:
            if key in kid and key != "/FT":  # /FT may still be required on kid
                del kid[key]
        kid[NameObject("/Parent")] = parent_ref
        kids.append(ref)
    parent[NameObject("/Kids")] = kids
    return parent_ref
