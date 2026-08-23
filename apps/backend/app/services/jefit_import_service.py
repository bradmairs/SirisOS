from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, datetime

from app.services.gym_service import GymService

_SECTION_HEADER_RE = re.compile(r"^### (.+?) #+\s*$")


@dataclass(frozen=True)
class JefitParsedSet:
    weight_kg: float
    reps: int


@dataclass(frozen=True)
class JefitParsedExercise:
    name: str
    sets: list[JefitParsedSet]


@dataclass(frozen=True)
class JefitParsedSession:
    external_id: str
    workout_date: date
    exercises: list[JefitParsedExercise]


@dataclass(frozen=True)
class JefitImportResult:
    sessions_imported: int
    sessions_skipped: int
    sets_imported: int
    earliest_date: date | None
    latest_date: date | None
    errors: list[str]


def parse_jefit_export(text: str) -> list[JefitParsedSession]:
    """Parses the EXERCISE LOGS section of a JEFIT full-database CSV export
    ("Backup & Export") into session groups keyed by JEFIT's own
    `belongsession` id.

    Only the EXERCISE LOGS section is used, not the separate WORKOUT
    SESSIONS or EXERCISE SET LOGS tables -- EXERCISE LOGS' `logs` field
    (e.g. "35x10,45x10,40x10", weight x reps per set) is already in the
    account's own display unit (confirmed against the kg-metric test
    account this was built against: that same row's `record` field is an
    Epley e1RM computed directly from `logs`' best set, with no unit
    conversion involved). EXERCISE SET LOGS' `weight_lbs` column, by
    contrast, is always in lbs regardless of account unit and would need
    converting -- using `logs` instead avoids that conversion and the extra
    join entirely. JEFIT does not track RIR, so every imported set has
    rir=None, same as SirisOS's own manual logging when RIR is left blank.
    """
    section_lines = _extract_section(text, "EXERCISE LOGS")
    if not section_lines:
        return []

    reader = csv.DictReader(section_lines)
    sessions: dict[str, dict[str, object]] = {}
    order: list[str] = []

    for row in reader:
        session_id = (row.get("belongsession") or "").strip()
        raw_date = (row.get("mydate") or "").strip()
        exercise_name = (row.get("ename") or "").strip()
        logs = (row.get("logs") or "").strip()
        if not session_id or not raw_date or not exercise_name or not logs:
            continue
        try:
            workout_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            continue

        sets = _parse_logs(logs)
        if not sets:
            continue

        if session_id not in sessions:
            sessions[session_id] = {"workout_date": workout_date, "exercises": []}
            order.append(session_id)
        # A session's exercises should all share one date; if they ever
        # disagree, keep the earliest rather than picking arbitrarily.
        if workout_date < sessions[session_id]["workout_date"]:  # type: ignore[operator]
            sessions[session_id]["workout_date"] = workout_date
        sessions[session_id]["exercises"].append(JefitParsedExercise(name=exercise_name, sets=sets))  # type: ignore[union-attr]

    return [
        JefitParsedSession(
            external_id=session_id,
            workout_date=sessions[session_id]["workout_date"],  # type: ignore[arg-type]
            exercises=sessions[session_id]["exercises"],  # type: ignore[arg-type]
        )
        for session_id in order
    ]


def _extract_section(text: str, name: str) -> list[str]:
    lines = text.splitlines()
    header_pattern = re.compile(rf"^### {re.escape(name)} #+\s*$")
    start = None
    for index, line in enumerate(lines):
        if header_pattern.match(line.strip()):
            start = index
            break
    if start is None:
        return []
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if _SECTION_HEADER_RE.match(lines[index].strip()):
            end = index
            break
    body = lines[start + 1 : end]
    return [line for line in body if line.strip() and not line.strip().startswith("#")]


def _parse_logs(logs: str) -> list[JefitParsedSet]:
    sets: list[JefitParsedSet] = []
    for part in logs.split(","):
        part = part.strip()
        if not part or "x" not in part:
            continue
        weight_str, _, reps_str = part.partition("x")
        try:
            weight_kg = round(float(weight_str), 1)
            reps = round(float(reps_str))
        except ValueError:
            continue
        if weight_kg <= 0 or reps <= 0:
            continue
        sets.append(JefitParsedSet(weight_kg=weight_kg, reps=reps))
    return sets


class JefitImportService:
    """Imports a JEFIT export into the exact same gym_workouts/
    gym_workout_sets tables manual logging already uses, so Progressive
    Overload, PRs, Strength Score, Muscle Map and Training Level all work on
    imported data unchanged -- no separate JEFIT-specific analytics path.
    """

    def __init__(self, gym_service: GymService | None = None) -> None:
        self._gym_service = gym_service or GymService()

    def import_export(self, text: str) -> JefitImportResult:
        sessions = sorted(parse_jefit_export(text), key=lambda item: item.workout_date)
        if not sessions:
            return JefitImportResult(
                sessions_imported=0,
                sessions_skipped=0,
                sets_imported=0,
                earliest_date=None,
                latest_date=None,
                errors=["No exercise log sessions found in this export."],
            )

        already_imported = self._gym_service.existing_external_ids("jefit")
        skipped = 0
        sets_imported = 0
        dates: list[date] = []
        errors: list[str] = []
        entries: list[dict] = []

        for parsed in sessions:
            if parsed.external_id in already_imported:
                skipped += 1
                continue
            sets_payload = [
                {"exercise": exercise.name, "weight_kg": item.weight_kg, "reps": item.reps, "rir": None}
                for exercise in parsed.exercises
                for item in exercise.sets
            ]
            if not sets_payload:
                continue
            entries.append(
                {
                    "workout_date": parsed.workout_date,
                    "name": "JEFIT import",
                    "notes": None,
                    "sets": sets_payload,
                    "source": "jefit",
                    "external_id": parsed.external_id,
                }
            )
            sets_imported += len(sets_payload)
            dates.append(parsed.workout_date)

        try:
            imported = self._gym_service.bulk_import_workouts(entries)
        except Exception as exc:  # noqa: BLE001 -- a store-level failure must be reported, not crash the request
            errors.append(f"Import failed: {exc}")
            imported = 0
            sets_imported = 0
            dates = []

        return JefitImportResult(
            sessions_imported=imported,
            sessions_skipped=skipped,
            sets_imported=sets_imported,
            earliest_date=min(dates) if dates else None,
            latest_date=max(dates) if dates else None,
            errors=errors,
        )
