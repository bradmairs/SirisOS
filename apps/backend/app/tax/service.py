"""Tax-claimable receipts (11.18): work-related deductions for an Australian return, by financial year.

Each claim is a receipt kept from email (a SirisAI document, linked by id) or added by hand, with what share of it was
for work. The ATO rules applied (individuals, employees; checked against ato.gov.au for 2025-26):

- The three golden rules: you spent the money yourself and weren't reimbursed, it was for earning your income (not
  private), and you have a record. A reimbursed claim counts as nothing; a part-private one only for its work share.
- $300 in total: if all your work-related claims come to $300 or less, you don't need written evidence (you still need
  to show how you worked them out). Over $300, every one needs a receipt or invoice.
- Small items: $10 or less each, $200 or less altogether, can be recorded in a diary instead of with receipts.
- Tools and equipment (a depreciating asset): $300 or less is deducted in full the year you buy it; over $300 is
  depreciated over its effective life (decline in value), so only part of it is claimed this year. Items in a set
  count as one item against the $300.
- Working from home, fixed rate: 70c an hour (from 1 July 2024), with a record of actual hours. The rate covers
  energy, internet, phone, stationery and computer consumables, so those can't also be claimed separately.
- Car, cents per kilometre: 88c a km (2024-25 and 2025-26), up to 5,000 work km, not home to work.
- Donations: $2 or more to a deductible gift recipient, with a receipt.
- Keep records for five years from when you lodge.

This is a record-keeper, not tax advice: the screen says to check with the ATO or a registered tax agent.
"""

from __future__ import annotations

import re
import secrets
from datetime import date, datetime
from typing import Any

from app.services import json_store

WFH_RATE = 0.70       # $ an hour, fixed rate method, from 1 July 2024
KM_RATE = 0.88        # $ a km, cents per kilometre method, 2024-25 and 2025-26
KM_CAP = 5000
NO_EVIDENCE_TOTAL = 300.0
ASSET_LIMIT = 300.0
SMALL_ITEM, SMALL_TOTAL = 10.0, 200.0

# id: (label, what it covers, whether it's work-related (the $300 rule counts these), depreciates over $300)
CATEGORIES: dict[str, dict[str, Any]] = {
    "equipment": {"label": "Tools and equipment", "work": True, "asset": True,
                  "hint": "Laptops, monitors, tools, a work bag, an office chair or desk. Over $300 is depreciated, not claimed at once."},
    "home-office": {"label": "Home office running costs", "work": True, "asset": False,
                    "hint": "Electricity, internet, phone, stationery: only if you're not using the 70c-an-hour fixed rate, which already covers them."},
    "phone-internet": {"label": "Phone and internet", "work": True, "asset": False,
                       "hint": "The work share of your phone and internet bills (not with the fixed rate)."},
    "professional": {"label": "Memberships and registration", "work": True, "asset": False,
                     "hint": "Engineers Australia, chartership (CPEng) and registration fees, union fees, work subscriptions."},
    "self-education": {"label": "Self-education and CPD", "work": True, "asset": False,
                       "hint": "Courses, conferences, textbooks and seminars tied to your current job."},
    "clothing": {"label": "Work clothing and PPE", "work": True, "asset": False,
                 "hint": "Protective gear (steel caps, hi-vis, hard hat), uniforms and occupation-specific clothing, and their laundry. Not everyday clothes."},
    "travel": {"label": "Work travel and car", "work": True, "asset": False,
               "hint": "Parking, tolls, fares and accommodation for work trips away from your usual workplace. Not home to work."},
    "other-work": {"label": "Other work-related", "work": True, "asset": False, "hint": "Anything else you spent to earn your pay."},
    "donation": {"label": "Donations", "work": False, "asset": False, "hint": "$2 or more to a registered charity (DGR), with a receipt."},
    "tax-affairs": {"label": "Managing your tax", "work": False, "asset": False, "hint": "A tax agent's fee, tax software, travel to your tax agent."},
    "income-protection": {"label": "Income protection insurance", "work": False, "asset": False, "hint": "Premiums paid yourself, not through super."},
}

# A first guess at the category from who a receipt is from.
GUESS = [
    (r"engineers australia|\bea\b|cpeng|union|professionals australia|registration board|bpeq", "professional"),
    (r"officeworks|jb hi.?fi|harvey norman|apple|dell|lenovo|bunnings|total tools|sydney tools|ikea|msy|centre com|umart|koala", "equipment"),
    (r"telstra|optus|vodafone|aussie broadband|tpg|iinet|superloop|belong|amaysim|origin|agl|energyaustralia|red energy|lumo", "phone-internet"),
    (r"udemy|coursera|linkedin learning|university|tafe|ieaust|conference|seminar|o'?reilly|pluralsight", "self-education"),
    (r"workwear|hard yakka|king gee|blundstone|steel ?cap|hi.?vis|rsea|totally workwear|protector alsafe", "clothing"),
    (r"wilson parking|secure parking|care park|linkt|citylink|eastlink|myki|uber|didi|ola|qantas|virgin|jetstar|airbnb|hotel", "travel"),
    (r"red cross|salvation army|unicef|world vision|cancer council|oxfam|rspca|smith family|donation", "donation"),
    (r"h&r block|etax|tax agent|accountant|itp", "tax-affairs"),
]


def _path():
    return json_store.data_path("SIRISOS_TAX_PATH", "tax.json")


def load() -> dict[str, Any]:
    raw = json_store.read(_path(), {})
    doc = raw if isinstance(raw, dict) else {}
    doc.setdefault("claims", [])
    doc.setdefault("not_tax", [])  # SirisAI receipt ids marked "not a tax receipt"
    doc.setdefault("years", {})   # "2026": {"wfh_hours": 0, "car_km": 0}
    return doc


def _save(doc: dict[str, Any]) -> None:
    json_store.write(_path(), doc)


def fy_of(day: str | date) -> int:
    """The financial year a day falls in, by the year it ends: 3 Nov 2026 is in 2027 (1 Jul 2026 to 30 Jun 2027)."""
    d = day if isinstance(day, date) else date.fromisoformat(str(day)[:10])
    return d.year + 1 if d.month >= 7 else d.year


def fy_label(fy: int) -> str:
    return f"{fy - 1}-{str(fy)[-2:]}"


def current_fy(today: date | None = None) -> int:
    return fy_of(today or date.today())


AMOUNT = re.compile(r"\$ ?([\d,]{1,12}(?:\.\d\d?)?)")


def amount_in(text: str) -> float | None:
    """The last dollar amount in a receipt's summary ("JB Hi-Fi, 20 Oct 2026, $899.00" is 899.0)."""
    found = AMOUNT.findall((text or "")[:2000])
    if not found:
        return None
    try:
        return float(found[-1].replace(",", ""))
    except ValueError:
        return None


def guess_category(*texts: str) -> str:
    hay = " ".join(t or "" for t in texts).lower()
    for pattern, cat in GUESS:
        if re.search(pattern, hay):
            return cat
    return "other-work"


def _clean(body: dict[str, Any], old: dict[str, Any] | None = None) -> dict[str, Any]:
    c = dict(old or {})
    for key in ("date", "vendor", "description", "category", "note"):
        if key in body:
            c[key] = str(body[key] or "").strip()[:300]
    for key in ("amount", "work_pct"):
        if key in body and body[key] is not None:
            c[key] = float(body[key])
    for key in ("reimbursed", "has_receipt", "set_item"):
        if key in body:
            c[key] = bool(body[key])
    if "doc_id" in body:
        c["doc_id"] = int(body["doc_id"]) if body["doc_id"] else None
    c.setdefault("work_pct", 100.0)
    c.setdefault("has_receipt", bool(c.get("doc_id")))
    c.setdefault("reimbursed", False)
    if c.get("category") not in CATEGORIES:
        c["category"] = "other-work"
    try:
        date.fromisoformat(c.get("date", ""))
    except ValueError:
        raise ValueError("A date like 2026-11-03.") from None
    if not (0 < c.get("amount", 0) < 1_000_000):
        raise ValueError("An amount over $0.")
    if not 0 <= c["work_pct"] <= 100:
        raise ValueError("A work share from 0 to 100%.")
    if not c.get("vendor") and not c.get("description"):
        raise ValueError("Who it's from or what it was.")
    return c


def add(body: dict[str, Any]) -> dict[str, Any]:
    doc = load()
    claim = _clean(body)
    claim["id"] = "tx_" + secrets.token_hex(5)
    claim["added"] = datetime.now().isoformat(timespec="seconds")  # noqa: DTZ005
    claim["source"] = "email" if claim.get("doc_id") else "manual"
    doc["claims"].append(claim)
    if claim.get("doc_id") in doc["not_tax"]:
        doc["not_tax"].remove(claim["doc_id"])
    _save(doc)
    return claim


def change(claim_id: str, body: dict[str, Any]) -> dict[str, Any]:
    doc = load()
    for i, c in enumerate(doc["claims"]):
        if c["id"] == claim_id:
            doc["claims"][i] = _clean(body, c)
            _save(doc)
            return doc["claims"][i]
    raise KeyError(claim_id)


def remove(claim_id: str) -> None:
    doc = load()
    before = len(doc["claims"])
    doc["claims"] = [c for c in doc["claims"] if c["id"] != claim_id]
    if len(doc["claims"]) == before:
        raise KeyError(claim_id)
    _save(doc)


def not_tax(doc_id: int, on: bool = True) -> None:
    doc = load()
    ids = set(doc["not_tax"])
    (ids.add if on else ids.discard)(doc_id)
    doc["not_tax"] = sorted(ids)
    _save(doc)


def set_year(fy: int, body: dict[str, Any]) -> dict[str, Any]:
    doc = load()
    year = doc["years"].setdefault(str(fy), {})
    for key in ("wfh_hours", "car_km"):
        if key in body and body[key] is not None:
            v = float(body[key])
            if not 0 <= v <= 10_000:
                raise ValueError("Hours or km from 0 to 10,000.")
            year[key] = v
    _save(doc)
    return year


def _treat(c: dict[str, Any]) -> dict[str, Any]:
    """How a claim counts: the work share, nothing if reimbursed, an asset over $300 depreciated."""
    cat = CATEGORIES[c["category"]]
    share = 0.0 if c.get("reimbursed") else round(c["amount"] * c["work_pct"] / 100, 2)
    how, note = "deduct", ""
    if c.get("reimbursed"):
        how, note = "none", "Reimbursed by your employer, so it can't be claimed."
    elif cat["asset"] and c["amount"] > ASSET_LIMIT:
        how, note = "depreciate", ("Over $300: claim its decline in value over its effective life (the ATO's depreciation "
                                   "tool works it out), not the whole cost this year.")
    elif cat["asset"] and c.get("set_item"):
        how, note = "check", "Part of a set: the set's total counts against the $300."
    elif c["category"] == "donation" and c["amount"] < 2:
        how, note, share = "none", "Donations under $2 can't be claimed.", 0.0
    elif c["category"] == "clothing":
        note = "Only protective, uniform or occupation-specific clothing counts."
    return {**c, "claimable": share if how != "none" else 0.0, "treatment": how, "treatment_note": note,
            "fy": fy_of(c["date"]), "work": cat["work"]}


def year(fy: int, receipts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    doc = load()
    claims = [_treat(c) for c in doc["claims"] if fy_of(c["date"]) == fy]
    claims.sort(key=lambda c: c["date"], reverse=True)
    settings = doc["years"].get(str(fy), {})
    hours, km = float(settings.get("wfh_hours") or 0), float(settings.get("car_km") or 0)
    wfh = round(hours * WFH_RATE, 2)
    car = round(min(km, KM_CAP) * KM_RATE, 2)

    by_cat: dict[str, dict[str, Any]] = {}
    for c in claims:
        b = by_cat.setdefault(c["category"], {"category": c["category"], "label": CATEGORIES[c["category"]]["label"], "count": 0, "claimable": 0.0, "depreciate": 0})
        b["count"] += 1
        b["claimable"] = round(b["claimable"] + (c["claimable"] if c["treatment"] != "depreciate" else 0), 2)
        b["depreciate"] += c["treatment"] == "depreciate"

    immediate = [c for c in claims if c["treatment"] in ("deduct", "check")]
    work_total = round(sum(c["claimable"] for c in immediate if c["work"]) + wfh + car, 2)
    total = round(sum(c["claimable"] for c in immediate) + wfh + car, 2)
    work_items = [c for c in claims if c["work"] and c["treatment"] != "none"]
    missing = [c["id"] for c in work_items if not c.get("has_receipt")]
    small = [c for c in work_items if c["amount"] <= SMALL_ITEM]
    small_total = round(sum(c["amount"] for c in small), 2)

    checks: list[dict[str, str]] = []
    if work_total > NO_EVIDENCE_TOTAL and missing:
        diary_ok = all(next(c for c in claims if c["id"] == m)["amount"] <= SMALL_ITEM for m in missing) and small_total <= SMALL_TOTAL
        checks.append({"level": "info" if diary_ok else "warn",
                       "text": (f"Work claims come to ${work_total:,.2f}, over $300, so each needs written evidence. "
                                + ("The ones without a receipt are all $10 or less and under $200 together: a diary record of them is enough."
                                   if diary_ok else f"{len(missing)} {'has' if len(missing) == 1 else 'have'} no receipt yet."))})
    elif work_total and work_total <= NO_EVIDENCE_TOTAL:
        checks.append({"level": "ok", "text": f"Work claims come to ${work_total:,.2f}: $300 or less, so receipts aren't required, "
                                              "but you need to be able to show how you worked each one out."})
    covered = [c for c in claims if c["category"] in ("home-office", "phone-internet") and c["treatment"] != "none"]
    if hours and covered:
        checks.append({"level": "warn", "text": "You're using the 70c-an-hour fixed rate, which already covers energy, internet, phone and "
                                                f"stationery: {len(covered)} home office or phone claim{'s' if len(covered) != 1 else ''} may be counted twice."})
    if hours:
        checks.append({"level": "info", "text": "Keep a record of your actual hours at home (a timesheet, roster or diary), and one bill for each "
                                                "expense the fixed rate covers."})
    if km > KM_CAP:
        checks.append({"level": "warn", "text": f"Cents per km is capped at {KM_CAP:,} km: {km:,.0f} km would need the logbook method."})
    deps = [c for c in claims if c["treatment"] == "depreciate"]
    if deps:
        checks.append({"level": "info", "text": f"{len(deps)} item{'s' if len(deps) != 1 else ''} over $300 to depreciate: not in the total below."})

    not_tax_ids = set(doc["not_tax"])
    claimed_ids = {c.get("doc_id") for c in doc["claims"] if c.get("doc_id")}
    to_sort = []
    for r in receipts or []:
        rid = r.get("id")
        added = str(r.get("added_at") or "")[:10]
        if not rid or rid in claimed_ids or rid in not_tax_ids or not added:
            continue
        try:
            if fy_of(added) != fy:
                continue
        except ValueError:
            continue
        to_sort.append({"doc_id": rid, "date": added, "vendor": r.get("sender") or "", "description": r.get("title") or "",
                        "amount": amount_in(r.get("summary") or ""), "category": guess_category(r.get("sender", ""), r.get("title", ""), r.get("summary", ""))})
    to_sort.sort(key=lambda x: x["date"], reverse=True)

    return {
        "fy": fy, "label": fy_label(fy), "start": f"{fy - 1}-07-01", "end": f"{fy}-06-30",
        "claims": claims, "by_category": sorted(by_cat.values(), key=lambda b: -b["claimable"]),
        "wfh": {"hours": hours, "rate": WFH_RATE, "claimable": wfh}, "car": {"km": km, "rate": KM_RATE, "cap": KM_CAP, "claimable": car},
        "work_total": work_total, "total": total, "missing_receipts": missing, "checks": checks, "to_sort": to_sort,
        "years": sorted({fy_of(c["date"]) for c in doc["claims"]} | {fy, current_fy()}, reverse=True),
    }


def csv_rows(fy: int) -> list[list[Any]]:
    y = year(fy)
    rows: list[list[Any]] = [["Date", "From", "What", "Category", "Amount", "Work %", "Claimable", "Treatment", "Receipt", "Source", "Note"]]
    for c in sorted(y["claims"], key=lambda c: c["date"]):
        rows.append([c["date"], c.get("vendor", ""), c.get("description", ""), CATEGORIES[c["category"]]["label"], f"{c['amount']:.2f}",
                     f"{c['work_pct']:g}", f"{c['claimable']:.2f}", c["treatment"], "yes" if c.get("has_receipt") else "no", c.get("source", ""),
                     c.get("note", "")])
    if y["wfh"]["hours"]:
        rows.append(["", "", f"Working from home: {y['wfh']['hours']:g} hours at 70c", "Working from home (fixed rate)", "", "", f"{y['wfh']['claimable']:.2f}", "deduct", "", "", ""])
    if y["car"]["km"]:
        rows.append(["", "", f"Car: {min(y['car']['km'], KM_CAP):g} km at 88c", "Car (cents per km)", "", "", f"{y['car']['claimable']:.2f}", "deduct", "", "", ""])
    return rows
