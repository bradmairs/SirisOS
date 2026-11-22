"""SirisOS's own data, for SirisAI to answer from (11.3): GET /api/v1/facts?topic=...

Read only, and one of the routes SirisAI's service key opens (service_key.py). Topics:

- **spending**: total, count, by budget line and by shop for a period, optionally only what matches `q` (a shop or a
  line, e.g. "fuel"). Periods: this-week, last-week, this-month, last-month, last-30-days, this-year, or `from`/`to`.
- **budget**: this month's lines, plan against spent and what's left, plus the cash flow to the next pay day.
- **subscriptions**: the repeating charges found in the bank files, with price rises.
- **meals**: the dinners planned lately, and when `q` was last on the plan.
- **goals**: this year's goals, how far along, the pace, and a step for any that's behind.
- **plan**: today's plan.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.hub.service import Hub

TOPICS = ("spending", "budget", "subscriptions", "meals", "goals", "plan")


def period(name: str | None, today: date, start: str | None = None, end: str | None = None) -> tuple[date, date, str]:
    if start or end:
        s = date.fromisoformat(start) if start else today - timedelta(days=30)
        e = date.fromisoformat(end) if end else today
        return s, e, f"{s.isoformat()} to {e.isoformat()}"
    n = (name or "this-month").lower()
    if n == "this-week":
        s = today - timedelta(days=today.weekday())
        return s, today, "this week"
    if n == "last-week":
        s = today - timedelta(days=today.weekday() + 7)
        return s, s + timedelta(days=6), "last week"
    if n == "last-month":
        first = today.replace(day=1)
        e = first - timedelta(days=1)
        return e.replace(day=1), e, e.strftime("%B %Y")
    if n == "last-30-days":
        return today - timedelta(days=29), today, "the last 30 days"
    if n == "this-year":
        return today.replace(month=1, day=1), today, str(today.year)
    return today.replace(day=1), today, today.strftime("%B %Y")


def spending(today: date, q: str | None, name: str | None, start: str | None, end: str | None) -> dict[str, Any]:
    from app.budget import actuals

    s, e, label = period(name, today, start, end)
    lines = {l["id"]: l.get("name") or "" for l in actuals._lines()}  # noqa: SLF001
    doc = actuals.load()
    txs = [t for t in doc["transactions"] if s.isoformat() <= t["date"] <= e.isoformat() and t["amount"] < 0 and not t.get("ignored")]
    if q:
        words = q.lower().split()
        txs = [t for t in txs if all(w in f"{t['description']} {lines.get(t.get('line_id') or '', '')}".lower() for w in words)]
    by_line: dict[str, float] = {}
    by_shop: dict[str, float] = {}
    for t in txs:
        by_line[lines.get(t.get("line_id") or "", "") or "Not sorted"] = by_line.get(lines.get(t.get("line_id") or "", "") or "Not sorted", 0) - t["amount"]
        shop = actuals.merchant(t["description"]) or t["description"][:30]
        by_shop[shop] = by_shop.get(shop, 0) - t["amount"]
    top = lambda d: [{"name": k, "spent": round(v, 2)} for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:8]]  # noqa: E731
    last = max((t["date"] for t in doc["transactions"]), default=None)
    return {"period": label, "from": s.isoformat(), "to": e.isoformat(), "matching": q, "spent": round(-sum(t["amount"] for t in txs), 2),
            "count": len(txs), "by_line": top(by_line), "by_shop": top(by_shop),
            "latest": [{"date": t["date"], "description": t["description"], "amount": -t["amount"]} for t in sorted(txs, key=lambda t: t["date"], reverse=True)[:10]],
            "data_until": last, "note": None if txs or not q else f"No spending matching '{q}' in {label}."}


async def answer(hub: Hub, topic: str, today: date, now: Any, q: str | None = None, name: str | None = None,
                 start: str | None = None, end: str | None = None) -> dict[str, Any]:
    if topic == "spending":
        return spending(today, q, name, start, end)
    if topic == "budget":
        from app.budget import actuals, forecast

        m = actuals.month()
        lines = [{**{k: l[k] for k in ("name", "plan", "spent", "status")}, "left": round(l["plan"] - l["spent"], 2)} for l in m["lines"]]
        cf = forecast.cashflow(today)
        return {"month": m["month"], "through_month": m["through"], "spent": m["spent"], "lines": lines, "over": [l["name"] for l in m["over"]],
                "cashflow": {k: cf.get(k) for k in ("ready", "start", "as_of", "per_day", "next_pay", "low", "end", "warn", "why")}, "currency": m["currency"]}
    if topic == "subscriptions":
        from app.budget import forecast

        ov = forecast.recurring_overview(today)
        return {"per_month": ov["per_month"], "subscriptions_per_month": ov["subscriptions_per_month"],
                "items": [{k: r.get(k) for k in ("name", "every", "amount", "was", "next", "subscription", "status", "flags", "line")} for r in ov["items"]]}
    if topic == "meals":
        from app.meals import service as meals

        plan = meals.load()["plan"]
        past = sorted(((d, p["title"]) for d, p in plan.items() if d <= today.isoformat()), reverse=True)
        found = None
        if q:
            found = next(({"date": d, "title": t} for d, t in past if q.lower() in t.lower()), None)
        coming = sorted((d, p["title"]) for d, p in plan.items() if d > today.isoformat())
        return {"recent": [{"date": d, "title": t} for d, t in past[:14]], "coming": [{"date": d, "title": t} for d, t in coming[:7]],
                "asked": q, "last_time": found, "note": None if found or not q else f"'{q}' isn't on the plan in the last four months."}
    if topic == "goals":
        from app.assist import goals_steer

        return await goals_steer.overview(hub, today)
    if topic == "plan":
        from app.assist import dayplan

        return await dayplan.today(hub, now)
    raise ValueError(f"topic must be one of: {', '.join(TOPICS)}")
