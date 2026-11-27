"""11.12: splitting the budget between incomes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.budget import split
from app.entrypoint import app
from tests.test_hub import AUTH

BUDGET = {
    "currency": "AUD",
    "income": [{"id": "sam", "name": "Sam's Pay", "amount": 6000, "every": "monthly"},
               {"id": "alex", "name": "Alex's Pay", "amount": 1846.15, "every": "fortnightly"},   # 4000 a month
               {"id": "allow", "name": "Car Allowance", "amount": 1000, "every": "monthly"}],
    "sections": {
        "expenses": [{"id": "rent", "name": "Rent", "amount": 3000, "every": "monthly"},
                     {"id": "power", "name": "Electricity", "amount": 600, "every": "quarterly"},   # 200 a month
                     {"id": "gymb", "name": "Gym - Sam", "amount": 100, "every": "monthly"}],
        "savings": [{"id": "house", "name": "House", "amount": 2000, "every": "monthly"}],
        "spending": [{"id": "ss", "name": "Sam", "amount": 500, "every": "monthly"},
                     {"id": "sa", "name": "Alex", "amount": 500, "every": "monthly"},
                     {"id": "joint", "name": "Joint", "amount": 1700, "every": "monthly"}],
    },
}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_BUDGET_PATH", str(tmp_path / "budget.json"))
    monkeypatch.setenv("SIRISOS_BUDGET_SPLIT_PATH", str(tmp_path / "budget-split.json"))
    c = TestClient(app, headers=AUTH)
    assert c.put("/api/v1/budget", json=BUDGET).status_code == 200
    return c


def by(result, sid):
    return next(s for s in result["sources"] if s["id"] == sid)


def test_by_income_everyone_puts_in_the_same_share_and_personal_lines_stay_with_their_owner(client):
    r = client.post("/api/v1/budget/split/preview", json={"sources": ["sam", "alex"], "method": "income"}).json()
    assert r["total"] == 8000 and r["income"] == pytest.approx(10000, abs=0.05) and r["short"] == 0
    sam, alex = by(r, "sam"), by(r, "alex")
    assert sam["total"] == pytest.approx(4800, abs=1) and alex["total"] == pytest.approx(3200, abs=1)  # 60/40, like their pay
    assert sam["percent_of_income"] == alex["percent_of_income"] == 80.0
    assert {line["name"] for line in sam["lines"] if line["personal"]} == {"Gym - Sam", "Sam"}
    assert {line["name"] for line in alex["lines"] if line["personal"]} == {"Alex"}
    assert alex["per_pay"] == pytest.approx(3200 * 12 / 26, abs=1)  # Alex's part per fortnightly pay
    assert r["left_out"] == [{"id": "allow", "name": "Car Allowance", "income": 1000.0}]


def test_equally_and_by_whole_lines(client):
    eq = client.post("/api/v1/budget/split/preview", json={"sources": ["sam", "alex"], "method": "equal"}).json()
    assert by(eq, "sam")["total"] == pytest.approx(4000, abs=1) == by(eq, "alex")["total"]
    lines = client.post("/api/v1/budget/split/preview", json={"sources": ["sam", "alex"], "method": "lines"}).json()
    every = [line for s in lines["sources"] for line in s["lines"]]
    assert all(line["whole"] for line in every) and len(every) == 7  # each line paid by one
    assert abs(by(lines, "sam")["total"] - 4800) <= 1700  # as near 60/40 as whole lines allow


def test_a_line_can_be_given_to_someone_or_shared(client):
    r = client.post("/api/v1/budget/split/preview", json={"sources": [], "method": "income", "personal": {"ss": "shared", "rent": "alex"}}).json()
    assert "ss" not in r["personal"] and r["personal"]["rent"] == "alex"
    assert next(line for line in by(r, "alex")["lines"] if line["id"] == "rent")["personal"]
    assert len(r["sources"]) == 3 and r["left_out"] == []  # empty: every income


def test_short_when_the_chosen_incomes_dont_cover_it(client):
    r = client.post("/api/v1/budget/split/preview", json={"sources": ["alex"]}).json()
    assert r["short"] == pytest.approx(4000, abs=1) and by(r, "alex")["left"] == pytest.approx(-4000, abs=1)
    assert client.post("/api/v1/budget/split/preview", json={"sources": ["nope"]}).status_code == 422


def test_a_kept_split_notices_the_budget_changing_and_redoes_on_the_same_choices(client):
    kept = client.put("/api/v1/budget/split", json={"sources": ["sam", "alex"], "method": "income"}).json()
    assert kept["stale"] is False and kept["saved"]["made_at"] and kept["settings"]["sources"] == ["sam", "alex"]
    changed = {**BUDGET, "sections": {**BUDGET["sections"], "expenses": [{**BUDGET["sections"]["expenses"][0], "amount": 3400}, *BUDGET["sections"]["expenses"][1:]]}}
    client.put("/api/v1/budget", json=changed)
    got = client.get("/api/v1/budget/split").json()
    assert got["stale"] is True and got["changes"] == ["Rent up from $3,000 to $3,400 a month"]
    assert got["now"]["total"] == 8400 and got["saved"]["result"]["total"] == 8000
    again = client.put("/api/v1/budget/split", json=got["settings"]).json()
    assert again["stale"] is False and again["now"]["total"] == 8400


def test_saving_the_budget_keeps_the_split(client, tmp_path):
    client.put("/api/v1/budget/split", json={"sources": [], "method": "equal"})
    client.put("/api/v1/budget", json=BUDGET)
    assert client.get("/api/v1/budget/split").json()["settings"]["method"] == "equal"


def test_owners_come_from_the_income_names():
    assert split.owner({"name": "Sam's Pay"}) == "sam" and split.owner({"name": "Alex’s pay"}) == "alex"
    assert split.owner({"name": "Car Allowance"}) == "" and split.owner({"name": "Sam pay"}) == "sam"


# -- 11.13: blocks ---------------------------------------------------------------------------------------------------

def _budget_with_relocation(client):
    b = {**BUDGET, "sections": {**BUDGET["sections"], "savings": [*BUDGET["sections"]["savings"],
                                                                 {"id": "reloc", "name": "Relocation", "amount": 500, "every": "monthly"},
                                                                 {"id": "travel", "name": "Travel", "amount": 300, "every": "monthly"}]}}
    client.put("/api/v1/budget", json=b)


def test_blocks_are_whole_expenses_whole_spending_and_each_savings_type_with_relocation_shared(client):
    _budget_with_relocation(client)
    r = client.post("/api/v1/budget/split/preview", json={"sources": ["sam", "alex"]}).json()  # blocks is the default
    assert r["method"] == "blocks"
    blocks = {b["name"]: b for b in r["blocks"]}
    assert list(blocks) == ["Expenses", "Spending", "House", "Relocation", "Travel"]
    assert blocks["Expenses"]["monthly"] == 3300 and blocks["Spending"]["monthly"] == 2700
    assert blocks["Relocation"]["rule"] == "shared" and [p["share"] for p in blocks["Relocation"]["paid_by"]] == [60.0, 40.0]
    for name in ("Expenses", "Spending", "House", "Travel"):
        assert len(blocks[name]["paid_by"]) == 1  # whole, to one income
    sam, alex = by(r, "sam"), by(r, "alex")
    assert sam["total"] + alex["total"] == pytest.approx(8800, abs=1)
    # the closest whole-block assignment to 60/40 of 8800 (5280 / 3520)
    assert abs(sam["total"] - 5280) <= 300 and abs(alex["total"] - 3520) <= 300
    assert {b["name"] for b in sam["blocks"]} | {b["name"] for b in alex["blocks"]} >= {"Expenses", "Spending", "House", "Travel", "Relocation"}
    assert next(b for b in sam["blocks"] if b["name"] == "Relocation")["shared"]


def test_a_block_can_be_given_to_an_income_or_shared(client):
    _budget_with_relocation(client)
    r = client.post("/api/v1/budget/split/preview", json={"sources": ["sam", "alex"], "blocks": {"expenses": "alex", "reloc": "auto", "house": "shared"}}).json()
    blocks = {b["name"]: b for b in r["blocks"]}
    assert blocks["Expenses"]["paid_by"] == [{"id": "alex", "name": "Alex's Pay", "monthly": 3300.0, "share": 100.0}]
    assert len(blocks["House"]["paid_by"]) == 2 and len(blocks["Relocation"]["paid_by"]) == 1
    kept = client.put("/api/v1/budget/split", json={"sources": ["sam", "alex"], "method": "blocks", "blocks": {"expenses": "alex"}}).json()
    assert kept["settings"]["blocks"] == {"expenses": "alex"} and kept["now"]["rules"]["expenses"] == "alex"


def test_the_assignment_is_the_closest_one_not_just_biggest_first():
    from app.budget import split

    # targets 50 / 50; biggest-first gives 6+2 against 5+... ; the best is {6, 4} / {5, 3+2}
    got = split._assign([6, 5, 4, 3, 2], {"a": 10, "b": 10})
    load = {"a": 0, "b": 0}
    for size, who in zip([6, 5, 4, 3, 2], got):
        load[who] += size
    assert sorted(load.values()) == [10, 10]
