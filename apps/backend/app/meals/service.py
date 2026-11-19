"""The week's dinners and the shopping for them (10.2).

Plan a dinner for each night, from your Mealie recipes when Mealie is set up
(mealie.py) or as plain words with your own ingredients. With Mealie, the plan
is Mealie's own meal plan, so planning in either shows in both. Dinners you
have often are offered first.

The shopping list is the week's ingredients, merged (two recipes with onion
make one line), less staples you always have (salt, pepper, oil...) and things
already on your Home Assistant shopping list. Tick what you still need and it
goes on that list, through SirisAI.

Kept in meals.json (SIRISOS_MEALS_PATH).
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from app.hub import sirisai_api
from app.hub.service import Hub
from app.meals import mealie
from app.services import json_store

DEFAULT_STAPLES = ["salt", "pepper", "olive oil", "oil", "water"]
DAYS = 7


def _path():
    return json_store.data_path("SIRISOS_MEALS_PATH", "meals.json")


def load() -> dict[str, Any]:
    doc = json_store.read(_path(), {}) or {}
    doc.setdefault("plan", {})
    doc.setdefault("counts", {})
    doc.setdefault("staples", list(DEFAULT_STAPLES))
    doc.setdefault("list", None)
    return doc


def save(doc: dict[str, Any]) -> None:
    cutoff = (date.today() - timedelta(days=120)).isoformat()  # noqa: DTZ011 (a rough trim)
    doc["plan"] = {k: v for k, v in doc["plan"].items() if k >= cutoff}
    json_store.write(_path(), doc)


def often(doc: dict[str, Any], n: int = 8) -> list[dict[str, Any]]:
    rows = sorted(doc["counts"].values(), key=lambda r: (-r["n"], r["title"].lower()))
    return [{"title": r["title"], "slug": r.get("slug"), "recipe_id": r.get("recipe_id"), "times": r["n"]} for r in rows[:n]]


async def week(start: date) -> dict[str, Any]:
    doc = load()
    end = start + timedelta(days=DAYS - 1)
    from_mealie: dict[str, dict[str, Any]] = {}
    error = None
    if mealie.configured():
        try:
            for p in await mealie.plans(start, end):
                from_mealie.setdefault(p["date"], p)
        except mealie.MealieError as exc:
            error = str(exc)
    days = []
    for i in range(DAYS):
        d = (start + timedelta(days=i)).isoformat()
        local = doc["plan"].get(d)
        m = from_mealie.get(d)
        if m:
            dinner = {"title": m["title"], "slug": m.get("slug"), "recipe_id": m.get("recipe_id"), "source": "mealie", "mealie_id": m.get("id"),
                      "url": mealie.recipe_link(m["slug"]) if m.get("slug") else None,
                      "ingredients": (local or {}).get("ingredients") if (local or {}).get("title") == m["title"] else None}
        elif local and not (mealie.configured() and error is None and local.get("source") == "mealie"):
            dinner = {**local, "url": mealie.recipe_link(local["slug"]) if local.get("slug") and mealie.configured() else None}
        else:
            dinner = None
        days.append({"date": d, "dinner": dinner})
    return {"start": start.isoformat(), "days": days, "often": often(doc), "staples": doc["staples"], "list": doc["list"],
            "mealie": {"configured": mealie.configured(), "error": error}}


def _count(doc: dict[str, Any], title: str, slug: str | None, recipe_id: str | None) -> None:
    key = (slug or title).lower()
    row = doc["counts"].setdefault(key, {"title": title, "slug": slug, "recipe_id": recipe_id, "n": 0})
    row["n"] += 1
    row["title"] = title


async def plan(on: date, title: str, slug: str | None = None, recipe_id: str | None = None,
               ingredients: list[str] | None = None, start: date | None = None) -> dict[str, Any]:
    title = title.strip()[:120]
    doc = load()
    entry: dict[str, Any] = {"title": title, "slug": slug, "recipe_id": recipe_id, "source": "local",
                             "ingredients": [i.strip()[:120] for i in ingredients or [] if i.strip()][:40] or None}
    if mealie.configured():
        for p in await mealie.plans(on, on):
            if p["date"] == on.isoformat() and p.get("id") is not None:
                await mealie.unplan(p["id"])
        made = await mealie.plan_dinner(on, title, recipe_id)
        entry |= {"source": "mealie", "mealie_id": made.get("id")}
    doc["plan"][on.isoformat()] = entry
    _count(doc, title, slug, recipe_id)
    save(doc)
    return await week(start or on)


async def unplan(on: date, start: date | None = None) -> dict[str, Any]:
    doc = load()
    if mealie.configured():
        for p in await mealie.plans(on, on):
            if p["date"] == on.isoformat() and p.get("id") is not None:
                await mealie.unplan(p["id"])
    doc["plan"].pop(on.isoformat(), None)
    save(doc)
    return await week(start or on)


def norm(name: str) -> str:
    n = re.sub(r"\([^)]*\)", " ", name.lower())
    n = re.sub(r"[^a-z ]+", " ", n)
    words = [w[:-1] if w.endswith("s") and len(w) > 3 and not w.endswith("ss") else w for w in n.split()]
    return " ".join(words)


def _has(text: str, word: str) -> bool:
    return bool(re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", text))


async def shopping(hub: Hub, start: date) -> dict[str, Any]:
    """The week's ingredients, merged, with what to skip (staples, already on the list)."""
    w = await week(start)
    doc = load()
    merged: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for day in w["days"]:
        dinner = day["dinner"]
        if not dinner:
            continue
        lines: list[dict[str, Any]] = []
        if dinner.get("slug") and mealie.configured():
            try:
                lines = (await mealie.recipe(dinner["slug"]))["ingredients"]
            except mealie.MealieError:
                missing.append(dinner["title"])
        elif dinner.get("ingredients"):
            lines = [{"name": i, "display": i} for i in dinner["ingredients"]]
        else:
            missing.append(dinner["title"])
        for line in lines:
            key = norm(line["name"])
            if not key:
                continue
            row = merged.setdefault(key, {"name": line["name"], "lines": [], "for": []})
            if line["display"] not in row["lines"]:
                row["lines"].append(line["display"])
            if dinner["title"] not in row["for"]:
                row["for"].append(dinner["title"])

    lists = (await sirisai_api.get(hub, "/siris/hub/v1/lists", timeout=10.0)) or {}
    all_lists = [lst for lst in lists.get("lists") or [] if isinstance(lst, dict)]
    chosen = doc["list"] if any(lst.get("entity_id") == doc["list"] for lst in all_lists) else next(
        (lst["entity_id"] for lst in all_lists if "shop" in (lst.get("entity_id", "") + (lst.get("name") or "")).lower()),
        all_lists[0]["entity_id"] if all_lists else None)
    on_list = [norm(i.get("summary") or "") for lst in all_lists if lst.get("entity_id") == chosen
               for i in lst.get("items") or [] if i.get("status") != "completed"]
    staples = [norm(s) for s in doc["staples"]]
    items = []
    for key, row in sorted(merged.items()):
        staple = any(_has(key, s) for s in staples if s)
        already = any(o and (_has(o, key) or _has(key, o)) for o in on_list)
        items.append({"key": key, "name": row["name"], "lines": row["lines"], "for": row["for"],
                      "staple": staple, "on_list": already, "need": not staple and not already})
    return {"start": w["start"], "items": items, "no_ingredients": missing,
            "lists": [{"entity_id": lst["entity_id"], "name": lst.get("name") or lst["entity_id"]} for lst in all_lists],
            "list": chosen, "staples": doc["staples"]}


async def add_to_list(hub: Hub, items: list[str], list_id: str) -> int:
    added = 0
    for item in items:
        await sirisai_api.post(hub, f"/siris/hub/v1/lists/{list_id}/items", json={"item": item[:200]}, timeout=10.0)
        added += 1
    doc = load()
    doc["list"] = list_id
    save(doc)
    return added


def set_staples(staples: list[str]) -> list[str]:
    doc = load()
    doc["staples"] = sorted({s.strip().lower()[:40] for s in staples if s.strip()})[:60]
    save(doc)
    return doc["staples"]


def tonight(today: date) -> dict[str, Any] | None:
    """For Home: tonight's dinner as last planned here (Mealie's own plan is read by the Meals page)."""
    entry = load()["plan"].get(today.isoformat())
    return {"title": entry["title"], "slug": entry.get("slug")} if entry else None
