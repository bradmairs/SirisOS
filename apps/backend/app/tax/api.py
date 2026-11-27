"""Tax-claimable receipts (11.18). See service.py.

    GET    /api/v1/tax?fy=2027           the financial year (by the year it ends): claims, totals, checks, receipts to sort
    POST   /api/v1/tax/claims            a claim (by hand, or from a receipt with `doc_id`)
    PUT    /api/v1/tax/claims/{id}       change one
    DELETE /api/v1/tax/claims/{id}
    POST   /api/v1/tax/not-tax/{doc_id}  a receipt from email that isn't a tax one (`on: false` puts it back)
    PUT    /api/v1/tax/years/{fy}        `wfh_hours`, `car_km`
    GET    /api/v1/tax/export?fy=        the year's claims as a CSV for your tax return or agent
"""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response

from app.auth import require_user
from app.hub import sirisai_api
from app.hub.service import Hub, get_hub
from app.tax import service

router = APIRouter(prefix="/api/v1/tax", tags=["tax"], dependencies=[Depends(require_user)])


async def _receipts(hub: Hub) -> tuple[list[dict[str, Any]], str | None]:
    """SirisAI's receipts kept from email; none (and why) if it can't be reached."""
    try:
        r = await sirisai_api.raw(hub, "GET", "/siris/documents", params={"kind": "receipt", "limit": 300}, timeout=20.0)
    except sirisai_api.SirisAIError as exc:
        return [], str(exc)[:200]
    if r.status_code >= 400:
        return [], f"SirisAI answered {r.status_code}"
    data = r.json() if r.content else []
    return (data if isinstance(data, list) else []), None


@router.get("")
async def year(fy: int | None = Query(None, ge=2000, le=2100), hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    receipts, problem = await _receipts(hub)
    out = service.year(fy or service.current_fy(), receipts)
    out["categories"] = [{"id": k, "label": v["label"], "hint": v["hint"]} for k, v in service.CATEGORIES.items()]
    out["email_problem"] = problem
    return out


def _bad(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


@router.post("/claims")
def add(body: dict[str, Any]) -> dict[str, Any]:
    try:
        return service.add(body)
    except (ValueError, TypeError) as exc:
        raise _bad(ValueError(str(exc))) from None


@router.put("/claims/{claim_id}")
def change(body: dict[str, Any], claim_id: str = Path(max_length=40)) -> dict[str, Any]:
    try:
        return service.change(claim_id, body)
    except KeyError:
        raise HTTPException(status_code=404, detail="No such claim.") from None
    except (ValueError, TypeError) as exc:
        raise _bad(ValueError(str(exc))) from None


@router.delete("/claims/{claim_id}")
def remove(claim_id: str = Path(max_length=40)) -> dict[str, bool]:
    try:
        service.remove(claim_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="No such claim.") from None
    return {"ok": True}


@router.post("/not-tax/{doc_id}")
def not_tax(doc_id: int = Path(ge=1), on: bool = True) -> dict[str, bool]:
    service.not_tax(doc_id, on)
    return {"ok": True}


@router.put("/years/{fy}")
def set_year(body: dict[str, Any], fy: int = Path(ge=2000, le=2100)) -> dict[str, Any]:
    try:
        return service.set_year(fy, body)
    except (ValueError, TypeError) as exc:
        raise _bad(ValueError(str(exc))) from None


@router.get("/export")
def export(fy: int = Query(..., ge=2000, le=2100)) -> Response:
    buf = io.StringIO()
    csv.writer(buf).writerows(service.csv_rows(fy))
    name = f"Tax claims {service.fy_label(fy)}.csv"
    return Response(content=buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})
