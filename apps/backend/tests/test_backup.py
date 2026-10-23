"""3.7: backups of SirisOS's own data, and putting one back."""

from __future__ import annotations

import io
import json
import tarfile
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.attention import service as attention
from app.backup import service
from app.entrypoint import app
from tests.test_hub import AUTH


@pytest.fixture
def dirs(monkeypatch, tmp_path):
    data, out = tmp_path / "data", tmp_path / "backups"
    (data / "brief-history").mkdir(parents=True)
    (data / "standards" / "as3600").mkdir(parents=True)
    (data / "tasks.json").write_text('{"tasks": [1]}')
    (data / "brief-history" / "2026-10-22.json").write_text("{}")
    (data / "standards" / "as3600" / "doc.pdf").write_bytes(b"%PDF")
    (data / ".tasks-abc.tmp").write_text("half")
    monkeypatch.setenv("SIRISOS_DATA_DIR", str(data))
    monkeypatch.setenv("SIRISOS_BACKUP_DIR", str(out))
    monkeypatch.setenv("SIRISOS_BACKUPS", "1")
    monkeypatch.setattr(service, "_last_error", None)
    return data, out


def names(path):
    with tarfile.open(path) as tar:
        return sorted(tar.getnames())


def test_backup_holds_the_data_but_not_standards_or_temp_files(dirs):
    data, out = dirs
    made = service.create("manual")
    assert made["files"] == 2 and made["kind"] == "manual"
    assert names(out / made["name"]) == ["data/brief-history/2026-10-22.json", "data/tasks.json", "manifest.json"]
    assert service.manifest(made["name"])["files"][1] == {"path": "tasks.json", "bytes": 14}


def test_standards_join_when_asked(dirs, monkeypatch):
    monkeypatch.setenv("SIRISOS_BACKUP_STANDARDS", "1")
    made = service.create("manual")
    assert "data/standards/as3600/doc.pdf" in names(dirs[1] / made["name"])


def test_a_backup_folder_inside_the_data_folder_is_left_out(dirs, monkeypatch):
    data, _ = dirs
    monkeypatch.setenv("SIRISOS_BACKUP_DIR", str(data / "snapshots"))
    first = service.create("manual", now=datetime(2026, 10, 1, tzinfo=timezone.utc))
    second = service.create("manual")
    assert not any("snapshots" in n for n in names(data / "snapshots" / second["name"]))
    assert first["name"] != second["name"]


def test_old_ones_are_pruned_per_kind(dirs):
    for day in range(1, 17):
        service.create("nightly", now=datetime(2026, 10, day, 18, tzinfo=timezone.utc))
    service.create("manual", now=datetime(2026, 9, 1, tzinfo=timezone.utc))
    kinds = [b["kind"] for b in service.backups()]
    assert kinds.count("nightly") == 14 and kinds.count("manual") == 1
    assert service.backups()[-1]["kind"] == "manual"


def test_restore_puts_files_back_and_can_be_undone(dirs):
    data, _ = dirs
    made = service.create("manual")
    (data / "tasks.json").write_text('{"tasks": []}')
    (data / "new.json").write_text("{}")
    done = service.restore(made["name"])
    assert done["restored"] == 2 and done["undo"].endswith("before-restore.tar.gz")
    assert json.loads((data / "tasks.json").read_text()) == {"tasks": [1]}
    assert (data / "new.json").exists()  # files the backup doesn't have stay
    service.restore(done["undo"])
    assert json.loads((data / "tasks.json").read_text()) == {"tasks": []}


def test_restore_ignores_paths_that_escape(dirs, tmp_path):
    _, out = dirs
    out.mkdir()
    evil = out / "sirisos-20261001-000000-manual.tar.gz"
    with tarfile.open(evil, "w:gz") as tar:
        for name, body in (("manifest.json", b"{}"), ("data/../escaped.json", b"x"), ("data/ok.json", b"{}"), ("/etc/x", b"x")):
            info = tarfile.TarInfo(name)
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
    assert service.restore(evil.name)["restored"] == 1
    assert not (tmp_path / "escaped.json").exists()


def test_bad_names_are_refused(dirs):
    with pytest.raises(FileNotFoundError):
        service.path_of("../tasks.json")


def test_nightly_is_due_once_after_the_hour(dirs, monkeypatch):
    monkeypatch.setenv("SIRISOS_TIMEZONE", "Australia/Melbourne")
    early = datetime(2026, 10, 22, 15, 0, tzinfo=timezone.utc)  # 2am in Melbourne
    late = datetime(2026, 10, 22, 17, 0, tzinfo=timezone.utc)  # 4am
    assert not service.due(early)
    assert service.due(late)
    service.create("nightly", now=late)
    assert not service.due(late)


def test_stale_and_failed_backups_reach_the_inbox(dirs, monkeypatch):
    assert attention.backup_items() == []  # none yet: nothing to nag about
    service.create("nightly", now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert attention.backup_items()[0]["title"] == "SirisOS hasn't backed up in over a day"
    monkeypatch.setattr(service, "_last_error", "PermissionError: denied")
    assert attention.backup_items()[0]["body"] == "PermissionError: denied"


def test_api(dirs):
    client = TestClient(app)
    assert client.get("/api/v1/backups").status_code == 401
    made = client.post("/api/v1/backups", headers=AUTH).json()
    listing = client.get("/api/v1/backups", headers=AUTH).json()
    assert listing["count"] == 1 and listing["backups"][0]["name"] == made["name"] and not listing["stale"]
    assert client.get(f"/api/v1/backups/{made['name']}", headers=AUTH).content[:2] == b"\x1f\x8b"
    assert client.post(f"/api/v1/backups/{made['name']}/restore", headers=AUTH, json={"confirm": "yes"}).status_code == 400
    assert client.post(f"/api/v1/backups/{made['name']}/restore", headers=AUTH, json={"confirm": "restore"}).json()["restored"] == 2
    assert client.post("/api/v1/backups/nope.tar.gz/restore", headers=AUTH, json={"confirm": "restore"}).status_code == 404


def test_unwritable_folder_is_a_503(dirs, monkeypatch, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("")
    monkeypatch.setenv("SIRISOS_BACKUP_DIR", str(blocker / "sub"))
    r = TestClient(app).post("/api/v1/backups", headers=AUTH)
    assert r.status_code == 503 and service.status()["error"]
