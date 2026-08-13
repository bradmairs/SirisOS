from datetime import date, timedelta
import random
import uuid

from app.services.ask_siris_service import AskSirisService
from app.services.coach_service import CoachService
from app.services.gym_service import GymService
from app.services.running_service import RunningService
from app.services.training_load_service import TrainingLoadService

# Same isolation approach as test_training_load.py / test_coach.py: a random
# far-future year per test (own disjoint range) plus unique exercise names,
# since AskSirisService matches exercises by substring against every logged
# exercise name in the shared dev/test database.


def _random_year() -> int:
    return random.randint(6000, 9999)


def _unique_exercise(label: str) -> str:
    return f"{label} {uuid.uuid4().hex[:8]}"


def _monday(year: int, week_offset: int) -> date:
    anchor = date(year, 3, 1)
    anchor -= timedelta(days=anchor.weekday())
    return anchor + timedelta(weeks=week_offset)


def _services() -> tuple[RunningService, GymService, AskSirisService]:
    running = RunningService()
    running.initialise()
    gym = GymService()
    gym.initialise()
    coach = CoachService(
        running_service=running,
        gym_service=gym,
        training_load_service=TrainingLoadService(running_service=running, gym_service=gym),
    )
    ask_siris = AskSirisService(running_service=running, gym_service=gym, coach_service=coach)
    return running, gym, ask_siris


def test_unrecognised_question_returns_suggestions() -> None:
    _, _, ask_siris = _services()

    result = ask_siris.answer("What's the weather like today?")

    assert result.understood is False
    assert result.suggestions


def test_last_time_at_weight_found() -> None:
    _, gym, ask_siris = _services()
    exercise = _unique_exercise("Deadlift")
    today = _monday(_random_year(), 0)

    gym.create_workout(
        workout_date=today - timedelta(weeks=1),
        name="Pull",
        notes=None,
        sets=[{"exercise": exercise, "weight_kg": 140, "reps": 3, "rir": 1}],
    )

    result = ask_siris.answer(f"When did I last {exercise} 140kg?", today=today)

    assert result.understood is True
    assert (today - timedelta(weeks=1)).isoformat() in result.answer


def test_last_time_at_weight_not_yet_reached() -> None:
    _, gym, ask_siris = _services()
    exercise = _unique_exercise("Squat")
    today = _monday(_random_year(), 0)

    gym.create_workout(
        workout_date=today,
        name="Legs",
        notes=None,
        sets=[{"exercise": exercise, "weight_kg": 100, "reps": 5, "rir": 2}],
    )

    result = ask_siris.answer(f"When did I last {exercise} 140kg?", today=today)

    assert result.understood is True
    assert "haven't lifted" in result.answer


def test_exercise_progress_since_date() -> None:
    _, gym, ask_siris = _services()
    exercise = _unique_exercise("Bench Press")
    year = _random_year()
    since = _monday(year, 4)
    today = _monday(year, 8)

    gym.create_workout(
        workout_date=since - timedelta(weeks=1),
        name="Push",
        notes=None,
        sets=[{"exercise": exercise, "weight_kg": 80, "reps": 8, "rir": 2}],
    )
    gym.create_workout(
        workout_date=today,
        name="Push",
        notes=None,
        sets=[{"exercise": exercise, "weight_kg": 90, "reps": 8, "rir": 2}],
    )

    result = ask_siris.answer(
        f"How much has my {exercise} improved since {since.isoformat()}?", today=today
    )

    assert result.understood is True
    assert "up" in result.answer


def test_most_improved_exercise() -> None:
    _, gym, ask_siris = _services()
    improved = _unique_exercise("Overhead Press")
    steady = _unique_exercise("Bicep Curl")
    today = _monday(_random_year(), 0)
    old = today - timedelta(days=120)

    gym.create_workout(
        workout_date=old, name="Push", notes=None,
        sets=[{"exercise": improved, "weight_kg": 40, "reps": 8, "rir": 2}],
    )
    gym.create_workout(
        workout_date=today, name="Push", notes=None,
        sets=[{"exercise": improved, "weight_kg": 55, "reps": 8, "rir": 2}],
    )
    gym.create_workout(
        workout_date=old, name="Push", notes=None,
        sets=[{"exercise": steady, "weight_kg": 20, "reps": 10, "rir": 2}],
    )
    gym.create_workout(
        workout_date=today, name="Push", notes=None,
        sets=[{"exercise": steady, "weight_kg": 20, "reps": 10, "rir": 2}],
    )

    result = ask_siris.answer("Which exercise has improved the most?", today=today)

    assert result.understood is True
    assert improved in result.answer


def test_best_distance() -> None:
    running, _, ask_siris = _services()
    today = _monday(_random_year(), 0)

    running.create_run(
        run_date=today - timedelta(weeks=1),
        run_type="outdoor",
        distance_km=5.0,
        average_pace_seconds_per_km=330,
        average_heart_rate=150,
    )
    running.create_run(
        run_date=today,
        run_type="outdoor",
        distance_km=5.1,
        average_pace_seconds_per_km=300,
        average_heart_rate=150,
    )

    result = ask_siris.answer("What's my best 5k this year?", today=today)

    assert result.understood is True
    assert today.isoformat() in result.answer


def test_training_counts_filtered_by_workout_name() -> None:
    _, gym, ask_siris = _services()
    today = _monday(_random_year(), 0)

    gym.create_workout(
        workout_date=today, name="Legs", notes=None,
        sets=[{"exercise": _unique_exercise("Squat"), "weight_kg": 100, "reps": 5, "rir": 2}],
    )
    gym.create_workout(
        workout_date=today - timedelta(days=2), name="Push", notes=None,
        sets=[{"exercise": _unique_exercise("Bench"), "weight_kg": 80, "reps": 8, "rir": 2}],
    )

    result = ask_siris.answer("How many leg workouts have I done this week?", today=today)

    assert result.understood is True
    assert "1" in result.answer


def test_weekly_summary_reuses_coach_headline() -> None:
    _, _, ask_siris = _services()
    today = _monday(_random_year(), 0)

    result = ask_siris.answer("How's my training going this week?", today=today)

    assert result.understood is True
    assert len(result.answer) > 0
