"""T01: Configuration system tests — TDD: RED → GREEN → REFACTOR."""

import json
import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

# pytest config sets pythonpath=src, so imports are relative to src/
from config.schema import Config, LLMProviderConfig, DataProviderConfig
from config.loader import resolve_api_key, validate_config_references, LLMRegistry


class TestConfigSchema:
    def test_load_minimal_config(self):
        """Given: simplest valid config JSON
           When: Config.model_validate_json(json_str)
           Then: Config object with version="1.0" """
        minimal = json.dumps({
            "version": "1.0",
            "global": {"language": "zh-CN", "data_priority": "local_first"},
            "llm_providers": {},
            "data_providers": {"providers": {}, "fallback_chain": {}},
            "pipelines": {},
            "agents": {},
        })
        config = Config.model_validate_json(minimal)
        assert config.version == "1.0"
        assert config.global_.language == "zh-CN"

    def test_missing_required_version_raises_error(self):
        """Given: JSON missing required 'version' field
           When: Config.model_validate_json(json_str)
           Then: ValidationError"""
        bad_json = json.dumps({
            "global": {"language": "zh-CN", "data_priority": "local_first"},
            "llm_providers": {},
            "data_providers": {"providers": {}, "fallback_chain": {}},
            "pipelines": {},
            "agents": {},
        })
        with pytest.raises(ValidationError):
            Config.model_validate_json(bad_json)

    def test_llm_provider_resolves_env_var(self):
        """Given: api_key_source="env:MY_KEY" and env var MY_KEY=sk-xxx
           When: call resolve_api_key()
           Then: returns "sk-xxx" """
        with patch.dict(os.environ, {"MY_KEY": "sk-abc123"}):
            provider = LLMProviderConfig(
                provider="anthropic",
                model="claude-opus-4-7",
                api_key_source="env:MY_KEY",
            )
            assert resolve_api_key(provider.api_key_source) == "sk-abc123"

    def test_data_provider_orders_by_priority(self):
        """Given: 3 data providers with priorities 2, 1, 3
           When: sorted by priority
           Then: ascending order [1, 2, 3]"""
        providers = [
            DataProviderConfig(priority=2, markets=["CN"], timeout_seconds=30, retry_count=3),
            DataProviderConfig(priority=1, markets=["CN"], timeout_seconds=30, retry_count=3),
            DataProviderConfig(priority=3, markets=["CN"], timeout_seconds=30, retry_count=3),
        ]
        sorted_ps = sorted(providers, key=lambda p: p.priority)
        assert sorted_ps[0].priority == 1
        assert sorted_ps[1].priority == 2
        assert sorted_ps[2].priority == 3

    def test_invalid_llm_provider_name_raises_error(self):
        """Given: agent referencing non-existent llm_provider_id
           When: validate_config_references()
           Then: ValueError"""
        config_json = json.dumps({
            "version": "1.0",
            "global": {"language": "zh-CN", "data_priority": "local_first"},
            "llm_providers": {
                "provider_deep": {
                    "provider": "anthropic",
                    "model": "claude-opus-4-7",
                    "api_key_source": "env:KEY",
                }
            },
            "data_providers": {"providers": {}, "fallback_chain": {}},
            "pipelines": {},
            "agents": {
                "test_agent": {
                    "llm": "nonexistent_provider",
                    "output_schema": "TestOutput",
                    "timeout_seconds": 120,
                }
            },
        })
        config = Config.model_validate_json(config_json)
        with pytest.raises(ValueError, match="unknown llm_provider"):
            validate_config_references(config)

    def test_fallback_chain_references_valid_providers(self):
        """Given: fallback_chain referencing non-existent provider
           When: validate_config_references()
           Then: ValueError"""
        config_json = json.dumps({
            "version": "1.0",
            "global": {"language": "zh-CN", "data_priority": "local_first"},
            "llm_providers": {},
            "data_providers": {
                "providers": {
                    "akshare": {
                        "enabled": True,
                        "priority": 1,
                        "markets": ["CN"],
                        "timeout_seconds": 30,
                        "retry_count": 3,
                    }
                },
                "fallback_chain": {"CN": ["nonexistent_provider"]},
            },
            "pipelines": {},
            "agents": {},
        })
        config = Config.model_validate_json(config_json)
        with pytest.raises(ValueError, match="fallback_chain"):
            validate_config_references(config)

    def test_pipeline_agents_reference_valid_agents(self):
        """Given: pipeline referencing non-existent agent
           When: validate_config_references()
           Then: ValueError"""
        config_json = json.dumps({
            "version": "1.0",
            "global": {"language": "zh-CN", "data_priority": "local_first"},
            "llm_providers": {},
            "data_providers": {"providers": {}, "fallback_chain": {}},
            "pipelines": {
                "test_pipeline": {
                    "name": "Test",
                    "phases": {
                        "phase_1": {"parallel": True, "agents": ["fake_agent"]}
                    },
                }
            },
            "agents": {},
        })
        config = Config.model_validate_json(config_json)
        with pytest.raises(ValueError, match="pipeline.*unknown agent"):
            validate_config_references(config)


class TestLLMRegistry:
    def test_resolve_anthropic_model_requires_env_key(self):
        """Given: agent config with provider=anthropic but no API key
           When: get_model()
           Then: model is created (may fail without key, but registry works)"""
        config_json = json.dumps({
            "version": "1.0",
            "global": {"language": "zh-CN", "data_priority": "local_first"},
            "llm_providers": {
                "provider_deep": {
                    "provider": "anthropic",
                    "model": "claude-opus-4-7",
                    "temperature": 0.3,
                    "max_tokens": 16000,
                    "api_key_source": "env:ANTHROPIC_API_KEY",
                    "timeout_seconds": 120,
                }
            },
            "data_providers": {"providers": {}, "fallback_chain": {}},
            "pipelines": {},
            "agents": {
                "test_agent": {
                    "llm": "provider_deep",
                    "output_schema": "TestOutput",
                    "timeout_seconds": 120,
                }
            },
        })
        config = Config.model_validate_json(config_json)
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}):
            registry = LLMRegistry(config)
            model = registry.get_model("test_agent")
            assert model is not None
            assert hasattr(model, "model") or hasattr(model, "model_name")
