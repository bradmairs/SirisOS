"""Apple Pay taps into the budget (11.17).

CommBank has no API for personal customers, so the budget's actual spending came only from a NetBank CSV import.
Now an iPhone Shortcuts automation ("When I tap any of my cards", iOS 17+) sends each Apple Pay purchase's shop,
amount and card here the moment it happens. Each becomes a spend, sorted onto a budget line the way imports are
(the rules you've taught it, else a guess from the shop's name). It's kept as a spend captured by hand, so when a
NetBank CSV later brings the bank's own line for the same purchase, that replaces it: nothing counts twice.

The Shortcut signs in with its own key (Budget → Apple Pay to the budget, shown once, kept only as its SHA-256),
which can only add a spend. The same shop and amount again within two minutes is taken as the automation firing
twice. Direct debits, BPAY and transfers don't go through Apple Pay: they still come from the CSV.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from datetime import date, datetime
from typing import Any

from app.budget import actuals
from app.services import json_store

TWICE_SECONDS = 120


def _path():
    return json_store.data_path("SIRISOS_BUDGET_TAPS_PATH", "budget-taps.json")


def _doc() -> dict[str, Any]:
    raw = json_store.read(_path(), {})
    return raw if isinstance(raw, dict) else {}


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def new_key() -> str:
    key = "pay_" + secrets.token_urlsafe(24)
    doc = _doc()
    doc.update(hash=_digest(key), made=datetime.now().isoformat(timespec="seconds"))  # noqa: DTZ005 (shown as is)
    json_store.write(_path(), doc)
    return key


def drop_key() -> None:
    doc = _doc()
    doc.pop("hash", None)
    json_store.write(_path(), doc)


def state() -> dict[str, Any]:
    doc = _doc()
    return {"on": bool(doc.get("hash")), "made": doc.get("made"), "last": doc.get("last"), "count": doc.get("count", 0)}


def matches(key: str | None) -> bool:
    stored = _doc().get("hash") or ""
    return bool(key and stored) and hmac.compare_digest(_digest(key), stored)


def amount_of(value: Any) -> float | None:
    """"$12.50", "12.50", "A$12.50", "12,50", 12.5: the amount spent, as a positive number."""
    # 11.17: cut short before parsing (an amount is never long; CodeQL flagged a regex run on a long one), and no
    # patterns with anything to backtrack over.
    text = str(value or "").replace("\u00a0", " ").strip()[:24]
    text = text.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz").lstrip("$").strip()
    head, comma, tail = text.rpartition(",")
    if comma and head.isdigit() and len(tail) == 2 and tail.isdigit():  # a decimal comma: "12,50"
        text = f"{head}.{tail}"
    v = actuals._amount(text)  # noqa: SLF001 - the CSV import's parser
    return abs(v) if v and v == v and abs(v) < 1_000_000 else None


def add(merchant: str, amount: Any, card: str = "", now: datetime | None = None) -> dict[str, Any]:
    """One Apple Pay tap: a spend on the budget, sorted onto a line. Returns {logged, line, say}."""
    shop = re.sub(r"\s+", " ", str(merchant or "")).strip()[:120]
    value = amount_of(amount)
    if not shop or not value:
        raise ValueError("A tap needs the shop and the amount.")
    now = now or datetime.now()  # noqa: DTZ005 (local, like the budget)
    doc = _doc()
    recent = [r for r in doc.get("recent", []) if r["at"] > time.time() - TWICE_SECONDS]
    if any(r["shop"] == shop.lower() and abs(r["amount"] - value) < 0.005 for r in recent):
        return {"logged": False, "say": f"Already got ${value:,.2f} at {shop}."}
    tx = actuals.add_manual(now.date(), shop, value, account=f"Apple Pay{' · ' + card.strip()[:40] if card.strip() else ''}")
    lines = {line["id"]: line["name"] for line in actuals._lines()}  # noqa: SLF001
    line = lines.get(tx.get("line_id") or "")
    doc["recent"] = [*recent, {"shop": shop.lower(), "amount": value, "at": time.time()}][-20:]
    doc["last"] = now.isoformat(timespec="minutes")
    doc["count"] = int(doc.get("count", 0)) + 1
    json_store.write(_path(), doc)
    return {"logged": True, "line": line, "id": tx["id"],
            "say": f"Logged ${value:,.2f} at {shop}" + (f" on {line}." if line else ": sort it on Budget.")}


def this_month(today: date | None = None) -> dict[str, Any]:
    """How many Apple Pay spends this month, and how many are still to sort."""
    today = today or date.today()
    ym = today.strftime("%Y-%m")
    taps = [t for t in actuals.load()["transactions"] if t.get("manual") and str(t.get("account", "")).startswith("Apple Pay") and t["date"].startswith(ym)]
    return {"taps": len(taps), "unsorted": sum(1 for t in taps if not t.get("line_id") and not t.get("ignored")),
            "spent": round(-sum(t["amount"] for t in taps), 2)}

