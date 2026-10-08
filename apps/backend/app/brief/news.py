"""News for the daily brief: stories on what Brad cares about, taken from his
Second Brain rather than a fixed list.

Interests come from two notes in the vault:

- "Daily Briefing Preferences": its "Topics, in order" list becomes one news
  query per topic, with earlier topics weighted higher. Edit the note and the
  brief follows.
- "Brad Mairs": the [[linked]] interests and recent topics give a vocabulary
  for ranking stories. A story mentioning Home Assistant, Ollama or the
  Goulburn Valley ranks above a generic one in the same topic.

Stories come from public RSS: Google News search per topic (Australian
edition, last day only), and ABC News Australia for top national stories.
No API keys. Each fetch is bounded (size and time) and parsed defensively,
and results are cached for 30 minutes.
"""

from __future__ import annotations

import asyncio
import email.utils
import html
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

PREFERENCES_NOTE = "Daily Briefing Preferences"
OWNER_NOTE = "Brad Mairs"
MAX_FEED_BYTES = 2_000_000
CACHE_SECONDS = 30 * 60
STORIES_PER_TOPIC = 3
TOP_STORIES_FEED = "https://www.abc.net.au/news/feed/2942460/rss.xml"

# Used when the vault isn't reachable or has no preferences note yet.
DEFAULT_TOPICS = [
    "AI and emerging technology",
    "Self-hosting and home lab",
    "Civil engineering and infrastructure",
    "Australian and Melbourne news",
    "Science and space",
]

# Turn a topic as Brad wrote it into a search that finds news, not essays.
QUERY_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bai\b|artificial intelligence|emerging tech", re.I), '"artificial intelligence" OR "AI model" OR OpenAI OR Anthropic OR "new AI"'),
    (re.compile(r"self-?host|home ?lab", re.I), 'self-hosted OR homelab OR "Home Assistant" OR Docker OR "open source" software'),
    (re.compile(r"civil engineering|infrastructure", re.I), 'infrastructure project Australia OR "civil engineering" OR "water infrastructure" Victoria'),
    (re.compile(r"australian|melbourne news", re.I), "Melbourne OR Victoria news"),
    (re.compile(r"science|space", re.I), "space OR NASA OR science discovery"),
    (re.compile(r"melbourne events|events worth", re.I), "Melbourne events this week OR weekend"),
]


@dataclass
class Topic:
    name: str
    query: str
    weight: float


@dataclass
class Story:
    title: str
    url: str
    source: str
    published: str | None
    topic: str
    score: float = 0.0
    matches: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "url": self.url, "source": self.source, "published": self.published,
                "topic": self.topic, "matches": self.matches[:3]}


def _plain(text: str) -> str:
    """[[Note|label]] -> label, [[Note]] -> Note, markdown emphasis gone."""
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    return re.sub(r"[*_`]", "", text).strip()


def topics_from_note(body: str | None) -> list[Topic]:
    """The ordered list under a "Topics" heading in the preferences note."""
    names: list[str] = []
    if body:
        section = re.search(r"^##+\s*Topics[^\n]*\n(.*?)(?=^##\s|\Z)", body, flags=re.M | re.S | re.I)
        if section:
            for line in section.group(1).splitlines():
                m = re.match(r"\s*(?:\d+[.)]|[-*])\s+(.+)", line)
                if m:
                    names.append(_plain(m.group(1)))
    names = names or DEFAULT_TOPICS
    topics = []
    for i, name in enumerate(names[:8]):
        query = next((q for pattern, q in QUERY_HINTS if pattern.search(name)), name)
        topics.append(Topic(name=name, query=query, weight=1.0 - i * 0.08))
    return topics


def vocabulary(*bodies: str | None, extra: list[str] | None = None) -> set[str]:
    """Phrases that mark a story as Brad's kind of story: every [[linked]] note in his notes
    (Home Assistant, Ollama, Goulburn Valley Water, Melbourne...) plus recent hot topics."""
    words: set[str] = set()
    for body in bodies:
        for m in re.finditer(r"\[\[([^\]|#]+)", body or ""):
            phrase = m.group(1).strip()
            if len(phrase) >= 3 and not re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", phrase):
                words.add(phrase.lower())
    for tag in extra or []:
        tag = tag.replace("-", " ").strip().lower()
        if len(tag) >= 3:
            words.add(tag)
    # Too generic to say anything about a story.
    return words - {"home", "career", "health", "finances", "learning", "relationships", "creativity", "brad mairs"}


def parse_feed(xml_text: str, topic: str) -> list[Story]:
    """RSS 2.0 items (Google News and ABC both use it). Anything malformed is skipped."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    stories = []
    for item in root.iter("item"):
        title = html.unescape((item.findtext("title") or "").strip())
        url = (item.findtext("link") or "").strip()
        if not title or not url.startswith(("http://", "https://")):
            continue
        source_el = item.find("source")
        source = (source_el.text or "").strip() if source_el is not None and source_el.text else ""
        # Google News titles end with " - Source"; keep the headline clean.
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3].strip()
        elif not source:
            m = re.match(r"(.+) - ([^-]{2,40})$", title)
            if m:
                title, source = m.group(1).strip(), m.group(2).strip()
        published = None
        if item.findtext("pubDate"):
            try:
                published = email.utils.parsedate_to_datetime(item.findtext("pubDate")).astimezone(timezone.utc).isoformat()
            except (TypeError, ValueError):
                published = None
        stories.append(Story(title=title, url=url, source=source, published=published, topic=topic))
    return stories


def rank(stories: list[Story], topics: list[Topic], vocab: set[str], now: datetime | None = None) -> list[Story]:
    """Score each story: topic priority, mentions of Brad's own interests, and freshness."""
    now = now or datetime.now(timezone.utc)
    weight = {t.name: t.weight for t in topics}
    for s in stories:
        text = s.title.lower()
        s.matches = sorted({v for v in vocab if re.search(r"(?<!\w)" + re.escape(v) + r"(?!\w)", text)},
                           key=lambda v: (-len(v), v))
        age_hours = 24.0
        if s.published:
            try:
                age_hours = max(0.0, (now - datetime.fromisoformat(s.published)).total_seconds() / 3600)
            except ValueError:
                pass
        s.score = weight.get(s.topic, 0.5) + 0.35 * min(len(s.matches), 3) + max(0.0, 0.3 - age_hours / 80)
    return sorted(stories, key=lambda s: -s.score)


def _key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()[:80]


def pick(stories: list[Story], topics: list[Topic], per_topic: int = STORIES_PER_TOPIC) -> list[dict[str, Any]]:
    """Group into topics in Brad's order, best stories first, no repeats across topics."""
    seen: set[str] = set()
    groups = []
    for t in topics:
        chosen = []
        for s in stories:
            if s.topic != t.name or _key(s.title) in seen:
                continue
            seen.add(_key(s.title))
            chosen.append(s.to_dict())
            if len(chosen) >= per_topic:
                break
        if chosen:
            groups.append({"topic": t.name, "stories": chosen})
    top = [s.to_dict() for s in stories if s.topic == "Top stories" and _key(s.title) not in seen][:3]
    if top:
        groups.append({"topic": "Top stories", "stories": top})
    return groups


def google_news_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote_plus(query + ' when:1d')}&hl=en-AU&gl=AU&ceid=AU:en"


async def _fetch(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        async with client.stream("GET", url, timeout=8.0, follow_redirects=True,
                                 headers={"User-Agent": "SirisOS/1.0 (daily brief)"}) as r:
            if r.status_code != 200:
                return None
            chunks, size = [], 0
            async for chunk in r.aiter_bytes():
                size += len(chunk)
                if size > MAX_FEED_BYTES:
                    return None
                chunks.append(chunk)
            return b"".join(chunks).decode(r.encoding or "utf-8", errors="replace")
    except httpx.HTTPError:
        return None


class NewsService:
    def __init__(self) -> None:
        self._cache: tuple[float, str, dict[str, Any]] | None = None
        self._lock = asyncio.Lock()

    async def stories(
        self,
        client: httpx.AsyncClient,
        load_note: Callable[[str], Awaitable[str | None]],
        hot_tags: list[str],
        fresh: bool = False,
    ) -> dict[str, Any]:
        async with self._lock:
            prefs, owner = await asyncio.gather(load_note(PREFERENCES_NOTE), load_note(OWNER_NOTE))
            topics = topics_from_note(prefs)
            signature = "|".join(t.name for t in topics)
            if not fresh and self._cache and self._cache[1] == signature and time.monotonic() - self._cache[0] < CACHE_SECONDS:
                return self._cache[2]

            feeds = [(t.name, google_news_url(t.query)) for t in topics] + [("Top stories", TOP_STORIES_FEED)]
            texts = await asyncio.gather(*(_fetch(client, url) for _, url in feeds))
            stories: list[Story] = []
            failed = 0
            for (name, _), text in zip(feeds, texts):
                if text is None:
                    failed += 1
                    continue
                stories += parse_feed(text, name)
            vocab = vocabulary(prefs, owner, extra=hot_tags)
            result = {
                "topics": pick(rank(stories, topics, vocab), topics),
                "interests_from": PREFERENCES_NOTE if prefs else "default topics (add a 'Daily Briefing Preferences' note)",
                "feeds_failed": failed,
                "feeds_total": len(feeds),
            }
            if stories:  # don't cache an outage
                self._cache = (time.monotonic(), signature, result)
            return result


news_service = NewsService()
