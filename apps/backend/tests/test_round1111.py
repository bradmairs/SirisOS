"""11.11: Update now, Sections you use, and versions that can't clash."""

from __future__ import annotations

import importlib.util
import subprocess
from datetime import date
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.assist import homeuse
from app.entrypoint import app
from app.terminal import commands
from app.updates import service as updates
from tests.test_hub import AUTH

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_HOME_USAGE_PATH", str(tmp_path / "home-usage.json"))
    monkeypatch.setenv("SIRISOS_LOG_DIR", str(tmp_path))
    updates._cache.update(at=0.0, value=None)
    return TestClient(app, headers=AUTH)


def _github(version: str, notes: str = "# SirisOS x\n\n**Faster, and quieter.**\n"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/main/VERSION"):
            return httpx.Response(200, text=version + "\n")
        if request.url.path.endswith(f"/docs/releases/{version}.md"):
            return httpx.Response(200, text=notes)
        return httpx.Response(404)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_a_newer_version_on_main_is_offered_with_its_headline(client, monkeypatch, tmp_path):
    monkeypatch.setattr(updates, "API_VERSION", "11.10.0")
    (tmp_path / "update.log").write_text("Started\nBuilding\nSirisOS: http://x\n")
    got = updates.status(client=_github("11.11.0"))
    assert got["newer"] and got["latest"] == "11.11.0" and got["headline"] == "Faster, and quieter."
    assert got["notes"].endswith("/docs/releases/11.11.0.md") and got["log"][-1] == "SirisOS: http://x"
    assert updates.status(client=_github("11.9.0"), force=True)["newer"] is False  # 11.9 is older than 11.10, not newer


def test_github_down_says_so(client):
    broken = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    got = updates.status(force=True, client=broken)
    assert got["error"].startswith("Couldn't check GitHub") and got["newer"] is False


def test_update_now_is_a_terminal_shortcut_that_runs_detached(client, monkeypatch):
    monkeypatch.setenv("SIRISOS_SOURCE_DIR", "~/apps/sirisos")
    found = commands.find("builtin:update-sirisos")
    assert found and found["name"] == "Update SirisOS"
    cmd = found["command"]
    assert cmd.startswith("cd ~/apps/sirisos && ") and "nohup setsid make update" in cmd and "data/logs/update.log" in cmd and cmd.rstrip().count("&") >= 2


def test_sections_can_be_taken_out_of_the_menu_and_counting_has_a_start(client):
    homeuse.record([{"phase": "evening", "widget": "/gym", "kind": "visit"}], date(2026, 11, 20))
    got = client.put("/api/v1/home/usage/menu", json={"hidden": ["household", "home", "fitness"]}).json()
    assert got["menu_hidden"] == ["fitness", "household"]  # Home can't be hidden
    assert got["counting_since"] == "2026-11-20"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def test_a_branch_whose_number_main_took_is_renumbered(tmp_path, monkeypatch):
    repo = tmp_path / "r"
    for rel, text in (("VERSION", "11.8.0\n"), ("apps/backend/app/main.py", 'API_VERSION = "11.8.0"\n'),
                      ("apps/web/src/version.ts", 'export const APP_VERSION = "11.8.0";\n'),
                      ("README.md", "**Version 11.8.0** ([release notes](docs/releases/11.8.0.md); more\n"),
                      ("docs/roadmap.md", "11.8.0: old\n")):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "8")
    _git(repo, "checkout", "-q", "-b", "mine")

    def release(v: str, line: str) -> None:
        for rel, text in (("VERSION", f"{v}\n"), ("apps/backend/app/main.py", f'API_VERSION = "{v}"\n'),
                          ("apps/web/src/version.ts", f'export const APP_VERSION = "{v}";\n'),
                          ("README.md", f"**Version {v}** ([release notes](docs/releases/{v}.md); more\n"),
                          (f"docs/releases/{v}.md", f"# SirisOS {v}\n\n**{line}**\n")):
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_text(text)
        (repo / "docs/roadmap.md").write_text((repo / "docs/roadmap.md").read_text() + f"{v}: {line}\n")
        _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
        _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", v)

    release("11.9.0", "habits")              # this branch
    _git(repo, "checkout", "-q", "main")
    release("11.9.0", "gym")                 # main took the same number meanwhile
    _git(repo, "checkout", "-q", "mine")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "merge", "-q", "-X", "ours", "main", "-m", "merge")
    (repo / "docs/roadmap.md").write_text("11.8.0: old\n11.9.0: gym\n11.9.0: habits\n")  # both kept, as a resolution would
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "both")

    spec = importlib.util.spec_from_file_location("rebase_version", ROOT / "scripts/rebase_version.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    monkeypatch.setattr(mod, "ROOT", repo)
    assert mod.main("main") == 0
    assert (repo / "VERSION").read_text().strip() == "11.10.0"
    assert 'API_VERSION = "11.10.0"' in (repo / "apps/backend/app/main.py").read_text()
    assert "**Version 11.10.0** ([release notes](docs/releases/11.10.0.md)" in (repo / "README.md").read_text()
    assert (repo / "docs/releases/11.10.0.md").read_text().startswith("# SirisOS 11.10.0\n\n**habits**")
    assert "**gym**" in (repo / "docs/releases/11.9.0.md").read_text()  # main's notes stay main's
    roadmap = (repo / "docs/roadmap.md").read_text()
    assert "11.9.0: gym" in roadmap and "11.10.0: habits" in roadmap
