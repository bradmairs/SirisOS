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
    # Calendar suggestions already dealt with: key -> "logged" (in EA) or "ignored".
    suggestions: dict[str, Literal["logged", "ignored"]] = Field(default_factory=dict)


class Profile(BaseModel):
    discipline: str = Field(default="Civil", max_length=60)
    area_of_practice: str = Field(default="Water infrastructure", max_length=120)
    brain_notes: list[str] = Field(default_factory=lambda: list(defaults.BRAIN_NOTES), max_length=10)


class UploadedFile(BaseModel):
    filename: str = Field(max_length=200)
    stored: str = Field(max_length=80)
    size: int = 0
    at: str


class Bia(BaseModel):
    required: bool | None = None
    state: Literal["VIC", "WA", "ACT"] | None = None
    cv: bool = False
    building_cpd: bool = False
    statement: str = Field(default="", max_length=8000)


class Application(BaseModel):
    area_of_practice: str = Field(default="", max_length=120)
    additional_area: str = Field(default="", max_length=120)
    additional_reason: str = Field(default="", max_length=2000)
    # How CPD is evidenced: the EA log export, or the questionnaire.
    cpd_evidence: Literal["log", "questionnaire"] | None = None
    cpd_answers: dict[str, str] = Field(default_factory=dict)
    part1: dict[str, Literal["yes", "not_sure"]] = Field(default_factory=dict)
    part2: dict[str, Literal["yes", "no"]] = Field(default_factory=dict)
    part3: dict[str, str] = Field(default_factory=dict)
    signed: bool = False
    bia: Bia = Field(default_factory=Bia)
    files: dict[str, UploadedFile] = Field(default_factory=dict)


class CareerDocument(BaseModel):
    profile: Profile = Field(default_factory=Profile)
    pathways: list[Pathway] = Field(default_factory=list, max_length=12)
    elements: list[Element] = Field(default_factory=list, max_length=40)
    evidence: list[Evidence] = Field(default_factory=list, max_length=500)
    goals: list[Goal] = Field(default_factory=list, max_length=50)
    cpd: Cpd = Field(default_factory=Cpd)
    # The Chartered application forms (application.py, 4.6).
    application: Application = Field(default_factory=Application)
    # Which default additions this file has had (see _upgrade).
    defaults_version: int = 1
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
        defaults_version=max(defaults.UPGRADES, default=1),
    )


def _upgrade(doc: CareerDocument) -> CareerDocument:
    """Add steps that came with later versions to a file made before them,
    once: a step removed after that stays removed."""
    latest = max(defaults.UPGRADES, default=1)
    if doc.defaults_version >= latest:
        return doc
    by_id = {p["id"]: p for p in defaults.PATHWAYS}
    for version in sorted(v for v in defaults.UPGRADES if v > doc.defaults_version):
        pathway_id, step_ids, after = defaults.UPGRADES[version]
        pathway = next((p for p in doc.pathways if p.id == pathway_id), None)
        if pathway is None:
            continue
        have = {s.id for s in pathway.steps}
        new = [Step.model_validate(s) for s in by_id[pathway_id]["steps"] if s["id"] in step_ids and s["id"] not in have]
        at = next((i + 1 for i, s in enumerate(pathway.steps) if s.id == after), len(pathway.steps))
        pathway.steps[at:at] = new
    doc.defaults_version = latest
    return doc


def load() -> CareerDocument:
    path = career_path()
    if not path.exists():
        return seeded()
    doc = CareerDocument.model_validate_json(path.read_text(encoding="utf-8"))
    if not doc.elements:
        doc.elements = [Element.model_validate(e) for e in defaults.STAGE2_ELEMENTS]
    return _upgrade(doc)


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
