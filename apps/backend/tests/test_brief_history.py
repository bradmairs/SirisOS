"""Past briefs and what changed since the last one."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.brief import history
from app.entrypoint import app
from tests.test_hub import AUTH


def brief(day: str, weekday: str, **extra) -> dict:
    base = {"date": day, "weekday": weekday, "headline": [f"Brief for {day}"], "weather": {"today": {"high_c": 18}},
            "tasks": [], "apps_attention": [], "email": {"unread": 0, "important": []}, "brain": {"inbox": 2},
            "career": {"cpd": {"total": 40}}, "status": {"show": True}}
    return {**base, **extra}


@pytest.fixture(autouse=True)
def folder(tmp_path, monkeypatch):
    monkeypatch.setenv("SIRISOS_BRIEF_HISTORY_PATH", str(tmp_path / "brief-history"))
    return tmp_path / "brief-history"


def test_says_what_changed_since_yesterday():
    prev = brief("2026-10-16", "Friday", tasks=[{"title": "Send levels to Dana"}, {"title": "Book the ute"}],
                 apps_attention=[{"name": "Engineering Archive", "state": "down"}])
    cur = brief("2026-10-17", "Saturday", weather={"today": {"high_c": 23}}, tasks=[{"title": "Send levels to Dana"}, {"title": "Pay rego"}],
                apps_attention=[{"name": "SirisLearn", "state": "degraded"}], email={"important": [{"from": "Dana"}]},
                brain={"inbox": 5}, career={"cpd": {"total": 41.5}})
    out = history.changes(prev, cur)
    assert out["label"] == "yesterday" and out["since"] == "2026-10-16"
    assert out["lines"] == [
        "5° warmer than yesterday.",
        "New to do: Pay rego.",
        "Off the list: Book the ute.",
        "SirisLearn is degraded now.",
        "Engineering Archive is working again.",
        "1 more important email than yesterday.",
        "Second Brain inbox up 3 (now 5).",
        "CPD up 1.5 hours since yesterday (now 41.5).",
    ]
    assert history.changes(None, cur) is None
    # Not the day before: named by its weekday.
    assert history.changes(brief("2026-10-14", "Wednesday"), brief("2026-10-17", "Saturday", brain={"inbox": 3}))["lines"] == [
        "Second Brain inbox up 1 (now 3)."]


def test_keeps_60_days_and_serves_them(folder):
    for day, weekday in [("2026-08-01", "Saturday"), ("2026-10-16", "Friday"), ("2026-10-17", "Saturday")]:
        history.save(brief(day, weekday))
    # The August one is more than 60 days before the 17th: pruned on that save.
    assert sorted(p.stem for p in folder.iterdir()) == ["2026-10-16", "2026-10-17"]
    assert "status" not in history.load("2026-10-17")
    assert history.previous("2026-10-17")["date"] == "2026-10-16"

    client = TestClient(app)
    days = client.get("/api/v1/brief/history", headers=AUTH).json()["days"]
    assert [d["date"] for d in days] == ["2026-10-17", "2026-10-16"] and days[0]["headline"] == ["Brief for 2026-10-17"]
    past = client.get("/api/v1/brief/history/2026-10-17", headers=AUTH).json()
    assert past["date"] == "2026-10-17" and past["changes"]["since"] == "2026-10-16"
    assert client.get("/api/v1/brief/history/2026-01-01", headers=AUTH).status_code == 404
    assert client.get("/api/v1/brief/history/..%2Fsecrets", headers=AUTH).status_code == 404
