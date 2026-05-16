"""Orchestrator Agent — intent routing, pipeline dispatch, progress tracking.

This is the central agent that:
1. Parses user messages to extract ticker/company name and report type
2. Routes to the correct pipeline
3. Executes phases in order, respecting parallel/serial config
4. Emits SSE progress events
5. Handles errors and fallbacks
"""

import asyncio
import logging
import time
from datetime import date, datetime
from typing import Optional, Callable, Awaitable
from uuid import UUID, uuid4

from config.loader import load_config
from config.schema import Config

logger = logging.getLogger(__name__)


class AgentContext:
    """Shared context passed through the agent pipeline."""
    def __init__(self, task_id: Optional[UUID], ticker: str, company_name: str,
                 report_type: str, template_id: str, config: Config):
        self.task_id = task_id or uuid4()
        self.ticker = ticker
        self.company_name = company_name
        self.report_type = report_type
        self.template_id = template_id
        self.config = config
        self.state: dict = {}  # Phase outputs accumulate here
        self.errors: list[dict] = []
        self.progress_callback: Optional[Callable[[str, int, str], Awaitable[None]]] = None
        self.created_at = datetime.now()

    def set_progress(self, phase: str, pct: int, message: str):
        """Record progress; if callback is set, invoke it asynchronously."""
        logger.info(f"[{self.task_id}] {phase} ({pct}%): {message}")
        if self.progress_callback:
            asyncio.ensure_future(self.progress_callback(phase, pct, message))


class Orchestrator:
    """Main orchestrator that routes user messages → pipeline execution."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or load_config()

    async def route(self, user_message: str, context: dict) -> dict:
        """Parse user intent and return a TaskSpec.

        Args:
            user_message: Raw user message text.
            context: Extra context (e.g. uploaded_files, preferred_template).

        Returns:
            dict with keys: pipeline_type, ticker, company_name, template_id, error (if any).
        """
        import re

        result = {
            "pipeline_type": "deep_dive",
            "ticker": None,
            "company_name": None,
            "template_id": context.get("preferred_template") or "deep_dive_default",
            "error": None,
        }

        # Detect report type from message
        if any(w in user_message for w in ["简报", "快报", "速览", "brief", "看下", "快速"]):
            result["pipeline_type"] = "brief"
        elif any(w in user_message for w in ["宏观", "周报"]):
            result["pipeline_type"] = "macro_weekly"
        elif any(w in user_message for w in ["ipo", "新股", "上市"]):
            result["pipeline_type"] = "ipo"

        # Extract ticker pattern: 600519.SH, AAPL, 0700.HK, etc.
        ticker_match = re.search(r'(\d{6}\.(?:SH|SZ|HK))', user_message)
        if ticker_match:
            result["ticker"] = ticker_match.group(1)
            result["company_name"] = ticker_match.group(1)
        else:
            # Try US ticker
            us_match = re.search(r'\b([A-Z]{1,5})\b', user_message)
            if us_match and us_match.group(1) not in ("HK", "SH", "SZ", "IPO"):
                result["ticker"] = us_match.group(1)
                result["company_name"] = us_match.group(1)

        # Try Chinese company name after action keywords
        if not result["ticker"]:
            name_match = re.search(
                r'(?:分析|看下?|研究|对比|聊聊|看看)\s*([一-鿿]{2,8}(?:公司|集团|股份|科技|银行|保险|证券|控股|实业|医药|汽车|能源|地产)?)',
                user_message
            )
            if name_match and len(name_match.group(1)) >= 2:
                result["company_name"] = name_match.group(1)
                result["ticker"] = name_match.group(1)

        if not result["ticker"] and not result["company_name"]:
            result["error"] = "无法识别公司名称或股票代码，请提供具体的公司名或代码（如 600519.SH 或 贵州茅台）"

        return result

    async def execute_pipeline(self, ctx: AgentContext) -> dict:
        """Execute the full report generation pipeline.

        Phases are read from config; parallel phases run agents concurrently.
        """
        pipeline = self.config.pipelines.get(ctx.report_type)
        if not pipeline:
            raise ValueError(f"Unknown pipeline: {ctx.report_type}")

        total_phases = len(pipeline.phases)
        for i, (phase_name, phase_cfg) in enumerate(pipeline.phases.items()):
            ctx.set_progress(phase_name, int((i / total_phases) * 100),
                             f"开始 {phase_name}")

            if phase_cfg.parallel:
                await self._run_parallel(ctx, phase_name, phase_cfg.agents)
            else:
                await self._run_serial(ctx, phase_name, phase_cfg, phase_cfg.agents)

        ctx.set_progress("complete", 100, "报告生成完成")
        return ctx.state

    async def _run_parallel(self, ctx: AgentContext, phase: str, agent_names: list[str]):
        """Execute agents in parallel."""
        tasks = [self._run_agent(ctx, name, phase) for name in agent_names]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_serial(self, ctx: AgentContext, phase: str, phase_cfg, agent_names: list[str]):
        """Execute agents serially (used for debate phases)."""
        for name in agent_names:
            await self._run_agent(ctx, name, phase)

    async def _run_agent(self, ctx: AgentContext, agent_name: str, phase: str):
        """Execute a single agent. In MVP, this is a stub that logs.

        Actual LLM invocation will be wired in when agent modules are built.
        """
        agent_cfg = self.config.agents.get(agent_name)
        if not agent_cfg:
            ctx.errors.append({"agent": agent_name, "error": "unknown agent"})
            return

        logger.info(f"[{ctx.task_id}] Running agent: {agent_name} (phase={phase})")
        ctx.set_progress(phase, ctx.state.get("_internal_pct", 50),
                         f"执行 {agent_name}")

        # Placeholder: in real implementation, this calls the agent's
        # LLM-backed function and stores results in ctx.state.
        ctx.state[agent_name] = {"status": "completed", "phase": phase}

        # Update internal progress
        ctx.state["_internal_pct"] = ctx.state.get("_internal_pct", 0) + 10


# ── Top-level entry point ──

_orchestrator: Optional[Orchestrator] = None


def get_orchestrator(config: Optional[Config] = None) -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator(config)
    return _orchestrator
