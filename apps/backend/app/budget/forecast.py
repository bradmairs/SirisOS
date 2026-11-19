"""Looking ahead with the money (10.1), from the bank imports (actuals.py):

- **Recurring charges**: the same shop, about the same amount, at a steady
  pace (weekly, fortnightly, monthly, quarterly or yearly). Each says when it's
  next due and is flagged when its price went up, when it isn't in the budget,
  or, for subscriptions, until you say you're keeping it.
- **Cash flow to the next pay day**: today's everyday balance, less the
  recurring charges as they fall due and your usual day-to-day spending, plus
  pay as it comes in, day by day. The lowest point is the thing to watch.
- **Plan suggestions**: after two full months of imports, the lines that
  usually run well over or under their plan, with a new amount and where the
  money went.
"""

from __future__ import annotations

import hashlib
import os
from collections import Counter, defaultdict
from datetime import date, timedelta
from statistics import median
from typing import Any

from app.budget import actuals
from app.budget import service as budget

PACES = [("weekly", 7, 6, 8), ("fortnightly", 14, 12, 16), ("monthly", 30, 26, 35), ("quarterly", 91, 84, 98), ("yearly", 365, 350, 380)]
SUBSCRIPTION_WORDS = ("netflix", "spotify", "disney", "stan", "binge", "apple.com", "youtube", "prime", "kayo", "paramount", "audible",
                      "adobe", "microsoft", "google", "dropbox", "icloud", "openai", "chatgpt", "patreon", "xbox", "playstation", "nintendo")
FORECAST_MIN_DAYS = 14
FORECAST_MAX_DAYS = 45


def low_mark() -> float:
    try:
        return float(os.getenv("SIRISOS_CASHFLOW_LOW", "200"))
    except ValueError:
        return 200.0


def rid(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def _spends(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return [t for t in doc["transactions"] if t["amount"] < 0 and not t.get("ignored")]


# -- recurring charges ------------------------------------------------------------------------------

def recurring(today: date | None = None, doc: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    today = today or budget.today()
    doc = doc or actuals.load()
    marks = doc.get("recurring", {})
    lines = {l["id"]: l for l in actuals._lines()}  # noqa: SLF001
    names = [(l.get("name") or "").lower() for l in lines.values()]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in _spends(doc):
        key = actuals.merchant(t["description"])
        if key:
            groups[key].append(t)
    out = []
    for key, txs in groups.items():
        txs = sorted(txs, key=lambda t: t["date"])
        days = sorted({t["date"] for t in txs})
        if len(days) < 2:
            continue
        gaps = [(date.fromisoformat(b) - date.fromisoformat(a)).days for a, b in zip(days, days[1:], strict=False)]
        gap = median(gaps)
        pace = next((p for p in PACES if p[2] <= gap <= p[3]), None)
        if pace is None:
            continue
        steady = sum(1 for g in gaps if pace[2] <= g <= pace[3]) / len(gaps)
        # Weekly or fortnightly needs 3 times; monthly and longer 2 (a new subscription shows up after its second charge).
        if steady < 0.7 or len(days) < (3 if pace[1] < 30 else 2):
            continue
        amounts = [-t["amount"] for t in txs]
        last, before = amounts[-1], amounts[:-1]
        usual = median(before) if before else last
        if not all(0.6 * usual <= a <= 1.6 * usual for a in before[-3:]):  # a shop you visit often, not a fixed charge
            continue
        last_day = date.fromisoformat(days[-1])
        nxt = last_day + timedelta(days=pace[1])
        if today - last_day > timedelta(days=round(pace[1] * 1.6)):
            continue  # stopped
        id_ = rid(key)
        line_ids = Counter(t.get("line_id") for t in txs if t.get("line_id"))
        line_id = line_ids.most_common(1)[0][0] if line_ids else None
        line = lines.get(line_id or "")
        in_budget = bool(line and line["section"] == "expenses") or any(key.split()[0] in n for n in names if n)
        subscription = any(w in key for w in SUBSCRIPTION_WORDS) or bool(line and "subscri" in (line.get("name") or "").lower())
        status = marks.get(id_)
        flags = []
        if before and last > usual * 1.02 and last - usual >= 0.5:
            flags.append("price_up")
        if not in_budget:
            flags.append("not_in_budget")
        if subscription and status not in ("keep", "cancelling"):
            flags.append("check")
        out.append({"id": id_, "name": txs[-1]["description"][:60], "key": key, "every": pace[0], "days": pace[1],
                    "amount": round(last, 2), "was": round(usual, 2) if "price_up" in flags else None,
                    "per_month": round(last * 30.44 / pace[1], 2), "last": days[-1], "next": nxt.isoformat(), "times": len(days),
                    "line_id": line_id, "line": line.get("name") if line else None, "subscription": subscription,
                    "status": status, "flags": [] if status == "ignore" else flags})
    out.sort(key=lambda r: (r["status"] == "ignore", -r["per_month"]))
    return out


def mark(id_: str, status: str | None) -> bool:
    doc = actuals.load()
    if not any(r["id"] == id_ for r in recurring(doc=doc)):
        return False
    marks = doc.setdefault("recurring", {})
    if status:
        marks[id_] = status
    else:
        marks.pop(id_, None)
    actuals.save(doc)
    return True


def recurring_overview(today: date | None = None) -> dict[str, Any]:
    rows = recurring(today)
    live = [r for r in rows if r["status"] not in ("ignore", "cancelling")]
    return {"items": rows, "per_month": round(sum(r["per_month"] for r in live), 2),
            "subscriptions_per_month": round(sum(r["per_month"] for r in live if r["subscription"]), 2),
            "flagged": sum(1 for r in rows if r["flags"]), "currency": budget.get().get("currency", "AUD")}


# -- cash flow ----------------------------------------------------------------------------------------

def _repeat(first: date, every: str, until: date) -> list[date]:
    step = {"weekly": 7, "fortnightly": 14}.get(every)
    months = {"monthly": 1, "quarterly": 3, "yearly": 12}.get(every)
    out, d, k = [], first, 0
    while d <= until and k < 400:
        out.append(d)
        k += 1
        if step:
            d = first + timedelta(days=step * k)
        elif months:
            d = budget._add_months(first, months * k, first.day)  # noqa: SLF001
        else:
            break
    return out


def daily_spend(doc: dict[str, Any], today: date, regular: set[str]) -> tuple[float, str]:
    """Usual day-to-day spending a day: the last 60 days of imported spends that aren't recurring charges,
    or the budget's spending section when there isn't three weeks of history."""
    start = today - timedelta(days=60)
    recent = [t for t in _spends(doc) if start.isoformat() <= t["date"] < today.isoformat() and actuals.merchant(t["description"]) not in regular]
    if recent:
        first = date.fromisoformat(min(t["date"] for t in doc["transactions"]))
        span = (today - max(first, start)).days
        if span >= 21:
            return sum(-t["amount"] for t in recent) / span, "your spending over the last " + (f"{span} days" if span < 60 else "two months")
    plan = budget.get()
    per_month = sum(budget.monthly(l) for l in plan.get("sections", {}).get("spending", []))
    return per_month / 30.44, "your budget's spending lines"


def cashflow(today: date | None = None) -> dict[str, Any]:
    today = today or budget.today()
    doc = actuals.load()
    plan = budget.get()
    cur = plan.get("currency", "AUD")
    bal = actuals.balances()
    everyday = [a for a in bal["accounts"] if a["kind"] == "everyday" and a["balance"] is not None]
    if not everyday:
        return {"ready": False, "currency": cur, "why": "Add your everyday account's balance (or a bank CSV with a balance column) to see the month ahead."}
    start = sum(a["balance"] for a in everyday)
    as_of = min(a["as_of"] for a in everyday)
    pays = budget.pay_days(plan, today)
    next_pay = date.fromisoformat(pays[0]["next"]) if pays else None
    end = today + timedelta(days=30)
    if next_pay:
        end = max(today + timedelta(days=FORECAST_MIN_DAYS), next_pay + timedelta(days=1))
    end = min(end, today + timedelta(days=FORECAST_MAX_DAYS))

    events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in plan.get("income", []):
        nxt = budget.next_pay(line, today)
        if nxt:
            for d in _repeat(nxt, line.get("every", "monthly"), end):
                events[d.isoformat()].append({"name": line.get("name") or "Pay", "amount": round(float(line.get("amount") or 0), 2)})
    regular = recurring(today, doc)
    for r in regular:
        if r["status"] in ("ignore", "cancelling"):
            continue
        nxt = date.fromisoformat(r["next"])
        while nxt < today:
            nxt += timedelta(days=r["days"])
        for d in _repeat(nxt, r["every"], end):
            events[d.isoformat()].append({"name": r["name"], "amount": -r["amount"]})
    per_day, basis = daily_spend(doc, today, {r["key"] for r in regular})

    days, balance = [], start
    low = {"date": today.isoformat(), "balance": round(start, 2)}
    d = today
    while d <= end:
        if d > today:
            balance -= per_day
        todays = events.get(d.isoformat(), [])
        balance += sum(e["amount"] for e in todays)
        days.append({"date": d.isoformat(), "balance": round(balance, 2), "events": todays})
        if balance < low["balance"]:
            low = {"date": d.isoformat(), "balance": round(balance, 2)}
        d += timedelta(days=1)
    mark_ = low_mark()
    return {"ready": True, "currency": cur, "start": round(start, 2), "as_of": as_of, "per_day": round(per_day, 2), "basis": basis,
            "next_pay": next_pay.isoformat() if next_pay else None, "days": days, "low": low, "end": days[-1]["balance"],
            "warn": low["balance"] < mark_, "low_mark": mark_,
            "bills": [{"date": k, **e} for k, es in sorted(events.items()) for e in es if e["amount"] < 0][:30]}


CASHFLOW_HOUR = 9


def push_message(local_now) -> list[dict[str, Any]]:
    """10.1: at 9am, when the balance looks like dipping under the low mark before pay (once per low point)."""
    if local_now.hour < CASHFLOW_HOUR:
        return []
    try:
        cf = cashflow(local_now.date())
    except Exception:  # noqa: BLE001
        return []
    if not cf.get("ready") or not cf["warn"]:
        return []
    low = cf["low"]
    when = date.fromisoformat(low["date"])
    pay = f", before pay on {date.fromisoformat(cf['next_pay']):%a %d %b}" if cf.get("next_pay") and cf["next_pay"] > low["date"] else ""
    return [{"key": f"cashflow:low:{low['date']}", "topic": "brief", "title": "Money's tight this cycle",
             "body": f"Your everyday account looks like getting down to {budget._money(low['balance'], cf['currency'])} "  # noqa: SLF001
                     f"on {when:%a %d %b}{pay}. See what's due in Budget.",
             "url": "/budget", "urgency": "normal"}]


# -- plan suggestions ---------------------------------------------------------------------------------

def _full_months(doc: dict[str, Any], today: date) -> list[str]:
    if not doc["transactions"]:
        return []
    first = date.fromisoformat(min(t["date"] for t in doc["transactions"]))
    last = date.fromisoformat(max(t["date"] for t in doc["transactions"]))
    out = []
    for ym in sorted({t["date"][:7] for t in doc["transactions"]}):
        y, m = int(ym[:4]), int(ym[5:])
        start = date(y, m, 1)
        end = budget._add_months(start, 1, 1) - timedelta(days=1)  # noqa: SLF001
        if ym < today.strftime("%Y-%m") and first <= start + timedelta(days=4) and last >= end - timedelta(days=4):
            out.append(ym)
    return out[-3:]


def suggestions(today: date | None = None) -> dict[str, Any]:
    today = today or budget.today()
    doc = actuals.load()
    months = _full_months(doc, today)
    cur = budget.get().get("currency", "AUD")
    if len(months) < 2:
        return {"ready": False, "months": months, "items": [], "currency": cur,
                "why": "After two full months of bank imports, this suggests changes to your plan."}
    out = []
    for line in actuals._lines():  # noqa: SLF001
        if line["section"] == "savings":
            continue
        txs = [t for t in _spends(doc) if t.get("line_id") == line["id"] and t["date"][:7] in months]
        avg = sum(-t["amount"] for t in txs) / len(months)
        plan = budget.monthly(line)
        if plan and avg > plan * 1.1 and avg - plan >= 20:
            kind = "raise"
        elif plan and txs and line.get("every") not in ("quarterly", "yearly") and avg < plan * 0.75 and plan - avg >= 20:
            kind = "lower"  # only lines with spending on them: none usually means it's paid another way
        elif not plan and avg >= 20:
            kind = "add"
        else:
            continue
        monthly_new = max(10, round(avg / 10) * 10)
        every = line.get("every", "monthly")
        amount = round(monthly_new / budget.PER_MONTH.get(every, 1.0))
        shops: dict[str, float] = defaultdict(float)
        for t in txs:
            shops[actuals.merchant(t["description"]) or t["description"][:30]] += -t["amount"]
        top = sorted(shops.items(), key=lambda kv: -kv[1])[:3]
        out.append({"line_id": line["id"], "name": line.get("name") or "Unnamed", "section": line["section"], "kind": kind,
                    "plan": round(plan, 2), "average": round(avg, 2), "amount": amount, "every": every, "monthly": monthly_new,
                    "where": [{"shop": s.title(), "per_month": round(v / len(months), 2)} for s, v in top]})
    out.sort(key=lambda s: -abs(s["average"] - s["plan"]))
    return {"ready": True, "months": months, "items": out, "currency": cur}
