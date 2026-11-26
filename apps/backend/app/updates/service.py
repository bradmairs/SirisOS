"""Update SirisOS from SirisOS (11.11).

- **Is there a newer version?** main's VERSION on GitHub (SIRISOS_GITHUB_REPO, the public repo), checked at most hourly,
  against the running one, with the new release's headline from its notes.
- **Update now** runs `make update` on the server through the Terminal (behind a fresh 2FA code, like any terminal
  shortcut), detached with nohup: the update restarts this very container, which would otherwise cut its own SSH
  session off halfway. Its output goes to data/logs/update.log, which the container reads at /app/logs/update.log.
  The checkout is SIRISOS_SOURCE_DIR on the server (~/Docker/SirisOS/SirisOS).
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

from app.main import API_VERSION

CHECK_SECONDS = 3600
COMMAND_ID = "builtin:update-sirisos"
_cache: dict[str, Any] = {"at": 0.0, "value": None}


def repo() -> str:
    return os.getenv("SIRISOS_GITHUB_REPO", "bradmairs/SirisOS").strip()


def source_dir() -> str:
    return os.getenv("SIRISOS_SOURCE_DIR", "~/Docker/SirisOS/SirisOS").strip() or "~/Docker/SirisOS/SirisOS"


def log_path() -> Path:
    return Path(os.getenv("SIRISOS_LOG_DIR", "/app/logs")) / "update.log"


def update_command() -> str:
    """Detached, so it survives this container restarting; its output in data/logs/update.log."""
    d = source_dir()
    return (f"cd {d} && mkdir -p data/logs && (echo \"Started $(date)\"; nohup setsid make update) "
            f"> data/logs/update.log 2>&1 < /dev/null & echo \"Updating in {d}: it carries on by itself.\"")


def parse(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", v)[:3]) or (0,)


def _fetch(client: httpx.Client) -> dict[str, Any]:
    base = f"https://raw.githubusercontent.com/{repo()}/main"
    latest = client.get(f"{base}/VERSION").raise_for_status().text.strip()
    headline = ""
    try:
        notes = client.get(f"{base}/docs/releases/{latest}.md")
        if notes.status_code == 200:
            m = re.search(r"^\*\*(.+?)\*\*\s*$", notes.text, re.M)
            headline = m.group(1) if m else ""
    except httpx.HTTPError:
        pass
    return {"latest": latest, "headline": headline}


def status(force: bool = False, client: httpx.Client | None = None) -> dict[str, Any]:
    now = time.monotonic()
    error = None
    if force or _cache["value"] is None or now - _cache["at"] > CHECK_SECONDS:
        try:
            with (client or httpx.Client(timeout=8.0, follow_redirects=True)) as c:
                _cache.update(at=now, value=_fetch(c))
        except (httpx.HTTPError, ValueError) as exc:
            error = f"Couldn't check GitHub: {type(exc).__name__}"
    got = _cache["value"] or {}
    latest = got.get("latest")
    return {"current": API_VERSION, "latest": latest, "newer": bool(latest) and parse(latest) > parse(API_VERSION),
            "headline": got.get("headline", ""), "notes": f"https://github.com/{repo()}/blob/main/docs/releases/{latest}.md" if latest else None,
            "error": error, "log": log_tail()}


def log_tail(lines: int = 12) -> list[str]:
    try:
        return log_path().read_text(errors="replace").splitlines()[-lines:]
    except OSError:
        return []
