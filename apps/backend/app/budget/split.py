"""Splitting the budget between incomes (11.12): who puts how much towards the expenses, savings and spending.

Choose the income sources to share it (all of them, or some: say both pays but not the car allowance) and how:

- **income** (the default): everyone puts in the same share of what they earn, so a bigger income pays more;
- **equal**: everyone puts in the same amount;
- **lines**: each line goes whole to one source (fewer transfers: "Sam pays the rent, Alex pays the power"),
  balanced as close as whole lines allow to the in-proportion amounts.

**Personal lines** go to their owner whatever the method: a line naming one source's owner ("Sam", "Gym - Sam",
"Phone - Alex") is suggested, and any line can be given to a source or left shared. The method still
balances the whole: what someone already pays personally counts towards their share, and the shared lines make up the
rest.

For each source: the total, per month and per its own pay (Alex's pay is fortnightly), by section and line, the share
of its income it takes, and what's left. The chosen split is kept (budget-split.json) with a fingerprint of the
budget it was worked out on; when the budget changes, the split says what changed and **Redo** works it out again
with the same choices.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from app.budget import service
from app.services import json_store

METHODS = ("income", "equal", "lines")
SECTION_LABEL = {"expenses": "Expenses", "savings": "Savings", "spending": "Spending"}


def _path():
    return json_store.data_path("SIRISOS_BUDGET_SPLIT_PATH", "budget-split.json")


def owner(source: dict[str, Any]) -> str:
    """Whose income a source is, from its name: "Sam's Pay" is Sam's, and so is "Sam pay". "Car Allowance" is
    nobody's, so a line like "Car Insurance" isn't taken as personal to it."""
    name = str(source.get("name") or "").strip()
    m = re.match(r"^([A-Za-z][\w-]*)(?:'s|’s)\s", name + " ") or re.match(r"^([A-Za-z][\w-]*)\s+(?:pay|salary|wages?|income)\b", name, re.I)
    return m.group(1).lower() if m else ""


def _lines(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return [{**line, "section": s, "monthly": round(service.monthly(line), 2)}
            for s in service.SECTIONS for line in (doc.get("sections") or {}).get(s, []) if service.monthly(line) > 0]


def suggested_personal(doc: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, str]:
    """Spending and savings lines named after a source's owner: {line id: source id}."""
    owners = {owner(s): s["id"] for s in sources if owner(s)}
    out = {}
    for line in _lines(doc):
        # "Sam", "Gym - Sam", "Phone (Alex)", "Alex's lunches": a line naming exactly one owner is theirs
        words = set(re.findall(r"[a-z][\w-]*", line["name"].lower().replace("’", "'").replace("'s", "")))
        named = [o for o in owners if o in words]
        if len(named) == 1:
            out[line["id"]] = owners[named[0]]
    return out


def fingerprint(doc: dict[str, Any]) -> str:
    keep = {"income": [(i["id"], i["amount"], i["every"]) for i in doc.get("income") or []],
            "lines": [(s, line["id"], line["name"], line["amount"], line["every"]) for s in service.SECTIONS
                      for line in (doc.get("sections") or {}).get(s, [])]}
    return hashlib.sha256(json.dumps(keep, sort_keys=True).encode()).hexdigest()[:16]


def _snapshot(doc: dict[str, Any]) -> dict[str, Any]:
    return {"income": {i["id"]: {"name": i["name"], "monthly": round(service.monthly(i), 2)} for i in doc.get("income") or []},
            "lines": {line["id"]: {"name": line["name"], "monthly": line["monthly"], "section": line["section"]} for line in _lines(doc)}}


def changes(before: dict[str, Any], doc: dict[str, Any]) -> list[str]:
    """What changed in the budget since a split was made, in words."""
    now = _snapshot(doc)
    out: list[str] = []
    for kind, label in (("income", "income"), ("lines", "line")):
        old, new = before.get(kind) or {}, now[kind]
        for k, v in new.items():
            if k not in old:
                out.append(f"{v['name']} added (${v['monthly']:,.0f} a month)")
            elif abs(old[k]["monthly"] - v["monthly"]) >= 0.5:
                out.append(f"{v['name']} {'up' if v['monthly'] > old[k]['monthly'] else 'down'} from ${old[k]['monthly']:,.0f} to ${v['monthly']:,.0f} a month")
            elif old[k]["name"] != v["name"]:
                out.append(f"{old[k]['name']} renamed {v['name']}")
        out += [f"{v['name']} removed" for k, v in old.items() if k not in new]
    return out[:12]


def compute(doc: dict[str, Any], sources: list[str] | None = None, method: str = "income",
            personal: dict[str, str] | None = None) -> dict[str, Any]:
    """The split. `sources`: income ids (None or empty: all). `personal`: {line id: source id, or "shared"} on top of
    the suggestions."""
    if method not in METHODS:
        raise ValueError(f"How to split is one of {', '.join(METHODS)}.")
    every = {i["id"]: i for i in doc.get("income") or []}
    chosen = [every[s] for s in (sources or list(every)) if s in every and service.monthly(every[s]) > 0]
    if not chosen:
        raise ValueError("Choose at least one income source with an amount.")
    ids = [s["id"] for s in chosen]
    income = {s["id"]: service.monthly(s) for s in chosen}
    lines = _lines(doc)
    pins = {**suggested_personal(doc, chosen), **(personal or {})}
    pins = {k: v for k, v in pins.items() if v in ids}  # "shared", or a source not in the split: shared
    total = sum(line["monthly"] for line in lines)
    weight = {i: (income[i] / sum(income.values())) if method != "equal" else 1 / len(ids) for i in ids}
    target = {i: weight[i] * total for i in ids}
    alloc: dict[str, dict[str, float]] = {i: {} for i in ids}  # source -> line id -> monthly
    for line in lines:
        if line["id"] in pins:
            alloc[pins[line["id"]]][line["id"]] = line["monthly"]
    pinned = {i: sum(alloc[i].values()) for i in ids}
    shared = [line for line in lines if line["id"] not in pins]
    pool = sum(line["monthly"] for line in shared)
    need = {i: max(0.0, target[i] - pinned[i]) for i in ids}
    if sum(need.values()) <= 0:
        need = dict(weight)
    share = {i: need[i] / sum(need.values()) for i in ids}
    if method == "lines":
        left = {i: share[i] * pool for i in ids}
        for line in sorted(shared, key=lambda x: -x["monthly"]):
            who = max(ids, key=lambda i: (left[i], -ids.index(i)))
            alloc[who][line["id"]] = line["monthly"]
            left[who] -= line["monthly"]
    else:
        for line in shared:
            for i in ids:
                alloc[i][line["id"]] = round(line["monthly"] * share[i], 2)
    by_id = {line["id"]: line for line in lines}
    out_sources = []
    for i in ids:
        src = every[i]
        mine = alloc[i]
        tot = round(sum(mine.values()), 2)
        per_pay = service.PER_MONTH.get(src.get("every") or "monthly", 1.0)
        out_sources.append({
            "id": i, "name": src["name"], "every": src.get("every") or "monthly", "income": round(income[i], 2),
            "total": tot, "per_pay": round(tot / per_pay, 2), "left": round(income[i] - tot, 2),
            "percent_of_income": round(tot / income[i] * 100, 1) if income[i] else None,
            "share_of_budget": round(tot / total * 100, 1) if total else 0.0,
            "share_of_income": round(income[i] / sum(income.values()) * 100, 1),
            "sections": {s: round(sum(v for k, v in mine.items() if by_id[k]["section"] == s), 2) for s in service.SECTIONS},
            "lines": [{"id": k, "name": by_id[k]["name"], "section": by_id[k]["section"], "monthly": round(v, 2),
                       "whole": abs(v - by_id[k]["monthly"]) < 0.01, "personal": k in pins}
                      for k, v in sorted(mine.items(), key=lambda kv: (service.SECTIONS.index(by_id[kv[0]]["section"]), -kv[1])) if v > 0],
        })
    left_out = [{"id": s["id"], "name": s["name"], "income": round(service.monthly(s), 2)} for s in every.values() if s["id"] not in ids]
    in_split = sum(income.values())
    return {
        "method": method, "sources": out_sources, "left_out": left_out, "total": round(total, 2),
        "income": round(in_split, 2), "short": round(max(0.0, total - in_split), 2),
        "personal": {k: v for k, v in pins.items()}, "suggested": suggested_personal(doc, chosen),
        "lines": [{"id": line["id"], "name": line["name"], "section": line["section"], "monthly": line["monthly"]} for line in lines],
    }


def _settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw or {}
    return {"sources": list(raw.get("sources") or []), "method": raw.get("method") if raw.get("method") in METHODS else "income",
            "personal": dict(raw.get("personal") or {})}


def get() -> dict[str, Any]:
    """The saved split checked against today's budget: still right, or what changed and the split it would be now."""
    doc = service.get()
    saved = json_store.read(_path(), None)
    if not saved:
        try:
            return {"saved": None, "now": compute(doc), "stale": False, "changes": [], "settings": _settings(None)}
        except ValueError as exc:
            return {"saved": None, "now": None, "stale": False, "changes": [], "settings": _settings(None), "error": str(exc)}
    settings = _settings(saved.get("settings"))
    stale = saved.get("fingerprint") != fingerprint(doc)
    known = {i["id"] for i in doc.get("income") or []}
    settings["sources"] = [s for s in settings["sources"] if s in known]
    try:
        now = compute(doc, **settings) if stale else saved.get("result")
        error = None
    except ValueError as exc:
        now, error = None, str(exc)
    return {"saved": {"made_at": saved.get("made_at"), "result": saved.get("result")}, "now": now, "stale": stale,
            "changes": changes(saved.get("snapshot") or {}, doc) if stale else [], "settings": settings, "error": error}


def save(sources: list[str] | None, method: str, personal: dict[str, str] | None) -> dict[str, Any]:
    doc = service.get()
    result = compute(doc, sources, method, personal)
    settings = {"sources": list(sources or []), "method": method, "personal": dict(personal or {})}
    json_store.write(_path(), {"settings": settings, "made_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "fingerprint": fingerprint(doc), "snapshot": _snapshot(doc), "result": result})
    return get()
