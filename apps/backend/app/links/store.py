"""Links document: groups of links, kept as one JSON file and written atomically."""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

URL_RE = re.compile(r"^https?://[^\s/]+", re.I)


def links_path() -> Path:
    return Path(os.getenv("SIRISOS_LINKS_PATH", "/app/data/links.json"))


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class Link(BaseModel):
    id: str = Field(default_factory=new_id, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    url: str = Field(min_length=1, max_length=2000)
    # An icon URL, or a data: URI for icons that only existed inside Homarr.
    icon: str | None = Field(default=None, max_length=600_000)
    note: str = Field(default="", max_length=200)

    @field_validator("url")
    @classmethod
    def http_only(cls, value: str) -> str:
        value = value.strip()
        if not URL_RE.match(value):
            raise ValueError("Links must be http:// or https:// addresses.")
        return value


class LinkGroup(BaseModel):
    id: str = Field(default_factory=new_id, max_length=40)
    name: str = Field(min_length=1, max_length=60)
    links: list[Link] = Field(default_factory=list, max_length=200)


class LinksDocument(BaseModel):
    groups: list[LinkGroup] = Field(default_factory=list, max_length=50)
    updated_at: str | None = None


# Links SirisOS adds by itself once, for apps Brad asked to have on the launchpad.
# Each is added the first time links are loaded after an update, then remembered
# in links-added.json beside links.json, so deleting or editing one sticks.
BUILT_IN: list[tuple[str, Link]] = [
    ("wheres-jug", Link(name="Where's Jug?", url="http://192.168.0.100:3045", icon="http://192.168.0.100:3045/img/jug.svg",
                        note="Black Ops Zombies leaderboard")),
]
GAMES_GROUP = re.compile(r"gam(e|ing)|play|fun|entertain", re.I)


def _added_path() -> Path:
    return links_path().with_name("links-added.json")


def _add_built_ins(doc: LinksDocument) -> LinksDocument:
    if os.getenv("SIRISOS_BUILT_IN_LINKS", "1") == "0":
        return doc
    added_path = _added_path()
    added = set(json.loads(added_path.read_text(encoding="utf-8"))) if added_path.exists() else set()
    pending = [(key, link) for key, link in BUILT_IN if key not in added]
    if not pending:
        return doc
    urls = {link.url.rstrip("/") for group in doc.groups for link in group.links}
    for key, link in pending:
        if link.url.rstrip("/") not in urls:
            group = next((g for g in doc.groups if GAMES_GROUP.search(g.name)), None)
            if group is None:
                group = LinkGroup(name="Games")
                doc.groups.append(group)
            group.links.append(link.model_copy(update={"id": new_id()}))
        added.add(key)
    doc = save(doc)
    added_path.write_text(json.dumps(sorted(added)) + "\n", encoding="utf-8")
    return doc


def load() -> LinksDocument:
    path = links_path()
    doc = LinksDocument.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else LinksDocument()
    return _add_built_ins(doc)


def save(doc: LinksDocument) -> LinksDocument:
    doc = doc.model_copy(update={"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    path = links_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=".links-", suffix=".tmp", delete=False) as handle:
        handle.write(json.dumps(doc.model_dump(), indent=2, ensure_ascii=False) + "\n")
        temp = Path(handle.name)
    temp.replace(path)
    return doc
