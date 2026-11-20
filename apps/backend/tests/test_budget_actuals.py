"""10.0: actual spending from a bank's CSV against the budget, learning shops from corrections,
the weekly review flagging lines over plan, and balances towards goals with a forecast."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app.budget import actuals
from app.budget import service as budget
from tests.test_budget import PLAN, client  # noqa: F401  (fixture)
from tests.test_hub import AUTH


@pytest.fixture
def c(client, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setenv("SIRISOS_BUDGET_ACTUALS_PATH", str(tmp_path / "budget-actuals.json"))
    monkeypatch.setattr(budget, "today", lambda: date(2026, 11, 19))
    assert client.put("/api/v1/budget", json=PLAN, headers=AUTH).status_code == 200
    return client


def _lines(c: TestClient) -> dict[str, str]:
    doc = c.get("/api/v1/budget", headers=AUTH).json()
    return {l["name"]: l["id"] for s in doc["sections"].values() for l in s}


# CommBank's export: no header, date, amount, description, balance.
COMMBANK = b"""03/11/2026,"-85.40","WOOLWORTHS 1234 MELBOURNE AU Card xx1234 Value Date: 01/11/2026","+2,014.60"
05/11/2026,"-64.10","ALDI STORES 402 RICHMOND",+1950.50
06/11/2026,"-39.00","JB HIFI 0042 MELBOURNE",+1911.50
06/11/2026,"-39.00","JB HIFI 0042 MELBOURNE",+1872.50
07/11/2026,"+3000.00","SALARY ACME PTY LTD",+4872.50
12/11/2026,"-910.00","WOOLWORTHS 1234 MELBOURNE AU",+3962.50
"""

# A headed export with debit and credit columns.
HEADED = b"""Date,Description,Debit,Credit,Balance
2026-11-08,UBER *TRIP HELP.UBER.COM,23.50,,500.00
2026-11-09,Refund thanks,,10.00,510.00
"""


def test_parse_headerless_and_headed():
    rows = actuals.parse_csv(COMMBANK)
    assert len(rows) == 6
    assert rows[0] == {"date": "2026-11-03", "description": rows[0]["description"], "amount": -85.4, "balance": 2014.6}
    assert rows[0]["description"].startswith("WOOLWORTHS")
    headed = actuals.parse_csv(HEADED)
    assert [r["amount"] for r in headed] == [-23.5, 10.0]
    with pytest.raises(ValueError):
        actuals.parse_csv(b"just,some,words\nno,dates,here\n")


def test_import_sorts_learns_and_shows_the_month(c):
    ids = _lines(c)
    r = c.post("/api/v1/budget/actuals/import", files={"file": ("cba.csv", COMMBANK, "text/csv")}, data={"account": "Everyday"}, headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 6  # the two identical JB Hi-Fi buys are both kept
    again = c.post("/api/v1/budget/actuals/import", files={"file": ("cba.csv", COMMBANK, "text/csv")}, data={"account": "Everyday"}, headers=AUTH).json()
    assert again["imported"] == 0 and again["skipped"] == 6

    m = c.get("/api/v1/budget/actuals?month=2026-11", headers=AUTH).json()
    groceries = next(l for l in m["lines"] if l["name"] == "Groceries")
    # Woolworths and Aldi guessed onto Groceries (planned 200 a week = 866.67 a month); 1059.50 spent, so over.
    assert groceries["spent"] == pytest.approx(1059.5) and groceries["status"] == "over"
    assert [o["name"] for o in m["over"]] == ["Groceries"]
    assert m["unsorted_count"] == 2  # JB Hi-Fi twice; the salary (money in) is left out
    assert m["spent"] == pytest.approx(1137.5)

    # Put one JB Hi-Fi on Rent (a stand-in line): the other follows, and the rule sticks for next time.
    tx = m["unsorted"][0]
    out = c.put(f"/api/v1/budget/actuals/{tx['id']}", json={"line_id": ids["Rent"]}, headers=AUTH).json()
    assert out["sorted_too"] == 1
    m = c.get("/api/v1/budget/actuals", headers=AUTH).json()
    assert m["unsorted_count"] == 0
    assert next(l for l in m["lines"] if l["name"] == "Rent")["spent"] == pytest.approx(78.0)
    # "Leave out" works too.
    woolies = next(t for t in m["guessed"] if t["amount"] == -910.0)
    c.put(f"/api/v1/budget/actuals/{woolies['id']}", json={"line_id": "ignore", "learn": False}, headers=AUTH)
    m = c.get("/api/v1/budget/actuals", headers=AUTH).json()
    assert not m["over"]

    # The import's balance column became the account's balance.
    bal = c.get("/api/v1/budget/balances", headers=AUTH).json()
    assert bal["accounts"][0]["name"] == "Everyday" and bal["accounts"][0]["balance"] == 3962.5


def test_bad_ids_and_months_are_refused(c):
    assert c.put("/api/v1/budget/actuals/..%2Fx", json={"line_id": None}, headers=AUTH).status_code == 404
    assert c.put("/api/v1/budget/actuals/abcdef123456", json={"line_id": None}, headers=AUTH).status_code == 404
    assert c.get("/api/v1/budget/actuals?month=nope", headers=AUTH).status_code == 422
    assert c.post("/api/v1/budget/actuals/import", files={"file": ("x.csv", b"", "text/csv")}, headers=AUTH).status_code == 422


def test_weekly_review_flags_lines_over_plan(c):
    from app.review import service as review

    c.post("/api/v1/budget/actuals/import", files={"file": ("cba.csv", COMMBANK, "text/csv")}, headers=AUTH)
    s = review._spending(date(2026, 11, 19))
    assert [o["name"] for o in s["over"]] == ["Groceries"]
    assert s["lines"][0].startswith("Groceries:") and "2 spends still to sort" in s["lines"][1]
    assert review._over_budget(date(2026, 11, 19)) == "1 budget line over this month. "


def test_balances_goal_progress_forecast_and_net_worth(c):
    ids = _lines(c)
    for d, v in [("2026-08-01", 1000), ("2026-09-01", 1500), ("2026-10-01", 2000), ("2026-11-01", 2500)]:
        actuals.set_balance("Holiday saver", v, date.fromisoformat(d), kind="savings")
    c.post("/api/v1/budget/balances", json={"account": "Car loan", "balance": 4000, "kind": "loan", "date": "2026-11-01"}, headers=AUTH)
    acc = next(a for a in c.get("/api/v1/budget/balances", headers=AUTH).json()["accounts"] if a["name"] == "Holiday saver")
    b = c.patch(f"/api/v1/budget/accounts/{acc['id']}", json={"line_id": ids["Holiday"]}, headers=AUTH).json()
    saver = next(a for a in b["accounts"] if a["name"] == "Holiday saver")
    assert saver["per_month"] == pytest.approx(500, rel=0.05)
    assert saver["goal"]["percent"] == 42  # 2500 of 6000
    assert saver["goal"]["eta"] == "Jun 2027"  # 3500 more at about 500 a month, from November
    assert b["net_worth"] == -1500  # 2500 saved less 4000 owed
    assert [p["month"] for p in b["series"]] == ["2026-08", "2026-09", "2026-10", "2026-11"]
    assert b["series"][-1]["net_worth"] == -1500
    assert c.delete(f"/api/v1/budget/accounts/{acc['id']}", headers=AUTH).json()["net_worth"] == -4000


def test_merchant_keys():
    assert actuals.merchant("WOOLWORTHS 1234 MELBOURNE AU Card xx1234") == "woolworths melbourne"
    assert actuals.merchant("VISA PURCHASE NETFLIX.COM") == "netflix.com"
    _ = datetime  # keep import for clarity of dates above


# 10.3: files are listed and can be taken out; the same purchase is never in twice.

OVERLAP = b"""Date,Description,Amount,Balance
12/11/2026,WOOLWORTHS 1234 MELBOURNE AU,-910.00,3962.50
13/11/2026,BP CONNECT RICHMOND,-70.00,3892.50
13/11/2026,BP CONNECT RICHMOND,-70.00,3822.50
"""


def test_overlapping_files_and_other_account_names_add_nothing_twice(c):
    first = c.post("/api/v1/budget/actuals/import", files={"file": ("nov-1.csv", COMMBANK, "text/csv")}, data={"account": "Everyday"}, headers=AUTH).json()
    assert first["imported"] == 6
    # The same file under another account name: nothing new.
    again = c.post("/api/v1/budget/actuals/import", files={"file": ("copy.csv", COMMBANK, "text/csv")}, data={"account": ""}, headers=AUTH).json()
    assert again["imported"] == 0 and again["skipped"] == 6
    # An export that overlaps on the 12th (same Woolworths, written differently) and adds two fuel stops on the 13th.
    nxt = c.post("/api/v1/budget/actuals/import", files={"file": ("nov-2.csv", OVERLAP, "text/csv")}, data={"account": "Everyday"}, headers=AUTH).json()
    assert nxt["imported"] == 2 and nxt["skipped"] == 1
    m = c.get("/api/v1/budget/actuals?month=2026-11", headers=AUTH).json()
    assert m["spent"] == pytest.approx(1137.5 + 140)
    files = c.get("/api/v1/budget/actuals/imports", headers=AUTH).json()["imports"]
    assert [(f["name"], f["transactions"]) for f in files] == [("nov-2.csv", 2), ("nov-1.csv", 6)]
    assert files[1]["first"] == "2026-11-03" and files[1]["last"] == "2026-11-12"


def test_removing_a_file_takes_its_transactions_out_and_it_can_be_added_again(c):
    a = c.post("/api/v1/budget/actuals/import", files={"file": ("nov-1.csv", COMMBANK, "text/csv")}, headers=AUTH).json()
    c.post("/api/v1/budget/actuals/import", files={"file": ("nov-2.csv", OVERLAP, "text/csv")}, headers=AUTH)
    r = c.delete(f"/api/v1/budget/actuals/imports/{a['import_id']}", headers=AUTH).json()
    assert r["removed"] == 6 and r["month"]["spent"] == pytest.approx(140)
    assert [f["name"] for f in c.get("/api/v1/budget/actuals/imports", headers=AUTH).json()["imports"]] == ["nov-2.csv"]
    back = c.post("/api/v1/budget/actuals/import", files={"file": ("nov-1.csv", COMMBANK, "text/csv")}, headers=AUTH).json()
    assert back["imported"] == 6
    assert c.delete("/api/v1/budget/actuals/imports/abcdef1234", headers=AUTH).status_code == 404
    assert c.delete("/api/v1/budget/actuals/imports/..%2Fx", headers=AUTH).status_code == 404


def test_duplicates_already_in_are_cleaned_up_once_and_older_files_can_go(c):
    from app.services import json_store

    tx = lambda i, acct, n: {"id": f"t{i}", "date": "2026-11-05", "description": f"ALDI STORES 402 RICHMOND{n}", "amount": -64.1, "account": acct}  # noqa: E731
    # Before 10.3: the same file twice under two account names, and two real identical buys in one.
    json_store.write(actuals._path(), {"transactions": [tx(1, "Bank", ""), tx(2, "Bank", ""), tx(3, "Everyday", ""), tx(4, "Everyday", "  "),
                                                        tx(5, "Bank", " Card xx1234")], "rules": {}, "accounts": [], "balances": []})
    doc = actuals.load()
    assert len(doc["transactions"]) == 3 and doc["dupes_removed"] == 2  # Bank had 3 (two coffees + the card-number copy)
    files = actuals.imports()
    assert files == [{"id": "earlier", "name": "Added before files were listed", "account": "Bank, Everyday", "at": None, "added": 3,
                      "transactions": 3, "first": "2026-11-05", "last": "2026-11-05"}]
    assert c.delete("/api/v1/budget/actuals/imports/earlier", headers=AUTH).json()["removed"] == 3
    assert actuals.load()["transactions"] == []
