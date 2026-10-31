"""Ask your manuals (6.4): "how do I descale the coffee machine?" answered
from the PDF manuals uploaded to appliances, with the page to look at.

Each manual's text is read page by page (pypdf) the first time it's asked
about and kept beside it (manuals/<file>.pages.json). A question finds the
best few pages by its words (the appliance's name and make count too), then
SirisAI answers from just those pages, citing them. Without SirisAI it
still returns the pages.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from typing import Any

import httpx

from app.hub import sirisai_api
from app.hub.service import Hub, shared_client
from app.maintenance import service

logger = logging.getLogger(__name__)
TOP = 4
STOP = set("the a an and or of to in on for with how do does i my is it what when where which can you your be this that from at by are not".split())


def _stem(w: str) -> str:
    """Rough enough for manuals: descale, descaling and descaled all match."""
    for suffix in ("ing", "ed", "es", "er", "s", "e"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 4:
            return w[: -len(suffix)]
    return w


def _words(text: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in STOP]


def pages(appliance: service.Appliance) -> list[str]:
    """The manual's pages as text, read once and kept."""
    if not appliance.manual:
        return []
    pdf = service.manuals_dir() / appliance.manual.stored
    cache = pdf.with_name(pdf.name + ".pages.json")
    if cache.exists():
        try:
            return list(json.loads(cache.read_text()))
        except (OSError, ValueError):
            pass
    if not pdf.exists() or pdf.suffix.lower() != ".pdf":
        return []
    try:
        from pypdf import PdfReader

        texts = [(p.extract_text() or "") for p in PdfReader(str(pdf)).pages]
    except Exception:  # noqa: BLE001 - a scanned or broken PDF has no text to search
        logger.info("Couldn't read %s", pdf.name, exc_info=True)
        texts = []
    cache.write_text(json.dumps(texts))
    return texts


def search(question: str, appliance_id: str | None = None, top: int = TOP) -> list[dict[str, Any]]:
    doc = service.load()
    q = Counter(_words(question))
    if not q:
        return []
    found = []
    for a in doc.appliances:
        if appliance_id and a.id != appliance_id:
            continue
        texts = pages(a)
        if not texts:
            continue
        name_bonus = sum(1 for w in _words(f"{a.name} {a.make} {a.model}") if w in q)
        n = len(texts)
        df = Counter(w for t in texts for w in set(_words(t)))
        for i, t in enumerate(texts):
            words = Counter(_words(t))
            score = sum(min(words[w], 5) * math.log(1 + n / (1 + df[w])) for w in q if words[w])
            if score:
                found.append({"appliance": a.name, "appliance_id": a.id, "page": i + 1, "score": round(score + name_bonus * 2, 2),
                              "text": re.sub(r"\s+", " ", t).strip()[:1500]})
    return sorted(found, key=lambda x: -x["score"])[:top]


async def ask(hub: Hub, question: str, appliance_id: str | None = None) -> dict[str, Any]:
    hits = search(question, appliance_id)
    sources = [{"appliance": h["appliance"], "appliance_id": h["appliance_id"], "page": h["page"], "snippet": h["text"][:240]} for h in hits]
    if not hits:
        return {"answer": None, "sources": [], "note": "Nothing in the uploaded manuals matches that. Upload the manual (a PDF with text) to the appliance first."}
    connector = sirisai_api.connector(hub)
    if connector is None:
        return {"answer": None, "sources": sources, "note": "SirisAI isn't connected: here are the pages that match."}
    excerpts = "\n\n".join(f"[{h['appliance']}, page {h['page']}]\n{h['text']}" for h in hits)
    prompt = ("(From SirisOS's appliance manuals. Answer only from these excerpts, in a few short steps, and say which page each "
              "step comes from, like (p. 12). If they don't cover it, say so.)\n\n"
              f"Question: {question}\n\nExcerpts:\n{excerpts}")
    try:
        response = await shared_client().post(f"{connector.base_url}/siris/ask", headers=connector.headers(), json={"prompt": prompt}, timeout=90.0)
    except httpx.HTTPError:
        return {"answer": None, "sources": sources, "note": "SirisAI didn't answer: here are the pages that match."}
    if response.status_code >= 400:
        return {"answer": None, "sources": sources, "note": f"SirisAI couldn't answer ({response.status_code}): here are the pages that match."}
    return {"answer": response.text.strip() or None, "sources": sources}
