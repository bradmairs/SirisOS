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
class HyperBackupTask:
    task_id: str
    name: str
    state: str
    last_result: str | None
    last_finish_at: str | None
    next_run_at: str | None
    destination: str | None
    running: bool
    failed: bool


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
    backup_tasks: tuple[HyperBackupTask, ...]
    running_backup_tasks: int
    failed_backup_tasks: int
    latest_backup_finish_at: str | None
    generated_at: str
    error: str | None = None


class SynologyService:
    def __init__(self) -> None:
        self._base_url = os.getenv("SYNOLOGY_URL", "").rstrip("/")
        self._username = os.getenv("SYNOLOGY_USERNAME", "")
        self._password = os.getenv("SYNOLOGY_PASSWORD", "")
        self._verify_ssl = os.getenv("SYNOLOGY_VERIFY_SSL", "true").lower() in {
            "1", "true", "yes", "on",
        }

    @property
    def configured(self) -> bool:
        return bool(self._base_url and self._username and self._password)

    async def snapshot(self) -> SynologySnapshot:
        generated_at = datetime.now().astimezone().isoformat()
        empty = dict(
            model=None,
            dsm_version=None,
            volumes=(),
            disks=(),
            unhealthy_volumes=0,
            unhealthy_disks=0,
            highest_used_percent=None,
            backup_api_available=False,
            backup_tasks=(),
            running_backup_tasks=0,
            failed_backup_tasks=0,
            latest_backup_finish_at=None,
        )
        if not self.configured:
            return SynologySnapshot(configured=False, available=False, generated_at=generated_at, **empty)

        try:
            async with httpx.AsyncClient(timeout=8.0, verify=self._verify_ssl, follow_redirects=True) as client:
                api_info = await self._api_info(client)
                sid = await self._login(client, api_info)
                try:
                    dsm_info = await self._call(client, api_info, sid, "SYNO.DSM.Info", "getinfo")
                    storage = await self._storage_info(client, api_info, sid)
                    backup_tasks = await self._backup_tasks(client, api_info, sid)
                finally:
                    await self._logout(client, api_info, sid)

            volumes = tuple(self._parse_volumes(storage))
            disks = tuple(self._parse_disks(storage))
            tasks = tuple(backup_tasks)
            latest_finish = max((t.last_finish_at for t in tasks if t.last_finish_at), default=None)
            return SynologySnapshot(
                configured=True,
                available=True,
                model=self._first_string(dsm_info, "model", "model_name"),
                dsm_version=self._first_string(dsm_info, "version_string", "version", "firmware_ver"),
                volumes=volumes,
                disks=disks,
                unhealthy_volumes=sum(not self._healthy(v.status) for v in volumes),
                unhealthy_disks=sum(not self._healthy(d.status) for d in disks),
                highest_used_percent=max((v.used_percent for v in volumes if v.used_percent is not None), default=None),
                backup_api_available="SYNO.Backup.Task" in api_info,
                backup_tasks=tasks,
                running_backup_tasks=sum(t.running for t in tasks),
                failed_backup_tasks=sum(t.failed for t in tasks),
                latest_backup_finish_at=latest_finish,
                generated_at=generated_at,
            )
        except Exception as exc:
            return SynologySnapshot(
                configured=True,
                available=False,
                generated_at=generated_at,
                error=f"{type(exc).__name__}: {exc}",
                **empty,
            )

    async def _api_info(self, client: httpx.AsyncClient) -> dict[str, dict[str, Any]]:
        response = await client.get(
            f"{self._base_url}/webapi/entry.cgi",
            params={"api": "SYNO.API.Info", "version": 1, "method": "query", "query": "all"},
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success") or not isinstance(payload.get("data"), dict):
            raise RuntimeError("Synology API discovery failed")
        return {str(k): v for k, v in payload["data"].items() if isinstance(v, dict)}

    async def _login(self, client: httpx.AsyncClient, api_info: dict[str, dict[str, Any]]) -> str:
        auth = api_info.get("SYNO.API.Auth", {})
        response = await client.get(
            f"{self._base_url}/webapi/{auth.get('path', 'auth.cgi')}",
            params={
                "api": "SYNO.API.Auth",
                "version": min(int(auth.get("maxVersion", 7)), 7),
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

    async def _logout(self, client: httpx.AsyncClient, api_info: dict[str, dict[str, Any]], sid: str) -> None:
        auth = api_info.get("SYNO.API.Auth", {})
        try:
            await client.get(
                f"{self._base_url}/webapi/{auth.get('path', 'auth.cgi')}",
                params={"api": "SYNO.API.Auth", "version": min(int(auth.get("maxVersion", 7)), 7), "method": "logout", "session": "SirisOS", "_sid": sid},
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
        *,
        tolerate_failure: bool = False,
    ) -> dict[str, Any]:
        info = api_info.get(api)
        if info is None:
            if tolerate_failure:
                return {}
            raise RuntimeError(f"Synology API {api} is unavailable")
        params: dict[str, Any] = {
            "api": api,
            "version": int(info.get("maxVersion", 1)),
            "method": method,
            "_sid": sid,
        }
        if extra:
            params.update(extra)
        response = await client.get(f"{self._base_url}/webapi/{info.get('path', 'entry.cgi')}", params=params)
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            if tolerate_failure:
                return {}
            raise RuntimeError(f"Synology API {api}.{method} failed")
        return payload.get("data") if isinstance(payload.get("data"), dict) else {}

    async def _backup_tasks(self, client: httpx.AsyncClient, api_info: dict[str, dict[str, Any]], sid: str) -> list[HyperBackupTask]:
        if "SYNO.Backup.Task" not in api_info:
            return []
        listed = await self._call(client, api_info, sid, "SYNO.Backup.Task", "list", tolerate_failure=True)
        raw = listed.get("task_list") or listed.get("tasks") or listed.get("list") or []
        if not isinstance(raw, list):
            return []
        result: list[HyperBackupTask] = []
        for item in raw[:50]:
            if not isinstance(item, dict):
                continue
            task_id = self._first_string(item, "task_id", "id") or "unknown"
            status = await self._call(
                client,
                api_info,
                sid,
                "SYNO.Backup.Task",
                "status",
                {"task_id": task_id, "additional": '["last_bkp_result"]'},
                tolerate_failure=True,
            )
            merged = {**item, **status}
            state = (self._first_string(merged, "state", "status", "task_status") or "unknown").lower()
            last_result = self._first_string(merged, "last_bkp_result", "last_result", "result", "last_status")
            normalized_result = (last_result or "").lower()
            running = state in {"running", "backup", "backing_up", "processing", "verifying"}
            failed = any(token in normalized_result for token in ("fail", "error", "broken", "cancel")) or state in {"error", "failed"}
            result.append(
                HyperBackupTask(
                    task_id=task_id,
                    name=self._first_string(merged, "name", "task_name", "display_name") or f"Task {task_id}",
                    state=state,
                    last_result=last_result,
                    last_finish_at=self._timestamp_string(merged, "last_finish_time", "last_backup_time", "last_bkp_time", "last_run_time"),
                    next_run_at=self._timestamp_string(merged, "next_backup_time", "next_run_time", "next_trigger_time"),
                    destination=self._first_string(merged, "target_name", "destination", "dest_name", "repository_name"),
                    running=running,
                    failed=failed,
                )
            )
        return result

    async def _storage_info(self, client: httpx.AsyncClient, api_info: dict[str, dict[str, Any]], sid: str) -> dict[str, Any]:
        if "SYNO.Storage.CGI.Storage" in api_info:
            return await self._call(client, api_info, sid, "SYNO.Storage.CGI.Storage", "load_info", {"action": "load_info"})
        storage: dict[str, Any] = {}
        if "SYNO.Core.Storage.Volume" in api_info:
            storage["volumes"] = (await self._call(client, api_info, sid, "SYNO.Core.Storage.Volume", "list", {"limit": -1, "offset": 0, "location": "internal"})).get("volumes", [])
        if "SYNO.Core.Storage.Disk" in api_info:
            storage["disks"] = (await self._call(client, api_info, sid, "SYNO.Core.Storage.Disk", "list")).get("disks", [])
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
            result.append(SynologyVolume(
                name=SynologyService._first_string(item, "display_name", "name", "id") or "Volume",
                path=SynologyService._first_string(item, "volume_path", "path") or "",
                status=SynologyService._first_string(item, "status", "status_text", "state") or "unknown",
                size_bytes=int(size) if size is not None else None,
                used_bytes=int(used) if used is not None else None,
                used_percent=round(percent, 1) if percent is not None else None,
            ))
        return result

    @staticmethod
    def _parse_disks(data: dict[str, Any]) -> list[SynologyDisk]:
        raw = data.get("disks") or data.get("disk") or []
        if isinstance(raw, dict):
            raw = raw.get("disks") or raw.get("disk") or []
        return [SynologyDisk(
            name=SynologyService._first_string(item, "display_name", "name", "id", "device") or "Disk",
            model=SynologyService._first_string(item, "model"),
            status=SynologyService._first_string(item, "status", "status_text", "state", "health") or "unknown",
            temperature_c=SynologyService._number(item, "temperature", "temp"),
        ) for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []

    @staticmethod
    def _timestamp_string(data: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = data.get(key)
            if value in (None, "", 0, "0"):
                continue
            if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
                try:
                    numeric = float(value)
                    if numeric > 10_000_000_000:
                        numeric /= 1000
                    return datetime.fromtimestamp(numeric).astimezone().isoformat()
                except (ValueError, OSError, OverflowError):
                    pass
            return str(value)
        return None

    @staticmethod
    def _healthy(status: str) -> bool:
        return status.strip().lower() in {"normal", "healthy", "good", "initialized", "ready", "1"}

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
            try:
                value = data.get(key)
                if value is not None:
                    return float(value)
            except (TypeError, ValueError):
                continue
        return None
