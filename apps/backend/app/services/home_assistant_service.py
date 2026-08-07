from dataclasses import dataclass
import os

import httpx


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
    error: str | None = None


class HomeAssistantService:
    """Server-side Home Assistant client. Credentials never leave the API container."""

    def __init__(self) -> None:
        self._base_url = os.getenv("HOME_ASSISTANT_URL", "").rstrip("/")
        self._token = os.getenv("HOME_ASSISTANT_TOKEN", "")

    @property
    def configured(self) -> bool:
        return bool(self._base_url and self._token)

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def snapshot(self) -> HomeAssistantSnapshot:
        if not self.configured:
            return HomeAssistantSnapshot(False, False, [], "Home Assistant is not configured.")

        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                response = await client.get(f"{self._base_url}/api/states", headers=self._headers)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                return HomeAssistantSnapshot(True, False, [], "Home Assistant returned an invalid state payload.")

            entities: list[HomeAssistantEntity] = []
            for item in payload:
                if not isinstance(item, dict):
                    continue
                entity_id = str(item.get("entity_id") or "")
                if not entity_id or "." not in entity_id:
                    continue
                attributes = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
                entities.append(
                    HomeAssistantEntity(
                        entity_id=entity_id,
                        state=str(item.get("state") or "unknown"),
                        name=str(attributes.get("friendly_name") or entity_id),
                        domain=entity_id.split(".", 1)[0],
                        last_changed=str(item.get("last_changed")) if item.get("last_changed") else None,
                    )
                )
            entities.sort(key=lambda item: (item.domain, item.name.lower()))
            return HomeAssistantSnapshot(True, True, entities)
        except (httpx.HTTPError, ValueError) as exc:
            return HomeAssistantSnapshot(True, False, [], f"Home Assistant request failed: {type(exc).__name__}")

    async def call_service(self, domain: str, service: str, entity_id: str) -> None:
        if not self.configured:
            raise RuntimeError("Home Assistant is not configured.")
        if not domain or not service or not entity_id:
            raise ValueError("domain, service and entity_id are required.")
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                response = await client.post(
                    f"{self._base_url}/api/services/{domain}/{service}",
                    headers=self._headers,
                    json={"entity_id": entity_id},
                )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Home Assistant service call failed: {type(exc).__name__}") from exc
