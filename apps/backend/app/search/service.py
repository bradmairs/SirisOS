"""Search everything (ADR 109): one query, fanned out to every source SirisOS
can reach, grouped by where each result lives.

Sources, all at once, each with its own timeout (a slow or dead one is
listed in `failed` and blanks only its own group):

- Apps: every connector's name and description (opens its status sheet).
- Widgets: what the home screen is showing right now (the hub's cache).
- Links: the Links board.
- Second Brain: SirisAI's /siris/brain/search.
- Chats: what was said in SirisAI conversations (the read-only
  `search_conversations` tool, run directly, no LLM).
- Apps with their own search: APD PM (every register), Engineering Archive
  (assets, media, files incl. OCR text), Engineering Reviewer (reviews).
- Engineering: the Standards Library (titles and page text), SirisOS
  projects and SirisHydro questions.

Screens and calculators are matched in the browser, so they appear while
typing, before this answers.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any, Awaitable, Callable
from urllib.parse import quote

from app.brief.service import SirisAISource
from app.hub.connectors.base import Connector
from app.hub.connectors.sirisai import SirisAIConnector
from app.hub.service import Hub, shared_client
from app.links import store as links_store

logger = logging.getLogger(__name__)

SOURCE_TIMEOUT = 4.0
PER_GROUP = 6
MIN_QUERY = 2


def words(query: str) -> list[str]:
    return [w for w in re.split(r"\s+", query.lower().strip()) if w]


def matches(query: str, *texts: Any) -> bool:
    """Every word of the query appears somewhere in the texts."""
    hay = " ".join(str(t) for t in texts if t).lower()
    return bool(hay) and all(w in hay for w in words(query))


def score(query: str, title: str, *rest: Any) -> float:
    """Exact title > title starts with it > a word in the title starts with it >
    title contains it > only the rest matches."""
    q, t = query.lower().strip(), (title or "").lower()
    if not q:
        return 0.0
    if t == q:
        return 4.0
    if t.startswith(q):
        return 3.0
    if re.search(r"(?<![a-z0-9])" + re.escape(q), t):
        return 2.5
    if q in t:
        return 2.0
    if matches(query, title):
        return 1.5
    return 1.0 if matches(query, title, *rest) else 0.5


def snippet(text: str, query: str, width: int = 70) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    found = [text.lower().find(w) for w in words(query)]
    at = min((i for i in found if i >= 0), default=0)
    start = max(0, at - width // 2)
    out = text[start:start + width * 2].strip()
    return ("…" if start else "") + out + ("…" if start + width * 2 < len(text) else "")


def hit(query: str, title: str, subtitle: str = "", *, url: str | None = None, kind: str = "",
        external: bool = False, app_id: str | None = None, extra: tuple[Any, ...] = ()) -> dict[str, Any]:
    return {"title": title, "subtitle": subtitle, "url": url, "kind": kind, "external": external,
            "app_id": app_id, "score": score(query, title, subtitle, *extra)}


def _external(url: str | None) -> bool:
    return bool(url) and not str(url).startswith("/")


# -- sources --------------------------------------------------------------------


def apps_source(hub: Hub, query: str) -> list[dict[str, Any]]:
    return [
        hit(query, c.name, c.description, url=c.launch_url, kind="app", external=bool(c.launch_url), app_id=c.id,
            extra=(c.category, c.id))
        for c in hub.connectors
        if matches(query, c.name, c.description, c.category, c.id)
    ]


async def widgets_source(hub: Hub, query: str) -> list[dict[str, Any]]:
    out = []
    for app in await hub.apps(with_widgets=True):
        widget = app.get("widget")
        if not isinstance(widget, dict) or "error" in widget:
            continue
        for item in widget.get("items") or []:
            if matches(query, item.get("title"), item.get("subtitle")):
                url = item.get("url") or app.get("launch_url")
                out.append(hit(query, str(item.get("title")), " · ".join(x for x in (app["name"], item.get("subtitle")) if x),
                               url=url, kind="widget", external=_external(url), app_id=app["id"]))
        for metric in widget.get("metrics") or []:
            if matches(query, metric.get("label")):
                out.append(hit(query, f"{metric.get('label')}: {metric.get('value')}", f"{app['name']} · {widget.get('title', '')}".rstrip(" ·"),
                               url=app.get("launch_url"), kind="metric", external=_external(app.get("launch_url")), app_id=app["id"]))
    return out


def links_source(query: str) -> list[dict[str, Any]]:
    out = []
    for group in links_store.load().groups:
        for link in group.links:
            if matches(query, link.name, link.note, link.url, group.name):
                out.append(hit(query, link.name, " · ".join(x for x in (group.name, link.note) if x), url=link.url,
                               kind="link", external=True, extra=(link.url,)))
    return out


async def brain_source(ai: SirisAISource, query: str) -> list[dict[str, Any]]:
    notes = await ai.get("/siris/brain/search", q=query, limit=PER_GROUP + 2) or []
    out = []
    for n in notes:
        excerpt = next(iter(n.get("excerpts") or []), "")
        h = hit(query, str(n.get("title")), excerpt or str(n.get("type") or "Note"),
                url=f"/brain?q={quote(str(n.get('title')))}", kind=str(n.get("type") or "note"), extra=tuple(n.get("excerpts") or []))
        h["score"] = max(h["score"], 1.0)  # the brain's own ranking already judged it relevant
        out.append(h)
    return out


async def chats_source(ai: SirisAISource, query: str) -> list[dict[str, Any]]:
    said = await ai.tool("search_conversations", query=query, limit=20) or []
    seen: set[str] = set()
    out = []
    for m in said:
        cid = m.get("conversation_id")
        if not cid or cid in seen:
            continue
        seen.add(cid)
        who = "You said" if m.get("role") == "user" else "Siris said"
        when = str(m.get("when") or "")[:10]
        out.append(hit(query, snippet(str(m.get("text") or ""), query), " · ".join(x for x in (who, when) if x),
                       url=f"/assistant?c={quote(cid)}", kind="chat"))
    return out


async def connector_source(connector: Connector, query: str) -> list[dict[str, Any]]:
    found = await connector.search(shared_client(), query)
    return [
        hit(query, h.title, h.subtitle, url=h.url, kind=h.kind, external=_external(h.url), app_id=connector.id)
        for h in found
        if h.title
    ]


def _projects(query: str) -> list[dict[str, Any]]:
    from app.api.projects import _service as project_service

    return [
        hit(query, p.name, f"Project · {p.status}", url=f"/engineering/projects/{p.id}", kind="project", extra=(p.description,))
        for p in project_service().list_projects()
        if matches(query, p.name, p.description, " ".join(p.tags or []))
    ]


def _hydro(query: str) -> list[dict[str, Any]]:
    from app.api.sirishydro import _load_history

    return [
        hit(query, h.question, f"SirisHydro · {str(h.created_at)[:10]}", url=f"/engineering/hydro?q={quote(h.question)}", kind="hydro")
        for h in _load_history()
        if matches(query, h.question)
    ]


def _standards(query: str) -> list[dict[str, Any]]:
    from app.api.engineering_standards import _search as search_standards

    seen: set[str] = set()
    out = []
    for s in search_standards(query, None, False, 12).hits:
        doc = s.document
        if doc.id in seen:
            continue
        seen.add(doc.id)
        title = " · ".join(x for x in (doc.reference, doc.title) if x)
        detail = s.citation or f"{doc.authority} {doc.edition}".strip()
        h = hit(query, title, f"Standard · {detail}" + (f" · {s.snippet}" if s.snippet else ""),
                url=f"/engineering/standards?q={quote(query)}", kind="standard")
        h["score"] = max(h["score"], 1.0)  # matched its page text
        out.append(h)
    return out


def engineering_source(query: str) -> list[dict[str, Any]]:
    """SirisOS's own engineering data. Each store is read on its own, so one
    unreadable file doesn't hide the others."""
    out: list[dict[str, Any]] = []
    errors = []
    for part in (_projects, _hydro, _standards):
        try:
            out += part(query)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Engineering search: %s failed: %s", part.__name__, exc)
            errors.append(exc)
    if errors and len(errors) == 3:
        raise errors[0]
    return out


def career_source(query: str) -> list[dict[str, Any]]:
    """Goals, competency evidence, pathway steps and CPD activities (ADR 110)."""
    from app.career import store as career_store

    doc = career_store.load()
    out = []
    for g in doc.goals:
        if matches(query, g.title, g.next_step, g.note):
            out.append(hit(query, g.title, "Goal" + (f" · next: {g.next_step}" if g.next_step else ""), url="/career?view=goals", kind="goal"))
    for e in doc.evidence:
        if matches(query, e.title, e.summary):
            out.append(hit(query, e.title, f"Evidence · elements {', '.join(e.elements) or 'none yet'}",
                           url="/career?view=competencies", kind="evidence", extra=(e.summary,)))
    for p in doc.pathways:
        for s in p.steps:
            if matches(query, s.title, s.detail, s.note, p.name):
                out.append(hit(query, s.title, f"{p.name} · {s.status}", url="/career?view=pathways", kind="step", extra=(s.detail,)))
    for r in doc.cpd.records:
        if matches(query, r.title, r.provider, r.type):
            out.append(hit(query, r.title, " · ".join(x for x in ("CPD", r.date or "", f"{r.hours:g} h", r.provider) if x),
                           url="/career?view=cpd", kind="cpd"))
    return out


# -- the search ----------------------------------------------------------------

GROUPS: list[tuple[str, str, str]] = [
    # id, label, icon
    ("apps", "Apps", "layout-grid"),
    ("brain", "Second Brain", "brain"),
    ("chats", "Siris chats", "sparkles"),
    ("widgets", "On your home screen", "gauge"),
    ("links", "Links", "link"),
    ("career", "Career", "award"),
    ("engineering", "Engineering", "ruler"),
]


async def _run(name: str, work: Callable[[], Awaitable[list[dict[str, Any]]]] | Callable[[], list[dict[str, Any]]],
               failed: list[str], blocking: bool = False) -> list[dict[str, Any]]:
    try:
        if blocking:
            return await asyncio.wait_for(asyncio.to_thread(work), SOURCE_TIMEOUT)  # type: ignore[arg-type]
        return await asyncio.wait_for(work(), SOURCE_TIMEOUT)  # type: ignore[misc]
    except NotImplementedError:
        return []
    except Exception as exc:  # noqa: BLE001 - one source never breaks the search
        logger.info("Search source %s unavailable: %s", name, exc)
        failed.append(name)
        return []


async def search(hub: Hub, query: str) -> dict[str, Any]:
    started = time.perf_counter()
    query = query.strip()[:200]
    if len(query) < MIN_QUERY:
        return {"query": query, "groups": [], "failed": [], "took_ms": 0}

    failed: list[str] = []
    labels: dict[str, tuple[str, str]] = {gid: (label, icon) for gid, label, icon in GROUPS}
    jobs: dict[str, Awaitable[list[dict[str, Any]]]] = {
        "widgets": _run("On your home screen", lambda: widgets_source(hub, query), failed),
        "links": _run("Links", lambda: links_source(query), failed, blocking=True),
        "engineering": _run("Engineering", lambda: engineering_source(query), failed, blocking=True),
        "career": _run("Career", lambda: career_source(query), failed, blocking=True),
    }
    connector = hub.get("sirisai")
    if isinstance(connector, SirisAIConnector) and connector.configured:
        ai = SirisAISource(connector)
        jobs["brain"] = _run("Second Brain", lambda: brain_source(ai, query), failed)
        jobs["chats"] = _run("Siris chats", lambda: chats_source(ai, query), failed)
    for c in hub.connectors:
        if c.configured and not c.launch_only and type(c).search is not Connector.search:
            labels[c.id] = (c.name, c.icon)
            jobs[c.id] = _run(c.name, lambda c=c: connector_source(c, query), failed)

    names = list(jobs)
    results = dict(zip(names, await asyncio.gather(*(jobs[n] for n in names))))
    results["apps"] = apps_source(hub, query)

    fixed = [g[0] for g in GROUPS]
    order = fixed + [n for n in names if n not in fixed]
    groups = []
    for gid in order:
        hits = sorted(results.get(gid) or [], key=lambda h: -h["score"])[:PER_GROUP]
        if hits:
            label, icon = labels.get(gid, (gid, "search"))
            groups.append({"id": gid, "label": label, "icon": icon, "hits": hits, "best": hits[0]["score"]})
    # Most relevant group first; ties keep the order above.
    rank = {gid: i for i, gid in enumerate(order)}
    groups.sort(key=lambda g: (-g["best"], rank[g["id"]]))
    return {"query": query, "groups": groups, "failed": sorted(set(failed)),
            "took_ms": int((time.perf_counter() - started) * 1000)}
