from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import os
from typing import Literal

PROGRESSIVE_OVERLOAD_INCREMENT_KG = 2.5

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class WorkoutModel(Base):
    __tablename__ = "gym_workouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workout_date: Mapped[date] = mapped_column(Date, index=True)
    name: Mapped[str] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sets: Mapped[list[WorkoutSetModel]] = relationship(
        back_populates="workout", cascade="all, delete-orphan", order_by="WorkoutSetModel.id"
    )


class WorkoutSetModel(Base):
    __tablename__ = "gym_workout_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("gym_workouts.id", ondelete="CASCADE"), index=True)
    exercise: Mapped[str] = mapped_column(String(120), index=True)
    weight_kg: Mapped[float] = mapped_column(Float)
    reps: Mapped[int] = mapped_column(Integer)
    rir: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workout: Mapped[WorkoutModel] = relationship(back_populates="sets")


@dataclass(frozen=True)
class WorkoutSet:
    id: int
    exercise: str
    weight_kg: float
    reps: int
    rir: int | None

    @property
    def volume_kg(self) -> float:
        return round(self.weight_kg * self.reps, 1)

    @property
    def estimated_one_rep_max_kg(self) -> float:
        return round(self.weight_kg * (1 + self.reps / 30), 1)


@dataclass(frozen=True)
class Workout:
    id: int
    workout_date: date
    name: str
    notes: str | None
    created_at: datetime
    sets: list[WorkoutSet]

    @property
    def total_volume_kg(self) -> float:
        return round(sum(item.volume_kg for item in self.sets), 1)


@dataclass(frozen=True)
class ExerciseHistoryPoint:
    workout_id: int
    workout_date: date
    workout_name: str
    weight_kg: float
    reps: int
    rir: int | None
    volume_kg: float
    estimated_one_rep_max_kg: float


@dataclass(frozen=True)
class ExerciseSummary:
    exercise: str
    set_count: int
    workout_count: int
    latest_date: date
    latest_weight_kg: float
    latest_reps: int
    best_weight_kg: float
    best_estimated_one_rep_max_kg: float
    best_set_volume_kg: float
    history: list[ExerciseHistoryPoint]


@dataclass(frozen=True)
class PersonalRecord:
    exercise: str
    record_type: Literal["weight", "estimated_one_rep_max", "set_volume"]
    value: float
    previous_value: float | None
    workout_date: date


@dataclass(frozen=True)
class ProgressiveOverloadSuggestion:
    exercise: str
    status: Literal["progress", "repeat", "no_data"]
    suggested_weight_kg: float | None
    suggested_reps: int | None
    rationale: str
    based_on_workout_date: date | None


class GymService:
    def __init__(self) -> None:
        database_url = os.getenv("DATABASE_URL", "postgresql+psycopg://sirisos:change-me@postgres:5432/sirisos")
        self._engine = create_engine(database_url, pool_pre_ping=True)
        self._sessions = sessionmaker(self._engine, expire_on_commit=False)

    def initialise(self) -> None:
        Base.metadata.create_all(self._engine)

    def list_workouts(self) -> list[Workout]:
        with self._sessions() as session:
            rows = list(session.scalars(select(WorkoutModel).order_by(WorkoutModel.workout_date.desc(), WorkoutModel.id.desc())))
            return [self._to_record(row) for row in rows]

    def create_workout(
        self, *, workout_date: date, name: str, notes: str | None, sets: list[dict]
    ) -> tuple[Workout, list[PersonalRecord]]:
        # Snapshot each exercise's bests before inserting, so the new sets are
        # never compared against themselves.
        exercise_names = {str(item["exercise"]).strip() for item in sets}
        prior_bests = {exercise: self.get_exercise(exercise) for exercise in exercise_names}

        with self._sessions() as session:
            row = WorkoutModel(
                workout_date=workout_date,
                name=name.strip(),
                notes=notes.strip() if notes and notes.strip() else None,
                created_at=datetime.now(timezone.utc),
            )
            for item in sets:
                row.sets.append(
                    WorkoutSetModel(
                        exercise=str(item["exercise"]).strip(),
                        weight_kg=float(item["weight_kg"]),
                        reps=int(item["reps"]),
                        rir=int(item["rir"]) if item.get("rir") is not None else None,
                    )
                )
            session.add(row)
            session.commit()
            session.refresh(row)
            workout = self._to_record(row)

        session_bests: dict[str, dict[str, float]] = {}
        for item in workout.sets:
            bucket = session_bests.setdefault(item.exercise, {"weight": 0.0, "e1rm": 0.0, "volume": 0.0})
            bucket["weight"] = max(bucket["weight"], item.weight_kg)
            bucket["e1rm"] = max(bucket["e1rm"], item.estimated_one_rep_max_kg)
            bucket["volume"] = max(bucket["volume"], item.volume_kg)

        records: list[PersonalRecord] = []
        for exercise, bests in session_bests.items():
            prior = prior_bests.get(exercise)
            if prior is None:
                # First time this exercise has ever been logged -- a new
                # entry, not a "record" over a prior best.
                continue
            if bests["weight"] > prior.best_weight_kg:
                records.append(
                    PersonalRecord(
                        exercise=exercise,
                        record_type="weight",
                        value=bests["weight"],
                        previous_value=prior.best_weight_kg,
                        workout_date=workout_date,
                    )
                )
            if bests["e1rm"] > prior.best_estimated_one_rep_max_kg:
                records.append(
                    PersonalRecord(
                        exercise=exercise,
                        record_type="estimated_one_rep_max",
                        value=bests["e1rm"],
                        previous_value=prior.best_estimated_one_rep_max_kg,
                        workout_date=workout_date,
                    )
                )
            if bests["volume"] > prior.best_set_volume_kg:
                records.append(
                    PersonalRecord(
                        exercise=exercise,
                        record_type="set_volume",
                        value=bests["volume"],
                        previous_value=prior.best_set_volume_kg,
                        workout_date=workout_date,
                    )
                )

        return workout, records

    def list_exercises(self) -> list[ExerciseSummary]:
        workouts = list(reversed(self.list_workouts()))
        grouped: dict[str, list[ExerciseHistoryPoint]] = {}
        display_names: dict[str, str] = {}
        workout_ids: dict[str, set[int]] = {}

        for workout in workouts:
            for item in workout.sets:
                key = item.exercise.strip().casefold()
                display_names.setdefault(key, item.exercise.strip())
                workout_ids.setdefault(key, set()).add(workout.id)
                grouped.setdefault(key, []).append(
                    ExerciseHistoryPoint(
                        workout_id=workout.id,
                        workout_date=workout.workout_date,
                        workout_name=workout.name,
                        weight_kg=item.weight_kg,
                        reps=item.reps,
                        rir=item.rir,
                        volume_kg=item.volume_kg,
                        estimated_one_rep_max_kg=item.estimated_one_rep_max_kg,
                    )
                )

        summaries: list[ExerciseSummary] = []
        for key, history in grouped.items():
            latest = history[-1]
            summaries.append(
                ExerciseSummary(
                    exercise=display_names[key],
                    set_count=len(history),
                    workout_count=len(workout_ids[key]),
                    latest_date=latest.workout_date,
                    latest_weight_kg=latest.weight_kg,
                    latest_reps=latest.reps,
                    best_weight_kg=max(point.weight_kg for point in history),
                    best_estimated_one_rep_max_kg=max(point.estimated_one_rep_max_kg for point in history),
                    best_set_volume_kg=max(point.volume_kg for point in history),
                    history=history,
                )
            )
        return sorted(summaries, key=lambda item: item.latest_date, reverse=True)

    def get_exercise(self, exercise: str) -> ExerciseSummary | None:
        target = exercise.strip().casefold()
        return next((item for item in self.list_exercises() if item.exercise.casefold() == target), None)

    def suggest_progressive_overload(self, exercise: str) -> ProgressiveOverloadSuggestion:
        # Deterministic v1: reasons only from the exercise's own most recent
        # session (straight-set training assumed -- pyramid/varied-weight
        # sessions aren't distinguished from a struggled session yet). No
        # Ollama involvement: this is exactly the kind of numeric judgement
        # the roadmap says should stay deterministic.
        summary = self.get_exercise(exercise)
        if summary is None or not summary.history:
            return ProgressiveOverloadSuggestion(
                exercise=exercise,
                status="no_data",
                suggested_weight_kg=None,
                suggested_reps=None,
                rationale=f"No prior sets logged for {exercise} yet.",
                based_on_workout_date=None,
            )

        last_workout_id = summary.history[-1].workout_id
        last_session = [point for point in summary.history if point.workout_id == last_workout_id]
        last_date = last_session[-1].workout_date
        weight = last_session[-1].weight_kg
        first_reps = last_session[0].reps
        last_reps = last_session[-1].reps
        rir_values = [point.rir for point in last_session if point.rir is not None]
        min_rir = min(rir_values) if rir_values else None

        reps_dropped = last_reps < first_reps
        near_failure = min_rir is not None and min_rir <= 1
        held_or_grew = last_reps >= first_reps
        comfortable = min_rir is None or min_rir >= 2

        rep_summary = ", ".join(
            f"{point.reps}@RIR{point.rir if point.rir is not None else '?'}" for point in last_session
        )

        if reps_dropped or near_failure:
            return ProgressiveOverloadSuggestion(
                exercise=summary.exercise,
                status="repeat",
                suggested_weight_kg=weight,
                suggested_reps=first_reps,
                rationale=(
                    f"On {last_date.isoformat()} your sets were {rep_summary} at {weight:g} kg -- "
                    f"repeat this weight before increasing."
                ),
                based_on_workout_date=last_date,
            )

        if held_or_grew and comfortable:
            suggested_weight = round(weight + PROGRESSIVE_OVERLOAD_INCREMENT_KG, 1)
            suggested_reps = min(point.reps for point in last_session)
            rir_label = "not recorded" if min_rir is None else f"RIR {min_rir}+"
            return ProgressiveOverloadSuggestion(
                exercise=summary.exercise,
                status="progress",
                suggested_weight_kg=suggested_weight,
                suggested_reps=suggested_reps,
                rationale=(
                    f"On {last_date.isoformat()} you held {suggested_reps}+ reps across "
                    f"{len(last_session)} set{'s' if len(last_session) != 1 else ''} at {weight:g} kg "
                    f"({rir_label}) -- try {suggested_weight:g} kg."
                ),
                based_on_workout_date=last_date,
            )

        return ProgressiveOverloadSuggestion(
            exercise=summary.exercise,
            status="repeat",
            suggested_weight_kg=weight,
            suggested_reps=last_reps,
            rationale=(
                f"Your last {exercise} session on {last_date.isoformat()} was mixed ({rep_summary}) -- "
                f"repeat {weight:g} kg and aim to hold reps across all sets."
            ),
            based_on_workout_date=last_date,
        )

    @staticmethod
    def _to_record(row: WorkoutModel) -> Workout:
        return Workout(
            id=row.id,
            workout_date=row.workout_date,
            name=row.name,
            notes=row.notes,
            created_at=row.created_at,
            sets=[
                WorkoutSet(id=item.id, exercise=item.exercise, weight_kg=item.weight_kg, reps=item.reps, rir=item.rir)
                for item in row.sets
            ],
        )
