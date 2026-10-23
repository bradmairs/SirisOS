"""Email triage (3.3): the replies SirisAI drafted in its morning triage, in
one place to read, edit, send, snooze or leave.

They're SirisAI attention items from the `triage` source: the title is
"Reply to <who>: <subject>" and the body is the email's opening followed by
"My draft…:" and the draft. Sending goes back through SirisAI (which sends
exactly the reply shown, edited or not); snoozing is SirisOS's own, like
the Inbox's.
"""

from __future__ import annotations

import re
from typing import Any

from app.attention import service as attention
from app.hub.service import Hub

_TITLE = re.compile(r"^Reply to (?P<who>.+?): (?P<subject>.*)$")
_DRAFT = re.compile(r"\n\nMy draft(?P<saved> \(saved in your Drafts folder\))?:\n\n", re.S)


def parse(item: dict[str, Any]) -> dict[str, Any]:
    m = _TITLE.match(item.get("title") or "")
    body = item.get("body") or ""
    split = _DRAFT.split(body, maxsplit=1)
    snippet, saved, draft = (split[0], bool(split[1]), split[2]) if len(split) == 3 else (body, False, "")
    actions = {a.get("id") for a in item.get("actions") or []}
    return {
        "id": item["id"],
        "who": m.group("who") if m else None,
        "subject": m.group("subject") if m else item.get("title"),
        "snippet": snippet.strip(),
        "draft": draft.strip(),
        "in_drafts_folder": saved,
        "can_send": "send" in actions,
        "created_at": item.get("created_at"),
    }


async def replies(hub: Hub) -> dict[str, Any]:
    items = await attention.ai_items(hub)
    if items is None:
        return {"replies": [], "snoozed": 0, "unavailable": True}
    later = attention.snoozed()
    triage = [i for i in items if i.get("source") == "triage" and str(i.get("title", "")).startswith("Reply to ")]
    return {
        "replies": [parse(i) for i in triage if i["id"] not in later],
        "snoozed": sum(1 for i in triage if i["id"] in later),
        "unavailable": False,
    }
