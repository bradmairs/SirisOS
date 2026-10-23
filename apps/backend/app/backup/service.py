"""Backups of SirisOS's own data (3.7).

Everything SirisOS keeps that exists nowhere else -- tasks, the journal and
wrap-ups, weekly reviews, career and CPD records, Home layout, links,
passkeys, shortcut keys, terminal 2FA, push subscriptions -- lives in the
data directory (SIRISOS_DATA_DIR, /app/data in the container). A backup is
that directory as one `.tar.gz` with a manifest, written to
SIRISOS_BACKUP_DIR (/app/backups; point it at the NAS to keep copies off the
server). The Engineering standards library is left out unless
SIRISOS_BACKUP_STANDARDS=1: it's large and its PDFs come from elsewhere.

One is made every night after SIRISOS_BACKUP_HOUR (3am in SIRISOS_TIMEZONE); 14 nightly
ones are kept, plus the last 10 made by hand and 5 taken just before a
restore. Restoring puts every file in the backup back (atomically, one file
at a time) after taking a fresh "before-restore" backup, so a restore can
itself be undone. Files the backup doesn't have are left alone.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import tarfile
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from app.main import API_VERSION

logger = logging.getLogger(__name__)

KINDS = {"nightly": 14, "manual": 10, "before-restore": 5}
STALE_HOURS = 36
NAME = re.compile(r"^sirisos-(\d{8}-\d{6})-(nightly|manual|before-restore)\.tar\.gz$")

_last_error: str | None = None


def data_dir() -> Path:
    return Path(os.getenv("SIRISOS_DATA_DIR", "/app/data"))


def backup_dir() -> Path:
    return Path(os.getenv("SIRISOS_BACKUP_DIR", "/app/backups"))


def _hour() -> int:
    try:
        return max(0, min(23, int(os.getenv("SIRISOS_BACKUP_HOUR", "3"))))
    except ValueError:
        return 3


def enabled() -> bool:
    return os.getenv("SIRISOS_BACKUPS", "1") not in ("0", "false", "no")


def _skip(rel: PurePosixPath) -> bool:
    top = rel.parts[0]
    if top in ("backups", "logs") or (top == "standards" and os.getenv("SIRISOS_BACKUP_STANDARDS") != "1"):
        return True
    return rel.name.endswith(".tmp") or rel.name.startswith(".")


def _files() -> list[tuple[PurePosixPath, Path]]:
    root = data_dir()
    if not root.is_dir():
        return []
    keep_out = backup_dir().resolve()
    out = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink() or path.resolve().is_relative_to(keep_out):
            continue
        rel = PurePosixPath(path.relative_to(root).as_posix())
        if _skip(rel):
            continue
        out.append((rel, path))
    return out


def _describe(path: Path) -> dict[str, Any] | None:
    match = NAME.match(path.name)
    if not match:
        return None
    created = datetime.strptime(match.group(1), "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
    return {"name": path.name, "kind": match.group(2), "created": created.isoformat(), "bytes": path.stat().st_size}


def backups() -> list[dict[str, Any]]:
    """Every backup, newest first."""
    folder = backup_dir()
    if not folder.is_dir():
        return []
    found = [d for p in folder.iterdir() if p.is_file() and (d := _describe(p))]
    return sorted(found, key=lambda d: d["created"], reverse=True)


def create(kind: str = "manual", now: datetime | None = None) -> dict[str, Any]:
    """Write one backup and prune old ones of the same kind."""
    global _last_error
    if kind not in KINDS:
        raise ValueError(f"Unknown backup kind {kind!r}")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    folder = backup_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        files = _files()
        manifest = {"app": "sirisos", "version": API_VERSION, "created": now.isoformat(timespec="seconds"), "kind": kind,
                    "files": [{"path": str(rel), "bytes": path.stat().st_size} for rel, path in files]}
        target = folder / f"sirisos-{now:%Y%m%d-%H%M%S}-{kind}.tar.gz"
        while target.exists():  # two in one second (a restore's safety copy, then undoing it)
            now += timedelta(seconds=1)
            target = folder / f"sirisos-{now:%Y%m%d-%H%M%S}-{kind}.tar.gz"
        with tempfile.NamedTemporaryFile(dir=folder, prefix=".backup-", suffix=".tmp", delete=False) as handle:
            temp = Path(handle.name)
        try:
            with tarfile.open(temp, "w:gz") as tar:
                raw = json.dumps(manifest, indent=2).encode()
                info = tarfile.TarInfo("manifest.json")
                info.size, info.mtime = len(raw), int(now.timestamp())
                tar.addfile(info, io.BytesIO(raw))
                for rel, path in files:
                    tar.add(path, arcname=f"data/{rel}", recursive=False)
            temp.replace(target)
        finally:
            temp.unlink(missing_ok=True)
    except OSError as exc:
        _last_error = f"{type(exc).__name__}: {exc}"
        logger.warning("SirisOS backup failed: %s", exc)
        raise
    _last_error = None
    prune(kind)
    return {**(_describe(target) or {}), "files": len(files)}


def prune(kind: str) -> None:
    for old in [b for b in backups() if b["kind"] == kind][KINDS[kind]:]:
        (backup_dir() / old["name"]).unlink(missing_ok=True)


def path_of(name: str) -> Path:
    """The backup called `name`; FileNotFoundError for anything else."""
    if not NAME.match(name):
        raise FileNotFoundError(name)
    path = backup_dir() / name
    if not path.is_file():
        raise FileNotFoundError(name)
    return path


def manifest(name: str) -> dict[str, Any]:
    with tarfile.open(path_of(name), "r:gz") as tar:
        member = tar.extractfile("manifest.json")
        if member is None:
            raise ValueError("This backup has no manifest.")
        return json.loads(member.read())


def _safe(member: tarfile.TarInfo) -> PurePosixPath | None:
    if not member.isfile() or not member.name.startswith("data/"):
        return None
    rel = PurePosixPath(member.name[len("data/"):])
    if rel.is_absolute() or not rel.parts or any(p in ("..", "") for p in rel.parts) or _skip(rel):
        return None
    return rel


def restore(name: str) -> dict[str, Any]:
    """Put every file in backup `name` back, after backing up what's there now."""
    source = path_of(name)
    manifest(name)  # refuse anything that isn't one of ours
    safety = create("before-restore")
    root = data_dir()
    restored = 0
    with tarfile.open(source, "r:gz") as tar:
        for member in tar.getmembers():
            rel = _safe(member)
            handle = tar.extractfile(member) if rel else None
            if rel is None or handle is None:
                continue
            target = root.joinpath(*rel.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.stem}-", suffix=".tmp", delete=False) as out:
                out.write(handle.read())
                temp = Path(out.name)
            temp.replace(target)
            restored += 1
    _forget_caches()
    return {"restored": restored, "from": name, "undo": safety["name"]}


def _forget_caches() -> None:
    """Modules that keep a file in memory read it again."""
    from app.hub import history

    history.reset()


def status(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    found = backups()
    newest = found[0]["created"] if found else None
    stale = newest is None or datetime.fromisoformat(newest) < now - timedelta(hours=STALE_HOURS)
    return {"enabled": enabled(), "folder": str(backup_dir()), "newest": newest, "count": len(found),
            "stale": stale, "error": _last_error, "nightly_hour": _hour()}


def due(now: datetime | None = None) -> bool:
    """True when tonight's backup hasn't been made yet (SIRISOS_TIMEZONE)."""
    from app.brief.service import zone

    local = (now or datetime.now(timezone.utc)).astimezone(zone())
    if local.hour < _hour():
        return False
    today = local.date()
    return not any(b["kind"] == "nightly" and datetime.fromisoformat(b["created"]).astimezone(zone()).date() == today for b in backups())


async def loop(every: float = 900.0) -> None:
    """Make the nightly backup; checked every 15 minutes."""
    while True:
        try:
            if due():
                await asyncio.to_thread(create, "nightly")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - the loop never dies
            logger.warning("Nightly backup failed: %s", exc)
        await asyncio.sleep(every)
