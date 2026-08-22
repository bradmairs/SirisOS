from datetime import datetime
from typing import Awaitable, Callable, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.homelab_alerts import home_assistant_service
from app.main import CurrentUsername, docker_monitor

ActionHandler = Callable[[dict[str, str], str], Awaitable[str]]

router = APIRouter(prefix="/api/v1/actions", tags=["actions"])

ActionRisk = Literal["none", "low", "medium", "high"]


class ActionCapability(BaseModel):
    id: str
    title: str
    description: str
    provider_id: str
    risk: ActionRisk
    requires_confirmation: bool


class ActionExecuteRequest(BaseModel):
    params: dict[str, str] = {}
    confirm: bool = False


class ActionExecuteResponse(BaseModel):
    capability_id: str
    accepted: bool
    result: str
    generated_at: str


def _docker_action(action: Literal["start", "stop", "restart"]) -> ActionHandler:
    async def handler(params: dict[str, str], username: str) -> str:
        container_id = params.get("container_id")
        if not container_id:
            raise ValueError("container_id is required.")
        return docker_monitor.action(container_id, action)

    return handler


async def _home_assistant_control(params: dict[str, str], username: str) -> str:
    domain = params.get("domain")
    service = params.get("service")
    entity_id = params.get("entity_id")
    if not domain or not service or not entity_id:
        raise ValueError("domain, service and entity_id are all required.")
    if domain == "cover":
        raise ValueError("Use the home_assistant.cover_control capability for cover devices.")
    await home_assistant_service.call_service(domain, service, entity_id)
    return f"{domain}.{service} executed on {entity_id}."


async def _home_assistant_cover_control(params: dict[str, str], username: str) -> str:
    service = params.get("service")
    entity_id = params.get("entity_id")
    if not service or not entity_id:
        raise ValueError("service and entity_id are required.")
    await home_assistant_service.call_service("cover", service, entity_id)
    return f"cover.{service} executed on {entity_id}."


# Stable capability IDs a future Planner/Hermes/UI can target without knowing
# provider-specific implementation details (README rule #19). Each handler
# delegates to an execution primitive that already has audit logging built
# in (DockerMonitor.action / HomeAssistantService.call_service ->
# HomelabAuditService/ActivityService) rather than inventing a second
# execution/audit path.
_CAPABILITIES: dict[str, tuple[ActionCapability, ActionHandler]] = {
    "docker.start": (
        ActionCapability(
            id="docker.start",
            title="Start container",
            description="Start a stopped Docker container.",
            provider_id="docker",
            risk="low",
            requires_confirmation=False,
        ),
        _docker_action("start"),
    ),
    "docker.stop": (
        ActionCapability(
            id="docker.stop",
            title="Stop container",
            description="Stop a running Docker container.",
            provider_id="docker",
            risk="medium",
            requires_confirmation=True,
        ),
        _docker_action("stop"),
    ),
    "docker.restart": (
        ActionCapability(
            id="docker.restart",
            title="Restart container",
            description="Restart a Docker container.",
            provider_id="docker",
            risk="medium",
            requires_confirmation=True,
        ),
        _docker_action("restart"),
    ),
    "home_assistant.control": (
        ActionCapability(
            id="home_assistant.control",
            title="Control device",
            description="Turn a light/switch/input_boolean on, off, or toggle it.",
            provider_id="home_assistant",
            risk="low",
            requires_confirmation=False,
        ),
        _home_assistant_control,
    ),
    "home_assistant.cover_control": (
        ActionCapability(
            id="home_assistant.cover_control",
            title="Control cover",
            description="Open, close or stop a cover (e.g. garage door, blinds).",
            provider_id="home_assistant",
            risk="medium",
            requires_confirmation=True,
        ),
        _home_assistant_cover_control,
    ),
}


@router.get("", response_model=list[ActionCapability])
async def list_capabilities(_: CurrentUsername) -> list[ActionCapability]:
    return [capability for capability, _handler in _CAPABILITIES.values()]


@router.post("/{capability_id}/execute", response_model=ActionExecuteResponse)
async def execute_capability(
    capability_id: str,
    request: ActionExecuteRequest,
    username: CurrentUsername,
) -> ActionExecuteResponse:
    entry = _CAPABILITIES.get(capability_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Unknown capability.")
    capability, handler = entry

    if capability.requires_confirmation and not request.confirm:
        raise HTTPException(
            status_code=400,
            detail=f"{capability.title} requires explicit confirmation (confirm: true).",
        )

    try:
        result = await handler(request.params, username)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"Action failed: {exc}") from exc

    return ActionExecuteResponse(
        capability_id=capability_id,
        accepted=True,
        result=result,
        generated_at=datetime.now().astimezone().isoformat(),
    )
