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
saved in kilograms (SirisGym is SI only). Dates can be
2024-03-05, 05/03/2024 (day first; month first when the day can't be), or
a Unix timestamp.

**Matching.** Each exercise name is matched to SirisGym's library: exact
name first, then ignoring case, punctuation and equipment words, then the
closest by shared words. The preview shows every name and what it maps to;
you can change any of them, or let it become your own exercise.

**JEFIT's full export (7.3).** The file JEFIT emails (### SETTING, ###
ROUTINES, ### WORKOUT SESSIONS, ### EXERCISE LOGS, ### EXERCISE SET LOGS …)
is read by its sections, not as generic tables: only EXERCISE LOGS are
workouts (ROUTINES hold planned sets and RECORDS bests, and reading them as
workouts added exercises you never did, and sets twice). Each log's own date
(`mydate`, the local day) is the day; its TIMESTAMP is UTC and isn't used.
Weights come from the log's sets (kg or lb by the export's unit setting);
each set's time comes from EXERCISE SET LOGS when it has one per set, so a
recent workout can be lined up with the Watch. A log repeated word for word
on a day is kept once.

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
        if not ({"weight", "reps", "logs", "seconds", "km"} & set(cols)) and not any(
                SETS.search(c) for r in table[1:6] for c in r):
            continue  # 6.95: a table of workout sessions (a date and a name, no sets) isn't exercises
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
            if when.tzinfo is not None:  # 6.96: a timestamp is UTC; the workout happened at local time
                from app.tasks.service import zone

                when = when.astimezone(zone()).replace(tzinfo=None)
            factor = LB if pounds else 1.0
            if logs is not None and len(r) > logs and SETS.search(r[logs]):
                for k, (w, reps) in enumerate(SETS.findall(r[logs])):
                    rows.append({"date": when, "exercise": name, "weight": float(w) * factor or None, "reps": int(reps), "order": (n, k + 1)})
                continue
            weight = _num(r[cols["weight"]]) if "weight" in cols else None
            reps = int(_num(r[cols["reps"]]) or 0) if "reps" in cols else 0
            secs = int(_num(r[cols["seconds"]]) or 0) if "seconds" in cols else 0
            dist = _num(r[cols["km"]]) if "km" in cols else None
            if not (weight or reps or secs or dist):
                continue  # 6.95: a row with no set in it (a session's name, a blank log) adds nothing
            rows.append({"date": when, "exercise": name, "weight": weight * factor if weight else None,
                         "reps": int(_num(r[cols["reps"]]) or 0) if "reps" in cols else None,
                         "seconds": int(_num(r[cols["seconds"]]) or 0) or None if "seconds" in cols else None,
                         "km": _num(r[cols["km"]]) if "km" in cols else None,
                         "order": (n, int(_num(r[cols["set"]]) or 0) if "set" in cols else 0)})
    return dedupe(rows)


def dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The same set twice (6.95): an export with overlapping files, or a log line
    repeated, gives identical rows. Sets are told apart by their number in the
    set (or in the logged line), so three real sets of 100x5 stay three; rows
    with no set number can't be told apart and are all kept."""
    seen: set[tuple] = set()
    out = []
    for r in rows:
        order = r.get("order") or (0, 0)
        if order[1]:
            key = (r["date"].isoformat(), r["exercise"].strip().lower(), order[1], r.get("weight"), r.get("reps"), r.get("seconds"), r.get("km"))
            if key in seen:
                continue
            seen.add(key)
        out.append(r)
    return out


def logged_days(doc: store.GymDoc) -> set[str]:
    """Days with a workout logged in SirisGym itself (not imported)."""
    return {service.day_of(s.started_at) for s in doc.sessions if not s.id.startswith("import-")}


SECTION = re.compile(r"^###\s+(.+?)\s+#{3,}\s*$")


def jefit_sections(text: str) -> dict[str, list[dict[str, str]]] | None:
    """JEFIT's full export split into its sections, each a list of rows by column name; None for any other file."""
    sections: dict[str, list[str]] = {}
    cur: str | None = None
    for line in text.splitlines():
        m = SECTION.match(line.strip())
        if m:
            cur = m.group(1).strip().upper()
            sections[cur] = []
            continue
        if line.startswith("####"):
            cur = None
            continue
        if cur is not None and line.strip():
            sections[cur].append(line)
    if "EXERCISE LOGS" not in sections:
        return None
    return {k: list(csv.DictReader(v)) for k, v in sections.items() if v}


def read_jefit(sections: dict[str, list[dict[str, str]]], unit: str | None = None) -> list[dict[str, Any]]:
    """Every set in JEFIT's EXERCISE LOGS (7.3): {date (local day and start), exercise, weight (kg), reps, order, at, start, end, source}."""
    from app.tasks.service import zone

    setting = (sections.get("SETTING") or [{}])[0]
    pounds = unit == "lb" if unit in ("kg", "lb") else "lb" in str(setting.get("mass") or "").lower()
    factor = LB if pounds else 1.0
    tz = zone()
    sessions = {r.get("_id"): r for r in sections.get("WORKOUT SESSIONS") or []}
    set_logs: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in sections.get("EXERCISE SET LOGS") or []:
        set_logs[r.get("exercise_log_id") or ""].append(r)

    def local(epoch: Any) -> datetime | None:
        try:
            n = int(float(epoch))
        except (TypeError, ValueError):
            return None
        return datetime.fromtimestamp(n, timezone.utc).astimezone(tz).replace(tzinfo=None) if n > 10**8 else None

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for n, log in enumerate(sections.get("EXERCISE LOGS") or []):
        name = (log.get("ename") or "").strip()
        day = (log.get("mydate") or "").strip()
        sets = SETS.findall(log.get("logs") or "")
        if not name or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) or not sets:
            continue
        key = (day, name.lower(), (log.get("logs") or "").strip())
        if key in seen:
            continue  # the same log twice on a day
        seen.add(key)
        sess = sessions.get(log.get("belongsession") or "") or {}
        start, end = local(sess.get("starttime")), local(sess.get("endtime"))
        if start is None or start.date().isoformat() != day:
            start, end = None, None  # a session synced on another day: its clock isn't this workout's
        timed = sorted(set_logs.get(log.get("_id") or "", []), key=lambda r: int(r.get("set_index") or 0))
        times = [local(r.get("log_time")) for r in timed] if len(timed) == len(sets) else [None] * len(sets)
        times = [t if t is not None and t.date().isoformat() == day else None for t in times]
        when = start or next((t for t in times if t), None) or datetime.fromisoformat(f"{day}T00:00:00")
        for k, (w, reps) in enumerate(sets):
            weight = round(float(w) * factor, 2)
            r = int(reps)
            if not weight and not r:
                continue  # 0x0: an empty set
            at = times[k]
            rows.append({"date": when, "exercise": name, "weight": weight or None, "reps": r or None, "order": (n, k + 1),
                         "at": at.replace(tzinfo=tz).astimezone(timezone.utc).isoformat(timespec="seconds") if at else None,
                         "start": start, "end": end, "source": "jefit"})
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
    out = []
    for t in texts:
        sections = jefit_sections(t)
        out += read_jefit(sections, unit) if sections else read_rows(t, unit)
    return out


EQUIPMENT_IN_NAME = (("smith", "smith"), ("ez bar", "ez bar"), ("ez-bar", "ez bar"), ("trap bar", "trap bar"), ("kettlebell", "kettlebell"),
                     ("dumbbell", "dumbbell"), ("barbell", "barbell"), ("cable", "cable"), ("machine", "machine"), ("lever", "machine"),
                     ("band", "band"), ("bodyweight", "bodyweight"))


def equipment_of(name: str) -> str | None:
    """The equipment a name says (7.3): "Machine Tricep Extension" is a machine, "Dip" says none."""
    n = name.lower()
    return next((e for word, e in EQUIPMENT_IN_NAME if word in n), None)


POSTURES = ("seated", "standing", "lying", "incline", "decline")


def _same_kit(name: str, ex: dict[str, Any]) -> bool:
    """Same equipment (when the name says), and no clash of position: seated isn't standing, incline isn't decline."""
    said = equipment_of(name)
    if not (said is None or said == ex.get("equipment") or (said == "ez bar" and ex.get("equipment") == "barbell")):
        return False
    a = {p for p in POSTURES if p in name.lower()}
    b = {p for p in POSTURES if p in str(ex.get("name", "")).lower()}
    return not (a and b and not a & b)


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
    # 7.3: a close match or a guess must use the same equipment the name says ("Cable Upright Row" isn't the barbell one).
    for e in exercises.values():
        if _key(e["name"]) == k and _same_kit(name, e):
            return e["id"], "close"
    want = set(k.split())
    best, score = None, 0.0
    for e in exercises.values():
        if not _same_kit(name, e):
            continue
        have = set(_key(e["name"]).split())
        if want and have:
            s = len(want & have) / len(want | have)
            if s > score:
                best, score = e["id"], s
    # 7.3: a guess needs two thirds of the words in common ("Cable Upright Row" isn't "Seated Cable Row").
    return (best, "guess") if best and score >= 0.67 else (None, "none")


MUSCLE_WORDS = (  # most specific first; whole words only (7.3: "machine" isn't a "chin")
    (r"leg curls?|hamstring|romanian|rdl|nordic", "hamstrings"), (r"leg press|leg extensions?|squats?|lunges?|step ?ups?|hack", "quads"),
    (r"calf|calves", "calves"), (r"glutes?|hip thrusts?|hip|kickbacks?", "glutes"), (r"(hanging |lying )?(leg|knee) raises?|hanging", "abs"),
    (r"triceps?|skull ?crushers?|push ?downs?|dips?|close ?grip", "triceps"), (r"curls?|biceps?", "biceps"),
    (r"bench|chest|fly|flyes|flies|pec|push ?ups?|crossovers?", "chest"),
    (r"shoulders?|delts?|raises?|upright rows?|overhead press|military|arnold|shrugs?|face ?pulls?", "shoulders"),
    (r"rows?|pull ?downs?|pull ?ups?|chin ?ups?|lats?|deadlifts?|pullovers?|back extensions?", "back"),
    (r"wrist|forearms?|grip", "forearms"), (r"crunch(es)?|planks?|abs?|core|sit ?ups?|leg raises?|russian", "abs"),
    (r"run|running|bike|cycling|row(ing)? machine|rower|treadmill|elliptical|cardio|stair|walk(ing)?|ski ?erg|jump rope", "cardio"),
)


def _guess_muscle(name: str) -> str:
    n = name.lower()
    for words, muscle in MUSCLE_WORDS:
        if re.search(rf"\b(?:{words})\b", n):
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
    live = sorted(set(days) & logged_days(doc))
    return {"sets": len(rows), "workouts": len(days), "from": days[0] if days else None, "to": days[-1] if days else None,
            "exercises": mapping, "replacing": sum(1 for d in days if f"import-{d.replace('-', '')}" in existing),
            "already_logged": live, "jefit": any(r.get("source") == "jefit" for r in rows), "removing": len(_stale(doc, set(days)) if any(r.get("source") == "jefit" for r in rows) else [])}


def _stale(doc: store.GymDoc, days: set[str]) -> list[store.Session]:
    """Imported days in the export's span that it doesn't have (7.3): what an older, wrong import left behind."""
    if not days:
        return []
    lo, hi = min(days), max(days)
    keep = {f"import-{d.replace('-', '')}" for d in days}
    return [x for x in doc.sessions if x.id.startswith("import-") and x.id not in keep and lo <= service.day_of(x.started_at) <= hi]


def commit(doc: store.GymDoc, rows: list[dict[str, Any]], choices: dict[str, str], skip_logged: bool = True) -> dict[str, Any]:
    """Save it. `choices`: source name -> exercise id, or "new" to make it your own exercise; unlisted names use the match.
    6.95: days already logged in SirisGym itself are left out (skip_logged), so a workout you logged live
    and in JEFIT isn't there twice."""
    skipped = sorted({r["date"].date().isoformat() for r in rows} & logged_days(doc)) if skip_logged else []
    rows = [r for r in rows if r["date"].date().isoformat() not in skipped]
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
            kit = equipment_of(name)
            kit = "barbell" if kit == "ez bar" else kit
            mine = store.CustomExercise(name=name[:80], primary=_guess_muscle(name), equipment=kit if kit in library.EQUIPMENT else "other")
            doc.exercises.append(mine)
            exercises[mine.id] = mine.model_dump()
            made += 1
        target[name] = mine.id
    by_day: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    first_time: dict[str, datetime] = {}
    last_time: dict[str, datetime] = {}
    for r in sorted(rows, key=lambda x: (x["date"], x["order"])):
        d = r["date"].date().isoformat()
        by_day[d][target[r["exercise"]]].append(r)
        first_time.setdefault(d, r["date"])
        if r.get("end") and (d not in last_time or r["end"] > last_time[d]):
            last_time[d] = r["end"]
    if any(r.get("source") == "jefit" for r in rows) and by_day:
        # 7.3: JEFIT's full export is the whole history, so an imported day it doesn't have (an older import that read the
        # routines as workouts, or put a workout on the wrong day) goes. Workouts logged in SirisGym are never touched.
        stale = _stale(doc, set(by_day))
        if stale:
            store.backup("before-jefit")
            doc.sessions = [x for x in doc.sessions if x not in stale]
    else:
        stale = []
    ids = set()
    for d, entries in by_day.items():
        sid = f"import-{d.replace('-', '')}"
        ids.add(sid)
        t = first_time[d]
        start = t if (t.hour or t.minute) else t.replace(hour=7)
        def set_of(ex: str, s: dict[str, Any]) -> store.SetLog:
            if exercises.get(ex, {}).get("kind") == "time" and not s.get("weight") and s.get("reps") and not s.get("seconds"):
                return store.SetLog(seconds=s["reps"], done=True, at=s.get("at"))  # JEFIT writes a timed set (a plank) as 0 x seconds
            return store.SetLog(weight=round(s["weight"], 2) if s.get("weight") else None, reps=s.get("reps") or None, seconds=s.get("seconds"),
                                km=s.get("km"), done=True, at=s.get("at"))

        logged = [store.EntryLog(exercise=ex, sets=[set_of(ex, s) for s in sets]) for ex, sets in entries.items()]
        was = next((x for x in doc.sessions if x.id == sid), None)
        end = last_time.get(d)
        session = store.Session(id=sid, title=service.trained_title(doc, logged), started_at=start.replace(tzinfo=None).isoformat(timespec="seconds"),
                                ended_at=end.isoformat(timespec="seconds") if end and end > start else None,
                                entries=logged, note="Imported", review=was.review if was else "")  # what you decided about the day stays
        doc.sessions = [x for x in doc.sessions if x.id != sid]
        doc.sessions.append(session)
    doc.sessions.sort(key=lambda x: x.started_at)
    tidied = 0
    if any(r.get("source") == "jefit" for r in rows):
        before = len(doc.exercises)
        store.clean_empty(doc)  # exercises only the old import used (routine names read as workouts) go too
        tidied = before - len(doc.exercises)
    store.save(doc)
    extra = {"removed": len(stale), "tidied": tidied} if any(r.get("source") == "jefit" for r in rows) else {}
    return {**extra, "workouts": len(ids), "sets": len(rows), "new_exercises": made, "skipped_days": skipped}
