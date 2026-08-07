from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os

import httpx


@dataclass(frozen=True)
class PrometheusSnapshot:
    configured: bool
    available: bool
    healthy_targets: int
    unhealthy_targets: int
    total_targets: int
    generated_at: str
    error: str | None = None


class PrometheusService:
    """Small read-only Prometheus API client with a short-lived snapshot cache."""

    def __init__(self) -> None:
        self._base_url = os.getenv("PROMETHEUS_URL", "").rstrip("/")
        self._cache: PrometheusSnapshot | None = None
        self._cache_until: datetime | None = None

    @property
    def configured(self) -> bool:
        return bool(self._base_url)

    async def snapshot(self, *, force: bool = False) -> PrometheusSnapshot:
        now = datetime.now(timezone.utc)
        if (
            not force
            and self._cache is not None
            and self._cache_until is not None
            and now < self._cache_until
        ):
            return self._cache

        if not self.configured:
            return PrometheusSnapshot(
                configured=False,
                available=False,
                healthy_targets=0,
                unhealthy_targets=0,
                total_targets=0,
                generated_at=now.isoformat(),
                error="Prometheus is not configured.",
            )

        try:
            result = await self.query("up")
            values = []
            for item in result:
                value = item.get("value")
                if isinstance(value, list) and len(value) >= 2:
                    try:
                        values.append(float(value[1]))
                    except (TypeError, ValueError):
                        continue
            healthy = sum(value >= 1 for value in values)
            total = len(values)
            snapshot = PrometheusSnapshot(
                configured=True,
                available=True,
                healthy_targets=healthy,
                unhealthy_targets=max(total - healthy, 0),
                total_targets=total,
                generated_at=now.isoformat(),
            )
        except RuntimeError as exc:
            snapshot = PrometheusSnapshot(
                configured=True,
                available=False,
                healthy_targets=0,
                unhealthy_targets=0,
                total_targets=0,
                generated_at=now.isoformat(),
                error=str(exc),
            )

        self._cache = snapshot
        self._cache_until = now + timedelta(seconds=15)
        return snapshot

    async def query(self, expression: str) -> list[dict]:
        if not self.configured:
            raise RuntimeError("Prometheus is not configured.")
        expression = expression.strip()
        if not expression:
            raise ValueError("PromQL expression is required.")
        if len(expression) > 1000:
            raise ValueError("PromQL expression is too long.")

        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                response = await client.get(
                    f"{self._base_url}/api/v1/query",
                    params={"query": expression},
                )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError(
                f"Prometheus request failed: {type(exc).__name__}"
            ) from exc

        if not isinstance(payload, dict) or payload.get("status") != "success":
            raise RuntimeError("Prometheus returned an unsuccessful query response.")
        data = payload.get("data")
        result = data.get("result") if isinstance(data, dict) else None
        if not isinstance(result, list):
            raise RuntimeError("Prometheus returned an invalid query result.")
        return [item for item in result if isinstance(item, dict)]
