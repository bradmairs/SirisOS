from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os

import httpx


@dataclass(frozen=True)
class UniFiDevice:
    id: str
    name: str
    model: str
    state: str
    ip_address: str | None
    firmware_version: str | None
    firmware_updatable: bool
    is_access_point: bool


@dataclass(frozen=True)
class UniFiSnapshot:
    configured: bool
    available: bool
    site_id: str | None
    site_name: str | None
    total_devices: int
    online_devices: int
    offline_devices: int
    access_points: int
    connected_clients: int
    wan_interfaces: int
    devices: list[UniFiDevice]
    generated_at: str
    error: str | None = None


class UniFiService:
    def __init__(self) -> None:
        self._base_url = os.getenv("UNIFI_URL", "").strip().rstrip("/")
        self._api_key = os.getenv("UNIFI_API_KEY", "").strip()
        self._site_id = os.getenv("UNIFI_SITE_ID", "").strip() or None
        self._verify_ssl = os.getenv("UNIFI_VERIFY_SSL", "false").lower() in {
            "1", "true", "yes", "on"
        }
        self._cached: UniFiSnapshot | None = None
        self._cached_at: datetime | None = None

    @property
    def configured(self) -> bool:
        return bool(self._base_url and self._api_key)

    @property
    def _headers(self) -> dict[str, str]:
        return {"Accept": "application/json", "X-API-Key": self._api_key}

    def _candidate_roots(self) -> list[str]:
        if self._base_url.endswith("/integration/v1"):
            return [self._base_url]
        return [
            f"{self._base_url}/proxy/network/integration/v1",
            f"{self._base_url}/integration/v1",
        ]

    async def _get(self, path: str) -> dict:
        last_error: Exception | None = None
        for root in self._candidate_roots():
            try:
                async with httpx.AsyncClient(
                    timeout=6.0,
                    follow_redirects=True,
                    verify=self._verify_ssl,
                ) as client:
                    response = await client.get(
                        f"{root}{path}", headers=self._headers
                    )
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, dict):
                    return payload
                raise ValueError("UniFi returned a non-object response")
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
        raise RuntimeError(
            f"UniFi request failed: {type(last_error).__name__ if last_error else 'UnknownError'}"
        )

    @staticmethod
    def _data(payload: dict) -> list[dict]:
        raw = payload.get("data")
        return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []

    @staticmethod
    def _is_access_point(item: dict) -> bool:
        values = " ".join(
            str(item.get(key, ""))
            for key in ("type", "productLine", "model", "name")
        ).lower()
        features = item.get("features")
        if isinstance(features, list):
            values += " " + " ".join(str(value).lower() for value in features)
        return any(token in values for token in ("access point", "access_point", "uap", "wifi"))

    async def snapshot(self, *, force: bool = False) -> UniFiSnapshot:
        now = datetime.now(timezone.utc)
        if (
            not force
            and self._cached is not None
            and self._cached_at is not None
            and now - self._cached_at < timedelta(seconds=15)
        ):
            return self._cached

        if not self.configured:
            return UniFiSnapshot(
                configured=False,
                available=False,
                site_id=None,
                site_name=None,
                total_devices=0,
                online_devices=0,
                offline_devices=0,
                access_points=0,
                connected_clients=0,
                wan_interfaces=0,
                devices=[],
                generated_at=now.astimezone().isoformat(),
                error="UniFi is not configured.",
            )

        try:
            sites = self._data(await self._get("/sites?offset=0&limit=100"))
            if not sites:
                raise RuntimeError("No UniFi sites were returned.")
            site = next(
                (item for item in sites if str(item.get("id")) == self._site_id),
                sites[0],
            )
            site_id = str(site.get("id") or "")
            if not site_id:
                raise RuntimeError("UniFi site has no id.")

            devices_payload = await self._get(
                f"/sites/{site_id}/devices?offset=0&limit=250"
            )
            clients_payload = await self._get(
                f"/sites/{site_id}/clients?offset=0&limit=500"
            )
            try:
                wans_payload = await self._get(
                    f"/sites/{site_id}/wans?offset=0&limit=50"
                )
                wans = self._data(wans_payload)
            except RuntimeError:
                wans = []

            devices_raw = self._data(devices_payload)
            clients = self._data(clients_payload)
            devices = [
                UniFiDevice(
                    id=str(item.get("id") or item.get("macAddress") or ""),
                    name=str(item.get("name") or item.get("model") or "UniFi device"),
                    model=str(item.get("model") or "Unknown"),
                    state=str(item.get("state") or "UNKNOWN").upper(),
                    ip_address=str(item.get("ipAddress")) if item.get("ipAddress") else None,
                    firmware_version=str(item.get("firmwareVersion")) if item.get("firmwareVersion") else None,
                    firmware_updatable=bool(item.get("firmwareUpdatable", False)),
                    is_access_point=self._is_access_point(item),
                )
                for item in devices_raw
            ]
            online = sum(item.state == "ONLINE" for item in devices)
            snapshot = UniFiSnapshot(
                configured=True,
                available=True,
                site_id=site_id,
                site_name=str(site.get("name") or site.get("internalReference") or "UniFi"),
                total_devices=len(devices),
                online_devices=online,
                offline_devices=len(devices) - online,
                access_points=sum(item.is_access_point for item in devices),
                connected_clients=len(clients),
                wan_interfaces=len(wans),
                devices=devices,
                generated_at=now.astimezone().isoformat(),
            )
        except RuntimeError as exc:
            snapshot = UniFiSnapshot(
                configured=True,
                available=False,
                site_id=self._site_id,
                site_name=None,
                total_devices=0,
                online_devices=0,
                offline_devices=0,
                access_points=0,
                connected_clients=0,
                wan_interfaces=0,
                devices=[],
                generated_at=now.astimezone().isoformat(),
                error=str(exc),
            )

        self._cached = snapshot
        self._cached_at = now
        return snapshot
