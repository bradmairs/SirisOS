from pathlib import Path


def test_supervisor_runs_explicit_api_entrypoint() -> None:
    root = Path(__file__).resolve().parents[3]
    supervisor = (root / "deploy" / "supervisord.conf").read_text(encoding="utf-8")
    assert "uvicorn app.entrypoint:app" in supervisor


def test_entrypoint_registers_modular_platform_routers() -> None:
    root = Path(__file__).resolve().parents[3]
    entrypoint = (root / "apps" / "backend" / "app" / "entrypoint.py").read_text(encoding="utf-8")
    required = (
        "activity_router",
        "health_router",
        "history_router",
        "infrastructure_router",
        "intelligence_router",
        "knowledge_router",
        "knowledge_context_router",
        "search_router",
        "synology_router",
    )
    for router_name in required:
        assert router_name in entrypoint
