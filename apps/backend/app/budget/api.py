"""The budget (7.7). See service.py.

    GET  /api/v1/budget              income, the three sections, monthly totals and history
    PUT  /api/v1/budget              the whole budget (income and sections), saved as one
    GET  /api/v1/budget/from-bills   SirisAI's renewals and bills found in email, as expense lines to add
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_user
from app.budget import service
from app.hub import sirisai_api
from app.hub.service import Hub, get_hub

router = APIRouter(prefix="/api/v1/budget", tags=["budget"], dependencies=[Depends(require_user)])


@router.get("")
def get_budget() -> dict[str, Any]:
    return service.get()


@router.put("")
def put_budget(body: dict[str, Any]) -> dict[str, Any]:
    try:
        return service.save(body)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/from-bills")
async def from_bills(hub: Hub = Depends(get_hub)) -> list[dict[str, Any]]:
    """Each subscription or bill SirisAI found in email, as an expense line
    (renewals are taken as monthly unless the email says yearly)."""
    bills = await sirisai_api.get(hub, "/siris/bills", params={"all": "true"}) or []
    lines, seen = [], set()
    for b in bills:
        if b.get("amount") is None or b.get("status") == "ignored" or b.get("service") in seen:
            continue
        seen.add(b.get("service"))
        yearly = "year" in (b.get("subject") or "").lower() or "annual" in (b.get("subject") or "").lower()
        lines.append({"name": b.get("service") or "Bill", "amount": b["amount"], "every": "yearly" if yearly else "monthly",
                      "note": b.get("label") or ""})
    return lines
