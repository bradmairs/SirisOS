"""Quick capture that files itself (11.3).

One line in Quick capture goes where it belongs, and says where:

- **A spend**, "spent $42 at Bunnings", "$18.50 parking", "paid 30 for the car wash": onto Budget, sorted onto a
  line like an imported one (and replaced by the bank's own line when its CSV comes in).
- **A dinner**, "tacos Thursday", "dinner tomorrow: spag bol", "fish and chips for tea tonight": onto Meals for that day.
- **A gym note**, "bench felt heavy today": onto today's (or the last day's) workout in SirisGym. Never to Siris.
- **A task with a when**, "call Sam back Friday", "book the dentist tomorrow 9am": a task due then.
- **Anything else** isn't handled here and goes to Siris as a note, as before.

Each answer has an undo.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from app.tasks.service import WEEKDAYS

_WHEN = r"(today|tonight|tomorrow|" + "|".join(WEEKDAYS) + r")"
# The line's spaces are collapsed to single ones first (understand), so these match one space at a time: no runs of
# optional whitespace for a long line of spaces to make slow (CodeQL's polynomial-regex check).
_MONEY = re.compile(r"^(?:(?:i )?(?:spent|paid) )?\$ ?(\d{1,6}(?:\.\d{1,2})?) (?:(?:at|on|for) )?(.+)$", re.I)
_MONEY_WORDS = re.compile(r"^(?:i )?(?:spent|paid) \$?(\d{1,6}(?:\.\d{1,2})?) (?:dollars? )?(?:at|on|for) (.+)$", re.I)
_DINNER_LEAD = re.compile(rf"^(?:dinner|tea)(?: on)?(?: {_WHEN})?(?: ?[:\-–])? (.+)$", re.I)
_DINNER_TAIL = re.compile(rf"^(.+?) for (?:dinner|tea)(?: (?:on )?{_WHEN})?$", re.I)
_DISH_DAY = re.compile(r"^([a-z][a-z'&-]*(?: [a-z][a-z'&-]*){0,3}) (?:on )?(tonight|tomorrow|" + "|".join(WEEKDAYS) + r")$", re.I)
_NOT_FOOD = {"meeting", "notes", "note", "from", "with", "about", "call", "email", "the", "my", "our", "work", "due", "until", "since",
             "after", "before", "back", "off", "out", "leave", "flight", "trip", "gym", "class", "appointment", "dentist", "doctor"}
_TASK_VERBS = ("call", "ring", "phone", "email", "text", "message", "buy", "get", "book", "pay", "pick", "drop", "send", "fix", "check",
               "ask", "tell", "remind", "renew", "cancel", "order", "post", "return", "take", "make", "finish", "submit", "clean", "write",
               "organise", "organize", "follow", "chase", "sort", "print", "sign", "lodge", "visit", "see", "meet", "collect")
_GYM = re.compile(r"\b(bench|squat|squats|deadlift|deadlifts|press|ohp|row|rows|pull[- ]?ups?|chin[- ]?ups?|dips?|curls?|lunges?|"
                  r"gym|workout|session|sets?|reps?|pb|pr|warm[- ]?up|lifts?|lifted|spotter)\b", re.I)
_WHEN_WORD = re.compile(rf"\b{_WHEN}\b|\b\d{{1,2}}(?::\d{{2}})? ?(?:am|pm)\b|\bnext week\b|\bthis weekend\b|\b\d{{1,2}}/\d{{1,2}}\b", re.I)


def _day(word: str | None, today: date) -> date:
    w = (word or "today").lower()
    if w in ("today", "tonight"):
        return today
    if w == "tomorrow":
        return today + timedelta(days=1)
    return today + timedelta(days=(WEEKDAYS.index(w) - today.weekday()) % 7)


def _cap(text: str) -> str:
    text = text.strip(" .,")
    return text[:1].upper() + text[1:]


def understand(text: str, today: date) -> dict[str, Any] | None:
    """What a line is, without doing anything: {kind, ...} or None for a Siris note."""
    t = " ".join(text.split())
    if not t or len(t) > 300 or re.match(r"https?://", t):
        return None
    if (m := _MONEY_WORDS.match(t)) or (m := _MONEY.match(t)):
        what = m.group(2)
        on = today - timedelta(days=1) if re.search(r"\byesterday\b", what, re.I) else today
        what = re.sub(r"\b(today|tonight|yesterday)\b", "", what, flags=re.I).strip(" ,.")
        return {"kind": "spend", "amount": float(m.group(1)), "what": _cap(what) or "Spend", "date": on}
    first = t.split()[0].lower().strip(",.")
    for rx in (_DINNER_LEAD, _DINNER_TAIL):
        if m := rx.match(t):
            dish, when = (m.group(2), m.group(1)) if rx is _DINNER_LEAD else (m.group(1), m.group(2))
            if dish and len(dish.split()) <= 8:
                return {"kind": "dinner", "title": _cap(dish), "date": _day(when, today)}
    if _GYM.search(t) and first not in _TASK_VERBS:
        return {"kind": "gym", "note": _cap(t)}
    if first not in _TASK_VERBS and (m := _DISH_DAY.match(t)):
        words = m.group(1).lower().split()
        if len(words) <= 3 and not set(words) & _NOT_FOOD:
            return {"kind": "dinner", "title": _cap(m.group(1)), "date": _day(m.group(2), today)}
    if first in _TASK_VERBS or re.match(r"^\s*(remind me|todo|to do|task)\b", t, re.I):
        return {"kind": "task", "text": t}
    return None


async def route(hub: Any, text: str, now: datetime) -> dict[str, Any]:
    """Do it. {handled: False} means it's a note for Siris (the app sends it there as before)."""
    today = now.date()
    what = understand(text, today)
    if what is None:
        return {"handled": False}
    kind = what["kind"]
    if kind == "spend":
        from app.budget import actuals
        from app.budget import service as budget

        tx = actuals.add_manual(what["date"], what["what"], what["amount"])
        line = next((l for s in budget.get().get("sections", {}).values() for l in s if l["id"] == tx.get("line_id")), None)
        where = f"Budget{(' · ' + line['name']) if line else ''}"
        return {"handled": True, "kind": kind, "where": where, "url": "/budget",
                "said": f"${what['amount']:,.2f} at {what['what']}", "undo": {"kind": "spend", "id": tx["id"]}}
    if kind == "dinner":
        from app.meals import service as meals

        before = (meals.load().get("plan") or {}).get(what["date"].isoformat())
        await meals.plan(what["date"], what["title"])
        day = "tonight" if what["date"] == today else "tomorrow" if what["date"] == today + timedelta(days=1) else what["date"].strftime("%A")
        return {"handled": True, "kind": kind, "where": "Meals", "url": "/meals", "said": f"{what['title']}, {day}",
                "undo": {"kind": "dinner", "date": what["date"].isoformat(), "before": before}}
    if kind == "gym":
        from app.gym import store as gym

        doc = gym.load()
        done = [s for s in gym.counted(doc) if s.ended_at]
        recent = max(done, key=lambda s: s.started_at) if done else None
        if not recent or datetime.fromisoformat(recent.started_at.replace("Z", "+00:00")) < now - timedelta(hours=30):
            return {"handled": True, "kind": "gym", "where": None, "said": "No workout in the last day to put that on.",
                    "error": "Start or finish a workout in SirisGym first, then add the note there.", "undo": None, "url": "/gym"}
        before = recent.note
        recent.note = (f"{before}\n{what['note']}" if before else what["note"])[:2000]
        gym.save(doc)
        return {"handled": True, "kind": kind, "where": f"SirisGym · {recent.title}", "url": "/gym?view=history", "said": what["note"],
                "undo": {"kind": "gym", "id": recent.id, "before": before}}
    from app.tasks import service as tasks

    task = tasks.add(tasks.due_today_unless_said(tasks.parse(what["text"], today), today))
    when = task.due and (date.fromisoformat(task.due).strftime("%a %-d %b") + (f", {task.time}" if task.time else ""))
    return {"handled": True, "kind": "task", "where": "Tasks", "url": "/tasks", "said": f"{task.title}{f' · {when}' if when else ''}",
            "undo": {"kind": "task", "id": task.id}}


async def undo(u: dict[str, Any]) -> bool:
    kind = u.get("kind")
    if kind == "spend":
        from app.budget import actuals

        return actuals.remove_tx(str(u.get("id")))
    if kind == "dinner":
        from app.meals import service as meals

        on = date.fromisoformat(str(u["date"]))
        before = u.get("before")
        if before:
            await meals.plan(on, before["title"], before.get("slug"), before.get("recipe_id"), before.get("ingredients"))
        else:
            await meals.unplan(on)
        return True
    if kind == "gym":
        from app.gym import store as gym

        doc = gym.load()
        for s in doc.sessions:
            if s.id == u.get("id"):
                s.note = u.get("before") or ""
                gym.save(doc)
                return True
        return False
    if kind == "task":
        from app.tasks import service as tasks

        try:
            tasks.delete(str(u.get("id")))
            return True
        except Exception:  # noqa: BLE001
            return False
    return False
