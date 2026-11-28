"""New versions of the standards in the library (11.21).

Each standard can say where it came from (`source` in its metadata):

- `url`: where the PDF downloads from. If the same link starts serving a different document, that's a new version.
- `page` + `pattern` (optional): for publishers that put each version at a new address (IDM_Version_5.6 then 5.7,
  ARR ..._V4.2 then _V4.3). The page's links (address and link text) are matched against the regex `pattern`; its
  first group, when there is one, is the version, and the highest wins. A link other than `url` is a new version.

Once a week (Sunday from SIRISOS_STANDARDS_CHECK_HOUR, 4am) each active standard with a source is checked: the page
for a newer link, then the file itself. A different file whose text is the same as what's stored (a PDF regenerated
with new timestamps) isn't a new version. A new version is stored as a new revision of the standard, exactly as a
manual "upload new revision" does: the old one is kept, marked superseded. Each update is logged
(standards-updates.json) and sent as a notification.

Downloads only ever come from the addresses you (or the library's import) set; anything that isn't a PDF, or is
over SIRISOS_STANDARDS_MAX_UPLOAD_MB, is refused.
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import json
import logging
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

from app.services import json_store

logger = logging.getLogger(__name__)

UA = "Mozilla/5.0 (SirisOS standards update check)"
KEEP_EVENTS = 200
_running = threading.Lock()


def _state_path() -> Path:
    return json_store.data_path("SIRISOS_STANDARDS_UPDATES_PATH", "standards-updates.json")


def state() -> dict[str, Any]:
    raw = json_store.read(_state_path(), {})
    raw = raw if isinstance(raw, dict) else {}
    raw.setdefault("events", [])
    return raw


def _save(doc: dict[str, Any]) -> None:
    doc["events"] = doc["events"][:KEEP_EVENTS]
    json_store.write(_state_path(), doc)


def check_hour() -> int:
    try:
        return max(0, min(23, int(os.getenv("SIRISOS_STANDARDS_CHECK_HOUR", "4"))))
    except ValueError:
        return 4


def due(now: datetime) -> bool:
    """Sunday from the check hour (local time), once a week."""
    from app.brief.service import zone

    local = now.astimezone(zone())
    last = state().get("last_run")
    if last and now - datetime.fromisoformat(last) < timedelta(days=6):
        return False
    return local.weekday() == 6 and local.hour >= check_hour()


# -- finding the newest file ---------------------------------------------------------------------------------------

_LINK = re.compile(r"<a\b[^>]*?href\s*=\s*[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.I | re.S)


def page_links(page_html: str, base: str) -> list[tuple[str, str]]:
    """(absolute address, link text) for each link on a page."""
    out = []
    for href, inner in _LINK.findall(page_html):
        text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", inner)).split())
        out.append((urljoin(base, html.unescape(href.strip())), text))
    return out


def _version_key(value: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", value or "")) or (0,)


def newest_link(links: list[tuple[str, str]], pattern: str) -> str | None:
    """The link whose address or text matches `pattern`, highest version (its first group) first."""
    rx = re.compile(pattern, re.I)
    found = []
    for href, text in links:
        m = rx.search(href) or rx.search(text)
        if m:
            found.append((_version_key(m.group(1) if m.groups() else ""), href))
    return max(found)[1] if found else None


# -- comparing ---------------------------------------------------------------------------------------------------

def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _same_text(new_pages: list[dict[str, Any]], old_pages: list[dict[str, Any]]) -> bool:
    return [_norm(p.get("text", "")) for p in new_pages] == [_norm(p.get("text", "")) for p in old_pages]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# -- the check ---------------------------------------------------------------------------------------------------

def check_one(client: httpx.Client, metadata: dict[str, Any]) -> dict[str, Any]:
    """Check one standard; store a new revision when there's a new version. Returns what happened."""
    from app.api import engineering_standards as es
    from app.services.engineering_standards_ocr import extract_standard_pages

    source = metadata.get("source") or {}
    url = source.get("url")
    out: dict[str, Any] = {"id": metadata["id"], "title": metadata["title"], "status": "current"}
    if not url:
        return {**out, "status": "no source"}
    if source.get("page") and source.get("pattern"):
        page = client.get(source["page"])
        page.raise_for_status()
        newer = newest_link(page_links(page.text, str(page.url)), source["pattern"])
        if newer and newer != url:
            out["new_url"] = newer
            url = newer
    response = client.get(url)
    response.raise_for_status()
    data = response.content
    if not data.startswith(b"%PDF"):
        return {**out, "status": "error", "why": f"{url} isn't a PDF any more"}
    if len(data) > es.MAX_UPLOAD_BYTES:
        return {**out, "status": "error", "why": f"the new file is over {es.MAX_UPLOAD_BYTES // 1024 // 1024} MB"}
    digest = _sha(data)
    directory, _, index_path = es._paths(metadata["id"])
    if digest == source.get("sha256") or (not source.get("sha256") and (directory / metadata["filename"]).exists()
                                           and _sha((directory / metadata["filename"]).read_bytes()) == digest):
        es._write_metadata({**metadata, "source": {**source, "sha256": digest, "checked_at": _now()}})
        return out
    # A different file: is it a different document, or the same one regenerated?
    probe = directory / ".update-probe.pdf"
    probe.write_bytes(data)
    try:
        new_pages = extract_standard_pages(probe).pages
    finally:
        probe.unlink(missing_ok=True)
    old_pages = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
    if not out.get("new_url") and _same_text(new_pages, old_pages):
        es._write_metadata({**metadata, "source": {**source, "sha256": digest, "checked_at": _now()}})
        return {**out, "status": "current", "note": "same text, file regenerated"}
    name = re.sub(r"[?#].*$", "", url.rsplit("/", 1)[-1]) if out.get("new_url") else metadata["filename"]
    if not name.lower().endswith(".pdf"):
        name = metadata["filename"]
    new = es.replace_document(metadata["id"], filename=es._safe_filename(name), data=data,
                              source={**source, "url": url, "sha256": digest, "checked_at": _now()})
    return {**out, "status": "updated", "new_id": new["id"], "revision": new["revision"], "from": metadata.get("edition"), "url": url}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run(now: datetime | None = None, only: str | None = None) -> dict[str, Any]:
    """Check every active standard with a source (or just `only`). One at a time; never two runs at once."""
    from app.api import engineering_standards as es

    if not _running.acquire(blocking=False):
        return {"skipped": "a check is already running"}
    try:
        results: list[dict[str, Any]] = []
        with httpx.Client(timeout=120.0, follow_redirects=True, headers={"User-Agent": UA}) as client:
            for path in sorted(es.LIBRARY_ROOT.glob("*/metadata.json")):
                try:
                    metadata = es._normalise_metadata(json.loads(path.read_text(encoding="utf-8")))
                except (OSError, json.JSONDecodeError):
                    continue
                if not metadata.get("active") or not (metadata.get("source") or {}).get("url") or (only and metadata["id"] != only):
                    continue
                try:
                    results.append(check_one(client, metadata))
                except Exception as exc:  # noqa: BLE001 - one publisher being down never stops the rest
                    results.append({"id": metadata["id"], "title": metadata["title"], "status": "error", "why": str(exc)[:200]})
        doc = state()
        stamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
        doc["last_run"] = stamp
        doc["last"] = {"checked": len(results), "updated": sum(r["status"] == "updated" for r in results),
                       "errors": [r for r in results if r["status"] == "error"][:20]}
        doc["events"] = [{"at": stamp, **r} for r in results if r["status"] == "updated"] + doc["events"]
        _save(doc)
        return {"checked": len(results), "results": results}
    finally:
        _running.release()


def start(only: str | None = None) -> bool:
    """Run in the background (from the screen's Check now)."""
    if _running.locked():
        return False
    threading.Thread(target=run, kwargs={"only": only}, daemon=True, name="standards-updates").start()
    return True


async def loop(every: float = 1800.0) -> None:
    while True:
        try:
            if due(datetime.now(timezone.utc)):
                await asyncio.to_thread(run)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - the loop never dies
            logger.warning("Standards update check failed: %s", exc)
        await asyncio.sleep(every)


def push_messages(now: datetime) -> list[dict[str, Any]]:
    """A notification for each standard updated in the last fortnight (each sent once, by its key)."""
    from app.push.notifier import message

    out = []
    for e in state()["events"]:
        if now - datetime.fromisoformat(e["at"]) > timedelta(days=14):
            break
        out.append(message(f"standard-updated:{e['new_id']}", "apps", f"New version of {e['title']}",
                           "SirisOS downloaded it and kept the old one as superseded.", "/engineering/standards"))
    return out
