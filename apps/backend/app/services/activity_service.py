from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os

from sqlalchemy import DateTime, Integer, String, Text, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class ActivityEventModel(Base):
    __tablename__ = "activity_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    module: Mapped[str] = mapped_column(String(40), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default="info")
    user: Mapped[str | None] = mapped_column(String(120), nullable=True)


@dataclass(frozen=True)
class ActivityEvent:
    id: int
    occurred_at: datetime
    module: str
    event_type: str
    title: str
    message: str
    severity: str
    user: str | None


class ActivityService:
    """Persistent cross-module activity feed for SirisOS."""

    def __init__(self) -> None:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://sirisos:change-me@postgres:5432/sirisos",
        )
        self._engine = create_engine(database_url, pool_pre_ping=True)
        self._sessions = sessionmaker(self._engine, expire_on_commit=False)

    def initialise(self) -> None:
        Base.metadata.create_all(self._engine)

    def record(
        self,
        *,
        module: str,
        event_type: str,
        title: str,
        message: str,
        severity: str = "info",
        user: str | None = None,
    ) -> ActivityEvent:
        now = datetime.now(timezone.utc)
        with self._sessions() as session:
            row = ActivityEventModel(
                occurred_at=now,
                module=module.strip().lower(),
                event_type=event_type.strip().lower(),
                title=title.strip(),
                message=message.strip(),
                severity=severity.strip().lower(),
                user=user,
            )
            session.add(row)
            cutoff = now - timedelta(days=90)
            session.execute(delete(ActivityEventModel).where(ActivityEventModel.occurred_at < cutoff))
            session.commit()
            session.refresh(row)
            return self._to_record(row)

    def list_events(self, *, limit: int = 50) -> list[ActivityEvent]:
        safe_limit = max(1, min(limit, 200))
        with self._sessions() as session:
            rows = list(
                session.scalars(
                    select(ActivityEventModel)
                    .order_by(ActivityEventModel.occurred_at.desc(), ActivityEventModel.id.desc())
                    .limit(safe_limit)
                )
            )
        return [self._to_record(row) for row in rows]

    @staticmethod
    def _to_record(row: ActivityEventModel) -> ActivityEvent:
        return ActivityEvent(
            id=row.id,
            occurred_at=row.occurred_at,
            module=row.module,
            event_type=row.event_type,
            title=row.title,
            message=row.message,
            severity=row.severity,
            user=row.user,
        )
