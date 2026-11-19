"""What you actually spend, and what you have (10.0): bank transactions against
the budget, and account balances towards the savings goals.

**Spending.** Import a bank's CSV export (CommBank, NAB, ANZ, Westpac, ING, Up
and most others: with or without a header row, one amount column or debit and
credit, dates as 19/11/2026 or 2026-11-19). Re-importing the same file adds
nothing twice. Each spend is put on one of your budget lines:

- by a rule you taught it (putting "WOOLWORTHS 1234 MELBOURNE" on Groceries
  teaches "woolworths" -> Groceries, and the others waiting are sorted too);
- or by a guess from the shop's name against your lines' names (Woolworths,
  Coles and Aldi on a line called Groceries; BP, Shell and Ampol on Fuel...);
- money in (pay, refunds, transfers) is left out unless you put it on a line.

The month then shows each line's spending against its plan, the lines that
are over, and what's still to sort.

**Balances.** Accounts (everyday, savings, super, a loan, a credit card) with
a balance now and then, typed in or taken from an import's balance column. A
savings line can be tied to an account, so its goal's progress is the real
balance, and its finish date is forecast from how fast the balance has grown
over the last three months. Net worth is everything less what's owed.

Kept in budget-actuals.json (SIRISOS_BUDGET_ACTUALS_PATH), next to budget.json.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from app.budget import service as budget
from app.services import json_store

MAX_TRANSACTIONS = 20000
ACCOUNT_KINDS = ("everyday", "savings", "super", "investment", "loan", "credit")
OWED = ("loan", "credit")

# Shops and words, for a first guess at the line (by the line's name).
GUESSES: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    (("groceries", "grocery", "food shopping", "supermarket"), ("woolworths", "coles", "aldi", "iga", "foodworks", "harris farm", "costco")),
    (("fuel", "petrol"), ("bp ", "shell", "caltex", "ampol", "7-eleven", "united petrol", "liberty", "puma energy", "metro petroleum")),
    (("eating out", "takeaway", "restaurants", "dining", "coffee", "cafes"), ("mcdonald", "kfc", "hungry jack", "subway", "domino", "uber eats",
                                                                         "menulog", "doordash", "cafe", "coffee", "restaurant", "grill", "sushi", "pizza")),
    (("transport", "public transport", "myki", "travel"), ("myki", "ptv", "opal", "translink", "uber *trip", "didi", "taxi")),
    (("subscriptions", "streaming"), ("netflix", "spotify", "disney", "stan.", "binge", "apple.com/bill", "youtube", "amazon prime", "kayo")),
    (("phone", "mobile", "internet"), ("telstra", "optus", "vodafone", "aussie broadband", "belong", "tpg", "superloop")),
    (("power", "electricity", "energy", "utilities", "gas"), ("agl", "origin energy", "energyaustralia", "red energy", "alinta", "powershop")),
    (("gym", "fitness"), ("anytime fitness", "fitness first", "jetts", "goodlife", "f45", "snap fitness")),
    (("health", "medical", "pharmacy", "chemist"), ("chemist warehouse", "priceline", "pharmacy", "medical", "dental", "physio")),
    (("clothes", "clothing"), ("uniqlo", "cotton on", "myer", "david jones", "rebel", "kmart apparel")),
    (("insurance",), ("insurance", "nrma", "racv", "aami", "budget direct", "bupa", "medibank", "hcf")),
    (("home", "household", "hardware"), ("bunnings", "ikea", "kmart", "big w", "target", "officeworks")),
]


def _path():
    return json_store.data_path("SIRISOS_BUDGET_ACTUALS_PATH", "budget-actuals.json")


def load() -> dict[str, Any]:
    doc = json_store.read(_path(), {}) or {}
    doc.setdefault("transactions", [])
    doc.setdefault("rules", {})
    doc.setdefault("accounts", [])
    doc.setdefault("balances", [])
    return doc


def save(doc: dict[str, Any]) -> None:
    doc["transactions"] = sorted(doc["transactions"], key=lambda t: (t["date"], t["id"]))[-MAX_TRANSACTIONS:]
    json_store.write(_path(), doc)


# -- reading a bank's CSV ---------------------------------------------------------------------------

_DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y", "%d %B %Y", "%Y/%m/%d")


def _date(text: str) -> date | None:
    text = text.strip()[:30]
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()  # noqa: DTZ007 (a calendar date, no time)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text[:19]).date()
    except ValueError:
        return None


def _amount(text: str) -> float | None:
    t = text.strip().replace("$", "").replace(",", "").replace(" ", "")
    if not t:
        return None
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    if t.upper().endswith("CR"):
        t = t[:-2]
    elif t.upper().endswith("DR"):
        t, neg = t[:-2], True
    try:
        v = float(t)
    except ValueError:
        return None
    return -abs(v) if neg else v


_HEADER = {
    "date": ("date", "transaction date", "posted date", "effective date", "value date"),
    "description": ("description", "narrative", "details", "transaction details", "memo", "payee", "merchant", "transaction description"),
    "amount": ("amount", "transaction amount", "amount (aud)", "value"),
    "debit": ("debit", "debit amount", "withdrawal", "withdrawals", "money out"),
    "credit": ("credit", "credit amount", "deposit", "deposits", "money in"),
    "balance": ("balance", "running balance", "account balance"),
}


def parse_csv(raw: bytes) -> list[dict[str, Any]]:
    """Rows of {date, description, amount (negative: money out), balance?} from a bank's CSV export."""
    text = raw.decode("utf-8-sig", errors="replace")
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    if not rows:
        return []
    head = [c.strip().lower() for c in rows[0]]
    cols: dict[str, int] = {}
    for key, names in _HEADER.items():
        for i, h in enumerate(head):
            if h in names and key not in cols:
                cols[key] = i
    body = rows[1:] if "date" in cols else rows
    if "date" not in cols:
        # No header (CommBank's export): the date is the column that reads as a date, the amount the first
        # number after it, the description the longest text, and a later number the balance.
        sample = body[: min(len(body), 20)]
        width = max(len(r) for r in sample)
        def share(i: int, fn) -> float:
            vals = [r[i] for r in sample if i < len(r) and r[i].strip()]
            return sum(1 for v in vals if fn(v) is not None) / max(1, len(vals))
        dates = [i for i in range(width) if share(i, _date) > 0.8]
        nums = [i for i in range(width) if i not in dates and share(i, _amount) > 0.8]
        texts = [i for i in range(width) if i not in dates and i not in nums]
        if not dates or not nums or not texts:
            raise ValueError("Couldn't find the date, amount and description columns in that file.")
        cols = {"date": dates[0], "amount": nums[0], "description": max(texts, key=lambda i: sum(len(r[i]) for r in sample if i < len(r)))}
        if len(nums) > 1:
            cols["balance"] = nums[-1]
    if "amount" not in cols and not ("debit" in cols or "credit" in cols):
        raise ValueError("Couldn't find an amount column (or debit and credit) in that file.")
    if "description" not in cols:
        raise ValueError("Couldn't find a description column in that file.")
    out = []
    for r in body:
        def cell(key: str, r: list[str] = r) -> str:
            i = cols.get(key)
            return r[i] if i is not None and i < len(r) else ""
        d = _date(cell("date"))
        if d is None:
            continue
        if "amount" in cols:
            amount = _amount(cell("amount"))
        else:
            debit, credit = _amount(cell("debit")) or 0.0, _amount(cell("credit")) or 0.0
            amount = abs(credit) - abs(debit)
        if amount is None or amount == 0:
            continue
        row = {"date": d.isoformat(), "description": re.sub(r"\s+", " ", cell("description")).strip()[:200], "amount": round(amount, 2)}
        bal = _amount(cell("balance")) if "balance" in cols else None
        if bal is not None:
            row["balance"] = round(bal, 2)
        out.append(row)
    return out


# -- sorting spends onto lines -----------------------------------------------------------------------

def merchant(description: str) -> str:
    """The shop, as a key: the leading words without card numbers, dates, places in capitals after them, or refs."""
    d = description.lower()
    d = re.sub(r"\b(visa|eftpos|card|purchase|debit|pos|ap|aus|au|value date)\b", " ", d)
    d = re.sub(r"[^a-z&.*' ]+", " ", d)
    words = [w for w in d.split() if len(w) > 1][:2]
    return " ".join(words)


def _lines() -> list[dict[str, Any]]:
    doc = budget.get()
    return [{**l, "section": s} for s in budget.SECTIONS for l in doc.get("sections", {}).get(s, [])]


def guess(description: str, lines: list[dict[str, Any]]) -> str | None:
    d = f" {description.lower()} "
    for names, shops in GUESSES:
        if any(s in d for s in shops):
            for l in lines:
                n = (l.get("name") or "").lower()
                if any(name in n for name in names):
                    return l["id"]
    return None


def _sort(tx: dict[str, Any], rules: dict[str, str], lines: list[dict[str, Any]]) -> None:
    if tx.get("line_id") or tx.get("ignored") or tx.get("by_hand"):
        return
    rule = rules.get(merchant(tx["description"]))
    if rule == "ignore":
        tx["ignored"] = True
    elif rule and any(l["id"] == rule for l in lines):
        tx["line_id"] = rule
    elif tx["amount"] < 0:
        tx["line_id"] = guess(tx["description"], lines)
        tx["guessed"] = bool(tx["line_id"])


def import_csv(raw: bytes, account: str = "") -> dict[str, Any]:
    rows = parse_csv(raw)
    if not rows:
        raise ValueError("No transactions in that file.")
    doc = load()
    lines = _lines()
    seen = {t["id"] for t in doc["transactions"]}
    account = account.strip()[:60] or "Bank"
    added = 0
    counts: dict[str, int] = {}
    for r in rows:
        key = f"{account}|{r['date']}|{r['amount']}|{r['description']}"
        counts[key] = counts.get(key, 0) + 1   # two identical coffees on one day are two transactions
        tx_id = hashlib.sha256(f"{key}|{counts[key]}".encode()).hexdigest()[:16]
        if tx_id in seen:
            continue
        tx = {"id": tx_id, "date": r["date"], "description": r["description"], "amount": r["amount"], "account": account}
        _sort(tx, doc["rules"], lines)
        doc["transactions"].append(tx)
        seen.add(tx_id)
        added += 1
    # The newest balance in the file, for the account's balance history.
    with_balance = [r for r in rows if "balance" in r]
    if with_balance:
        last = max(with_balance, key=lambda r: r["date"])
        _record_balance(doc, account, last["balance"], last["date"])
    save(doc)
    return {"imported": added, "skipped": len(rows) - added, "account": account}


def assign(tx_id: str, line_id: str | None, learn: bool = True) -> dict[str, Any] | None:
    """Put a transaction on a line ("ignore" leaves it out); by default every other waiting one from that shop follows."""
    doc = load()
    tx = next((t for t in doc["transactions"] if t["id"] == tx_id), None)
    if tx is None:
        return None
    tx.pop("guessed", None)
    tx["by_hand"] = True
    if line_id == "ignore":
        tx["ignored"], tx["line_id"] = True, None
    else:
        tx["ignored"], tx["line_id"] = False, line_id or None
    sorted_too = 0
    if learn and line_id:
        key = merchant(tx["description"])
        if key:
            doc["rules"][key] = line_id
            lines = _lines()
            for other in doc["transactions"]:
                if other["id"] != tx_id and not other.get("by_hand") and merchant(other["description"]) == key:
                    other.pop("line_id", None)
                    other.pop("ignored", None)
                    other.pop("guessed", None)
                    _sort(other, doc["rules"], lines)
                    sorted_too += 1
    save(doc)
    return {"transaction": tx, "sorted_too": sorted_too}


def month(ym: str | None = None) -> dict[str, Any]:
    """A month's spending against the plan, line by line, and what's still to sort."""
    today = budget.today()
    ym = ym or today.strftime("%Y-%m")
    doc = load()
    lines = _lines()
    txs = [t for t in doc["transactions"] if t["date"].startswith(ym)]
    by_line: dict[str, float] = {}
    for t in txs:
        if t.get("line_id") and not t.get("ignored"):
            by_line[t["line_id"]] = by_line.get(t["line_id"], 0) - t["amount"]
    # How far through the month it is, so "on track" means something on the 10th.
    y, m = int(ym[:4]), int(ym[5:7])
    import calendar as _cal
    days = _cal.monthrange(y, m)[1]
    through = 1.0 if ym < today.strftime("%Y-%m") else min(1.0, today.day / days)
    rows = []
    for l in lines:
        plan = round(budget.monthly(l), 2)
        spent = round(by_line.get(l["id"], 0), 2)
        if not plan and not spent:
            continue
        status = "over" if plan and spent > plan else "ahead" if plan and spent > plan * through * 1.1 and through < 1 else "ok"
        rows.append({"id": l["id"], "name": l.get("name") or "", "section": l["section"], "plan": plan, "spent": spent, "status": status})
    unsorted = [t for t in txs if t["amount"] < 0 and not t.get("line_id") and not t.get("ignored")]
    spent_total = round(sum(-t["amount"] for t in txs if t["amount"] < 0 and not t.get("ignored")), 2)
    return {"month": ym, "through": round(through, 2), "lines": sorted(rows, key=lambda r: -r["spent"]),
            "over": [r for r in rows if r["status"] == "over"], "spent": spent_total,
            "unsorted": sorted(unsorted, key=lambda t: t["date"], reverse=True)[:100], "unsorted_count": len(unsorted),
            "guessed": [t for t in txs if t.get("guessed")][:50],
            "months": sorted({t["date"][:7] for t in doc["transactions"]}, reverse=True)[:24],
            "currency": budget.get().get("currency", "AUD"), "has_data": bool(doc["transactions"])}


def review_line(today: date) -> list[str]:
    """For the weekly review: the lines over plan this month, in words."""
    m = month(today.strftime("%Y-%m"))
    cur = m["currency"]
    out = [f"{r['name']}: {budget._money(r['spent'], cur)} of {budget._money(r['plan'], cur)} this month" for r in m["over"]]
    if m["unsorted_count"]:
        out.append(f"{m['unsorted_count']} spend{'s' if m['unsorted_count'] != 1 else ''} still to sort in Budget")
    return out


# -- balances ----------------------------------------------------------------------------------------

def _account(doc: dict[str, Any], name: str, kind: str = "everyday") -> dict[str, Any]:
    found = next((a for a in doc["accounts"] if a["name"].lower() == name.lower()), None)
    if found is None:
        found = {"id": uuid.uuid4().hex[:10], "name": name[:60], "kind": kind if kind in ACCOUNT_KINDS else "everyday", "line_id": None}
        doc["accounts"].append(found)
    return found


def _record_balance(doc: dict[str, Any], account: str, balance: float, on: str) -> None:
    acc = _account(doc, account)
    doc["balances"] = [b for b in doc["balances"] if not (b["account_id"] == acc["id"] and b["date"] == on)]
    doc["balances"].append({"account_id": acc["id"], "date": on, "balance": round(balance, 2)})
    doc["balances"] = sorted(doc["balances"], key=lambda b: (b["date"], b["account_id"]))[-5000:]


def set_balance(name: str, balance: float, on: date | None = None, kind: str | None = None, line_id: str | None = None) -> dict[str, Any]:
    doc = load()
    acc = _account(doc, name.strip(), kind or "everyday")
    if kind:
        acc["kind"] = kind if kind in ACCOUNT_KINDS else acc["kind"]
    if line_id is not None:
        acc["line_id"] = line_id or None
    _record_balance(doc, acc["name"], balance, (on or budget.today()).isoformat())
    save(doc)
    return balances()


def change_account(account_id: str, name: str | None = None, kind: str | None = None, line_id: str | None = None,
                   remove: bool = False) -> dict[str, Any] | None:
    doc = load()
    acc = next((a for a in doc["accounts"] if a["id"] == account_id), None)
    if acc is None:
        return None
    if remove:
        doc["accounts"] = [a for a in doc["accounts"] if a["id"] != account_id]
        doc["balances"] = [b for b in doc["balances"] if b["account_id"] != account_id]
    else:
        if name:
            acc["name"] = name.strip()[:60]
        if kind in ACCOUNT_KINDS:
            acc["kind"] = kind
        if line_id is not None:
            acc["line_id"] = line_id or None
    save(doc)
    return balances()


def _monthly_change(points: list[tuple[str, float]]) -> float | None:
    """Average change per month over about the last three months (needs points at least 3 weeks apart)."""
    if len(points) < 2:
        return None
    end_d, end_v = points[-1]
    end = date.fromisoformat(end_d)
    earlier = [(d, v) for d, v in points if (end - date.fromisoformat(d)).days >= 21]
    if not earlier:
        return None
    start_d, start_v = min(earlier, key=lambda p: abs((end - date.fromisoformat(p[0])).days - 91))
    days = (end - date.fromisoformat(start_d)).days
    return (end_v - start_v) / days * 30.44


def balances() -> dict[str, Any]:
    doc = load()
    lines = {l["id"]: l for l in _lines()}
    accounts = []
    for a in doc["accounts"]:
        pts = [(b["date"], b["balance"]) for b in doc["balances"] if b["account_id"] == a["id"]]
        latest = pts[-1] if pts else None
        rate = _monthly_change(pts)
        entry = {**a, "balance": latest[1] if latest else None, "as_of": latest[0] if latest else None, "per_month": round(rate, 2) if rate is not None else None}
        line = lines.get(a.get("line_id") or "")
        if line and line.get("goal") and latest:
            goal, have = float(line["goal"]), latest[1]
            entry["goal"] = {"line": line.get("name"), "target": goal, "percent": max(0, min(100, round(100 * have / goal))) if goal else None}
            if have >= goal:
                entry["goal"]["eta"] = "reached"
            elif rate and rate > 0:
                months = (goal - have) / rate
                eta = date.fromisoformat(latest[0]) + timedelta(days=round(months * 30.44))
                entry["goal"]["eta"] = eta.strftime("%b %Y")
                entry["goal"]["months"] = round(months, 1)
        accounts.append(entry)
    # Net worth by month: each account's last balance up to that month's end, carried forward.
    months = sorted({b["date"][:7] for b in doc["balances"]})
    series = []
    for ym in months[-24:]:
        total = 0.0
        for a in doc["accounts"]:
            pts = [b for b in doc["balances"] if b["account_id"] == a["id"] and b["date"][:7] <= ym]
            if pts:
                v = pts[-1]["balance"]
                total += -abs(v) if a["kind"] in OWED else v
        series.append({"month": ym, "net_worth": round(total, 2)})
    net = sum((-abs(a["balance"]) if a["kind"] in OWED else a["balance"]) for a in accounts if a["balance"] is not None)
    return {"accounts": accounts, "net_worth": round(net, 2) if accounts else None, "series": series,
            "kinds": list(ACCOUNT_KINDS), "currency": budget.get().get("currency", "AUD")}
