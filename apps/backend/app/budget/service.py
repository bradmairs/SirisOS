"""The budget (SirisOS 7.7): income, then where it goes, in sections:
expenses (bills and the fixed costs), savings (with goals) and spending
(the day-to-day). Each line has an amount and how often it comes or goes
(weekly, fortnightly, monthly, quarterly, yearly), so everything can be
shown per week, fortnight, month or year.

Pay day (9.5): an income line can have a pay day, any date it was (or will
be) paid. The next one follows from how often it comes. SirisAI is given a
reminder for 8am on each next pay day (kept in step when the date or the line
changes), and Home shows the pay on the day.

Kept in budget.json in the data directory (backed up nightly with the rest).
Each save also records that month's totals, so the Budget screen can chart
how the plan has changed over time.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from app.brief.service import zone
from app.services import json_store

SECTIONS = ("expenses", "savings", "spending")
PER_MONTH = {"weekly": 52 / 12, "fortnightly": 26 / 12, "monthly": 1.0, "quarterly": 1 / 3, "yearly": 1 / 12}
STARTER = {
    "currency": "AUD",
    "income": [],
    "sections": {"expenses": [], "savings": [], "spending": []},
    "history": [],
}


def _path():
    return json_store.data_path("SIRISOS_BUDGET_PATH", "budget.json")


def monthly(line: dict[str, Any]) -> float:
    return float(line.get("amount") or 0) * PER_MONTH.get(line.get("every") or "monthly", 1.0)


def _clean_line(line: dict[str, Any], section: str | None) -> dict[str, Any]:
    name = str(line.get("name") or "").strip()[:80]
    amount = float(line.get("amount") or 0)
    if amount < 0 or amount > 10_000_000:
        raise ValueError(f"'{name or 'A line'}' has an amount out of range.")
    every = line.get("every") or "monthly"
    if every not in PER_MONTH:
        raise ValueError(f"'{name}': how often is weekly, fortnightly, monthly, quarterly or yearly.")
    out = {"id": str(line.get("id") or uuid.uuid4().hex[:10]), "name": name, "amount": round(amount, 2), "every": every}
    if section == "savings":
        for key in ("goal", "saved"):
            value = line.get(key)
            if value not in (None, ""):
                value = float(value)
                if value < 0:
                    raise ValueError(f"'{name}': {key} can't be negative.")
                out[key] = round(value, 2)
    if line.get("note"):
        out["note"] = str(line["note"])[:200]
    if section is None and line.get("pay_day"):  # 9.5: income only
        try:
            out["pay_day"] = date.fromisoformat(str(line["pay_day"])[:10]).isoformat()
        except ValueError:
            raise ValueError(f"'{name}': the pay day isn't a date.") from None
    return out


def _add_months(d: date, months: int, day: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(day, calendar.monthrange(y, m)[1]))


def next_pay(line: dict[str, Any], today: date) -> date | None:
    """The next pay day on or after today, from the line's pay day and how often it comes. Monthly pay on the 31st
    falls on the last day of shorter months."""
    if not line.get("pay_day"):
        return None
    start = date.fromisoformat(line["pay_day"])
    every = line.get("every") or "monthly"
    if start >= today:
        return start
    if every in ("weekly", "fortnightly"):
        step = 7 if every == "weekly" else 14
        return start + timedelta(days=-(-(today - start).days // step) * step)
    months = {"monthly": 1, "quarterly": 3, "yearly": 12}[every]
    n = ((today.year - start.year) * 12 + today.month - start.month) // months
    for k in (n, n + 1, n + 2):
        d = _add_months(start, k * months, start.day)
        if d >= today:
            return d
    return None


def pay_days(doc: dict[str, Any], today: date) -> list[dict[str, Any]]:
    """Each income line with a pay day: when it's next paid and how much."""
    out = []
    for i in doc.get("income", []):
        nxt = next_pay(i, today)
        if nxt:
            out.append({"id": i["id"], "name": i.get("name") or "Pay", "amount": i.get("amount") or 0, "every": i.get("every"),
                        "next": nxt.isoformat(), "days": (nxt - today).days})
    return sorted(out, key=lambda p: p["next"])


def totals(doc: dict[str, Any]) -> dict[str, float]:
    t = {"income": sum(monthly(i) for i in doc.get("income", []))}
    for section in SECTIONS:
        t[section] = sum(monthly(i) for i in doc.get("sections", {}).get(section, []))
    t["left"] = t["income"] - t["expenses"] - t["savings"] - t["spending"]
    return {k: round(v, 2) for k, v in t.items()}


def today() -> date:
    return datetime.now(zone()).date()


def get() -> dict[str, Any]:
    doc = json_store.read(_path(), None) or {**STARTER, "sections": {s: [] for s in SECTIONS}}
    return {**doc, "totals": totals(doc), "pay_days": pay_days(doc, today())}


def save(body: dict[str, Any]) -> dict[str, Any]:
    income = [_clean_line(i, None) for i in (body.get("income") or [])[:30]]
    sections = {s: [_clean_line(i, s) for i in ((body.get("sections") or {}).get(s) or [])[:60]] for s in SECTIONS}
    old = json_store.read(_path(), None) or {}
    doc = {"currency": str(body.get("currency") or old.get("currency") or "AUD")[:3].upper(), "income": income, "sections": sections,
           "pay_reminders": old.get("pay_reminders") or {}}
    month = datetime.now(zone()).strftime("%Y-%m")
    history = [h for h in old.get("history", []) if h.get("month") != month]
    history.append({"month": month, **totals(doc)})
    doc["history"] = sorted(history, key=lambda h: h["month"])[-36:]
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    json_store.write(_path(), doc)
    return {**doc, "totals": totals(doc), "pay_days": pay_days(doc, today())}


# -- SirisAI's pay day reminders (9.5) ------------------------------------------------------------------------------

PAY_HOUR = 8


def _money(amount: float, currency: str) -> str:
    return f"${amount:,.2f}" if currency in ("AUD", "USD", "NZD", "CAD") else f"{amount:,.2f} {currency}"


async def sync_pay_reminders(hub: Any) -> dict[str, Any]:
    """One SirisAI reminder per income line, for 8am on its next pay day. A changed date, a removed line or a pay day
    that's passed replaces or cancels it. What SirisAI was given is kept in budget.json (pay_reminders), so this only
    calls SirisAI when something changed. Returns what it did."""
    from app.hub import sirisai_api

    doc = json_store.read(_path(), None)
    if not doc:
        return {"set": 0, "cancelled": 0}
    on = today()
    kept: dict[str, Any] = dict(doc.get("pay_reminders") or {})
    want = {p["id"]: p for p in pay_days(doc, on)}
    set_n = cancelled = 0
    for line_id, r in list(kept.items()):
        p = want.get(line_id)
        stale = p is None or r.get("date") != p["next"] or r.get("message") != _message(p, doc)
        if stale or r.get("date", "") < on.isoformat():
            if r.get("id") and (r.get("date") or "") >= on.isoformat():  # a past one has already gone off
                try:
                    await sirisai_api.post(hub, f"/siris/hub/v1/reminders/{r['id']}/done")
                except Exception:  # noqa: BLE001 - already gone
                    pass
                cancelled += 1
            kept.pop(line_id)
    for line_id, p in want.items():
        if line_id in kept:
            continue
        due = datetime.combine(date.fromisoformat(p["next"]), time(PAY_HOUR), tzinfo=zone())
        if due < datetime.now(zone()):
            continue  # today's 8am has gone: Home still shows it today
        made = await sirisai_api.post(hub, "/siris/hub/v1/reminders", json={"message": _message(p, doc), "due_at": due.isoformat()})
        if made and made.get("id"):
            kept[line_id] = {"id": made["id"], "date": p["next"], "message": _message(p, doc)}
            set_n += 1
    if kept != (doc.get("pay_reminders") or {}):
        doc["pay_reminders"] = kept
        json_store.write(_path(), doc)
    return {"set": set_n, "cancelled": cancelled}


def _message(p: dict[str, Any], doc: dict[str, Any]) -> str:
    return f"Pay day: {p['name']}, {_money(float(p['amount']), doc.get('currency') or 'AUD')}, is due in today."
