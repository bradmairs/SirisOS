"""CPD from Engineers Australia (ADR 110).

Brad logs CPD once, in Engineers Australia's portal ("Record my CPD"). It
has no API, but it exports the record: filter by date, then export as a
spreadsheet. SirisOS reads that file. Nothing is typed in twice.

- CSV and Excel (.xlsx) are both read. Columns are found by name, loosely
  ("Date", "Start date", "Activity", "Title", "Hours", "Duration", ...),
  because the export's exact headings aren't documented and may change.
- Importing again is safe. Each activity is identified by its date, title
  and hours, so re-importing the full history (or an overlapping range)
  updates rather than duplicates.
- The 150-hour requirement has three minimums: area of practice, risk
  management, and business and management. If the export has hour columns
  for those, they're used as they are. Otherwise each activity is placed by
  keywords and marked as a guess, which Brad can correct. His correction
  survives re-imports.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from app.career import defaults
from app.career.store import CareerDocument, CpdImport, CpdRecord, save

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000


class CpdImportError(ValueError):
    pass


# Header name -> field. Checked in order; the first column that matches wins.
FIELDS: list[tuple[str, re.Pattern[str]]] = [
    ("date", re.compile(r"^(start\s*)?date|date\s*(of\s*activity|completed|started|from)|^activity\s*date|^completed|^from$", re.I)),
    ("end", re.compile(r"^(end|finish)\s*date|^to$|date\s*to", re.I)),
    ("risk", re.compile(r"risk", re.I)),
    ("business", re.compile(r"business|management\s*(hours|skills)", re.I)),
    ("area", re.compile(r"area\s*of\s*practice|technical\s*hours|engineering\s*hours|practice\s*area\s*hours", re.I)),
    ("hours", re.compile(r"hours|duration|^cpd$|^time", re.I)),
    ("type", re.compile(r"type|category|kind|format", re.I)),
    ("provider", re.compile(r"provider|organi[sz]|presenter|host|institution|delivered\s*by", re.I)),
    ("title", re.compile(r"title|^activity|topic|^name|course|event|subject|description", re.I)),
    ("notes", re.compile(r"note|outcome|learning|reflect|comment|how|relevance", re.I)),
]

RISK_WORDS = re.compile(r"\brisk|safety|hazard|\bwhs\b|\bohs\b|\bhse\b|safe\s*design|incident|fatigue", re.I)
BUSINESS_WORDS = re.compile(
    r"manage|leadership|business|financ|commercial|contract|procure|budget|negotiat|communicat|presentation"
    r"|ethic|governance|mentor|stakeholder|team|people|strategy|law\b|legal", re.I)
TECHNICAL_WORDS = re.compile(
    r"design|hydraul|water|wastewater|sewer|stormwater|drainage|pipe|pump|civil|geotech|structur|asset"
    r"|model|gis|civil\s*3d|infra|treatment|standard|code|engineering|technical|survey|road|pavement", re.I)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def _rows_from_csv(raw: bytes) -> list[list[str]]:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return [[c.strip() for c in row] for row in csv.reader(io.StringIO(text), dialect)][: MAX_ROWS + 20]


def _rows_from_xlsx(raw: bytes) -> list[list[str]]:
    from openpyxl import load_workbook

    try:
        book = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 - any unreadable workbook
        raise CpdImportError("That Excel file couldn't be read.") from exc
    best: list[list[str]] = []
    for sheet in book.worksheets:  # the sheet that looks most like a CPD table
        rows = [[_cell(v) for v in row] for _, row in zip(range(MAX_ROWS + 20), sheet.iter_rows(values_only=True))]
        if _header_index(rows) is not None and len(rows) > len(best):
            best = rows
    book.close()
    return best


def _columns(header: list[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    for i, name in enumerate(header):
        name = re.sub(r"\s+", " ", name).strip()
        if not name:
            continue
        for field, pattern in FIELDS:
            if field not in found and pattern.search(name):
                found[field] = i
                break
    return found


def _header_index(rows: list[list[str]]) -> int | None:
    """The first of the top 15 rows that names a date, an activity and hours."""
    for i, row in enumerate(rows[:15]):
        cols = _columns(row)
        if {"date", "title", "hours"} <= cols.keys() or {"title", "hours"} <= cols.keys():
            return i
    return None


def parse_date(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    value = value.split("T")[0].split(" 00:00")[0]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    try:  # Excel serial day number
        serial = float(value)
        if 20000 < serial < 80000:
            return (date(1899, 12, 30) + timedelta(days=int(serial))).isoformat()
    except ValueError:
        pass
    return None


def parse_hours(value: str) -> float:
    value = value.strip().lower()
    if not value:
        return 0.0
    m = re.match(r"^(\d+):(\d{2})$", value)  # 1:30
    if m:
        return int(m.group(1)) + int(m.group(2)) / 60
    hours = re.search(r"(\d+(?:[.,]\d+)?)\s*h", value)
    minutes = re.search(r"(\d+)\s*m", value)
    if hours or minutes:
        return (float(hours.group(1).replace(",", ".")) if hours else 0.0) + (int(minutes.group(1)) / 60 if minutes else 0.0)
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return 0.0


def record_id(day: str | None, title: str, hours: float) -> str:
    key = f"{day or ''}|{re.sub(r'[^a-z0-9]+', ' ', title.lower()).strip()}|{round(hours, 2)}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def guess_category(*texts: str) -> str:
    text = " ".join(texts)
    if RISK_WORDS.search(text):
        return "risk"
    if BUSINESS_WORDS.search(text):
        return "business"
    if TECHNICAL_WORDS.search(text):
        return "area"
    return "other"


def parse(raw: bytes, filename: str) -> list[CpdRecord]:
    if len(raw) > MAX_UPLOAD_BYTES:
        raise CpdImportError("That file is larger than 5 MB.")
    name = filename.lower()
    if name.endswith((".xlsx", ".xlsm")) or raw[:2] == b"PK":
        rows = _rows_from_xlsx(raw)
    elif name.endswith((".csv", ".txt", ".tsv")) or not name:
        rows = _rows_from_csv(raw)
    elif name.endswith(".xls"):
        raise CpdImportError("Old .xls files aren't supported: export as CSV or .xlsx instead.")
    elif name.endswith(".pdf"):
        raise CpdImportError("PDF reports can't be read reliably: export your CPD as CSV or Excel instead.")
    else:
        rows = _rows_from_csv(raw)
    at = _header_index(rows)
    if at is None:
        raise CpdImportError("Couldn't find the CPD table: expected columns for the activity and its hours (and ideally the date).")
    cols = _columns(rows[at])
    split_cols = [c for c in ("area", "risk", "business") if c in cols]

    def get(row: list[str], field: str) -> str:
        i = cols.get(field)
        return row[i] if i is not None and i < len(row) else ""

    records: list[CpdRecord] = []
    for row in rows[at + 1:]:
        title = get(row, "title")
        if not title or re.match(r"^(total|sub-?total)\b", title, re.I):
            continue
        hours = parse_hours(get(row, "hours"))
        split = {c: parse_hours(get(row, c)) for c in split_cols}
        split = {c: h for c, h in split.items() if h > 0}
        if not hours and split:
            hours = sum(split.values())
        if hours <= 0:
            continue
        day = parse_date(get(row, "date")) or parse_date(get(row, "end"))
        kind, provider, notes = get(row, "type"), get(row, "provider"), get(row, "notes")
        if split_cols:
            rest = round(hours - sum(split.values()), 2)
            if rest > 0:
                split["other"] = rest
            basis = "export"
        else:
            split = {guess_category(title, kind, notes, provider): hours}
            basis = "guess"
        records.append(CpdRecord(id=record_id(day, title, hours), date=day, title=title[:300], provider=provider[:200],
                                 type=kind[:120], hours=round(hours, 2), split=split, basis=basis, notes=notes[:1000]))
    if not records:
        raise CpdImportError("The file has a CPD table but no activities with hours in it.")
    return records


def merge(doc: CareerDocument, records: Iterable[CpdRecord], filename: str) -> tuple[CareerDocument, CpdImport]:
    """Upsert by activity id: a re-export of the same history changes nothing."""
    existing = {r.id: r for r in doc.cpd.records}
    added = updated = unchanged = 0
    for record in records:
        old = existing.get(record.id)
        if old is None:
            added += 1
        elif old.model_dump() == record.model_dump():
            unchanged += 1
        else:
            updated += 1
        existing[record.id] = record
    summary = CpdImport(at=datetime.now(timezone.utc).isoformat(timespec="seconds"), filename=filename[:200],
                        added=added, updated=updated, unchanged=unchanged)
    cpd = doc.cpd.model_copy(update={
        "records": sorted(existing.values(), key=lambda r: (r.date or "", r.title), reverse=True),
        "imports": [summary, *doc.cpd.imports][:20],
    })
    return save(doc.model_copy(update={"cpd": cpd})), summary


def split_for(record: CpdRecord, overrides: dict[str, str]) -> tuple[dict[str, float], str]:
    if record.id in overrides:
        return {overrides[record.id]: record.hours}, "you"
    return record.split or {"other": record.hours}, record.basis


def _years_before(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # 29 February
        return day.replace(year=day.year - years, day=28)


def summary(doc: CareerDocument, today: date | None = None) -> dict[str, Any]:
    """The rolling three-year window Engineers Australia counts, by category,
    against the 150-hour total and the three minimums."""
    today = today or date.today()
    req = defaults.CPD_REQUIREMENT
    start = _years_before(today, req["years"])
    drops_by = _years_before(today + timedelta(days=90), req["years"])
    totals = {c: 0.0 for c in defaults.CPD_CATEGORIES}
    expiring = 0.0
    by_year: dict[str, float] = {}
    guessed = 0
    for r in doc.cpd.records:
        if not r.date:
            continue
        d = date.fromisoformat(r.date)
        if not (start < d <= today):
            continue
        split, basis = split_for(r, doc.cpd.overrides)
        for c, h in split.items():
            totals[c if c in totals else "other"] += h
        by_year[str(d.year)] = by_year.get(str(d.year), 0.0) + r.hours
        guessed += basis == "guess"
        # Drops out of the window within 90 days.
        if d <= drops_by:
            expiring += r.hours
    total = sum(totals.values())
    minimums = [
        {"category": c, "label": defaults.CPD_CATEGORIES[c], "hours": round(totals[c], 1), "minimum": m,
         "short": round(max(0.0, m - totals[c]), 1)}
        for c, m in req["minimums"].items()
    ]
    last = doc.cpd.imports[0] if doc.cpd.imports else None
    return {
        "window": {"from": start.isoformat(), "to": today.isoformat(), "years": req["years"]},
        "total": round(total, 1),
        "required": req["total"],
        "short": round(max(0.0, req["total"] - total), 1),
        "met": total >= req["total"] and all(m["short"] == 0 for m in minimums),
        "categories": {c: round(h, 1) for c, h in totals.items()},
        "minimums": minimums,
        "by_year": dict(sorted(by_year.items())),
        "expiring_90_days": round(expiring, 1),
        "guessed": guessed,
        "records": len(doc.cpd.records),
        "last_import": last.model_dump() if last else None,
        "latest_activity": max((r.date for r in doc.cpd.records if r.date), default=None),
    }
