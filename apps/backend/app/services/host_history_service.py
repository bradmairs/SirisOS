from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os

from sqlalchemy import DateTime, Float, Integer, String, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class HostMetricSampleModel(Base):
    __tablename__ = "host_metric_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    memory_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    disk_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    load_1m: Mapped[float | None] = mapped_column(Float, nullable=True)


@dataclass(frozen=True)
class HostMetricSample:
    sampled_at: datetime
    hostname: str | None
    cpu_percent: float | None
    memory_percent: float | None
    disk_percent: float | None
    load_1m: float | None


class HostHistoryService:
    """Store low-frequency host samples for persistent trend charts."""

    def __init__(self) -> None:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://sirisos:change-me@postgres:5432/sirisos",
        )
        self._engine = create_engine(database_url, pool_pre_ping=True)
        self._session_factory = sessionmaker(self._engine, expire_on_commit=False)

    def initialise(self) -> None:
        Base.metadata.create_all(self._engine)

    def record_if_due(
        self,
        *,
        hostname: str | None,
        cpu_percent: float | None,
        memory_percent: float | None,
        disk_percent: float | None,
        load_1m: float | None,
        minimum_interval_seconds: int = 60,
    ) -> None:
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:
            latest = session.scalar(
                select(HostMetricSampleModel)
                .order_by(HostMetricSampleModel.sampled_at.desc())
                .limit(1)
            )
            if latest is not None:
                latest_at = latest.sampled_at
                if latest_at.tzinfo is None:
                    latest_at = latest_at.replace(tzinfo=timezone.utc)
                if (now - latest_at).total_seconds() < minimum_interval_seconds:
                    return

            session.add(
                HostMetricSampleModel(
                    sampled_at=now,
                    hostname=hostname,
                    cpu_percent=cpu_percent,
                    memory_percent=memory_percent,
                    disk_percent=disk_percent,
                    load_1m=load_1m,
                )
            )
            cutoff = now - timedelta(days=30)
            session.execute(
                delete(HostMetricSampleModel).where(
                    HostMetricSampleModel.sampled_at < cutoff
                )
            )
            session.commit()

    def history(self, *, hours: int = 24, limit: int = 720) -> list[HostMetricSample]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with self._session_factory() as session:
            rows = list(
                session.scalars(
                    select(HostMetricSampleModel)
                    .where(HostMetricSampleModel.sampled_at >= cutoff)
                    .order_by(HostMetricSampleModel.sampled_at.asc())
                    .limit(limit)
                )
            )
        return [
            HostMetricSample(
                sampled_at=row.sampled_at,
                hostname=row.hostname,
                cpu_percent=row.cpu_percent,
                memory_percent=row.memory_percent,
                disk_percent=row.disk_percent,
                load_1m=row.load_1m,
            )
            for row in rows
        ]
