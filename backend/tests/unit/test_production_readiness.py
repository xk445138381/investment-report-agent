import pytest

from api.main import _readiness_status
from api.main import _mongodb_readiness_status
from api.routes.config_routes import _runtime_config_writes_allowed


def test_readiness_requires_production_env_vars(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("REQUIRED_ENV_VARS", "SECRET_KEY,DEEPSEEK_API_KEY,QVERIS_API_KEY")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("QVERIS_API_KEY", raising=False)

    status = _readiness_status()

    assert status["status"] == "not_ready"
    assert "missing_env:SECRET_KEY" in status["errors"]
    assert "missing_env:DEEPSEEK_API_KEY" in status["errors"]
    assert "missing_env:QVERIS_API_KEY" in status["errors"]
    assert "unsafe_secret_key" in status["errors"]


def test_readiness_passes_with_required_production_env_vars(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("REQUIRED_ENV_VARS", "SECRET_KEY,DEEPSEEK_API_KEY,QVERIS_API_KEY")
    monkeypatch.setenv("SECRET_KEY", "prod-secret-that-is-not-a-placeholder")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setenv("QVERIS_API_KEY", "qveris-key")

    status = _readiness_status()

    assert status["status"] == "ok"
    assert status["errors"] == []


def test_runtime_config_writes_disabled_by_default_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("ENABLE_RUNTIME_CONFIG_WRITES", raising=False)

    assert _runtime_config_writes_allowed() is False


def test_runtime_config_writes_can_be_enabled_explicitly(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ENABLE_RUNTIME_CONFIG_WRITES", "true")

    assert _runtime_config_writes_allowed() is True


def test_readiness_exposes_mongodb_required_flag(monkeypatch):
    monkeypatch.setenv("REQUIRE_MONGODB", "true")

    status = _readiness_status()

    assert status["checks"]["mongodb_required"] is True


@pytest.mark.asyncio
async def test_mongodb_readiness_skips_when_not_required(monkeypatch):
    monkeypatch.delenv("REQUIRE_MONGODB", raising=False)

    ok, error = await _mongodb_readiness_status()

    assert ok is True
    assert error is None
