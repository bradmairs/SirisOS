"""The Health section. See service.py; the data and scores are SirisAI's (5.8).

    GET    /api/v1/health                   readiness, sleep, activity, vitals, weight, insights, bedtime
    GET    /api/v1/health/today             today's readiness and energy (Home, the brief)
    POST   /api/v1/health/log               {"kind": "water", "amount": 250} or {"kind": "symptom", "text": "..."}
    POST   /api/v1/health/meal              a meal photo, for a rough estimate
    GET    /api/v1/health/goals             goals tied to a health number, with progress
    POST   /api/v1/health/goals             {"metric": "running_km", "target": 1000, "end": "2026-12-31"}
    POST   /api/v1/health/apple-export      the Health app's export.zip, for years of history
    GET    /api/v1/health/export.csv        ?start=&end=
    GET    /api/v1/health/report            a printable summary for a doctor
    DELETE /api/v1/health/data              ?start=&end=&source=
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from app.auth import require_user
from app.health import service
from app.hub import sirisai_api
from app.hub.service import Hub, get_hub

router = APIRouter(prefix="/api/v1/health", tags=["health"], dependencies=[Depends(require_user)])


class LogRequest(BaseModel):
    kind: str = Field(pattern=r"^(water|caffeine|alcohol|mood|energy|symptom|supplement|medication|feeling|note)$")
    amount: float | None = Field(default=None, ge=0, le=20000)
    text: str = Field(default="", max_length=500)


class GoalRequest(BaseModel):
    metric: str = Field(pattern=r"^(running_km|walk_run_km|exercise_minutes|steps|active_energy_kcal|mindful_minutes)$")
    target: float = Field(gt=0, le=10_000_000)
    start: str = Field(default="", pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    title: str = Field(default="", max_length=120)


def _fail(exc: sirisai_api.SirisAIError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=str(exc))


@router.get("")
async def get_health(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.overview(hub)


@router.get("/today")
async def get_today(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.today(hub)


@router.post("/log")
async def log(body: LogRequest, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    try:
        return {"logged": await service.tool(hub, "health_log", body.model_dump(exclude_none=True))}
    except sirisai_api.SirisAIError as exc:
        raise _fail(exc) from None


@router.get("/goals")
async def goals(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    try:
        return {"goals": await service.tool(hub, "health_goals") or []}
    except sirisai_api.SirisAIError:
        return {"goals": []}


@router.post("/goals")
async def add_goal(body: GoalRequest, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    try:
        return {"goal": await service.tool(hub, "health_set_goal", {k: v for k, v in body.model_dump().items() if v})}
    except sirisai_api.SirisAIError as exc:
        raise _fail(exc) from None


async def _upload(hub: Hub, path: str, file: UploadFile, params: dict[str, Any] | None = None, timeout: float = 120.0) -> Any:
    data = await file.read()
    try:
        response = await sirisai_api.raw(hub, "POST", path, timeout=timeout, params=params,
                                         files={"file": (file.filename or "upload", data, file.content_type or "application/octet-stream")})
    except sirisai_api.SirisAIError as exc:
        raise _fail(exc) from None
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text[:300]
        raise HTTPException(status_code=response.status_code if response.status_code in (404, 413, 422) else 502, detail=f"SirisAI: {detail}")
    return response.json()


@router.post("/apple-export")
async def apple_export(file: UploadFile = File(...), years: int = Query(5, ge=1, le=20), hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await _upload(hub, "/siris/health/apple-export", file, {"years": years}, timeout=900.0)


@router.post("/meal")
async def meal(file: UploadFile = File(...), hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await _upload(hub, "/siris/health/meal", file)


async def _get(hub: Hub, path: str, params: dict[str, Any]) -> Any:
    try:
        response = await sirisai_api.raw(hub, "GET", path, params={k: v for k, v in params.items() if v}, timeout=120.0)
    except sirisai_api.SirisAIError as exc:
        raise _fail(exc) from None
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code if response.status_code in (403, 404, 422) else 502, detail="SirisAI couldn't do that.")
    return response


@router.get("/export.csv")
async def export_csv(start: str = "", end: str = "", hub: Hub = Depends(get_hub)) -> Response:
    response = await _get(hub, "/siris/health/export.csv", {"start": start, "end": end})
    return Response(response.content, media_type="text/csv",
                    headers={"Content-Disposition": response.headers.get("content-disposition", 'attachment; filename="health.csv"')})


@router.get("/report", response_class=HTMLResponse)
async def report(days: int = Query(90, ge=7, le=730), hub: Hub = Depends(get_hub)) -> HTMLResponse:
    response = await _get(hub, "/siris/health/report", {"days": days})
    return HTMLResponse(response.text)


@router.delete("/data")
async def delete_data(start: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"), end: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
                      source: str = "", hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    try:
        response = await sirisai_api.raw(hub, "DELETE", "/siris/health/data", params={"start": start, "end": end, **({"source": source} if source else {})})
    except sirisai_api.SirisAIError as exc:
        raise _fail(exc) from None
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="SirisAI couldn't delete that.")
    return response.json()
