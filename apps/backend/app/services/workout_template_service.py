from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os

from sqlalchemy import DateTime, ForeignKey, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class WorkoutTemplateModel(Base):
    __tablename__ = "gym_workout_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    exercises: Mapped[list[WorkoutTemplateExerciseModel]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="WorkoutTemplateExerciseModel.position",
    )


class WorkoutTemplateExerciseModel(Base):
    __tablename__ = "gym_workout_template_exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("gym_workout_templates.id", ondelete="CASCADE"), index=True
    )
    exercise: Mapped[str] = mapped_column(String(120))
    target_sets: Mapped[int] = mapped_column(Integer, default=1)
    target_reps: Mapped[int] = mapped_column(Integer, default=8)
    target_rir: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position: Mapped[int] = mapped_column(Integer)
    template: Mapped[WorkoutTemplateModel] = relationship(back_populates="exercises")


@dataclass(frozen=True)
class WorkoutTemplateExercise:
    exercise: str
    target_sets: int
    target_reps: int
    target_rir: int | None


@dataclass(frozen=True)
class WorkoutTemplate:
    id: int
    name: str
    created_at: datetime
    exercises: list[WorkoutTemplateExercise]


class WorkoutTemplateService:
    def __init__(self) -> None:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://sirisos:change-me@postgres:5432/sirisos",
        )
        self._engine = create_engine(database_url, pool_pre_ping=True)
        self._sessions = sessionmaker(self._engine, expire_on_commit=False)

    def initialise(self) -> None:
        Base.metadata.create_all(self._engine)

    def list_templates(self) -> list[WorkoutTemplate]:
        with self._sessions() as session:
            rows = list(
                session.scalars(
                    select(WorkoutTemplateModel).order_by(WorkoutTemplateModel.name.asc())
                )
            )
            return [self._to_record(row) for row in rows]

    def create_template(self, *, name: str, exercises: list[dict]) -> WorkoutTemplate:
        clean_name = name.strip()
        with self._sessions() as session:
            existing = session.scalar(
                select(WorkoutTemplateModel).where(WorkoutTemplateModel.name == clean_name)
            )
            if existing is not None:
                raise ValueError("A workout template with that name already exists.")

            row = WorkoutTemplateModel(
                name=clean_name,
                created_at=datetime.now(timezone.utc),
            )
            for position, item in enumerate(exercises):
                row.exercises.append(
                    WorkoutTemplateExerciseModel(
                        exercise=str(item["exercise"]).strip(),
                        target_sets=int(item.get("target_sets", 1)),
                        target_reps=int(item.get("target_reps", 8)),
                        target_rir=(
                            int(item["target_rir"])
                            if item.get("target_rir") is not None
                            else None
                        ),
                        position=position,
                    )
                )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._to_record(row)

    def delete_template(self, template_id: int) -> bool:
        with self._sessions() as session:
            row = session.get(WorkoutTemplateModel, template_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    @staticmethod
    def _to_record(row: WorkoutTemplateModel) -> WorkoutTemplate:
        return WorkoutTemplate(
            id=row.id,
            name=row.name,
            created_at=row.created_at,
            exercises=[
                WorkoutTemplateExercise(
                    exercise=item.exercise,
                    target_sets=item.target_sets,
                    target_reps=item.target_reps,
                    target_rir=item.target_rir,
                )
                for item in row.exercises
            ],
        )
