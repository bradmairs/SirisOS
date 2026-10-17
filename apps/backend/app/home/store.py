"""Home layout: which widgets show on Home and in what order, kept
separately for phone and desktop. Widgets are named by id ("weather",
"app:reviewer"...); ids Home doesn't know (an app removed later) are ignored
by the web app, and widgets missing from `order` keep their natural place."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.services import json_store

WidgetId = str


class DeviceLayout(BaseModel):
    order: list[WidgetId] = Field(default_factory=list, max_length=200)
    hidden: list[WidgetId] = Field(default_factory=list, max_length=200)


class HomeLayout(BaseModel):
    phone: DeviceLayout = Field(default_factory=DeviceLayout)
    desktop: DeviceLayout = Field(default_factory=DeviceLayout)
    updated_at: str | None = None


def _path():
    return json_store.data_path("SIRISOS_HOME_LAYOUT_PATH", "home-layout.json")


def _clean(ids: list[str]) -> list[str]:
    seen: list[str] = []
    for i in ids:
        i = i.strip()[:80]
        if i and i not in seen:
            seen.append(i)
    return seen


def load() -> HomeLayout:
    return HomeLayout.model_validate(json_store.read(_path(), {}))


def save(layout: HomeLayout) -> HomeLayout:
    for device in (layout.phone, layout.desktop):
        device.order = _clean(device.order)
        device.hidden = _clean(device.hidden)
    layout.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json_store.write(_path(), layout.model_dump())
    return layout
