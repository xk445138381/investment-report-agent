"""Configuration management API endpoints."""

import os, json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from api.config_accessor import get_config

router = APIRouter(tags=["config"])

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "config.json"


def _env_enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _runtime_config_writes_allowed() -> bool:
    env = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development")).strip().lower()
    return env not in {"production", "prod"} or _env_enabled("ENABLE_RUNTIME_CONFIG_WRITES")


@router.get("/config")
async def get_current_config():
    """Get the currently active configuration."""
    config = get_config()
    providers = {}
    llm_dict = config.llm_providers if isinstance(config.llm_providers, dict) else {}
    for pid, pcfg in llm_dict.items():
        key_var = pcfg.api_key_source.replace("env:", "") if getattr(pcfg, "api_key_source", "").startswith("env:") else ""
        providers[pid] = {
            "provider": getattr(pcfg, "provider", "?"),
            "model": getattr(pcfg, "model", "?"),
            "timeout_seconds": getattr(pcfg, "timeout_seconds", 120),
            "api_key_set": bool(os.environ.get(key_var, "")),
            "note": getattr(pcfg, "note", ""),
        }

    agents = {}
    agent_dict = config.agents if isinstance(config.agents, dict) else {}
    for aid, acfg in agent_dict.items():
        agents[aid] = {
            "llm": getattr(acfg, "llm", None),
            "timeout_seconds": getattr(acfg, "timeout_seconds", 120),
            "note": getattr(acfg, "note", ""),
        }

    return {
        "version": config.version,
        "pipelines": list(config.pipelines.keys()),
        "llm_providers": providers,
        "agents": agents,
    }


@router.post("/config/switch-agent-llm")
async def switch_agent_llm(data: dict):
    """Switch an agent's LLM provider at runtime.

    Body: {"agent_name": "duan_case", "llm_provider": "provider_heavy"}
    """
    if not _runtime_config_writes_allowed():
        raise HTTPException(403, "Runtime config writes are disabled in production")

    agent_name = data.get("agent_name", "")
    llm_provider = data.get("llm_provider", "")

    config = get_config()
    if agent_name not in config.agents:
        return {"error": f"Unknown agent: {agent_name}"}
    if llm_provider not in config.llm_providers:
        return {"error": f"Unknown provider: {llm_provider}"}

    agent_cfg = config.agents[agent_name]
    agent_cfg.llm = llm_provider

    # Write back to config.json
    try:
        raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        if "agents" in raw and agent_name in raw["agents"]:
            raw["agents"][agent_name]["llm"] = llm_provider
        _CONFIG_PATH.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        return {"error": f"Failed to save config: {e}"}

    # Clear LLMRegistry model cache for this agent
    try:
        from config.loader import LLMRegistry
        registry = LLMRegistry(get_config())
        if agent_name in registry._models:
            del registry._models[agent_name]
    except Exception:
        pass

    return {
        "ok": True,
        "agent": agent_name,
        "llm_provider": llm_provider,
        "model": str(config.llm_providers[llm_provider].model),
    }
