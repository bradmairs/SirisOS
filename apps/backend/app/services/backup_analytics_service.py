from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json

from app.services.time_series_history_service import history_service


@dataclass(frozen=True)
class BackupTaskProtection:
    task_id: str
    task_name: str
    completions: int
    successes: int
    failures: int
    success_rate_percent: float | None
    last_finish_at: str | None
    last_result: str | None


@dataclass(frozen=True)
class BackupProtectionSummary:
    days: int
    completions: int
    successes: int
    failures: int
    success_rate_percent: float | None
    last_finish_at: str | None
    last_failure_at: str | None
    protected: bool | None
    tasks: list[BackupTaskProtection]


class BackupAnalyticsService:
    def summary(self, *, days: int = 30) -> BackupProtectionSummary:
        observations = history_service.history(
            source="synology_backup",
            metric="completion",
            hours=days * 24,
            limit=5000,
        )
        by_task: dict[tuple[str, str], list] = {}
        parsed: list[tuple[object, dict[str, object]]] = []
        for item in observations:
            payload: dict[str, object] = {}
            if item.text_value:
                try:
                    decoded = json.loads(item.text_value)
                    if isinstance(decoded, dict):
                        payload = decoded
                except json.JSONDecodeError:
                    pass
            parsed.append((item, payload))
            key = (
                item.dimensions.get("task_id", "unknown"),
                item.dimensions.get("task", "Backup task"),
            )
            by_task.setdefault(key, []).append((item, payload))

        completions = len(observations)
        successes = sum(1 for item in observations if item.numeric_value == 1)
        failures = sum(1 for item in observations if item.numeric_value == 0)
        success_rate = (successes / completions * 100.0) if completions else None

        last_finish_at: str | None = None
        last_failure_at: str | None = None
        task_summaries: list[BackupTaskProtection] = []

        def finish_value(payload: dict[str, object], fallback: datetime) -> str:
            value = payload.get("finish_at")
            return str(value) if value else fallback.astimezone(timezone.utc).isoformat()

        for item, payload in parsed:
            finish = finish_value(payload, item.observed_at)
            if last_finish_at is None or finish > last_finish_at:
                last_finish_at = finish
            if item.numeric_value == 0 and (last_failure_at is None or finish > last_failure_at):
                last_failure_at = finish

        for (task_id, task_name), entries in sorted(by_task.items(), key=lambda entry: entry[0][1].lower()):
            count = len(entries)
            task_successes = sum(1 for item, _ in entries if item.numeric_value == 1)
            task_failures = sum(1 for item, _ in entries if item.numeric_value == 0)
            latest_item, latest_payload = max(
                entries,
                key=lambda pair: finish_value(pair[1], pair[0].observed_at),
            )
            task_summaries.append(
                BackupTaskProtection(
                    task_id=task_id,
                    task_name=task_name,
                    completions=count,
                    successes=task_successes,
                    failures=task_failures,
                    success_rate_percent=(task_successes / count * 100.0) if count else None,
                    last_finish_at=finish_value(latest_payload, latest_item.observed_at),
                    last_result=str(latest_payload.get("result")) if latest_payload.get("result") is not None else latest_item.text_value,
                )
            )

        protected: bool | None
        if completions == 0:
            protected = None
        else:
            protected = failures == 0

        return BackupProtectionSummary(
            days=days,
            completions=completions,
            successes=successes,
            failures=failures,
            success_rate_percent=success_rate,
            last_finish_at=last_finish_at,
            last_failure_at=last_failure_at,
            protected=protected,
            tasks=task_summaries,
        )


backup_analytics_service = BackupAnalyticsService()
