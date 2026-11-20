"""10.2: the week's dinners from Mealie (its own meal plan), and the shopping for them onto Home Assistant's list."""

from __future__ import annotations

import json
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from app.meals import service
from tests.test_hub import AUTH, ENV

MEALIE = "http://mealie.local:9925"
RECIPES = {
    "chicken-stir-fry": {"id": "r1", "slug": "chicken-stir-fry", "name": "Chicken stir fry", "recipeIngredient": [
        {"display": "500 g chicken thighs", "food": {"name": "chicken thighs"}},
        {"display": "2 onions, sliced", "food": {"name": "onions"}},
        {"display": "1 tbsp olive oil", "food": {"name": "olive oil"}},
        {"display": "Salt and pepper", "note": "Salt and pepper"}]},
    "spag-bol": {"id": "r2", "slug": "spag-bol", "name": "Spag bol", "recipeIngredient": [
        {"display": "1 onion", "food": {"name": "onion"}}, {"display": "500 g beef mince", "food": {"name": "beef mince"}},
        {"display": "400 g spaghetti", "food": {"name": "spaghetti"}}]},
}


@pytest.fixture
def world(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_MEALS_PATH", str(tmp_path / "meals.json"))
    monkeypatch.setenv("SIRISOS_MEALIE_URL", MEALIE)
    monkeypatch.setenv("SIRISOS_MEALIE_TOKEN", "test-token")
    state = {"plans": [], "next": 10, "added": [], "households": True, "auth": []}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith(MEALIE):
            state["auth"].append(request.headers.get("authorization"))
            path = request.url.path
            if path.startswith("/api/households") and not state["households"]:
                return httpx.Response(404)
            if path == "/api/recipes":
                q = request.url.params.get("search", "").lower()
                return httpx.Response(200, json={"items": [r for r in RECIPES.values() if q in r["name"].lower()]})
            if path.startswith("/api/recipes/"):
                slug = path.rsplit("/", 1)[1]
                return httpx.Response(200, json=RECIPES[slug]) if slug in RECIPES else httpx.Response(404)
            if path.endswith("/mealplans") and request.method == "GET":
                s, e = request.url.params["start_date"], request.url.params["end_date"]
                return httpx.Response(200, json={"items": [p for p in state["plans"] if s <= p["date"] <= e]})
            if path.endswith("/mealplans") and request.method == "POST":
                body = json.loads(request.content)
                rec = next((r for r in RECIPES.values() if r["id"] == body.get("recipeId")), None)
                plan = {"id": state["next"], "date": body["date"], "entryType": body["entryType"], "title": body.get("title"),
                        "recipeId": body.get("recipeId"), "recipe": {"name": rec["name"], "slug": rec["slug"], "id": rec["id"]} if rec else None}
                state["next"] += 1
                state["plans"].append(plan)
                return httpx.Response(201, json=plan)
            if "/mealplans/" in path and request.method == "DELETE":
                pid = int(path.rsplit("/", 1)[1])
                state["plans"] = [p for p in state["plans"] if p["id"] != pid]
                return httpx.Response(200, json={})
            return httpx.Response(404)
        # SirisAI
        if request.url.path == "/siris/hub/v1/lists":
            return httpx.Response(200, json={"lists": [
                {"entity_id": "todo.chores", "name": "Chores", "items": []},
                {"entity_id": "todo.shopping_list", "name": "Shopping list", "items": [{"summary": "Spaghetti", "status": "needs_action"}]}]})
        if request.url.path.startswith("/siris/hub/v1/lists/") and request.method == "POST":
            state["added"].append((request.url.path.split("/")[5], json.loads(request.content)["item"]))
            return httpx.Response(200, json={"lists": []})
        return httpx.Response(404)

    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    reset_hub(ENV)
    return TestClient(app), state


START = "2026-11-23"


def test_plan_from_mealie_and_shop_for_the_week(world):
    c, state = world
    found = c.get("/api/v1/meals/recipes?q=stir", headers=AUTH).json()
    assert found["configured"] and [r["slug"] for r in found["recipes"]] == ["chicken-stir-fry"]
    assert found["recipes"][0]["url"] == f"{MEALIE}/g/home/r/chicken-stir-fry"

    w = c.put(f"/api/v1/meals/{START}", json={"title": "Chicken stir fry", "slug": "chicken-stir-fry", "recipe_id": "r1", "start": START}, headers=AUTH).json()
    assert w["days"][0]["dinner"]["title"] == "Chicken stir fry" and w["days"][0]["dinner"]["source"] == "mealie"
    assert state["plans"][0]["entryType"] == "dinner" and state["plans"][0]["recipeId"] == "r1"
    c.put("/api/v1/meals/2026-11-24", json={"title": "Spag bol", "slug": "spag-bol", "recipe_id": "r2", "start": START}, headers=AUTH)
    c.put("/api/v1/meals/2026-11-25", json={"title": "Tacos", "ingredients": ["Tortillas", "Beef mince", "Cheese"], "start": START}, headers=AUTH)
    # Replanning a night replaces Mealie's entry rather than adding a second.
    c.put("/api/v1/meals/2026-11-24", json={"title": "Spag bol", "slug": "spag-bol", "recipe_id": "r2", "start": START}, headers=AUTH)
    assert sum(1 for p in state["plans"] if p["date"] == "2026-11-24") == 1
    assert all(a == "Bearer test-token" for a in state["auth"])

    w = c.get(f"/api/v1/meals?start={START}", headers=AUTH).json()
    assert [d["dinner"]["title"] if d["dinner"] else None for d in w["days"][:4]] == ["Chicken stir fry", "Spag bol", "Tacos", None]
    assert w["often"][0]["title"] == "Spag bol" and w["often"][0]["times"] == 2

    s = c.get(f"/api/v1/meals/shopping?start={START}", headers=AUTH).json()
    by = {i["key"]: i for i in s["items"]}
    assert by["onion"]["for"] == ["Chicken stir fry", "Spag bol"] and by["onion"]["need"]  # onions + onion, merged
    assert by["olive oil"]["staple"] and by["salt and pepper"]["staple"]
    assert by["spaghetti"]["on_list"] and not by["spaghetti"]["need"]  # already on the shopping list
    assert by["beef mince"]["for"] == ["Spag bol", "Tacos"]  # Mealie's and your own, together
    assert s["list"] == "todo.shopping_list"  # the one called shopping, not the first

    r = c.post("/api/v1/meals/shopping", json={"items": ["Onion", "Chicken thighs"], "list": "todo.shopping_list"}, headers=AUTH)
    assert r.json() == {"added": 2, "list": "todo.shopping_list"}
    assert state["added"] == [("todo.shopping_list", "Onion"), ("todo.shopping_list", "Chicken thighs")]
    assert c.post("/api/v1/meals/shopping", json={"items": ["x"], "list": "light.kitchen"}, headers=AUTH).status_code == 404

    # Unplanning removes it from Mealie too.
    c.delete(f"/api/v1/meals/{START}?start={START}", headers=AUTH)
    assert not any(p["date"] == START for p in state["plans"])


def test_mealie_1_paths_and_staples(world):
    c, state = world
    state["households"] = False  # Mealie 1: meal plans under /api/groups
    c.put(f"/api/v1/meals/{START}", json={"title": "Chicken stir fry", "slug": "chicken-stir-fry", "recipe_id": "r1", "start": START}, headers=AUTH)
    assert state["plans"] and c.get(f"/api/v1/meals?start={START}", headers=AUTH).json()["days"][0]["dinner"]["title"] == "Chicken stir fry"
    assert c.put("/api/v1/meals/staples", json={"staples": ["Onion", " salt "]}, headers=AUTH).json() == {"staples": ["onion", "salt"]}
    by = {i["key"]: i for i in c.get(f"/api/v1/meals/shopping?start={START}", headers=AUTH).json()["items"]}
    assert by["onion"]["staple"] and not by["olive oil"]["staple"]


def test_without_mealie_plain_dinners_and_tonight(world, monkeypatch):
    c, _ = world
    monkeypatch.delenv("SIRISOS_MEALIE_URL")
    assert c.get("/api/v1/meals/recipes?q=x", headers=AUTH).json() == {"configured": False, "recipes": []}
    w = c.put(f"/api/v1/meals/{START}", json={"title": "Leftovers", "start": START}, headers=AUTH).json()
    assert w["mealie"]["configured"] is False and w["days"][0]["dinner"]["title"] == "Leftovers"
    s = c.get(f"/api/v1/meals/shopping?start={START}", headers=AUTH).json()
    assert s["no_ingredients"] == ["Leftovers"]
    assert service.tonight(date(2026, 11, 23)) == {"title": "Leftovers", "slug": None}
    assert c.put(f"/api/v1/meals/{START}", json={"title": "x", "slug": "../etc"}, headers=AUTH).status_code == 422


def test_a_broken_token_is_said_plainly(world):
    c, _ = world

    def refuse(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    hub_service.transport = httpx.MockTransport(refuse)
    reset_hub(ENV)
    w = c.get(f"/api/v1/meals?start={START}", headers=AUTH).json()
    assert "API token" in w["mealie"]["error"]
    r = c.get("/api/v1/meals/recipes?q=x", headers=AUTH)
    assert r.status_code == 502 and "API token" in r.json()["detail"]


def test_an_address_without_http_works_and_bad_ones_are_explained(world, monkeypatch):
    """10.34: Brad set SIRISOS_MEALIE_URL=192.168.0.100:9000 and got "UnsupportedProtocol"."""
    from app.meals import mealie

    c, state = world
    monkeypatch.setenv("SIRISOS_MEALIE_URL", "mealie.local:9925/")
    assert mealie.base_url() == MEALIE and mealie.public_url() == MEALIE
    assert c.get("/api/v1/meals/recipes?q=stir", headers=AUTH).json()["recipes"][0]["slug"] == "chicken-stir-fry"
    monkeypatch.setenv("SIRISOS_MEALIE_URL", "https://mealie.example")
    assert mealie.base_url() == "https://mealie.example"

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    hub_service.transport = httpx.MockTransport(down)
    reset_hub(ENV)
    monkeypatch.setenv("SIRISOS_MEALIE_URL", "192.168.0.100:9000")
    w = c.get(f"/api/v1/meals?start={START}", headers=AUTH).json()
    assert w["mealie"]["error"] == "Nothing answered at http://192.168.0.100:9000: check Mealie is running and the address and port are right."
