from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import os
from urllib.parse import urlparse, urlunparse

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, WebSocketException


@dataclass(frozen=True)
class HomeAssistantEntity:
    entity_id: str
    state: str
    name: str
    domain: str
    last_changed: str | None


@dataclass(frozen=True)
class HomeAssistantSnapshot:
    configured: bool
    available: bool
    entities: list[HomeAssistantEntity]
    live_connected: bool = False
    sequence: int = 0
    error: str | None = None


_ALLOWED_SERVICES: dict[str, set[str]] = {
    "light": {"turn_on", "turn_off", "toggle"},
    "switch": {"turn_on", "turn_off", "toggle"},
    "input_boolean": {"turn_on", "turn_off", "toggle"},
    "cover": {"open_cover", "close_cover", "stop_cover"},
}


class HomeAssistantService:
    """Server-side Home Assistant client with a cached state_changed stream."""

    def __init__(self) -> None:
        self._base_url = os.getenv("HOME_ASSISTANT_URL", "").rstrip("/")
        self._token = os.getenv("HOME_ASSISTANT_TOKEN", "")
        self._entities: dict[str, HomeAssistantEntity] = {}
        self._listener_task: asyncio.Task[None] | None = None
        self._live_connected = False
        self._sequence = 0
        self._last_error: str | None = None
        self._lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return bool(self._base_url and self._token)

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    @property
    def _websocket_url(self) -> str:
        parsed = urlparse(self._base_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        return urlunparse((scheme, parsed.netloc, "/api/websocket", "", "", ""))

    async def snapshot(self) -> HomeAssistantSnapshot:
        if not self.configured:
            return HomeAssistantSnapshot(
                False,
                False,
                [],
                error="Home Assistant is not configured.",
            )

        self._ensure_listener()
        async with self._lock:
            cached = list(self._entities.values())
            live_connected = self._live_connected
            sequence = self._sequence
            last_error = self._last_error

        if cached:
            return HomeAssistantSnapshot(
                True,
                True,
                sorted(cached, key=lambda item: (item.domain, item.name.lower())),
                live_connected=live_connected,
                sequence=sequence,
                error=None if live_connected else last_error,
            )

        return await self._rest_snapshot()

    async def call_service(self, domain: str, service: str, entity_id: str) -> None:
        if not self.configured:
            raise RuntimeError("Home Assistant is not configured.")
        allowed = _ALLOWED_SERVICES.get(domain)
        if allowed is None or service not in allowed:
            raise ValueError(f"Service {domain}.{service} is not permitted by SirisOS.")
        if not entity_id.startswith(f"{domain}."):
            raise ValueError("Entity domain does not match the requested service domain.")

        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                response = await client.post(
                    f"{self._base_url}/api/services/{domain}/{service}",
                    headers=self._headers,
                    json={"entity_id": entity_id},
                )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Home Assistant service call failed: {type(exc).__name__}"
            ) from exc

    def _ensure_listener(self) -> None:
        if not self.configured:
            return
        if self._listener_task is None or self._listener_task.done():
            self._listener_task = asyncio.create_task(self._listen_forever())

    async def _rest_snapshot(self) -> HomeAssistantSnapshot:
        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                response = await client.get(
                    f"{self._base_url}/api/states",
                    headers=self._headers,
                )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                return HomeAssistantSnapshot(
                    True,
                    False,
                    [],
                    error="Home Assistant returned an invalid state payload.",
                )

            entities = [
                entity
                for item in payload
                if isinstance(item, dict)
                if (entity := self._entity_from_state(item)) is not None
            ]
            async with self._lock:
                self._entities = {item.entity_id: item for item in entities}
                self._sequence += 1
                sequence = self._sequence
                live_connected = self._live_connected
                last_error = self._last_error
            return HomeAssistantSnapshot(
                True,
                True,
                sorted(entities, key=lambda item: (item.domain, item.name.lower())),
                live_connected=live_connected,
                sequence=sequence,
                error=None if live_connected else last_error,
            )
        except (httpx.HTTPError, ValueError) as exc:
            error = f"Home Assistant request failed: {type(exc).__name__}"
            async with self._lock:
                self._last_error = error
            return HomeAssistantSnapshot(True, False, [], error=error)

    async def _listen_forever(self) -> None:
        while self.configured:
            try:
                async with connect(
                    self._websocket_url,
                    open_timeout=5,
                    close_timeout=3,
                    ping_interval=20,
                    ping_timeout=10,
                ) as websocket:
                    required = json.loads(await websocket.recv())
                    if required.get("type") != "auth_required":
                        raise RuntimeError("Unexpected Home Assistant WebSocket handshake.")

                    await websocket.send(
                        json.dumps({"type": "auth", "access_token": self._token})
                    )
                    auth = json.loads(await websocket.recv())
                    if auth.get("type") != "auth_ok":
                        raise RuntimeError("Home Assistant WebSocket authentication failed.")

                    await websocket.send(
                        json.dumps(
                            {
                                "id": 1,
                                "type": "subscribe_events",
                                "event_type": "state_changed",
                            }
                        )
                    )
                    result = json.loads(await websocket.recv())
                    if result.get("type") != "result" or not result.get("success"):
                        raise RuntimeError("Home Assistant state subscription failed.")

                    async with self._lock:
                        self._live_connected = True
                        self._last_error = None

                    if not self._entities:
                        await self._rest_snapshot()

                    async for raw in websocket:
                        message = json.loads(raw)
                        if message.get("type") != "event":
                            continue
                        event = message.get("event")
                        data = event.get("data") if isinstance(event, dict) else None
                        if not isinstance(data, dict):
                            continue
                        entity_id = str(data.get("entity_id") or "")
                        new_state = data.get("new_state")
                        async with self._lock:
                            if new_state is None:
                                self._entities.pop(entity_id, None)
                            elif isinstance(new_state, dict):
                                entity = self._entity_from_state(new_state)
                                if entity is not None:
                                    self._entities[entity.entity_id] = entity
                            self._sequence += 1
            except (
                asyncio.CancelledError,
                ConnectionClosed,
                WebSocketException,
                OSError,
                ValueError,
                RuntimeError,
            ) as exc:
                if isinstance(exc, asyncio.CancelledError):
                    raise
                async with self._lock:
                    self._live_connected = False
                    self._last_error = f"Live state stream unavailable: {type(exc).__name__}"
                await asyncio.sleep(5)

    @staticmethod
    def _entity_from_state(item: dict) -> HomeAssistantEntity | None:
        entity_id = str(item.get("entity_id") or "")
        if not entity_id or "." not in entity_id:
            return None
        attributes = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
        return HomeAssistantEntity(
            entity_id=entity_id,
            state=str(item.get("state") or "unknown"),
            name=str(attributes.get("friendly_name") or entity_id),
            domain=entity_id.split(".", 1)[0],
            last_changed=str(item.get("last_changed")) if item.get("last_changed") else None,
        )
