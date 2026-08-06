from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os

from sqlalchemy import DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class HomelabAuditModel(Base):
    __tablename__ = "homelab_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    username: Mapped[str] = mapped_column(String(100))
    container_id: Mapped[str] = mapped_column(String(100))
    container_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(30))
    result: Mapped[str] = mapped_column(String(30))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


@dataclass(frozen=True)
class HomelabAuditEvent:
    id: int
    occurred_at: datetime
    username: str
    container_id: str
    container_name: str | None
    action: str
    result: str
    detail: str | None


class HomelabAuditService:
    def __init__(self) -> None:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://sirisos:change-me@postgres:5432/sirisos",
        )
        self._engine = create_engine(database_url, pool_pre_ping=True)
        self._session_factory = sessionmaker(self._engine, expire_on_commit=False)

    def initialise(self) -> None:
        Base.metadata.create_all(self._engine)

    def record(
        self,
        *,
        username: str,
        container_id: str,
        container_name: str | None,
        action: str,
        result: str,
        detail: str | None = None,
    ) -> None:
        with self._session_factory() as session:
            session.add(
                HomelabAuditModel(
                    occurred_at=datetime.now(timezone.utc),
                    username=username,
                    container_id=container_id,
                    container_name=container_name,
                    action=action,
                    result=result,
                    detail=detail,
                )
            )
            session.commit()

    def recent(self, *, limit: int = 100) -> list[HomelabAuditEvent]:
        with self._session_factory() as session:
            rows = list(
                session.scalars(
                    select(HomelabAuditModel)
                    .order_by(HomelabAuditModel.occurred_at.desc())
                    .limit(max(1, min(limit, 500)))
                )
            )
        return [
            HomelabAuditEvent(
                id=row.id,
                occurred_at=row.occurred_at,
                username=row.username,
                container_id=row.container_id,
                container_name=row.container_name,
                action=row.action,
                result=row.result,
                detail=row.detail,
            )
            for row in rows
        ]
