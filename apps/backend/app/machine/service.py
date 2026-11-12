"""The server itself (8.9): disk space, and whether the local AI is still all on the GPU.

- **Disk**: the disks under SirisOS's data and backups. At SIRISOS_DISK_WARN_PERCENT (85) used, with under
  SIRISOS_DISK_WARN_FREE_GB (100) left, it says so in the inbox (a big NAS at 86% with a terabyte free is fine); at
  SIRISOS_DISK_ALERT_PERCENT (95), or under 10 GB left, it's urgent, since a full disk stops backups, uploads and the
  databases.
- **The GPU**: Ollama's loaded models (GET /api/ps on OLLAMA_URL). A model with part of it outside VRAM is running
  partly from system RAM on the CPU: slow, and the RAM it takes is what Brad wants left alone. It's said once a day
  while it lasts, with the fix.

Checked at most every CHECK_SECONDS; the inbox reads the last result, so a slow Ollama never holds it up.
"""

from __future__ import annotations

import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

CHECK_SECONDS = 300
_cache: dict[str, Any] = {"at": 0.0, "value": None}


def _int(env: str, default: int) -> int:
    try:
        return max(50, min(99, int(os.getenv(env, str(default)))))
    except ValueError:
        return default


def _gb(env: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(env, str(default))))
    except ValueError:
        return default


def enabled() -> bool:
    return os.getenv("SIRISOS_MACHINE_WATCH", "1") not in ("0", "false", "no")


def ollama_url() -> str:
    return os.getenv("OLLAMA_URL", "").strip().rstrip("/")


def disks() -> list[dict[str, Any]]:
    """Each distinct disk under the data and backup folders."""
    from app.backup import service as backup

    seen: set[int] = set()
    out = []
    for label, path in (("Data", backup.data_dir()), ("Backups", backup.backup_dir()), ("Backup copy", backup.copy_dir())):
        if path is None or not Path(path).exists():
            continue
        try:
            dev = os.stat(path).st_dev
            if dev in seen:
                continue
            seen.add(dev)
            u = shutil.disk_usage(path)
        except OSError:
            continue
        out.append({"label": label, "path": str(path), "total_gb": round(u.total / 1e9, 1), "free_gb": round(u.free / 1e9, 1),
                    "used_percent": round(u.used / u.total * 100) if u.total else 0})
    return out


def gpu(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ollama's loaded models, each with how much of it is in VRAM."""
    out = []
    for m in models:
        size, vram = int(m.get("size") or 0), int(m.get("size_vram") or 0)
        if not size:
            continue
        out.append({"name": m.get("name") or m.get("model") or "?", "size_gb": round(size / 1e9, 1), "vram_gb": round(vram / 1e9, 1),
                    "ram_gb": round(max(0, size - vram) / 1e9, 1), "on_gpu_percent": round(vram / size * 100)})
    return out


async def _ollama() -> dict[str, Any]:
    url = ollama_url()
    if not url:
        return {"configured": False, "models": [], "error": None}
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(f"{url}/api/ps")
            r.raise_for_status()
            return {"configured": True, "models": gpu(r.json().get("models") or []), "error": None}
    except (httpx.HTTPError, ValueError) as exc:
        return {"configured": True, "models": [], "error": f"{type(exc).__name__}: {exc}"[:200]}


async def status(force: bool = False) -> dict[str, Any]:
    now = time.monotonic()
    if not force and _cache["value"] is not None and now - _cache["at"] < CHECK_SECONDS:
        return _cache["value"]
    value = {"checked": datetime.now(timezone.utc).isoformat(timespec="seconds"), "disks": disks(), "ollama": await _ollama(),
             "warn_percent": _int("SIRISOS_DISK_WARN_PERCENT", 85), "alert_percent": _int("SIRISOS_DISK_ALERT_PERCENT", 95),
             "warn_free_gb": _gb("SIRISOS_DISK_WARN_FREE_GB", 100)}
    _cache.update(at=now, value=value)
    return value


def items(s: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Inbox items from the last check."""
    if not s:
        return []
    day = s["checked"][:10]
    out = []
    room = s.get("warn_free_gb", 100)
    for d in s["disks"]:
        urgent = d["used_percent"] >= s["alert_percent"] or d["free_gb"] < 10
        if not urgent and (d["used_percent"] < s["warn_percent"] or d["free_gb"] >= room):
            continue
        out.append({"key": f"machine:disk:{d['label']}:{'alert' if urgent else 'warn'}:{day}", "kind": "alert",
                    "severity": "urgent" if urgent else "attention",
                    "title": f"The server's {d['label'].lower()} disk is {d['used_percent']}% full",
                    "body": f"{d['free_gb']} GB left of {d['total_gb']} GB ({d['path']}). "
                            + ("Backups and uploads will start failing when it's full. " if urgent else "")
                            + "Old Docker images are often the quickest win: docker image prune -a.",
                    "source": "machine", "app": "SirisOS", "url": "/status"})
    for m in s["ollama"]["models"]:
        if m["on_gpu_percent"] >= 98:
            continue
        out.append({"key": f"machine:gpu:{m['name']}:{day}", "kind": "alert", "severity": "attention",
                    "title": f"{m['name']} is using system RAM, not just the GPU",
                    "body": f"{m['ram_gb']} GB of its {m['size_gb']} GB is outside the GPU ({m['on_gpu_percent']}% on the GPU), so it's slower "
                            "and taking the server's RAM. Usually a second model loaded beside it, or a longer context: only one model "
                            "should be loaded (OLLAMA_MAX_LOADED_MODELS=1), and restarting Ollama clears it.",
                    "source": "machine", "app": "SirisOS", "url": "/status"})
    return out
