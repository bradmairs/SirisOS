"""8.9: backups copied off the server and checked, the server's disk and GPU, the weekly review's goals and overdue
tasks, and Add to SirisOS from the Share Sheet."""

from __future__ import annotations

import asyncio
import io
import json
import tarfile
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.attention import service as attention
from app.backup import service as backup
from app.entrypoint import app
from app.hub import sirisai_api
from app.machine import service as machine
from app.share import service as share
from app.tasks import service as tasks
from app.tasks import store as task_store
from tests.test_hub import AUTH


@pytest.fixture
def dirs(monkeypatch, tmp_path):
    data, out, nas = tmp_path / "data", tmp_path / "backups", tmp_path / "nas"
    data.mkdir()
    nas.mkdir()
    (data / "tasks.json").write_text('{"tasks": []}')
    (data / "gym.json").write_text('{"sessions": []}')
    monkeypatch.setenv("SIRISOS_DATA_DIR", str(data))
    monkeypatch.setenv("SIRISOS_BACKUP_DIR", str(out))
    monkeypatch.setenv("SIRISOS_BACKUP_COPY_DIR", str(nas))
    monkeypatch.setenv("SIRISOS_BACKUPS", "1")
    monkeypatch.setattr(backup, "_last_error", None)
    monkeypatch.setattr(backup, "_copy_error", None)
    return data, out, nas


# -- backups ----------------------------------------------------------------------


def test_each_nightly_backup_is_copied_off_the_server_and_old_copies_go(dirs, monkeypatch):
    data, out, nas = dirs
    monkeypatch.setattr(backup, "COPIES", 2)
    start = datetime(2026, 11, 1, 3, tzinfo=timezone.utc)
    for i in range(3):
        made = backup.create("nightly", now=start + timedelta(days=i))
        assert backup.copy_out(made["name"])["to"] == str(nas)
    kept = sorted(p.name for p in nas.iterdir())
    assert kept == ["sirisos-20261102-030000-nightly.tar.gz", "sirisos-20261103-030000-nightly.tar.gz"]
    s = backup.status(now=start + timedelta(days=2, hours=1))
    assert s["copy"]["newest"].startswith("2026-11-03") and not s["copy"]["stale"]


def test_a_missing_nas_is_said_in_the_inbox(dirs, monkeypatch):
    data, out, nas = dirs
    monkeypatch.setenv("SIRISOS_BACKUP_COPY_DIR", str(nas / "not-mounted"))
    made = backup.create("nightly")
    assert backup.copy_out(made["name"]) is None
    items = attention.backup_items()
    item = next(i for i in items if i["key"].startswith("backup:copy:"))
    assert "isn't there" in item["body"] and "NAS" in item["body"]


def test_the_restore_check_passes_a_good_backup_and_catches_a_broken_one(dirs):
    data, out, nas = dirs
    good = backup.create("manual")
    result = backup.check()
    assert result["ok"] and result["files"] == 2 and result["name"] == good["name"]
    assert backup.status()["check"]["ok"]
    assert not backup.check_due()  # done this week
    # a backup whose tasks.json is cut short
    bad = out / "sirisos-20991231-000000-manual.tar.gz"
    with tarfile.open(bad, "w:gz") as tar:
        raw = json.dumps({"files": [{"path": "tasks.json", "bytes": 13}, {"path": "gym.json", "bytes": 16}]}).encode()
        info = tarfile.TarInfo("manifest.json"); info.size = len(raw); tar.addfile(info, io.BytesIO(raw))
        broken = b'{"tasks": [  '
        info = tarfile.TarInfo("data/tasks.json"); info.size = len(broken); tar.addfile(info, io.BytesIO(broken))
    result = backup.check(bad.name)
    assert not result["ok"]
    assert "tasks.json isn't readable JSON" in result["problems"] and "gym.json is missing" in result["problems"]
    item = next(i for i in attention.backup_items() if i["key"].startswith("backup:check:"))
    assert "restore check" in item["title"]


def test_the_check_runs_from_the_page(dirs):
    backup.create("manual")
    assert TestClient(app, headers=AUTH).post("/api/v1/backups/check").json()["ok"]


# -- the server --------------------------------------------------------------------


def test_a_full_disk_and_a_model_spilling_out_of_the_gpu_go_to_the_inbox():
    s = {"checked": "2026-11-12T01:00:00+00:00", "warn_percent": 85, "alert_percent": 95,
         "disks": [{"label": "Data", "path": "/app/data", "total_gb": 1000, "free_gb": 30, "used_percent": 97},
                   {"label": "Backups", "path": "/app/backups", "total_gb": 1000, "free_gb": 600, "used_percent": 40},
                   {"label": "Backup copy", "path": "/app/backup-copy", "total_gb": 7000, "free_gb": 1003, "used_percent": 86}],
         "ollama": {"configured": True, "error": None, "models": machine.gpu([
             {"name": "llama3.1:8b", "size": 9_000_000_000, "size_vram": 6_000_000_000},
             {"name": "nomic-embed-text", "size": 600_000_000, "size_vram": 600_000_000}])}}
    items = machine.items(s)
    assert [i["severity"] for i in items] == ["urgent", "attention"]
    assert items[0]["title"] == "The server's data disk is 97% full"
    assert items[1]["title"] == "llama3.1:8b is using system RAM, not just the GPU" and "3.0 GB" in items[1]["body"]


def test_the_server_page_reads_the_disks(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    got = TestClient(app, headers=AUTH).get("/api/v1/machine?fresh=1").json()
    assert got["disks"][0]["label"] == "Data" and 0 <= got["disks"][0]["used_percent"] <= 100
    assert got["ollama"] == {"configured": False, "models": [], "error": None}


# -- the weekly review ---------------------------------------------------------------


def test_the_sunday_push_counts_overdue_tasks_and_the_gym_week_isnt_a_push_of_its_own(monkeypatch, tmp_path):
    from app.push import notifier
    from app.review import service as review

    monkeypatch.setenv("SIRISOS_TASKS_PATH", str(tmp_path / "tasks.json"))
    monkeypatch.setenv("SIRISOS_REVIEW_PATH", str(tmp_path / "review.json"))
    tasks.add(task_store.Task(title="Renew rego", due="2026-11-10", created_at=task_store.now()))
    sunday = datetime(2026, 11, 15, 17, tzinfo=review.zone())
    msg = review.push_message(sunday)[0]
    assert "1 overdue task to sort" in msg["body"]
    assert "gym_week_message(now)" not in open(notifier.__file__).read().split("def collect")[1]


def test_the_review_shows_goals_behind_the_pace(monkeypatch):
    from app.goals import service as goals
    from app.review import service as review

    async def overview(hub, year, today):
        return {"through_year": 87, "goals": [{"title": "Run 1000 km", "percent": 50, "state": "behind"},
                                              {"title": "Read 12 books", "percent": 100, "state": "done"},
                                              {"title": "Gym 150 times", "percent": 85, "state": "on_track"}]}
    monkeypatch.setattr(goals, "overview", overview)
    g = asyncio.run(review._goals(None, date(2026, 11, 15)))
    assert g == {"through_year": 87, "behind": [{"title": "Run 1000 km", "percent": 50}], "on_track": 1,
                 "done": [{"title": "Read 12 books", "percent": 100}], "total": 3}


# -- Add to SirisOS ------------------------------------------------------------------


@pytest.fixture
def keyed(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_SHARE_PATH", str(tmp_path / "share.json"))
    monkeypatch.setenv("SIRISOS_TASKS_PATH", str(tmp_path / "tasks.json"))
    monkeypatch.setattr(tasks, "today", lambda: date(2026, 11, 12))
    share._recent.clear()
    key = TestClient(app, headers=AUTH).post("/api/v1/share/key").json()["key"]
    return TestClient(app, headers={"X-SirisOS-Key": key}), key


def test_the_share_key_is_shown_once_and_only_adds(keyed, tmp_path):
    bare, key = keyed
    assert key.startswith("so_") and key not in (tmp_path / "share.json").read_text()
    assert TestClient(app).post("/api/v1/share", json={"text": "hi"}, headers={"X-SirisOS-Key": "so_wrong"}).status_code == 401
    assert bare.get("/api/v1/tasks").status_code == 401  # the key opens nothing else
    assert TestClient(app, headers=AUTH).get("/api/v1/share/key").json()["on"]


def test_shared_text_becomes_a_task_or_a_note_and_a_link_is_saved(keyed, monkeypatch):
    bare, _ = keyed
    sent = []

    async def post(hub, path, json=None, **kw):
        sent.append((path, json))
        return {"title": "Saved"}
    monkeypatch.setattr(sirisai_api, "post", post)
    r = bare.post("/api/v1/share", json={"text": "todo: buy milk"}).json()
    assert r["kind"] == "task" and r["say"] == "Added a task: Buy milk."
    assert [t.title for t in task_store.load().tasks] == ["Buy milk"]
    assert bare.post("/api/v1/share", json={"text": "call the plumber tomorrow", "task": True}).json()["say"] == "Added a task: Call the plumber, due Fri 13 Nov."
    assert bare.post("/api/v1/share", json={"text": "https://example.com/article"}).json()["kind"] == "url"
    assert bare.post("/api/v1/share", json={"text": "The bin code is 4321"}).json()["kind"] == "note"
    assert sent == [("/siris/brain/capture", {"url": "https://example.com/article"}),
                    ("/siris/brain/capture", {"text": "The bin code is 4321", "tags": ["shared"]})]


def test_a_shared_receipt_goes_to_life_admin(keyed, monkeypatch):
    bare, _ = keyed
    import httpx

    async def raw(hub, method, path, timeout=60.0, **kw):
        assert path == "/siris/documents" and kw["files"]["file"][0] == "receipt.pdf"
        return httpx.Response(200, json={"title": "JB Hi-Fi receipt", "kind": "receipt", "things": [{"name": "Soundbar"}]})
    monkeypatch.setattr(sirisai_api, "raw", raw)
    r = bare.post("/api/v1/share", files={"file": ("receipt.pdf", b"%PDF-1.4 receipt", "application/pdf")}).json()
    assert r == {"kind": "document", "say": "Filed: JB Hi-Fi receipt (receipt), and added Soundbar to Things you own.", "link": "/life"}


def test_too_many_at_once_are_refused(keyed, monkeypatch):
    bare, _ = keyed
    monkeypatch.setattr(share, "LIMIT_PER_HOUR", 0)
    assert bare.post("/api/v1/share", json={"text": "x"}).status_code == 429
