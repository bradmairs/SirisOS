"""Splitting the budget between incomes (11.12): who puts how much towards the expenses, savings and spending.

Choose the income sources to share it (all of them, or some: say both pays but not the car allowance) and how:

- **blocks** (11.13, the default): Expenses as one block, Spending as one block, and each savings type on its own.
  Each block goes whole to one income, the assignment closest to everyone paying the same share of their income;
  a block can instead be shared, weighted by income (Relocation is, unless changed), or given to one income;
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

METHODS = ("blocks", "income", "equal", "lines")
RULES = ("auto", "shared")  # a block's rule: one of these, or an income's id
SHARED_BY_DEFAULT = re.compile(r"relocat", re.I)  # 11.13: Relocation is shared between the incomes by default
SEARCH_LIMIT = 200_000  # assignments tried in full before falling back to biggest-first
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


def blocks_of(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Expenses as one block, Spending as one, and each savings line on its own (11.13)."""
    lines = _lines(doc)
    out = []
    for section in ("expenses", "spending"):
        mine = [line for line in lines if line["section"] == section]
        if mine:
            out.append({"key": section, "name": SECTION_LABEL[section], "monthly": round(sum(x["monthly"] for x in mine), 2),
                        "lines": [x["id"] for x in mine]})
    out += [{"key": x["id"], "name": x["name"], "monthly": x["monthly"], "lines": [x["id"]]} for x in lines if x["section"] == "savings"]
    return out


def default_rules(doc: dict[str, Any]) -> dict[str, str]:
    return {b["key"]: "shared" for b in blocks_of(doc) if SHARED_BY_DEFAULT.search(b["name"]) and b["key"] not in ("expenses", "spending")}


def _assign(sizes: list[float], room: dict[str, float]) -> list[str]:
    """Each block to one income, so that what each pays is as close as can be to its target (`room`: target less
    what it already pays). Every assignment is tried when there are few enough; otherwise biggest block first."""
    ids = list(room)
    if not sizes:
        return []
    if len(ids) ** len(sizes) <= SEARCH_LIMIT:
        from itertools import product

        best, best_cost = None, float("inf")
        for combo in product(range(len(ids)), repeat=len(sizes)):
            load = dict.fromkeys(ids, 0.0)
            for size, who in zip(sizes, combo):
                load[ids[who]] += size
            cost = sum((room[i] - load[i]) ** 2 for i in ids)
            if cost < best_cost - 1e-6:
                best, best_cost = combo, cost
        return [ids[w] for w in best]  # type: ignore[union-attr]
    left = dict(room)
    out: list[str] = [""] * len(sizes)
    for n in sorted(range(len(sizes)), key=lambda k: -sizes[k]):
        who = max(ids, key=lambda i: (left[i], -ids.index(i)))
        out[n] = who
        left[who] -= sizes[n]
    return out


def compute(doc: dict[str, Any], sources: list[str] | None = None, method: str = "blocks",
            personal: dict[str, str] | None = None, blocks: dict[str, str] | None = None) -> dict[str, Any]:
    """The split. `sources`: income ids (None or empty: all). `personal`: {line id: source id, or "shared"} on top of
    the suggestions (not for blocks). `blocks`: {block key: "auto", "shared" or an income id} on top of the
    defaults (blocks only)."""
    if method not in METHODS:
        raise ValueError(f"How to split is one of {', '.join(METHODS)}.")
    every = {i["id"]: i for i in doc.get("income") or []}
    chosen = [every[s] for s in (sources or list(every)) if s in every and service.monthly(every[s]) > 0]
    if not chosen:
        raise ValueError("Choose at least one income source with an amount.")
    ids = [s["id"] for s in chosen]
    income = {s["id"]: service.monthly(s) for s in chosen}
    lines = _lines(doc)
    by_income = {i: income[i] / sum(income.values()) for i in ids}
    if method == "blocks":
        return _blocks(doc, every, ids, income, lines, by_income, blocks)
    pins = {**suggested_personal(doc, chosen), **(personal or {})}
    pins = {k: v for k, v in pins.items() if v in ids}  # "shared", or a source not in the split: shared
    total = sum(line["monthly"] for line in lines)
    weight = dict(by_income) if method != "equal" else {i: 1 / len(ids) for i in ids}
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
    return _result(method, every, ids, income, lines, alloc, set(pins), {
        "personal": {k: v for k, v in pins.items()}, "suggested": suggested_personal(doc, chosen)})


def _blocks(doc: dict[str, Any], every: dict[str, Any], ids: list[str], income: dict[str, float], lines: list[dict[str, Any]],
            weight: dict[str, float], blocks: dict[str, str] | None) -> dict[str, Any]:
    """Blocks (11.13): each block whole to one income, closest to everyone paying the same share of their income; a
    shared block split by income; a block given to an income stays with it."""
    all_blocks = blocks_of(doc)
    rules = {**default_rules(doc), **{k: v for k, v in (blocks or {}).items() if v in RULES or v in every}}
    rule = {b["key"]: (rules.get(b["key"], "auto") if rules.get(b["key"], "auto") in RULES or rules.get(b["key"]) in ids else "auto")
            for b in all_blocks}
    total = sum(b["monthly"] for b in all_blocks)
    target = {i: weight[i] * total for i in ids}
    load = dict.fromkeys(ids, 0.0)
    payer: dict[str, dict[str, float]] = {}  # block key -> income -> share (0-1)
    for b in all_blocks:
        if rule[b["key"]] == "shared":
            payer[b["key"]] = dict(weight)
        elif rule[b["key"]] in ids:
            payer[b["key"]] = {rule[b["key"]]: 1.0}
        else:
            continue
        for i, part in payer[b["key"]].items():
            load[i] += b["monthly"] * part
    auto = [b for b in all_blocks if b["key"] not in payer]
    for b, who in zip(auto, _assign([b["monthly"] for b in auto], {i: target[i] - load[i] for i in ids})):
        payer[b["key"]] = {who: 1.0}
    by_id = {line["id"]: line for line in lines}
    alloc: dict[str, dict[str, float]] = {i: {} for i in ids}
    for b in all_blocks:
        for i, part in payer[b["key"]].items():
            for lid in b["lines"]:
                alloc[i][lid] = round(by_id[lid]["monthly"] * part, 2)
    block_out = [{"key": b["key"], "name": b["name"], "monthly": b["monthly"], "rule": rule[b["key"]],
                  "paid_by": [{"id": i, "name": every[i]["name"], "monthly": round(b["monthly"] * part, 2), "share": round(part * 100, 1)}
                              for i, part in payer[b["key"]].items()]} for b in all_blocks]
    out = _result("blocks", every, ids, income, lines, alloc, set(), {"personal": {}, "suggested": {}, "blocks": block_out, "rules": rule})
    for s in out["sources"]:  # what each income pays, block by block
        s["blocks"] = [{"key": b["key"], "name": b["name"], "monthly": p["monthly"], "shared": len(b["paid_by"]) > 1, "share": p["share"]}
                       for b in block_out for p in b["paid_by"] if p["id"] == s["id"] and p["monthly"] > 0]
    return out


def _result(method: str, every: dict[str, Any], ids: list[str], income: dict[str, float], lines: list[dict[str, Any]],
            alloc: dict[str, dict[str, float]], pins: set[str], extra: dict[str, Any]) -> dict[str, Any]:
    total = sum(line["monthly"] for line in lines)
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
        "lines": [{"id": line["id"], "name": line["name"], "section": line["section"], "monthly": line["monthly"]} for line in lines],
        "blocks": [], **extra,
    }


def _settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw or {}
    return {"sources": list(raw.get("sources") or []), "method": raw.get("method") if raw.get("method") in METHODS else "blocks",
            "personal": dict(raw.get("personal") or {}), "blocks": dict(raw.get("blocks") or {})}


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


def save(sources: list[str] | None, method: str, personal: dict[str, str] | None, blocks: dict[str, str] | None = None) -> dict[str, Any]:
    doc = service.get()
    result = compute(doc, sources, method, personal, blocks)
    settings = {"sources": list(sources or []), "method": method, "personal": dict(personal or {}), "blocks": dict(blocks or {})}
    json_store.write(_path(), {"settings": settings, "made_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "fingerprint": fingerprint(doc), "snapshot": _snapshot(doc), "result": result})
    return get()
