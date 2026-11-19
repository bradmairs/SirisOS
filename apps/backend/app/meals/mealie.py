"""Mealie (mealie.io), the self-hosted recipe manager, for the meal plan (10.2).

Set SIRISOS_MEALIE_URL (e.g. http://192.168.0.100:9925) and SIRISOS_MEALIE_TOKEN
(an API token from Mealie: your profile, then API Tokens). SirisOS then:

- searches your recipes when you plan a dinner;
- reads and writes Mealie's own meal plan (dinners), so planning in either
  shows in both;
- reads each recipe's ingredients for the shopping list.

Mealie 2 keeps meal plans under /api/households; Mealie 1 under /api/groups.
Both are tried (2 first).
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any

import httpx

from app.hub.service import shared_client

TIMEOUT = 10.0


class MealieError(Exception):
    pass


def configured() -> bool:
    return bool(base_url() and os.getenv("SIRISOS_MEALIE_TOKEN", "").strip())


def base_url() -> str:
    return os.getenv("SIRISOS_MEALIE_URL", "").strip().rstrip("/")


def public_url() -> str:
    """Where your browser reaches Mealie (SIRISOS_MEALIE_PUBLIC_URL), for links; the API address otherwise."""
    return (os.getenv("SIRISOS_MEALIE_PUBLIC_URL", "").strip() or base_url()).rstrip("/")


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.getenv('SIRISOS_MEALIE_TOKEN', '').strip()}", "Accept": "application/json"}


async def _call(method: str, path: str, **kw: Any) -> httpx.Response:
    if not configured():
        raise MealieError("Mealie isn't set up.")
    try:
        r = await shared_client().request(method, f"{base_url()}{path}", headers=_headers(), timeout=TIMEOUT, **kw)
    except httpx.HTTPError as exc:
        raise MealieError(f"Mealie can't be reached ({type(exc).__name__}).") from exc
    if r.status_code in (401, 403):
        raise MealieError("Mealie turned down the API token: make a new one in Mealie (your profile, API Tokens).")
    return r


async def _plans_path(method: str, suffix: str = "", **kw: Any) -> httpx.Response:
    r = await _call(method, "/api/households/mealplans" + suffix, **kw)  # Mealie 2
    if r.status_code == 404:
        r = await _call(method, "/api/groups/mealplans" + suffix, **kw)  # Mealie 1
    return r


def recipe_link(slug: str) -> str:
    """A recipe's page in Mealie: SIRISOS_MEALIE_RECIPE_URL with {slug}, else Mealie 2's default group's page."""
    template = os.getenv("SIRISOS_MEALIE_RECIPE_URL", "").strip() or f"{public_url()}/g/home/r/{{slug}}"
    return template.replace("{slug}", slug)


def _recipe(r: dict[str, Any]) -> dict[str, Any]:
    return {"id": r.get("id"), "slug": r.get("slug"), "name": r.get("name") or "Recipe",
            "time": r.get("totalTime") or r.get("performTime"), "image": bool(r.get("image")),
            "url": recipe_link(r["slug"]) if r.get("slug") else None}


async def search(q: str, limit: int = 12) -> list[dict[str, Any]]:
    r = await _call("GET", "/api/recipes", params={"search": q, "perPage": limit, "page": 1, "orderBy": "name"})
    if r.status_code >= 400:
        raise MealieError(f"Mealie's recipe search failed ({r.status_code}).")
    return [_recipe(x) for x in (r.json().get("items") or [])][:limit]


async def recipe(slug: str) -> dict[str, Any]:
    r = await _call("GET", f"/api/recipes/{slug}")
    if r.status_code >= 400:
        raise MealieError(f"Mealie has no recipe '{slug}'.")
    body = r.json()
    out = _recipe(body)
    out["ingredients"] = [ingredient(i) for i in body.get("recipeIngredient") or []]
    out["ingredients"] = [i for i in out["ingredients"] if i["name"]]
    out["servings"] = body.get("recipeYield") or body.get("recipeServings")
    return out


def ingredient(i: dict[str, Any]) -> dict[str, Any]:
    """One ingredient line: the food on its own (for matching against the list) and the line as Mealie shows it."""
    food = (i.get("food") or {}).get("name") if isinstance(i.get("food"), dict) else None
    display = (i.get("display") or i.get("originalText") or i.get("note") or "").strip()
    name = (food or display).strip()
    return {"name": name[:120], "display": display[:200] or name[:200]}


async def plans(start: date, end: date) -> list[dict[str, Any]]:
    """Dinners Mealie has planned from `start` to `end`."""
    r = await _plans_path("GET", params={"start_date": start.isoformat(), "end_date": end.isoformat(), "perPage": 100, "page": 1})
    if r.status_code >= 400:
        raise MealieError(f"Mealie's meal plan couldn't be read ({r.status_code}).")
    body = r.json()
    items = body.get("items") if isinstance(body, dict) else body
    out = []
    for p in items or []:
        if (p.get("entryType") or "dinner") != "dinner":
            continue
        rec = p.get("recipe") or {}
        out.append({"id": p.get("id"), "date": str(p.get("date"))[:10], "title": rec.get("name") or p.get("title") or "Dinner",
                    "slug": rec.get("slug"), "recipe_id": p.get("recipeId") or rec.get("id"), "note": p.get("text") or ""})
    return out


async def plan_dinner(on: date, title: str, recipe_id: str | None) -> dict[str, Any]:
    body: dict[str, Any] = {"date": on.isoformat(), "entryType": "dinner", "title": "" if recipe_id else title, "text": ""}
    if recipe_id:
        body["recipeId"] = recipe_id
    r = await _plans_path("POST", json=body)
    if r.status_code >= 400:
        raise MealieError(f"Mealie didn't take the meal plan ({r.status_code}).")
    return r.json() if r.content else {}


async def unplan(plan_id: str | int) -> None:
    r = await _plans_path("DELETE", f"/{plan_id}")
    if r.status_code >= 400 and r.status_code != 404:
        raise MealieError(f"Mealie didn't remove it ({r.status_code}).")
