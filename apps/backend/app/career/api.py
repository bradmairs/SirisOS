"""Career API (ADR 110): pathways to Chartered and registration, competency
evidence, goals, and CPD imported from Engineers Australia."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.auth import require_user
from app.career import cpd, defaults, store

router = APIRouter(prefix="/api/v1/career", tags=["career"], dependencies=[Depends(require_user)])


def overview(doc: store.CareerDocument) -> dict[str, Any]:
    """Progress at a glance: CPD against the requirement, each pathway's
    next step, which competency elements have no evidence yet, and goals."""
    pathways = []
    for p in doc.pathways:
        live = [s for s in p.steps if s.status != "na"]
        done = sum(s.status == "done" for s in live)
        nxt = next((s for s in p.steps if s.status in ("doing", "todo")), None)
        pathways.append({"id": p.id, "name": p.name, "done": done, "total": len(live),
                         "next": {"id": nxt.id, "title": nxt.title, "status": nxt.status} if nxt else None})
    counts = {e.id: 0 for e in doc.elements}
    for ev in doc.evidence:
        for el in ev.elements:
            if el in counts:
                counts[el] += 1
    gaps = [e.model_dump() for e in doc.elements if counts[e.id] == 0]
    goals = [g.model_dump() for g in doc.goals if g.status == "active"]
    goals.sort(key=lambda g: g["target_date"] or "9999")
    summary = cpd.summary(doc)
    steps = []
    for p in pathways:
        if p["next"] and p["done"] < p["total"]:
            steps.append({"title": p["next"]["title"], "detail": p["name"], "kind": "pathway"})
    for g in goals:
        if g["next_step"]:
            steps.append({"title": g["next_step"], "detail": g["title"], "kind": "goal"})
    for m in summary["minimums"]:
        if m["short"] > 0:
            steps.append({"title": f"{m['short']:g} more hours of {m['label'].lower()} CPD", "detail": "CPD minimum", "kind": "cpd"})
    if summary["short"] > 0:
        steps.append({"title": f"{summary['short']:g} more CPD hours in this 3-year window", "detail": "CPD total", "kind": "cpd"})
    if gaps:
        steps.append({"title": f"Evidence for {len(gaps)} competenc{'y' if len(gaps) == 1 else 'ies'}, starting with {gaps[0]['title'].lower()}",
                      "detail": "Chartered", "kind": "evidence"})
    return {
        "cpd": summary,
        "pathways": pathways,
        "competencies": {"total": len(doc.elements), "evidenced": len(doc.elements) - len(gaps), "counts": counts, "gaps": gaps},
        "goals": goals,
        "next_steps": steps[:8],
        "categories": defaults.CPD_CATEGORIES,
    }


@router.get("")
def get_career() -> dict[str, Any]:
    doc = store.load()
    return {"document": doc.model_dump(), "overview": overview(doc)}


@router.get("/overview")
def get_overview() -> dict[str, Any]:
    return overview(store.load())


@router.put("")
def put_career(edit: store.CareerEdit) -> dict[str, Any]:
    doc = store.apply_edit(edit)
    return {"document": doc.model_dump(), "overview": overview(doc)}


@router.post("/cpd/import")
async def import_cpd(file: UploadFile = File(...)) -> dict[str, Any]:
    raw = await file.read(cpd.MAX_UPLOAD_BYTES + 1)
    try:
        records = cpd.parse(raw, file.filename or "")
    except cpd.CpdImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    doc, result = cpd.merge(store.load(), records, file.filename or "upload")
    return {"import": result.model_dump(), "document": doc.model_dump(), "overview": overview(doc)}


class Recategorise(BaseModel):
    category: store.Category | None = None


@router.put("/cpd/{record_id}/category")
def recategorise(record_id: str, body: Recategorise) -> dict[str, Any]:
    """Correct a guessed category (null puts the guess back). Survives re-imports."""
    doc = store.load()
    if not any(r.id == record_id for r in doc.cpd.records):
        raise HTTPException(status_code=404, detail="No CPD activity with that id.")
    overrides = dict(doc.cpd.overrides)
    if body.category is None:
        overrides.pop(record_id, None)
    else:
        overrides[record_id] = body.category
    doc = store.save(doc.model_copy(update={"cpd": doc.cpd.model_copy(update={"overrides": overrides})}))
    return {"document": doc.model_dump(), "overview": overview(doc)}
