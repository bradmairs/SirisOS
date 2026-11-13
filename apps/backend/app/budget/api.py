"""The budget (7.7). See service.py.

    GET  /api/v1/budget              income, the three sections, monthly totals and history
    PUT  /api/v1/budget              the whole budget (income and sections), saved as one
    GET  /api/v1/budget/from-bills   SirisAI's renewals and bills found in email, as expense lines to add
    GET  /api/v1/budget/pay-days     (9.5) each income line's next pay day; `today` lists the ones paid today, for Home
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
async def put_budget(body: dict[str, Any], hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    try:
        out = service.save(body)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    try:  # 9.5: SirisAI's pay day reminders follow the budget; it's saved either way
        await service.sync_pay_reminders(hub)
    except Exception:  # noqa: BLE001
        pass
    return out


@router.get("/pay-days")
def get_pay_days() -> dict[str, Any]:
    doc = service.get()
    days = doc["pay_days"]
    return {"currency": doc.get("currency", "AUD"), "pay_days": days, "today": [p for p in days if p["days"] == 0]}


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
