"""The budget (SirisOS 7.6): income, then where it goes, in sections:
expenses (bills and the fixed costs), savings (with goals) and spending
(the day-to-day). Each line has an amount and how often it comes or goes
(weekly, fortnightly, monthly, quarterly, yearly), so everything can be
shown per week, fortnight, month or year.

Kept in budget.json in the data directory (backed up nightly with the rest).
Each save also records that month's totals, so the Budget screen can chart
how the plan has changed over time.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
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
    return out


def totals(doc: dict[str, Any]) -> dict[str, float]:
    t = {"income": sum(monthly(i) for i in doc.get("income", []))}
    for section in SECTIONS:
        t[section] = sum(monthly(i) for i in doc.get("sections", {}).get(section, []))
    t["left"] = t["income"] - t["expenses"] - t["savings"] - t["spending"]
    return {k: round(v, 2) for k, v in t.items()}


def get() -> dict[str, Any]:
    doc = json_store.read(_path(), None) or {**STARTER, "sections": {s: [] for s in SECTIONS}}
    return {**doc, "totals": totals(doc)}


def save(body: dict[str, Any]) -> dict[str, Any]:
    income = [_clean_line(i, None) for i in (body.get("income") or [])[:30]]
    sections = {s: [_clean_line(i, s) for i in ((body.get("sections") or {}).get(s) or [])[:60]] for s in SECTIONS}
    old = json_store.read(_path(), None) or {}
    doc = {"currency": str(body.get("currency") or old.get("currency") or "AUD")[:3].upper(), "income": income, "sections": sections}
    month = datetime.now(zone()).strftime("%Y-%m")
    history = [h for h in old.get("history", []) if h.get("month") != month]
    history.append({"month": month, **totals(doc)})
    doc["history"] = sorted(history, key=lambda h: h["month"])[-36:]
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    json_store.write(_path(), doc)
    return {**doc, "totals": totals(doc)}
