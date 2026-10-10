"""The career document (ADR 111): one JSON file, written atomically, seeded
from defaults.py the first time it's read.

What Brad edits here (pathway progress, goals, evidence) lives in this file.
CPD is never typed in here: Engineers Australia is where it's logged, and
`cpd.records` only ever comes from importing its export (cpd.py).
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.career import defaults

StepStatus = Literal["todo", "doing", "done", "na"]
GoalStatus = Literal["active", "done", "paused"]
Category = Literal["area", "risk", "business", "other"]


def career_path() -> Path:
    return Path(os.getenv("SIRISOS_CAREER_PATH", "/app/data/career.json"))


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class Step(BaseModel):
    id: str = Field(default_factory=new_id, max_length=40)
    title: str = Field(min_length=1, max_length=160)
    detail: str = Field(default="", max_length=1000)
    status: StepStatus = "todo"
    note: str = Field(default="", max_length=2000)
    done_on: str | None = Field(default=None, max_length=10)


class Pathway(BaseModel):
    id: str = Field(default_factory=new_id, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    body: str = Field(default="", max_length=120)
    url: str = Field(default="", max_length=500)
    summary: str = Field(default="", max_length=600)
    steps: list[Step] = Field(default_factory=list, max_length=40)


class Element(BaseModel):
    id: str = Field(max_length=10)
    unit: str = Field(max_length=60)
    title: str = Field(max_length=120)


class EvidenceLink(BaseModel):
    label: str = Field(min_length=1, max_length=160)
    # A SirisOS route ("/brain?q=…", "/engineering/projects/…") or any http(s) address.
    url: str = Field(min_length=1, max_length=1000)


class Evidence(BaseModel):
    id: str = Field(default_factory=new_id, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=4000)
    date: str | None = Field(default=None, max_length=10)
    elements: list[str] = Field(default_factory=list, max_length=16)
    links: list[EvidenceLink] = Field(default_factory=list, max_length=12)


class Goal(BaseModel):
    id: str = Field(default_factory=new_id, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    target_date: str | None = Field(default=None, max_length=10)
    next_step: str = Field(default="", max_length=400)
    status: GoalStatus = "active"
    note: str = Field(default="", max_length=2000)


class CpdRecord(BaseModel):
    id: str
    date: str | None = None
    title: str
    provider: str = ""
    type: str = ""
    hours: float = 0.0
    # Hours per requirement category, from the export's own columns when it has them.
    split: dict[str, float] = Field(default_factory=dict)
    # How `split` was decided: "export" (its columns), "guess" (keywords) or "you".
    basis: Literal["export", "guess", "you"] = "guess"
    notes: str = ""


class CpdImport(BaseModel):
    at: str
    filename: str
    added: int
    updated: int
    unchanged: int


class Cpd(BaseModel):
    records: list[CpdRecord] = Field(default_factory=list)
    imports: list[CpdImport] = Field(default_factory=list)
    # Brad's own category for a record, kept across re-imports.
    overrides: dict[str, Category] = Field(default_factory=dict)


class Profile(BaseModel):
    discipline: str = Field(default="Civil", max_length=60)
    area_of_practice: str = Field(default="Water infrastructure", max_length=120)
    brain_notes: list[str] = Field(default_factory=lambda: list(defaults.BRAIN_NOTES), max_length=10)


class CareerDocument(BaseModel):
    profile: Profile = Field(default_factory=Profile)
    pathways: list[Pathway] = Field(default_factory=list, max_length=12)
    elements: list[Element] = Field(default_factory=list, max_length=40)
    evidence: list[Evidence] = Field(default_factory=list, max_length=500)
    goals: list[Goal] = Field(default_factory=list, max_length=50)
    cpd: Cpd = Field(default_factory=Cpd)
    updated_at: str | None = None


class CareerEdit(BaseModel):
    """What the Career tab saves. CPD isn't part of it: that only changes by import."""

    profile: Profile
    pathways: list[Pathway] = Field(max_length=12)
    evidence: list[Evidence] = Field(max_length=500)
    goals: list[Goal] = Field(max_length=50)


def seeded() -> CareerDocument:
    return CareerDocument(
        pathways=[Pathway.model_validate(p) for p in copy.deepcopy(defaults.PATHWAYS)],
        elements=[Element.model_validate(e) for e in defaults.STAGE2_ELEMENTS],
    )


def load() -> CareerDocument:
    path = career_path()
    if not path.exists():
        return seeded()
    doc = CareerDocument.model_validate_json(path.read_text(encoding="utf-8"))
    if not doc.elements:
        doc.elements = [Element.model_validate(e) for e in defaults.STAGE2_ELEMENTS]
    return doc


def save(doc: CareerDocument) -> CareerDocument:
    doc = doc.model_copy(update={"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    path = career_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=".career-", suffix=".tmp", delete=False) as handle:
        handle.write(json.dumps(doc.model_dump(), indent=2, ensure_ascii=False) + "\n")
        temp = Path(handle.name)
    temp.replace(path)
    return doc


def apply_edit(edit: CareerEdit) -> CareerDocument:
    doc = load()
    valid = {e.id for e in doc.elements}
    evidence = [e.model_copy(update={"elements": [x for x in dict.fromkeys(e.elements) if x in valid]}) for e in edit.evidence]
    return save(doc.model_copy(update={"profile": edit.profile, "pathways": edit.pathways, "evidence": evidence, "goals": edit.goals}))
