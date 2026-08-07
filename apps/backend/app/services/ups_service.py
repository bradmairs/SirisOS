from dataclasses import dataclass
from datetime import datetime
import asyncio
import os
import re


@dataclass(frozen=True)
class UpsSnapshot:
    configured: bool
    available: bool
    ups_name: str | None
    description: str | None
    status: str | None
    on_battery: bool
    low_battery: bool
    battery_charge_percent: float | None
    battery_runtime_seconds: float | None
    load_percent: float | None
    input_voltage: float | None
    output_voltage: float | None
    generated_at: str
    error: str | None = None


class UpsService:
    def __init__(self) -> None:
        self._host = os.getenv("NUT_HOST", "").strip()
        self._port = int(os.getenv("NUT_PORT", "3493"))
        self._ups_name = os.getenv("NUT_UPS_NAME", "").strip()
        self._timeout = float(os.getenv("NUT_TIMEOUT_SECONDS", "4"))

    @property
    def configured(self) -> bool:
        return bool(self._host)

    async def snapshot(self) -> UpsSnapshot:
        generated_at = datetime.now().astimezone().isoformat()
        if not self.configured:
            return UpsSnapshot(
                configured=False,
                available=False,
                ups_name=None,
                description=None,
                status=None,
                on_battery=False,
                low_battery=False,
                battery_charge_percent=None,
                battery_runtime_seconds=None,
                load_percent=None,
                input_voltage=None,
                output_voltage=None,
                generated_at=generated_at,
            )

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=self._timeout,
            )
            try:
                ups_name, description = await self._resolve_ups(reader, writer)
                values = await self._list_vars(reader, writer, ups_name)
            finally:
                writer.close()
                await writer.wait_closed()

            status = values.get("ups.status")
            tokens = set((status or "").upper().split())
            return UpsSnapshot(
                configured=True,
                available=True,
                ups_name=ups_name,
                description=description,
                status=status,
                on_battery="OB" in tokens,
                low_battery="LB" in tokens,
                battery_charge_percent=self._number(values.get("battery.charge")),
                battery_runtime_seconds=self._number(values.get("battery.runtime")),
                load_percent=self._number(values.get("ups.load")),
                input_voltage=self._number(values.get("input.voltage")),
                output_voltage=self._number(values.get("output.voltage")),
                generated_at=generated_at,
            )
        except Exception as exc:
            return UpsSnapshot(
                configured=True,
                available=False,
                ups_name=self._ups_name or None,
                description=None,
                status=None,
                on_battery=False,
                low_battery=False,
                battery_charge_percent=None,
                battery_runtime_seconds=None,
                load_percent=None,
                input_voltage=None,
                output_voltage=None,
                generated_at=generated_at,
                error=f"{type(exc).__name__}: {exc}",
            )

    async def _resolve_ups(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> tuple[str, str | None]:
        if self._ups_name:
            return self._ups_name, None
        lines = await self._command(reader, writer, "LIST UPS")
        for line in lines:
            match = re.match(r'^UPS\s+(\S+)\s+"(.*)"$', line)
            if match:
                return match.group(1), match.group(2)
        raise RuntimeError("NUT server did not expose any UPS devices")

    async def _list_vars(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        ups_name: str,
    ) -> dict[str, str]:
        lines = await self._command(reader, writer, f"LIST VAR {ups_name}")
        result: dict[str, str] = {}
        pattern = re.compile(r'^VAR\s+\S+\s+(\S+)\s+"(.*)"$')
        for line in lines:
            match = pattern.match(line)
            if match:
                result[match.group(1)] = match.group(2)
        if not result:
            raise RuntimeError(f"NUT returned no variables for {ups_name}")
        return result

    async def _command(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        command: str,
    ) -> list[str]:
        writer.write(f"{command}\n".encode())
        await writer.drain()
        lines: list[str] = []
        end_marker = f"END {command}"
        while True:
            raw = await asyncio.wait_for(reader.readline(), timeout=self._timeout)
            if not raw:
                break
            line = raw.decode(errors="replace").strip()
            if line.startswith("ERR "):
                raise RuntimeError(line)
            if line == end_marker:
                break
            if line.startswith("BEGIN "):
                continue
            lines.append(line)
        return lines

    @staticmethod
    def _number(value: str | None) -> float | None:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
