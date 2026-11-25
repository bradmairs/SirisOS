"""Downloading kept receipts (11.8.0).

One receipt, or all of them (a search, or a chosen few) as a zip for tax time or a warranty claim: each receipt's own
file (the invoice PDF, the photo, or the email when the receipt is written in it), named by date and who it's from,
and receipts.csv listing them. An email is saved as a web page that can't run or load anything.
"""

from __future__ import annotations

import asyncio
import csv
import io
import re
import zipfile
from typing import Any
from urllib.parse import quote

from app.hub import sirisai_api
from app.hub.service import Hub

MAX_RECEIPTS = 300
# An email saved from SirisOS opens as a plain page: nothing in it may run or load (it came from the internet).
EMAIL_GUARD = ('<meta charset="utf-8"><meta http-equiv="Content-Security-Policy" '
               "content=\"default-src 'none'; style-src 'unsafe-inline'; img-src data:\">\n")


def safe_name(text: str, limit: int = 80) -> str:
    """A file name that works on a phone, a Mac and Windows."""
    cleaned = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", " ", text or "")
    cleaned = " ".join(cleaned.split()).strip(" .")
    return cleaned[:limit].rstrip(" .") or "Receipt"


def main_file(doc: dict[str, Any]) -> str | None:
    files = doc.get("files") or []
    chosen = doc.get("receipt_file")
    return chosen if chosen in files else (files[0] if files else None)


def file_name(doc: dict[str, Any], original: str | None) -> str:
    """'2026-11-03 Bunnings - Cordless drill.pdf': the date it came, who from, what."""
    day = str(doc.get("added_at") or "")[:10]
    who = safe_name(str(doc.get("sender") or ""), 40)
    what = safe_name(str(doc.get("title") or "Receipt"), 60)
    base = " - ".join(x for x in (who if who != "Receipt" else "", what) if x)
    ext = ".txt"
    if original:
        ext = ".html" if original == "email.html" else ".txt" if original == "email.txt" else (
            "." + original.rsplit(".", 1)[1].lower() if "." in original else "")
    return safe_name(f"{day} {base}".strip(), 110) + ext


def guard_email(data: bytes) -> bytes:
    return EMAIL_GUARD.encode() + data


async def _file(hub: Hub, doc_id: int, name: str) -> bytes | None:
    try:
        r = await sirisai_api.raw(hub, "GET", f"/siris/documents/{doc_id}/files/{quote(name, safe='')}", timeout=60.0)
    except sirisai_api.SirisAIError:
        return None
    return r.content if r.status_code < 400 else None


async def _doc(hub: Hub, doc_id: int) -> dict[str, Any] | None:
    try:
        r = await sirisai_api.raw(hub, "GET", f"/siris/documents/{doc_id}", timeout=30.0)
    except sirisai_api.SirisAIError:
        return None
    return r.json() if r.status_code < 400 and r.content else None


async def content(hub: Hub, doc: dict[str, Any]) -> tuple[str, bytes] | None:
    """(file name, bytes) for one receipt: its own file, else its text."""
    name = main_file(doc)
    if name:
        data = await _file(hub, int(doc["id"]), name)
        if data is not None:
            return file_name(doc, name), guard_email(data) if name == "email.html" else data
    if doc.get("text"):
        return file_name(doc, None), str(doc["text"]).encode()
    return None


async def zip_of(hub: Hub, docs: list[dict[str, Any]]) -> tuple[bytes, int]:
    """A zip of the receipts and receipts.csv; returns (zip, how many receipts are in it)."""
    gate = asyncio.Semaphore(4)

    async def one(d: dict[str, Any]) -> tuple[dict[str, Any], tuple[str, bytes] | None]:
        async with gate:
            full = d if "files" in d else (await _doc(hub, int(d["id"])) or d)
            return full, await content(hub, full)

    got = await asyncio.gather(*(one(d) for d in docs[:MAX_RECEIPTS]))
    buf = io.BytesIO()
    index = io.StringIO()
    rows = csv.writer(index)
    rows.writerow(["Date", "From", "Receipt", "Summary", "File"])
    used: set[str] = set()
    count = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for doc, item in got:
            name = ""
            if item:
                name, data = item
                stem, dot, ext = name.rpartition(".")
                n = 2
                while name.lower() in used:
                    name = f"{stem} ({n}).{ext}" if dot else f"{name} ({n})"
                    n += 1
                used.add(name.lower())
                z.writestr(name, data)
                count += 1
            rows.writerow([str(doc.get("added_at") or "")[:10], doc.get("sender") or "", doc.get("title") or "",
                           doc.get("summary") or "", name or "(no file)"])
        z.writestr("receipts.csv", "﻿" + index.getvalue())  # the mark lets Excel read it as UTF-8
    return buf.getvalue(), count
