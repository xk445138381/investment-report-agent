"""Configuration management API endpoints."""

from fastapi import APIRouter
from api.config_accessor import get_config

router = APIRouter(tags=["config"])


@router.get("/config")
async def get_current_config():
    """Get the currently active configuration (API keys masked)."""
    config = get_config()
    return {
        "version": config.version,
        "pipelines": list(config.pipelines.keys()),
        "agents": list(config.agents.keys()),
        "llm_providers": list(config.llm_providers.keys()),
    }
