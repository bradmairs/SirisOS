"""Bringing years of workouts in from another app (6.6): JEFIT first, but any
CSV with a date, an exercise and weight/reps will do.

**Reading.** A .csv, or a .zip of them. A file can hold several tables one
after another (a heading line, or a blank line, between them); each table
whose header names a date and an exercise is read. Two shapes are
understood:
- a row per set: date, exercise, weight, reps (and set number, seconds,
  distance if present);
- a row per exercise with its sets written out, like "60x10,62.5x8,65x6"
  (or "60 x 10" / "60×10"); a log column holding these is spotted by its
  content.
Weights are in pounds when a header says lb/lbs (or you say so), and are
saved in your SirisGYM unit. Dates can be
2024-03-05, 05/03/2024 (day first; month first when the day can't be), or
a Unix timestamp.

**Matching.** Each exercise name is matched to SirisGYM's library: exact
name first, then ignoring case, punctuation and equipment words, then the
closest by shared words. The preview shows every name and what it maps to;
you can change any of them, or let it become your own exercise.

**Saving.** One workout per day (a second session that day joins it), with
ids `import-YYYYMMDD`, so importing the same export again replaces those
days instead of doubling them. Nothing is saved on a preview.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.gym import library, service, store

LB = 0.45359237
SETS = re.compile(r"(\d+(?:\.\d+)?)\s*[x×X\*]\s*(\d+)")
EQUIP_WORDS = {"barbell", "dumbbell", "dumbbells", "db", "bb", "machine", "cable", "smith", "ez", "bar", "lever", "seated", "standing", "the", "with", "on"}
HEADERS = {
    "date": ("date", "mydate", "workout date", "logdate", "day", "start", "start time", "datetime", "timestamp", "workout_date"),
    "exercise": ("exercise", "exercise name", "exercisename", "ename", "name", "exercise_name", "movement"),
    "weight": ("weight", "weight (kg)", "weight(kg)", "kg", "weight (lbs)", "weight(lbs)", "weight (lb)", "lbs", "lb", "load"),
    "reps": ("reps", "rep", "repetitions", "rep count"),
    "set": ("set", "set #", "set number", "set_order", "setorder", "set order"),
    "seconds": ("seconds", "duration", "duration (s)", "time (s)", "time"),
    "km": ("distance", "distance (km)", "km"),
    "logs": ("logs", "log", "sets", "record", "records", "details"),
}


def _norm(h: str) -> str:
    return re.sub(r"\s+", " ", h.strip().lower().replace("_", " "))


def _columns(header: list[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    for i, h in enumerate(header):
        n = _norm(h)
        for key, names in HEADERS.items():
            if key not in found and (n in names or n.replace(" ", "") in {x.replace(" ", "") for x in names}):
                found[key] = i
    return found


def _tables(text: str) -> list[list[list[str]]]:
    """Split a file into tables at heading lines (###, ---) or blank lines."""
    blocks, cur = [], []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith(("###", "---", "===")):
            if cur:
                blocks.append(cur)
                cur = []
            continue
        cur.append(line)
    if cur:
        blocks.append(cur)
    out = []
    for b in blocks:
        try:
            dialect = csv.Sniffer().sniff(b[0], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        out.append(list(csv.reader(b, dialect)))
    return out


def parse_date(value: str) -> datetime | None:
    v = value.strip()
    if not v:
        return None
    if re.fullmatch(r"\d{9,13}", v):
        n = int(v)
        return datetime.fromtimestamp(n / 1000 if n > 10**11 else n, timezone.utc)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(v[:19], fmt)
        except ValueError:
            pass
    m = re.match(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", v)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y += 2000 if y < 100 else 0
        day, month = (a, b) if a > 12 or b <= 12 else (b, a)  # day first, unless that can't be
        try:
            return datetime(y, month, day)
        except ValueError:
            return None
    return None


def _num(v: str) -> float | None:
    try:
        return float(v.replace(",", "").strip()) if v and v.strip() else None
    except ValueError:
        return None


def read_rows(text: str, unit: str | None = None) -> list[dict[str, Any]]:
    """Every set found: {date, exercise, weight (kg), reps, seconds, km, order}. `unit` (kg/lb) overrides what the headers say."""
    rows: list[dict[str, Any]] = []
    for table in _tables(text):
        if len(table) < 2:
            continue
        cols = _columns(table[0])
        if "date" not in cols or "exercise" not in cols:
            continue
        pounds = unit == "lb" if unit else ("weight" in cols and re.search(r"\blbs?\b", table[0][cols["weight"]].lower()) is not None)
        logs = cols.get("logs")
        if logs is None and "reps" not in cols:  # a sets column under another name: find it by what's in it
            for i in range(len(table[0])):
                if i not in cols.values() and sum(bool(SETS.search(r[i])) for r in table[1:6] if len(r) > i) >= 1:
                    logs = i
                    break
        for n, r in enumerate(table[1:]):
            if len(r) <= max(cols.values()):
                continue
            when, name = parse_date(r[cols["date"]]), r[cols["exercise"]].strip()
            if not when or not name:
                continue
            factor = LB if pounds else 1.0
            if logs is not None and len(r) > logs and SETS.search(r[logs]):
                for k, (w, reps) in enumerate(SETS.findall(r[logs])):
                    rows.append({"date": when, "exercise": name, "weight": float(w) * factor or None, "reps": int(reps), "order": (n, k)})
                continue
            weight = _num(r[cols["weight"]]) if "weight" in cols else None
            rows.append({"date": when, "exercise": name, "weight": weight * factor if weight else None,
                         "reps": int(_num(r[cols["reps"]]) or 0) if "reps" in cols else None,
                         "seconds": int(_num(r[cols["seconds"]]) or 0) or None if "seconds" in cols else None,
                         "km": _num(r[cols["km"]]) if "km" in cols else None,
                         "order": (n, int(_num(r[cols["set"]]) or 0) if "set" in cols else 0)})
    return rows


def read_upload(raw: bytes, filename: str, unit: str | None = None) -> list[dict[str, Any]]:
    texts = []
    if filename.lower().endswith(".zip") or raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for info in z.infolist():
                if info.filename.lower().endswith((".csv", ".txt")) and info.file_size < 200_000_000:
                    texts.append(z.read(info).decode("utf-8-sig", errors="replace"))
    else:
        texts.append(raw.decode("utf-8-sig", errors="replace"))
    return [row for t in texts for row in read_rows(t, unit)]


def _key(name: str) -> str:
    words = [w for w in re.findall(r"[a-z0-9]+", name.lower()) if w not in EQUIP_WORDS]
    return " ".join(w[:-1] if w.endswith("s") and len(w) > 3 else w for w in words)


def match(name: str, exercises: dict[str, dict[str, Any]]) -> tuple[str | None, str]:
    """(exercise id, how sure: exact / close / guess / none)."""
    low = name.strip().lower()
    for e in exercises.values():
        if e["name"].lower() == low:
            return e["id"], "exact"
    k = _key(name)
    for e in exercises.values():
        if _key(e["name"]) == k:
            return e["id"], "close"
    want = set(k.split())
    best, score = None, 0.0
    for e in exercises.values():
        have = set(_key(e["name"]).split())
        if want and have:
            s = len(want & have) / len(want | have)
            if s > score:
                best, score = e["id"], s
    return (best, "guess") if best and score >= 0.5 else (None, "none")


def _guess_muscle(name: str) -> str:
    n = name.lower()
    for words, muscle in ((("bench", "chest", "fly", "pec", "push-up", "pushup"), "chest"), (("row", "pull", "lat", "deadlift", "chin"), "back"),
                          (("press", "shoulder", "raise", "delt"), "shoulders"), (("curl",), "biceps"), (("tricep", "extension", "pushdown", "dip"), "triceps"),
                          (("squat", "leg press", "lunge", "leg extension"), "quads"), (("leg curl", "hamstring", "romanian"), "hamstrings"),
                          (("glute", "hip"), "glutes"), (("calf",), "calves"), (("crunch", "plank", "ab", "core"), "abs"),
                          (("run", "bike", "row machine", "treadmill", "elliptical", "cardio"), "cardio")):
        if any(w in n for w in words):
            return muscle
    return "full body"


def preview(doc: store.GymDoc, rows: list[dict[str, Any]]) -> dict[str, Any]:
    exercises = service.exercises(doc)
    names = sorted({r["exercise"] for r in rows})
    counts: dict[str, int] = defaultdict(int)
    for r in rows:
        counts[r["exercise"]] += 1
    mapping = []
    for n in names:
        ex_id, how = match(n, exercises)
        mapping.append({"name": n, "sets": counts[n], "match": ex_id, "match_name": exercises[ex_id]["name"] if ex_id else None, "how": how,
                        "new_muscle": _guess_muscle(n)})
    days = sorted({r["date"].date().isoformat() for r in rows})
    existing = {s.id for s in doc.sessions}
    return {"sets": len(rows), "workouts": len(days), "from": days[0] if days else None, "to": days[-1] if days else None,
            "exercises": mapping, "replacing": sum(1 for d in days if f"import-{d.replace('-', '')}" in existing)}


def commit(doc: store.GymDoc, rows: list[dict[str, Any]], choices: dict[str, str]) -> dict[str, Any]:
    """Save it. `choices`: source name -> exercise id, or "new" to make it your own exercise; unlisted names use the match."""
    exercises = service.exercises(doc)
    target: dict[str, str] = {}
    made = 0
    for name in sorted({r["exercise"] for r in rows}):
        pick = choices.get(name)
        if pick and pick != "new" and pick in exercises:
            target[name] = pick
            continue
        auto = match(name, exercises)[0] if pick != "new" else None
        if auto:
            target[name] = auto
            continue
        mine = next((e for e in doc.exercises if e.name.lower() == name.lower()), None)
        if mine is None:
            mine = store.CustomExercise(name=name[:80], primary=_guess_muscle(name), equipment="other")
            doc.exercises.append(mine)
            exercises[mine.id] = mine.model_dump()
            made += 1
        target[name] = mine.id
    to_unit = 1 / LB if doc.settings.unit == "lb" else 1.0
    by_day: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    first_time: dict[str, datetime] = {}
    for r in sorted(rows, key=lambda x: (x["date"], x["order"])):
        d = r["date"].date().isoformat()
        by_day[d][target[r["exercise"]]].append(r)
        first_time.setdefault(d, r["date"])
    ids = set()
    for d, entries in by_day.items():
        sid = f"import-{d.replace('-', '')}"
        ids.add(sid)
        t = first_time[d]
        start = t if (t.hour or t.minute) else t.replace(hour=7)
        session = store.Session(
            id=sid, title="Imported workout", started_at=start.replace(tzinfo=None).isoformat(timespec="seconds"), ended_at=None,
            entries=[store.EntryLog(exercise=ex, sets=[store.SetLog(weight=round(s["weight"] * to_unit, 2) if s.get("weight") else None, reps=s.get("reps") or None, seconds=s.get("seconds"),
                                                                   km=s.get("km"), done=True) for s in sets][:40]) for ex, sets in entries.items()][:40],
            note="Imported")
        doc.sessions = [x for x in doc.sessions if x.id != sid]
        doc.sessions.append(session)
    doc.sessions.sort(key=lambda x: x.started_at)
    store.save(doc)
    return {"workouts": len(ids), "sets": len(rows), "new_exercises": made}
