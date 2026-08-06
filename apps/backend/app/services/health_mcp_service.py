from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import httpx


@dataclass(frozen=True)
class HealthMetric:
    name: str
    value: float | str | None
    unit: str | None
    date: str | None


@dataclass(frozen=True)
class HealthSnapshot:
    available: bool
    endpoint_configured: bool
    tools: list[str]
    metrics: list[HealthMetric]
    error: str | None = None


class HealthMcpService:
    """Small Streamable HTTP MCP client for Health Auto Export on the local LAN."""

    def __init__(self) -> None:
        self.endpoint = os.getenv("HEALTH_AUTO_EXPORT_MCP_URL", "").strip()
        self.token = os.getenv("HEALTH_AUTO_EXPORT_MCP_TOKEN", "").strip()
        self.timeout = float(os.getenv("HEALTH_AUTO_EXPORT_MCP_TIMEOUT_SECONDS", "12"))

    def snapshot(self) -> HealthSnapshot:
        if not self.endpoint or not self.token:
            return HealthSnapshot(False, False, [], [], "Health MCP integration is not configured.")
        try:
            with httpx.Client(timeout=self.timeout) as client:
                session_id = self._initialize(client)
                tools = self._list_tools(client, session_id)
                metrics = self._fetch_summary_metrics(client, session_id, tools)
                return HealthSnapshot(True, True, [item.get("name", "") for item in tools], metrics)
        except Exception as exc:  # Integration must fail gracefully when iPhone server is offline.
            return HealthSnapshot(False, True, [], [], str(exc))

    def _headers(self, session_id: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if session_id:
            headers["Mcp-Session-Id"] = session_id
        return headers

    def _post(self, client: httpx.Client, payload: dict[str, Any], session_id: str | None = None) -> tuple[dict[str, Any], str | None]:
        response = client.post(self.endpoint, headers=self._headers(session_id), json=payload)
        response.raise_for_status()
        body = self._decode_response(response)
        if "error" in body:
            raise RuntimeError(body["error"].get("message", "MCP request failed."))
        return body, response.headers.get("mcp-session-id") or session_id

    @staticmethod
    def _decode_response(response: httpx.Response) -> dict[str, Any]:
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" not in content_type:
            return response.json()
        for line in response.text.splitlines():
            if line.startswith("data:"):
                value = line.removeprefix("data:").strip()
                if value and value != "[DONE]":
                    return json.loads(value)
        raise RuntimeError("Health MCP server returned an empty event stream.")

    def _initialize(self, client: httpx.Client) -> str | None:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "SirisOS", "version": "0.1.0"},
            },
        }
        _, session_id = self._post(client, payload)
        self._post(
            client,
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            session_id,
        )
        return session_id

    def _list_tools(self, client: httpx.Client, session_id: str | None) -> list[dict[str, Any]]:
        body, _ = self._post(
            client,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            session_id,
        )
        return body.get("result", {}).get("tools", [])

    def _fetch_summary_metrics(self, client: httpx.Client, session_id: str | None, tools: list[dict[str, Any]]) -> list[HealthMetric]:
        tool = next((item for item in tools if item.get("name") == "get_health_metrics"), None)
        if tool is None:
            return []

        today = date.today()
        arguments = self._build_arguments(
            tool.get("inputSchema", {}),
            start=(today - timedelta(days=7)).isoformat(),
            end=today.isoformat(),
        )
        body, _ = self._post(
            client,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "get_health_metrics", "arguments": arguments},
            },
            session_id,
        )
        return self._extract_metrics(body.get("result", {}))

    @staticmethod
    def _build_arguments(schema: dict[str, Any], *, start: str, end: str) -> dict[str, Any]:
        properties = schema.get("properties", {})
        args: dict[str, Any] = {}
        if "start" in properties:
            args["start"] = start
        if "end" in properties:
            args["end"] = end
        requested = [
            "step_count",
            "resting_heart_rate",
            "sleep_analysis",
            "body_mass",
            "active_energy",
            "vo2_max",
        ]
        for key in ("metrics", "metric_names", "names"):
            if key in properties:
                args[key] = requested
                break
        for key in ("aggregate", "summarize"):
            if key in properties:
                args[key] = True
        return args

    @classmethod
    def _extract_metrics(cls, result: dict[str, Any]) -> list[HealthMetric]:
        payload: Any = result.get("structuredContent")
        if payload is None:
            content = result.get("content", [])
            text = next((item.get("text") for item in content if item.get("type") == "text"), None)
            if text:
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    payload = {"raw": text}
        metrics = cls._find_metrics(payload)
        output: list[HealthMetric] = []
        for item in metrics:
            data = item.get("data") or []
            latest = data[-1] if isinstance(data, list) and data else {}
            value = latest.get("qty") if isinstance(latest, dict) else None
            if value is None:
                value = item.get("value") or item.get("qty")
            output.append(
                HealthMetric(
                    name=str(item.get("name", "unknown")),
                    value=value,
                    unit=item.get("units") or item.get("unit"),
                    date=latest.get("date") if isinstance(latest, dict) else None,
                )
            )
        return output

    @classmethod
    def _find_metrics(cls, value: Any) -> list[dict[str, Any]]:
        if isinstance(value, dict):
            if isinstance(value.get("metrics"), list):
                return [item for item in value["metrics"] if isinstance(item, dict)]
            for child in value.values():
                found = cls._find_metrics(child)
                if found:
                    return found
        elif isinstance(value, list):
            if value and all(isinstance(item, dict) and "name" in item for item in value):
                return value
            for child in value:
                found = cls._find_metrics(child)
                if found:
                    return found
        return []
