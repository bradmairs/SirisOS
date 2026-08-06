from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import os

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

    def create_workout(self, *, workout_date: date, name: str, notes: str | None, sets: list[dict]) -> Workout:
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
            return self._to_record(row)

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
