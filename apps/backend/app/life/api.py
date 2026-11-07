"""Life admin, from SirisAI (SirisOS 7.3): the document inbox, bills and
subscriptions found in email, trips coming up, and how fast SirisAI is
answering. The data is SirisAI's (4.6); these pass it through.

    GET    /api/v1/life/documents             ?q=
    POST   /api/v1/life/documents             a PDF, photo or text file of a letter or bill
    GET    /api/v1/life/documents/{id}
    DELETE /api/v1/life/documents/{id}
    GET    /api/v1/life/bills                 ?all=
    POST   /api/v1/life/bills/scan
    POST   /api/v1/life/bills/{id}/status     {"status": "done" | "ignored" | "open"}
    GET    /api/v1/life/travel
    POST   /api/v1/life/travel/away           ?on=
    GET    /api/v1/life/speed                 per-stage reply times and the background jobs
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile
from pydantic import BaseModel, Field

from app.auth import require_user
from app.hub import sirisai_api
from app.hub.service import Hub, get_hub

router = APIRouter(prefix="/api/v1/life", tags=["life"], dependencies=[Depends(require_user)])


def _fail(exc: sirisai_api.SirisAIError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=str(exc))


async def _call(hub: Hub, method: str, path: str, timeout: float = 30.0, **kwargs: Any) -> Any:
    try:
        response = await sirisai_api.raw(hub, method, path, timeout=timeout, **kwargs)
    except sirisai_api.SirisAIError as exc:
        raise _fail(exc) from None
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text[:300]
        raise HTTPException(status_code=response.status_code if response.status_code in (404, 413, 422) else 502, detail=f"SirisAI: {detail}")
    return response.json() if response.content else None


@router.get("/documents")
async def documents(q: str = Query("", max_length=200), hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "GET", "/siris/documents", params={"q": q})


@router.post("/documents")
async def add_document(file: UploadFile = File(...), hub: Hub = Depends(get_hub)) -> Any:
    data = await file.read()
    return await _call(hub, "POST", "/siris/documents", timeout=300.0,
                       files={"file": (file.filename or "document", data, file.content_type or "application/octet-stream")})


@router.get("/documents/{doc_id}")
async def document(doc_id: int = Path(ge=1), hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "GET", f"/siris/documents/{doc_id}")


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: int = Path(ge=1), hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "DELETE", f"/siris/documents/{doc_id}")


@router.get("/bills")
async def bills(all: bool = False, hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "GET", "/siris/bills", params={"all": str(all).lower()})


@router.post("/bills/scan")
async def scan_bills(hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "POST", "/siris/bills/scan", timeout=180.0)


class BillStatus(BaseModel):
    status: str = Field(pattern=r"^(open|done|ignored)$")


@router.post("/bills/{bill_id}/status")
async def bill_status(request: BillStatus, bill_id: int = Path(ge=1), hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "POST", f"/siris/bills/{bill_id}/status", json=request.model_dump())


@router.get("/travel")
async def travel(hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "GET", "/siris/travel", timeout=60.0)


@router.post("/travel/away")
async def travel_away(on: bool = True, hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "POST", "/siris/travel/away", params={"on": str(on).lower()})


@router.get("/speed")
async def speed(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    timings = await sirisai_api.get(hub, "/siris/timings")
    jobs = await sirisai_api.get(hub, "/siris/scheduler/jobs")
    if timings is None and jobs is None:
        raise HTTPException(status_code=503, detail="SirisAI isn't reachable, or is older than 4.6.")
    return {"timings": timings or {"stages": {}, "recent": []}, "jobs": jobs or []}


# -- things, people and news (7.6, SirisAI 4.9) --------------------------------


@router.get("/things")
async def things(q: str = Query("", max_length=200), hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "GET", "/siris/things", params={"q": q})


@router.post("/things")
async def add_thing(body: dict[str, Any], hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "POST", "/siris/things", json=body)


@router.put("/things/{thing_id}")
async def update_thing(body: dict[str, Any], thing_id: int = Path(ge=1), hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "PUT", f"/siris/things/{thing_id}", json=body)


@router.delete("/things/{thing_id}")
async def delete_thing(thing_id: int = Path(ge=1), hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "DELETE", f"/siris/things/{thing_id}")


@router.get("/people")
async def people(hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "GET", "/siris/people")


@router.post("/people")
async def add_person(body: dict[str, Any], hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "POST", "/siris/people", json=body)


@router.put("/people/{person_id}")
async def update_person(body: dict[str, Any], person_id: int = Path(ge=1), hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "PUT", f"/siris/people/{person_id}", json=body)


@router.delete("/people/{person_id}")
async def delete_person(person_id: int = Path(ge=1), hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "DELETE", f"/siris/people/{person_id}")


@router.get("/people/{person_id}/gifts")
async def person_gifts(person_id: int = Path(ge=1), hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "GET", f"/siris/people/{person_id}/gifts")


@router.get("/news")
async def news(hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "GET", "/siris/news", timeout=45.0)


@router.get("/trial")
async def speed_trial(hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "GET", "/siris/timings/trial")


@router.post("/trial")
async def start_speed_trial(days: int = Query(14, ge=2, le=60), hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "POST", "/siris/timings/trial", params={"days": days})


@router.get("/reliability")
async def reliability(hub: Hub = Depends(get_hub)) -> Any:
    return await _call(hub, "GET", "/siris/reliability")
