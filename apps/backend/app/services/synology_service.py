from dataclasses import dataclass
from datetime import datetime
import os
from typing import Any

import httpx


@dataclass(frozen=True)
class SynologyVolume:
    name: str
    path: str
    status: str
    size_bytes: int | None
    used_bytes: int | None
    used_percent: float | None


@dataclass(frozen=True)
class SynologyDisk:
    name: str
    model: str | None
    status: str
    temperature_c: float | None


@dataclass(frozen=True)
class SynologySnapshot:
    configured: bool
    available: bool
    model: str | None
    dsm_version: str | None
    volumes: tuple[SynologyVolume, ...]
    disks: tuple[SynologyDisk, ...]
    unhealthy_volumes: int
    unhealthy_disks: int
    highest_used_percent: float | None
    backup_api_available: bool
    generated_at: str
    error: str | None = None


class SynologyService:
    def __init__(self) -> None:
        self._base_url = os.getenv("SYNOLOGY_URL", "").rstrip("/")
        self._username = os.getenv("SYNOLOGY_USERNAME", "")
        self._password = os.getenv("SYNOLOGY_PASSWORD", "")
        self._verify_ssl = os.getenv("SYNOLOGY_VERIFY_SSL", "true").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    @property
    def configured(self) -> bool:
        return bool(self._base_url and self._username and self._password)

    async def snapshot(self) -> SynologySnapshot:
        generated_at = datetime.now().astimezone().isoformat()
        if not self.configured:
            return SynologySnapshot(
                configured=False,
                available=False,
                model=None,
                dsm_version=None,
                volumes=(),
                disks=(),
                unhealthy_volumes=0,
                unhealthy_disks=0,
                highest_used_percent=None,
                backup_api_available=False,
                generated_at=generated_at,
            )

        try:
            async with httpx.AsyncClient(
                timeout=8.0,
                verify=self._verify_ssl,
                follow_redirects=True,
            ) as client:
                api_info = await self._api_info(client)
                sid = await self._login(client, api_info)
                try:
                    dsm_info = await self._call(
                        client,
                        api_info,
                        sid,
                        "SYNO.DSM.Info",
                        "getinfo",
                    )
                    storage = await self._storage_info(client, api_info, sid)
                finally:
                    await self._logout(client, api_info, sid)

            volumes = tuple(self._parse_volumes(storage))
            disks = tuple(self._parse_disks(storage))
            unhealthy_volumes = sum(not self._healthy(item.status) for item in volumes)
            unhealthy_disks = sum(not self._healthy(item.status) for item in disks)
            highest = max(
                (item.used_percent for item in volumes if item.used_percent is not None),
                default=None,
            )
            return SynologySnapshot(
                configured=True,
                available=True,
                model=self._first_string(dsm_info, "model", "model_name"),
                dsm_version=self._first_string(
                    dsm_info,
                    "version_string",
                    "version",
                    "firmware_ver",
                ),
                volumes=volumes,
                disks=disks,
                unhealthy_volumes=unhealthy_volumes,
                unhealthy_disks=unhealthy_disks,
                highest_used_percent=highest,
                backup_api_available=any(
                    name.startswith(("SYNO.Backup", "SYNO.HyperBackup"))
                    for name in api_info
                ),
                generated_at=generated_at,
            )
        except Exception as exc:
            return SynologySnapshot(
                configured=True,
                available=False,
                model=None,
                dsm_version=None,
                volumes=(),
                disks=(),
                unhealthy_volumes=0,
                unhealthy_disks=0,
                highest_used_percent=None,
                backup_api_available=False,
                generated_at=generated_at,
                error=f"{type(exc).__name__}: {exc}",
            )

    async def _api_info(self, client: httpx.AsyncClient) -> dict[str, dict[str, Any]]:
        response = await client.get(
            f"{self._base_url}/webapi/entry.cgi",
            params={
                "api": "SYNO.API.Info",
                "version": 1,
                "method": "query",
                "query": "all",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            raise RuntimeError("Synology API discovery failed")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("Invalid Synology API discovery response")
        return {str(key): value for key, value in data.items() if isinstance(value, dict)}

    async def _login(
        self,
        client: httpx.AsyncClient,
        api_info: dict[str, dict[str, Any]],
    ) -> str:
        auth = api_info.get("SYNO.API.Auth", {})
        path = auth.get("path", "auth.cgi")
        version = min(int(auth.get("maxVersion", 7)), 7)
        response = await client.get(
            f"{self._base_url}/webapi/{path}",
            params={
                "api": "SYNO.API.Auth",
                "version": version,
                "method": "login",
                "account": self._username,
                "passwd": self._password,
                "session": "SirisOS",
                "format": "sid",
            },
        )
        response.raise_for_status()
        payload = response.json()
        sid = (payload.get("data") or {}).get("sid") if payload.get("success") else None
        if not sid:
            raise RuntimeError("Synology authentication failed")
        return str(sid)

    async def _logout(
        self,
        client: httpx.AsyncClient,
        api_info: dict[str, dict[str, Any]],
        sid: str,
    ) -> None:
        auth = api_info.get("SYNO.API.Auth", {})
        path = auth.get("path", "auth.cgi")
        version = min(int(auth.get("maxVersion", 7)), 7)
        try:
            await client.get(
                f"{self._base_url}/webapi/{path}",
                params={
                    "api": "SYNO.API.Auth",
                    "version": version,
                    "method": "logout",
                    "session": "SirisOS",
                    "_sid": sid,
                },
            )
        except Exception:
            pass

    async def _call(
        self,
        client: httpx.AsyncClient,
        api_info: dict[str, dict[str, Any]],
        sid: str,
        api: str,
        method: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        info = api_info.get(api)
        if info is None:
            raise RuntimeError(f"Synology API {api} is unavailable")
        path = info.get("path", "entry.cgi")
        version = int(info.get("maxVersion", 1))
        params: dict[str, Any] = {
            "api": api,
            "version": version,
            "method": method,
            "_sid": sid,
        }
        if extra:
            params.update(extra)
        response = await client.get(f"{self._base_url}/webapi/{path}", params=params)
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            raise RuntimeError(f"Synology API {api}.{method} failed")
        data = payload.get("data")
        return data if isinstance(data, dict) else {}

    async def _storage_info(
        self,
        client: httpx.AsyncClient,
        api_info: dict[str, dict[str, Any]],
        sid: str,
    ) -> dict[str, Any]:
        if "SYNO.Storage.CGI.Storage" in api_info:
            return await self._call(
                client,
                api_info,
                sid,
                "SYNO.Storage.CGI.Storage",
                "load_info",
                {"action": "load_info"},
            )

        storage: dict[str, Any] = {}
        if "SYNO.Core.Storage.Volume" in api_info:
            storage["volumes"] = (
                await self._call(
                    client,
                    api_info,
                    sid,
                    "SYNO.Core.Storage.Volume",
                    "list",
                    {"limit": -1, "offset": 0, "location": "internal"},
                )
            ).get("volumes", [])
        if "SYNO.Core.Storage.Disk" in api_info:
            storage["disks"] = (
                await self._call(
                    client,
                    api_info,
                    sid,
                    "SYNO.Core.Storage.Disk",
                    "list",
                )
            ).get("disks", [])
        return storage

    @staticmethod
    def _parse_volumes(data: dict[str, Any]) -> list[SynologyVolume]:
        raw = data.get("volumes") or data.get("volume") or []
        if isinstance(raw, dict):
            raw = raw.get("volumes") or raw.get("volume") or []
        result: list[SynologyVolume] = []
        for item in raw if isinstance(raw, list) else []:
            if not isinstance(item, dict):
                continue
            size = SynologyService._number(item, "size", "total_size", "totalSize")
            free = SynologyService._number(item, "free", "free_size", "available_size", "avail_size")
            used = SynologyService._number(item, "used", "used_size")
            if used is None and size is not None and free is not None:
                used = max(0.0, size - free)
            percent = SynologyService._number(item, "used_percent", "usage", "usedPercent")
            if percent is None and used is not None and size:
                percent = (used / size) * 100
            result.append(
                SynologyVolume(
                    name=SynologyService._first_string(item, "display_name", "name", "id") or "Volume",
                    path=SynologyService._first_string(item, "volume_path", "path") or "",
                    status=SynologyService._first_string(item, "status", "status_text", "state") or "unknown",
                    size_bytes=int(size) if size is not None else None,
                    used_bytes=int(used) if used is not None else None,
                    used_percent=round(percent, 1) if percent is not None else None,
                )
            )
        return result

    @staticmethod
    def _parse_disks(data: dict[str, Any]) -> list[SynologyDisk]:
        raw = data.get("disks") or data.get("disk") or []
        if isinstance(raw, dict):
            raw = raw.get("disks") or raw.get("disk") or []
        result: list[SynologyDisk] = []
        for item in raw if isinstance(raw, list) else []:
            if not isinstance(item, dict):
                continue
            result.append(
                SynologyDisk(
                    name=SynologyService._first_string(item, "display_name", "name", "id", "device") or "Disk",
                    model=SynologyService._first_string(item, "model"),
                    status=SynologyService._first_string(item, "status", "status_text", "state", "health") or "unknown",
                    temperature_c=SynologyService._number(item, "temperature", "temp"),
                )
            )
        return result

    @staticmethod
    def _healthy(status: str) -> bool:
        normalized = status.strip().lower()
        return normalized in {"normal", "healthy", "good", "initialized", "ready", "1"}

    @staticmethod
    def _first_string(data: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = data.get(key)
            if value is not None and str(value).strip():
                return str(value)
        return None

    @staticmethod
    def _number(data: dict[str, Any], *keys: str) -> float | None:
        for key in keys:
            value = data.get(key)
            try:
                if value is not None:
                    return float(value)
            except (TypeError, ValueError):
                continue
        return None
