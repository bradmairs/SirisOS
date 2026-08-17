from datetime import date, timedelta
from pathlib import Path

import pytest

from app.services.gym_service import GymService

# muscle_group_workload() aggregates by a trailing date window across all
# exercises, not scoped by exercise name, so it needs a genuinely isolated
# database per test -- same reasoning as TrainingLoadService's tests.


def _service(tmp_path: Path, monkeypatch) -> GymService:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/muscle_groups.db")
    service = GymService()
    service.initialise()
    return service


def test_new_exercise_is_untagged_by_default(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    service.create_workout(
        workout_date=date(2026, 1, 1), name="Push", notes=None,
        sets=[{"exercise": "Bench Press", "weight_kg": 80, "reps": 8, "rir": 2}],
    )

    summary = service.get_exercise("Bench Press")

    assert summary.muscle_group is None
    assert service.list_untagged_exercises() == ["Bench Press"]


def test_tag_exercise_applies_to_existing_and_future_sets(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    service.create_workout(
        workout_date=date(2026, 1, 1), name="Push", notes=None,
        sets=[{"exercise": "Bench Press", "weight_kg": 80, "reps": 8, "rir": 2}],
    )

    service.tag_exercise("Bench Press", "chest")

    assert service.get_exercise("Bench Press").muscle_group == "chest"
    assert service.list_untagged_exercises() == []

    service.create_workout(
        workout_date=date(2026, 1, 8), name="Push", notes=None,
        sets=[{"exercise": "bench press", "weight_kg": 82.5, "reps": 8, "rir": 2}],
    )
    assert service.get_exercise("Bench Press").muscle_group == "chest"


def test_tag_exercise_is_case_insensitive_and_upserts(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    service.create_workout(
        workout_date=date(2026, 1, 1), name="Legs", notes=None,
        sets=[{"exercise": "Squat", "weight_kg": 100, "reps": 5, "rir": 2}],
    )

    service.tag_exercise("SQUAT", "legs")
    assert service.get_exercise("Squat").muscle_group == "legs"

    # Retagging the same exercise replaces the tag rather than erroring.
    service.tag_exercise("squat", "core")
    assert service.get_exercise("Squat").muscle_group == "core"


def test_tag_exercise_rejects_unknown_muscle_group(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)

    with pytest.raises(ValueError):
        service.tag_exercise("Bench Press", "not_a_real_group")


def test_muscle_group_workload_sums_tagged_exercises_only(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    today = date.today()
    service.create_workout(
        workout_date=today, name="Push", notes=None,
        sets=[
            {"exercise": "Bench Press", "weight_kg": 80, "reps": 8, "rir": 2},
            {"exercise": "Overhead Press", "weight_kg": 40, "reps": 8, "rir": 2},
            {"exercise": "Unknown Machine", "weight_kg": 20, "reps": 10, "rir": 2},
        ],
    )
    service.tag_exercise("Bench Press", "chest")
    service.tag_exercise("Overhead Press", "shoulders")
    # "Unknown Machine" deliberately left untagged.

    workload = service.muscle_group_workload(days=7)
    by_group = {item.muscle_group: item for item in workload}

    assert by_group["chest"].total_volume_kg == 640.0
    assert by_group["chest"].set_count == 1
    assert by_group["chest"].exercise_count == 1
    assert by_group["shoulders"].total_volume_kg == 320.0
    # Every known group is present even with zero workload, and untagged
    # sets don't silently attribute to any group.
    assert by_group["legs"].total_volume_kg == 0.0
    assert sum(item.set_count for item in workload) == 2


def test_muscle_group_workload_excludes_sets_outside_the_window(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    today = date.today()
    service.create_workout(
        workout_date=today - timedelta(days=30), name="Push", notes=None,
        sets=[{"exercise": "Bench Press", "weight_kg": 80, "reps": 8, "rir": 2}],
    )
    service.tag_exercise("Bench Press", "chest")

    workload = service.muscle_group_workload(days=7)
    by_group = {item.muscle_group: item for item in workload}

    assert by_group["chest"].total_volume_kg == 0.0
    assert by_group["chest"].set_count == 0


def test_fatigue_is_zero_for_a_never_trained_group(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)

    fatigue = {item.muscle_group: item for item in service.muscle_group_fatigue()}

    assert fatigue["legs"].fatigue_fraction == 0.0
    assert fatigue["legs"].last_trained_date is None
    assert fatigue["legs"].days_since_trained is None
    assert fatigue["legs"].ready_at is None


def test_fatigue_is_maximal_the_day_a_group_is_first_trained(tmp_path: Path, monkeypatch) -> None:
    # No baseline exists yet, so a first-ever session has nothing to compare
    # against -- treated as fresh/maximal rather than silently zero, since a
    # baseline of zero would otherwise divide out to "not fatigued at all".
    service = _service(tmp_path, monkeypatch)
    today = date.today()
    service.create_workout(
        workout_date=today, name="Push", notes=None,
        sets=[{"exercise": "Bench Press", "weight_kg": 80, "reps": 8, "rir": 2}],
    )
    service.tag_exercise("Bench Press", "chest")

    fatigue = {item.muscle_group: item for item in service.muscle_group_fatigue()}

    assert fatigue["chest"].fatigue_fraction == 1.0
    assert fatigue["chest"].last_trained_date == today
    assert fatigue["chest"].days_since_trained == 0
    assert fatigue["chest"].ready_at == today + timedelta(days=3)


def test_fatigue_decays_toward_zero_as_recovery_window_elapses(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    today = date.today()
    # Establish a baseline: several past sessions at 400 kg each, well
    # outside the 3-day recovery window, so they set the "typical session"
    # reference without themselves counting as current fatigue.
    for weeks_ago in (2, 3, 4):
        service.create_workout(
            workout_date=today - timedelta(weeks=weeks_ago), name="Push", notes=None,
            sets=[{"exercise": "Bench Press", "weight_kg": 100, "reps": 4, "rir": 2}],
        )
    service.tag_exercise("Bench Press", "chest")
    # One more session exactly at the recovery window boundary.
    service.create_workout(
        workout_date=today - timedelta(days=3), name="Push", notes=None,
        sets=[{"exercise": "Bench Press", "weight_kg": 100, "reps": 4, "rir": 2}],
    )

    fatigue = {item.muscle_group: item for item in service.muscle_group_fatigue()}

    # A session exactly at the recovery-window boundary has fully decayed.
    assert fatigue["chest"].fatigue_fraction == 0.0
    assert fatigue["chest"].last_trained_date == today - timedelta(days=3)
    assert fatigue["chest"].days_since_trained == 3


def test_fatigue_is_partial_partway_through_the_recovery_window(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    today = date.today()
    for weeks_ago in (2, 3, 4):
        service.create_workout(
            workout_date=today - timedelta(weeks=weeks_ago), name="Push", notes=None,
            sets=[{"exercise": "Bench Press", "weight_kg": 100, "reps": 4, "rir": 2}],
        )
    service.tag_exercise("Bench Press", "chest")
    # Trained yesterday: 1 of 3 recovery-window days elapsed.
    service.create_workout(
        workout_date=today - timedelta(days=1), name="Push", notes=None,
        sets=[{"exercise": "Bench Press", "weight_kg": 100, "reps": 4, "rir": 2}],
    )

    fatigue = {item.muscle_group: item for item in service.muscle_group_fatigue()}

    assert fatigue["chest"].fatigue_fraction == pytest.approx(2 / 3, abs=0.01)
    assert fatigue["chest"].days_since_trained == 1
    assert fatigue["chest"].ready_at == today + timedelta(days=2)
