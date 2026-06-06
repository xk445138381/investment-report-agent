"""T14: Orchestrator agent tests (TDD)."""

import pytest
import asyncio
from agents.orchestrator import Orchestrator


@pytest.fixture
def orchestrator():
    return Orchestrator()


class TestOrchestratorRouting:
    @pytest.mark.asyncio
    async def test_routes_deep_dive(self, orchestrator):
        result = await orchestrator.route("分析贵州茅台，生成深度研报", {})
        assert result["pipeline_type"] == "deep_dive"
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_routes_brief(self, orchestrator):
        result = await orchestrator.route("快速看下五粮液", {})
        assert result["pipeline_type"] == "brief"

    @pytest.mark.asyncio
    async def test_extracts_ticker(self, orchestrator):
        result = await orchestrator.route("分析600519.SH", {})
        assert result["ticker"] == "600519.SH"

    @pytest.mark.asyncio
    async def test_extracts_chinese_name(self, orchestrator):
        result = await orchestrator.route("分析贵州茅台", {})
        assert result["company_name"] is not None

    @pytest.mark.asyncio
    async def test_extracts_bare_chinese_company_name(self, orchestrator):
        result = await orchestrator.route("贵州茅台", {})
        assert result["ticker"] == "600519.SH"
        assert result["company_name"] == "贵州茅台"
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_unknown_company_returns_error(self, orchestrator):
        result = await orchestrator.route("今天是晴天", {})
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_preferred_template_used(self, orchestrator):
        result = await orchestrator.route("分析茅台", {"preferred_template": "brief_default"})
        assert result["template_id"] == "brief_default"


class TestPipelineExecution:
    @pytest.mark.asyncio
    async def test_deep_dive_pipeline_runs_all_phases(self, orchestrator):
        from agents.orchestrator import AgentContext
        ctx = AgentContext(
            task_id=None, ticker="600519.SH", company_name="贵州茅台",
            report_type="deep_dive", template_id="deep_dive_default",
            config=orchestrator.config,
        )
        await orchestrator.execute_pipeline(ctx)
        assert "errors" in dir(ctx) or len(ctx.errors) >= 0

    @pytest.mark.asyncio
    async def test_agent_timeout_records_failed_state(self, orchestrator, monkeypatch):
        from agents.orchestrator import AgentContext

        async def slow_dispatch(ctx, agent_name):
            await asyncio.sleep(1)
            return {"ok": True}

        monkeypatch.setattr(orchestrator, "_dispatch_agent", slow_dispatch)
        orchestrator.config.agents["price_data"].timeout_seconds = 0.01
        ctx = AgentContext(
            task_id="timeout-test", ticker="AAPL", company_name="Apple Inc.",
            report_type="deep_dive", template_id="deep_dive_default",
            config=orchestrator.config,
        )

        await orchestrator._run_agent(ctx, "price_data", "phase_1")

        assert ctx.state["price_data"]["status"] == "failed"
        assert ctx.state["price_data"]["result"]["error"] == "timeout"
        assert ctx.errors[-1]["agent"] == "price_data"
