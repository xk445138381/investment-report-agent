"""Configuration loader — loads config.json, validates, resolves references.

Core entry point: load_config() → Config
Also provides: validate_config_references(), resolve_api_key(), LLMRegistry
"""

import json
import os
from pathlib import Path
from typing import Optional

from .schema import Config
from .defaults import (
    DEFAULT_LLM_PROVIDERS,
    DEFAULT_DATA_PROVIDERS,
    DEFAULT_PIPELINES,
    DEFAULT_AGENTS,
)


def resolve_api_key(source: str) -> Optional[str]:
    """Resolve API key from env: prefix or plain text.

    Examples:
        "env:ANTHROPIC_API_KEY" → os.environ["ANTHROPIC_API_KEY"]
        "sk-plaintext-xxx"      → "sk-plaintext-xxx"
    """
    if source.startswith("env:"):
        var_name = source[4:]
        return os.environ.get(var_name)
    return source if source else None


def _merge_defaults(config_dict: dict) -> dict:
    """Merge default values into config dict for missing keys."""
    result = dict(config_dict)

    if not result.get("llm_providers"):
        result["llm_providers"] = DEFAULT_LLM_PROVIDERS

    if not result.get("data_providers") or not result["data_providers"].get("providers"):
        result["data_providers"] = DEFAULT_DATA_PROVIDERS

    if not result.get("pipelines"):
        result["pipelines"] = DEFAULT_PIPELINES

    if not result.get("agents"):
        result["agents"] = DEFAULT_AGENTS

    return result


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from a JSON file.

    Resolution order:
      1. config_path argument (absolute or relative path)
      2. INVESTMENT_REPORT_CONFIG environment variable
      3. config.json in current working directory
      4. Default configuration (no file needed)
    """
    if config_path:
        path = Path(config_path)
    elif os.environ.get("INVESTMENT_REPORT_CONFIG"):
        path = Path(os.environ["INVESTMENT_REPORT_CONFIG"])
    else:
        path = Path("config.json")

    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
    else:
        raw = {
            "version": "1.0",
            "global": {"language": "zh-CN", "data_priority": "local_first"},
        }

    raw = _merge_defaults(raw)
    config = Config.model_validate(raw)
    validate_config_references(config)
    return config


def validate_config_references(config: Config) -> None:
    """Validate that all cross-references within the config are valid.

    Checks:
      - Every agent's llm field references an existing llm_providers key
      - Every fallback_chain value references existing providers
      - Every pipeline's agents reference existing agent configs
    """
    # Check agent → llm_provider references
    known_llm_providers = set(config.llm_providers.keys())
    for agent_name, agent_cfg in config.agents.items():
        if agent_cfg.llm not in known_llm_providers:
            raise ValueError(
                f"Agent '{agent_name}' references unknown llm_provider "
                f"'{agent_cfg.llm}'. Known providers: {known_llm_providers}"
            )

    # Check fallback_chain → provider references
    known_data_providers = set(config.data_providers.providers.keys())
    for market, chain in config.data_providers.fallback_chain.items():
        for provider_name in chain:
            if provider_name not in known_data_providers:
                raise ValueError(
                    f"fallback_chain.{market} references unknown provider "
                    f"'{provider_name}'. Known providers: {known_data_providers}"
                )

    # Check pipeline agents → agent references
    known_agents = set(config.agents.keys())
    for pipeline_name, pipeline in config.pipelines.items():
        for phase_name, phase in pipeline.phases.items():
            for agent_name in phase.agents:
                if agent_name not in known_agents:
                    raise ValueError(
                        f"pipeline '{pipeline_name}' phase '{phase_name}' "
                        f"references unknown agent '{agent_name}'. "
                        f"Known agents: {known_agents}"
                    )


class LLMRegistry:
    """Resolves agent_name → LangChain ChatModel instance."""

    def __init__(self, config: Config):
        self._config = config
        self._models: dict[str, object] = {}  # agent_name → ChatModel

    def get_model(self, agent_name: str):
        """Get or create the ChatModel for a given agent."""
        if agent_name in self._models:
            return self._models[agent_name]

        agent_cfg = self._config.agents.get(agent_name)
        if agent_cfg is None:
            # Fall back to default quick provider
            provider_id = "provider_quick"
        else:
            provider_id = agent_cfg.llm

        provider_cfg = self._config.llm_providers[provider_id]
        api_key = resolve_api_key(provider_cfg.api_key_source)

        model = self._build_model(provider_cfg, api_key)
        self._models[agent_name] = model
        return model

    def _build_model(self, provider_cfg, api_key: Optional[str]):
        """Build the appropriate LangChain ChatModel based on provider."""
        provider = provider_cfg.provider

        if provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=provider_cfg.model,
                temperature=provider_cfg.temperature,
                max_tokens=provider_cfg.max_tokens,
                timeout=provider_cfg.timeout_seconds,
                api_key=api_key,
            )

        elif provider == "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=provider_cfg.model,
                temperature=provider_cfg.temperature,
                max_tokens=provider_cfg.max_tokens,
                timeout=provider_cfg.timeout_seconds,
                api_key=api_key,
                base_url=provider_cfg.base_url,
            )

        elif provider == "deepseek":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=provider_cfg.model,
                temperature=provider_cfg.temperature,
                max_tokens=provider_cfg.max_tokens,
                timeout=provider_cfg.timeout_seconds,
                api_key=api_key,
                base_url=provider_cfg.base_url or "https://api.deepseek.com/v1",
            )

        elif provider == "ollama":
            from langchain_ollama import ChatOllama

            return ChatOllama(
                model=provider_cfg.model,
                temperature=provider_cfg.temperature,
                base_url=provider_cfg.base_url or "http://localhost:11434",
            )

        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
