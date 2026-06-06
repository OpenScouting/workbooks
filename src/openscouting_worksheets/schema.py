"""Pydantic models defining the YAML grammar that volunteers edit.

The schema is small and deliberately controlled: each field type maps to a
single rendering primitive in `fields.py`. Adding a new visual primitive
means adding one model variant here and one Flowable subclass there.
"""

from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field as _F, model_validator


# ---------- Field type definitions ----------

class _FieldBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TextFieldDef(_FieldBase):
    type: Literal["text_field"] = "text_field"
    placeholder: Optional[str] = None


class TextBoxDef(_FieldBase):
    type: Literal["text_box"] = "text_box"
    lines: int = _F(default=5, ge=1, le=40)


class CheckboxDef(_FieldBase):
    type: Literal["checkbox"] = "checkbox"
    label: Optional[str] = None


class ChecklistDef(_FieldBase):
    type: Literal["checklist"] = "checklist"
    items: list[str] = _F(min_length=1)


class LabeledRowsDef(_FieldBase):
    type: Literal["labeled_rows"] = "labeled_rows"
    labels: list[str] = _F(min_length=1)
    lines_each: int = _F(default=2, ge=1, le=10)


class TableDef(_FieldBase):
    type: Literal["table"] = "table"
    headers: Optional[list[str]] = None
    rows: int = _F(ge=1, le=40)
    cols: int = _F(ge=1, le=8)

    @model_validator(mode="after")
    def _check_headers(self):
        if self.headers is not None and len(self.headers) != self.cols:
            raise ValueError(
                f"table headers length ({len(self.headers)}) must match cols ({self.cols})"
            )
        return self


class SubField(BaseModel):
    """A field nested inside a repeated_block template entry."""
    model_config = ConfigDict(extra="forbid")
    label: str
    type: Literal["text_field", "text_box"]
    lines: Optional[int] = _F(default=None, ge=1, le=20)


class RepeatedBlockDef(_FieldBase):
    type: Literal["repeated_block"] = "repeated_block"
    count: int = _F(ge=1, le=20)
    template: list[SubField] = _F(min_length=1)


class PairGridDef(_FieldBase):
    type: Literal["pair_grid"] = "pair_grid"
    left_title: str
    right_title: str
    col_headers: list[str] = _F(min_length=1, max_length=4)
    rows: int = _F(default=5, ge=1, le=20)


class CalloutDef(_FieldBase):
    type: Literal["callout"] = "callout"
    text: str


FieldDef = Annotated[
    Union[
        TextFieldDef,
        TextBoxDef,
        CheckboxDef,
        ChecklistDef,
        LabeledRowsDef,
        TableDef,
        RepeatedBlockDef,
        PairGridDef,
        CalloutDef,
    ],
    _F(discriminator="type"),
]


# ---------- Requirement tree ----------

class Requirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    intro: Optional[str] = None         # bold lead-in (e.g., "Do the following:")
    prompt: Optional[str] = None        # the actual question
    notes: Optional[list[str]] = None   # footnote-style explanations
    field: Optional[FieldDef] = None
    children: Optional[list["Requirement"]] = None


# ---------- Reference pages ----------

class ReferenceColumn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Optional[str] = None
    body: str  # markdown-ish, or a relative path ending in .md


class ReferencePage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Optional[str] = None
    body: Optional[str] = None
    columns: Optional[list[ReferenceColumn]] = None

    @model_validator(mode="after")
    def _check_payload(self):
        if not self.body and not self.columns:
            raise ValueError("reference_page must have either 'body' or 'columns'")
        return self


# ---------- Top-level badge ----------

class BadgeMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    slug: str
    description: Optional[str] = None
    cover_image: Optional[str] = None
    requirements_revision: Optional[str] = None
    workbook_version: Optional[str] = None
    # URL of the official Scouting America requirements page for this badge.
    # Defaults to https://www.scouting.org/merit-badges/<slug>/ when unset.
    official_url: Optional[str] = None
    # "active" (default) or "retired" — retired badges are kept for the
    # historical record but excluded from `build-all`.
    status: Literal["active", "retired"] = "active"
    # Prior names this badge was known by (e.g., American Indian Culture was
    # formerly Indian Lore). Informational; surfaced for provenance.
    former_names: Optional[list[str]] = None


class Badge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    badge: BadgeMeta
    requirements: list[Requirement] = _F(min_length=1)
    reference_pages: Optional[list[ReferencePage]] = None

    @model_validator(mode="after")
    def _check_unique_ids(self):
        seen: set[str] = set()
        def walk(reqs: list[Requirement]):
            for r in reqs:
                if r.id in seen:
                    raise ValueError(f"duplicate requirement id: {r.id!r}")
                seen.add(r.id)
                if r.children:
                    walk(r.children)
        walk(self.requirements)
        return self
