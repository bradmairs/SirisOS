"""The budget (7.7). See service.py.

    GET  /api/v1/budget              income, the three sections, monthly totals and history
    PUT  /api/v1/budget              the whole budget (income and sections), saved as one
    GET  /api/v1/budget/split        (11.12) the saved split between incomes, checked against today's budget
    POST /api/v1/budget/split/preview  {sources, method, personal}: what a split would be
    PUT  /api/v1/budget/split        {sources, method, personal}: keep it
    GET  /api/v1/budget/from-bills   SirisAI's renewals and bills found in email, as expense lines to add
    POST /api/v1/budget/actuals/import      (9.9) a bank's CSV export (multipart `file`, `account`)
    GET  /api/v1/budget/actuals?month=      the month's spending against the plan, line by line, and what's to sort
    GET  /api/v1/budget/actuals/imports     (10.3) the files added, each with its transactions still in
    DELETE /api/v1/budget/actuals/imports/{id}  take a file's transactions out ("earlier": the ones from before files were listed)
    PUT  /api/v1/budget/actuals/{id}        put a transaction on a line (`line_id`, or "ignore"); the shop is learned
    GET  /api/v1/budget/balances            accounts, latest balances, goal progress and forecasts, net worth by month
    POST /api/v1/budget/balances            a balance for an account (`account`, `balance`, optional `kind`, `line_id`, `date`)
    PATCH/DELETE /api/v1/budget/accounts/{id}  rename, change kind or goal line, or remove
    GET  /api/v1/budget/cashflow            (10.1) the everyday balance day by day to after the next pay, and its lowest point
    GET  /api/v1/budget/recurring           recurring charges found in the imports, flagged (price up, not in the budget, check)
    PUT  /api/v1/budget/recurring/{id}      `status`: keep, cancelling, ignore, or null
    GET  /api/v1/budget/suggestions         after two full months, lines that usually run over or under, with a new amount
    GET  /api/v1/budget/pay-days     (9.5) each income line's next pay day; `today` lists the ones paid today, for Home
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.auth import require_user
from app.budget import actuals, forecast, service
from app.hub import sirisai_api
from app.hub.service import Hub, get_hub

router = APIRouter(prefix="/api/v1/budget", tags=["budget"], dependencies=[Depends(require_user)])


@router.get("")
def get_budget() -> dict[str, Any]:
    return service.get()


class SplitIn(BaseModel):
    sources: list[str] = Field(default_factory=list, max_length=30)  # empty: every income source
    method: str = Field(default="blocks", pattern="^(blocks|income|equal|lines)$")
    personal: dict[str, str] = Field(default_factory=dict)  # line id -> source id, or "shared"
    blocks: dict[str, str] = Field(default_factory=dict)  # 11.13: block key -> "auto", "shared" or an income id


@router.get("/split")
def get_split() -> dict[str, Any]:
    """The saved split between incomes, checked against today's budget (11.12)."""
    from app.budget import split

    return split.get()


@router.post("/split/preview")
def preview_split(body: SplitIn) -> dict[str, Any]:
    """What a split would be, without keeping it (11.12)."""
    from app.budget import split

    try:
        return split.compute(service.get(), body.sources, body.method, body.personal, body.blocks)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/split")
def put_split(body: SplitIn) -> dict[str, Any]:
    """Keep a split: worked out now, and checked against the budget from then on (11.12)."""
    from app.budget import split

    try:
        return split.save(body.sources, body.method, body.personal, body.blocks)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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


# -- 9.9: actual spending and balances -----------------------------------------------------------------

_ID = re.compile(r"[a-z0-9]{6,32}")
_MONTH = re.compile(r"\d{4}-\d{2}")
MAX_CSV = 5 * 1024 * 1024


def _id(value: str) -> str:
    if not _ID.fullmatch(value):
        raise HTTPException(status_code=404, detail="Not found.")
    return value


@router.post("/actuals/import")
async def import_actuals(file: UploadFile = File(...), account: str = Form("")) -> dict[str, Any]:
    raw = await file.read(MAX_CSV + 1)
    if len(raw) > MAX_CSV:
        raise HTTPException(status_code=413, detail="That file is too big (5 MB at most).")
    try:
        out = actuals.import_csv(raw, account, (file.filename or "").rsplit("/", 1)[-1])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return {**out, "month": actuals.month()}


@router.get("/actuals")
def get_actuals(month: str | None = None) -> dict[str, Any]:
    if month and not _MONTH.fullmatch(month):
        raise HTTPException(status_code=422, detail="Month as YYYY-MM.")
    return actuals.month(month)


@router.get("/actuals/imports")
def get_imports() -> dict[str, Any]:
    return {"imports": actuals.imports()}


@router.delete("/actuals/imports/{import_id}")
def delete_import(import_id: str) -> dict[str, Any]:
    if import_id != actuals.EARLIER:
        _id(import_id)
    gone = actuals.remove_import(import_id)
    if gone is None:
        raise HTTPException(status_code=404, detail="No such file.")
    return {"removed": gone, "month": actuals.month()}


class Assign(BaseModel):
    line_id: str | None = Field(None, max_length=40)
    learn: bool = True


@router.put("/actuals/{tx_id}")
def assign_actual(tx_id: str, body: Assign) -> dict[str, Any]:
    out = actuals.assign(_id(tx_id), body.line_id, body.learn)
    if out is None:
        raise HTTPException(status_code=404, detail="No such transaction.")
    return out


@router.get("/balances")
def get_balances() -> dict[str, Any]:
    return actuals.balances()


class BalanceIn(BaseModel):
    account: str = Field(..., min_length=1, max_length=60)
    balance: float
    kind: str | None = Field(None, max_length=20)
    line_id: str | None = Field(None, max_length=40)
    date: dt.date | None = None


@router.post("/balances")
def add_balance(body: BalanceIn) -> dict[str, Any]:
    return actuals.set_balance(body.account, body.balance, body.date, body.kind, body.line_id)


class AccountChange(BaseModel):
    name: str | None = Field(None, max_length=60)
    kind: str | None = Field(None, max_length=20)
    line_id: str | None = Field(None, max_length=40)


@router.patch("/accounts/{account_id}")
def change_account(account_id: str, body: AccountChange) -> dict[str, Any]:
    out = actuals.change_account(_id(account_id), body.name, body.kind, body.line_id)
    if out is None:
        raise HTTPException(status_code=404, detail="No such account.")
    return out


@router.delete("/accounts/{account_id}")
def remove_account(account_id: str) -> dict[str, Any]:
    out = actuals.change_account(_id(account_id), remove=True)
    if out is None:
        raise HTTPException(status_code=404, detail="No such account.")
    return out


# -- 10.1: looking ahead -------------------------------------------------------------------------------

@router.get("/cashflow")
def get_cashflow() -> dict[str, Any]:
    return forecast.cashflow()


@router.get("/recurring")
def get_recurring() -> dict[str, Any]:
    return forecast.recurring_overview()


class Mark(BaseModel):
    status: str | None = Field(None, pattern="^(keep|cancelling|ignore)$")


@router.put("/recurring/{rec_id}")
def mark_recurring(rec_id: str, body: Mark) -> dict[str, Any]:
    if not forecast.mark(_id(rec_id), body.status):
        raise HTTPException(status_code=404, detail="No such recurring charge.")
    return forecast.recurring_overview()


@router.get("/suggestions")
def get_suggestions() -> dict[str, Any]:
    return forecast.suggestions()
