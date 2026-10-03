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


def load() -> LinksDocument:
    path = links_path()
    if not path.exists():
        return LinksDocument()
    return LinksDocument.model_validate_json(path.read_text(encoding="utf-8"))


def save(doc: LinksDocument) -> LinksDocument:
    doc = doc.model_copy(update={"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    path = links_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=".links-", suffix=".tmp", delete=False) as handle:
        handle.write(json.dumps(doc.model_dump(), indent=2, ensure_ascii=False) + "\n")
        temp = Path(handle.name)
    temp.replace(path)
    return doc
