"""Home maintenance (5.2): recurring jobs and the appliances they're for,
kept in the rooms of the 3D house.

- A **job** repeats every N days ("Clean the AC filters", every 90 days).
  It's due N days after you last did it. Until you say when you last did
  it, it isn't due: "When did you last do it?" is the first question.
  Tapping Done makes today the last time; Snooze pushes it on a week.
- An **appliance** has its room (and, optionally, the device in the house
  it is), its make and model, when it was bought, its warranty, and its
  manual: a link, or a PDF you upload.
- Due and overdue jobs show on Home and glow in their rooms in the house.
  A notification (topic "home") goes once, on the morning a job comes due,
  with Done and Snooze buttons. A warranty about to run out says so once,
  30 days before.

Room ids are the house's (apps/web/src/house/layout.ts).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.services import json_store

DUE_SOON_DAYS = 7
WARRANTY_WARN_DAYS = 30
MAX_MANUAL_BYTES = 30 * 1024 * 1024


def _id() -> str:
    return uuid.uuid4().hex[:10]


class Job(BaseModel):
    id: str = Field(default_factory=_id, max_length=40)
    title: str = Field(min_length=1, max_length=160)
    room: str = Field(min_length=1, max_length=40)
    appliance: str | None = Field(default=None, max_length=40)
    every_days: int = Field(ge=1, le=3650)
    last_done: str | None = Field(default=None, max_length=10)
    snoozed_until: str | None = Field(default=None, max_length=10)
    notes: str = Field(default="", max_length=2000)


class Manual(BaseModel):
    filename: str = Field(max_length=200)
    stored: str = Field(max_length=80)
    size: int = 0


class Appliance(BaseModel):
    id: str = Field(default_factory=_id, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    room: str = Field(min_length=1, max_length=40)
    device: str | None = Field(default=None, max_length=80)  # its id in the house (a MAC or entity id)
    make: str = Field(default="", max_length=80)
    model: str = Field(default="", max_length=80)
    bought_on: str | None = Field(default=None, max_length=10)
    warranty_until: str | None = Field(default=None, max_length=10)
    manual_url: str = Field(default="", max_length=1000)
    manual: Manual | None = None
    notes: str = Field(default="", max_length=2000)


class Document(BaseModel):
    jobs: list[Job] = Field(default_factory=list, max_length=300)
    appliances: list[Appliance] = Field(default_factory=list, max_length=300)
    seeded: bool = False


# A starting set for 13 Peck Walk, none due until you say when you last did them.
STARTERS: list[dict[str, Any]] = [
    {"title": "Clean the split-system AC filters", "room": "office", "every_days": 90},
    {"title": "Test the smoke alarms", "room": "hall1", "every_days": 30},
    {"title": "Replace the smoke alarm batteries", "room": "hall1", "every_days": 365},
    {"title": "Clear the gutters and roof drains", "room": "terrace", "every_days": 180},
    {"title": "Check the BBQ gas bottle and hoses", "room": "bbq", "every_days": 90},
    {"title": "Clean the BBQ grill and drip tray", "room": "bbq", "every_days": 30},
    {"title": "Clean the dishwasher filter", "room": "kitchen", "every_days": 30},
    {"title": "Clean the rangehood filters", "room": "kitchen", "every_days": 90},
    {"title": "Run a washing machine clean cycle", "room": "store", "every_days": 30},
    {"title": "Clear the balcony drain", "room": "balcony", "every_days": 90},
    {"title": "Service the car", "room": "garage", "every_days": 365},
    {"title": "Lubricate the garage door", "room": "garage", "every_days": 180},
]


def _path() -> Path:
    return json_store.data_path("SIRISOS_MAINTENANCE_PATH", "maintenance.json")


def manuals_dir() -> Path:
    return _path().parent / "manuals"


def load() -> Document:
    raw = json_store.read(_path(), None)
    doc = Document.model_validate(raw) if isinstance(raw, dict) else Document()
    if not doc.seeded:
        doc.jobs += [Job.model_validate(s) for s in STARTERS]
        doc.seeded = True
        save(doc)
    return doc


def save(doc: Document) -> Document:
    json_store.write(_path(), doc.model_dump())
    return doc


def _day(iso: str | None) -> date | None:
    try:
        return date.fromisoformat(iso[:10]) if iso else None
    except ValueError:
        return None


def due_on(job: Job) -> date | None:
    last = _day(job.last_done)
    if last is None:
        return None
    due = last + timedelta(days=job.every_days)
    snoozed = _day(job.snoozed_until)
    return max(due, snoozed) if snoozed else due


def state(job: Job, today: date) -> Literal["unset", "overdue", "due", "soon", "ok"]:
    due = due_on(job)
    if due is None:
        return "unset"
    if due < today:
        return "overdue"
    if due == today:
        return "due"
    return "soon" if (due - today).days <= DUE_SOON_DAYS else "ok"


def job_view(job: Job, today: date) -> dict[str, Any]:
    due = due_on(job)
    return {**job.model_dump(), "due_on": due.isoformat() if due else None, "state": state(job, today),
            "days": (due - today).days if due else None}


def warranty_left(a: Appliance, today: date) -> int | None:
    until = _day(a.warranty_until)
    return (until - today).days if until else None


def overview(today: date) -> dict[str, Any]:
    doc = load()
    jobs = sorted((job_view(j, today) for j in doc.jobs),
                  key=lambda j: ({"overdue": 0, "due": 1, "soon": 2, "ok": 3, "unset": 4}[j["state"]], j["due_on"] or "", j["title"]))
    appliances = [{**a.model_dump(), "warranty_days": warranty_left(a, today)} for a in doc.appliances]
    needs = [j for j in jobs if j["state"] in ("overdue", "due")]
    return {
        "today": today.isoformat(),
        "jobs": jobs,
        "appliances": sorted(appliances, key=lambda a: a["name"].lower()),
        "summary": {
            "overdue": sum(j["state"] == "overdue" for j in jobs),
            "due": sum(j["state"] == "due" for j in jobs),
            "soon": sum(j["state"] == "soon" for j in jobs),
            "unset": sum(j["state"] == "unset" for j in jobs),
            "rooms": sorted({j["room"] for j in needs}),
            "warranties_ending": [a["id"] for a in appliances if a["warranty_days"] is not None and 0 <= a["warranty_days"] <= WARRANTY_WARN_DAYS],
        },
    }


def find_job(doc: Document, job_id: str) -> Job:
    for j in doc.jobs:
        if j.id == job_id:
            return j
    raise LookupError(job_id)


def find_appliance(doc: Document, appliance_id: str) -> Appliance:
    for a in doc.appliances:
        if a.id == appliance_id:
            return a
    raise LookupError(appliance_id)


def done(job_id: str, on: date) -> Job:
    doc = load()
    job = find_job(doc, job_id)
    job.last_done, job.snoozed_until = on.isoformat(), None
    save(doc)
    return job


def snooze(job_id: str, today: date, days: int = 7) -> Job:
    doc = load()
    job = find_job(doc, job_id)
    job.snoozed_until = (max(today, due_on(job) or today) + timedelta(days=days)).isoformat()
    save(doc)
    return job


def push_messages(now: datetime, hour: int = 9) -> list[dict[str, Any]]:
    """Once per job on the morning it comes due (or the first morning it's
    overdue after SirisOS starts), and once per warranty 30 days out."""
    from app.push.notifier import message

    if now.hour < hour:
        return []
    today = now.date()
    doc = load()
    out = []
    for j in doc.jobs:
        if state(j, today) in ("due", "overdue"):
            due = due_on(j)
            late = "" if due == today else f" · {(today - due).days} days overdue"
            out.append(message(f"home:job:{j.id}:{due.isoformat()}", "home", j.title, f"Due{late}. {j.notes}".strip()[:200], "/house?view=maintenance",
                               target=f"homejob:{j.id}", actions=[{"id": "done", "title": "Done"}, {"id": "snooze", "title": "Next week"}]))
    for a in doc.appliances:
        left = warranty_left(a, today)
        if left is not None and 0 <= left <= WARRANTY_WARN_DAYS:
            out.append(message(f"home:warranty:{a.id}:{a.warranty_until}", "home", f"{a.name}: warranty ends in {left} days",
                               f"On {a.warranty_until}. Anything to claim, do it now.", "/house?view=maintenance"))
    return out


def save_manual(appliance_id: str, filename: str, raw: bytes) -> Appliance:
    suffix = Path(filename).suffix.lower()
    if suffix not in (".pdf", ".png", ".jpg", ".jpeg"):
        raise ValueError("Upload the manual as a PDF or a photo.")
    if len(raw) > MAX_MANUAL_BYTES:
        raise ValueError("That file is over 30 MB.")
    doc = load()
    a = find_appliance(doc, appliance_id)
    folder = manuals_dir()
    folder.mkdir(parents=True, exist_ok=True)
    stored = f"{a.id}{suffix}"
    if a.manual and a.manual.stored != stored:
        (folder / a.manual.stored).unlink(missing_ok=True)
    (folder / stored).write_bytes(raw)
    a.manual = Manual(filename=Path(filename).name[:200], stored=stored, size=len(raw))
    save(doc)
    return a


def remove_appliance(appliance_id: str) -> None:
    doc = load()
    a = find_appliance(doc, appliance_id)
    if a.manual:
        (manuals_dir() / a.manual.stored).unlink(missing_ok=True)
    doc.appliances = [x for x in doc.appliances if x.id != appliance_id]
    for j in doc.jobs:
        if j.appliance == appliance_id:
            j.appliance = None
    save(doc)


