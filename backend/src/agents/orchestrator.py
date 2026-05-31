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
    def __init__(self, task_id: str, ticker: str, company_name: str,
                 report_type: str, template_id: str, config: Config):
        self.task_id = task_id
        self.ticker = ticker
        self.company_name = company_name
        self.report_type = report_type
        self.template_id = template_id
        self.config = config
        self.state: dict = {}  # Phase outputs accumulate here
        self.errors: list[dict] = []
        self.progress_callback: Optional[Callable[[str, int, str], Awaitable[None]]] = None
        self.created_at = datetime.now()

    async def set_progress(self, phase: str, pct: int, message: str):
        """Record progress; if callback is set, await it."""
        logger.info(f"[{self.task_id}] {phase} ({pct}%): {message}")
        if self.progress_callback:
            await self.progress_callback(phase, pct, message)


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

        template_id = context.get("preferred_template") or "deep_dive_default"
        result = {
            "pipeline_type": "deep_dive",
            "ticker": None,
            "company_name": None,
            "template_id": template_id,
            "error": None,
        }

        # Detect report type: template-based routing
        if "value_investor" in template_id:
            result["pipeline_type"] = "value_deep_dive"
        elif "quick_scan" in template_id or any(w in user_message for w in ["扫", "快", "速", "技术"]):
            result["pipeline_type"] = "quick_scan"
        elif any(w in user_message for w in ["宏观", "周报"]):
            result["pipeline_type"] = "macro_weekly"
        elif any(w in user_message for w in ["ipo", "新股", "上市"]):
            result["pipeline_type"] = "ipo"
        elif any(w in user_message for w in ["简报", "快报", "速览", "brief", "快速"]):
            result["pipeline_type"] = "brief"

        # Extract ticker pattern: 600519.SH, 000858.SZ, 0700.HK (HK: 1-5 digits)
        ticker_match = re.search(r'(\d{1,6}\.(?:SH|SZ|HK))', user_message)
        if ticker_match:
            result["ticker"] = ticker_match.group(1)
            result["company_name"] = ticker_match.group(1)
        else:
            # Try US ticker — only match standalone uppercase 2-5 letters
            # preceded by a non-alphanumeric or start, not followed by CJK chars
            us_match = re.search(r'(?<![一-鿿\w])([A-Z]{1,5})(?![一-鿿\w])', user_message)
            if us_match and us_match.group(1) not in ("HK", "SH", "SZ", "IPO", "A", "I", "AI"):
                result["ticker"] = us_match.group(1)
                result["company_name"] = us_match.group(1)

        # Try 6-digit CN stock code without suffix (002472 -> 002472.SZ, 600519 -> 600519.SH)
        if not result["ticker"]:
            cn_code = re.search(r'(\d{6})', user_message)
            if cn_code:
                code = cn_code.group(1)
                suffix = ".SH" if code.startswith("6") else ".SZ"
                result["ticker"] = code + suffix
                result["company_name"] = code + suffix

        # Try Chinese company name after action keywords
        if not result["ticker"]:
            name_match = re.search(
                r'(?:分析|看下?|研究|对比|聊聊|看看)\s*([一-鿿]{2,8}(?:公司|集团|股份|科技|银行|保险|证券|控股|实业|医药|汽车|能源|地产)?)',
                user_message
            )
            if name_match and len(name_match.group(1)) >= 2:
                result["company_name"] = name_match.group(1)
                result["ticker"] = name_match.group(1)

        # Resolve company name from ticker lookup
        if result["ticker"] and (not result["company_name"] or result["company_name"] == result["ticker"]):
            try:
                from providers.qveris_provider import COMPANY_NAMES
                name = COMPANY_NAMES.get(result["ticker"])
                if name:
                    result["company_name"] = name
                else:
                    # Try Sina HTTP for CN stock name (fast, works for all A-shares)
                    try:
                        import requests
                        code = result["ticker"].split(".")[0]
                        prefix = "sh" if code.startswith("6") else "sz"
                        r = requests.get(f"https://hq.sinajs.cn/list={prefix}{code}",
                                        headers={"Referer": "https://finance.sina.com.cn"},
                                        timeout=5)
                        if r.status_code == 200 and '="' in r.text:
                            # Format: var hq_str_sh600519="贵州茅台,1680.00,..."
                            parts = r.text.split('="')[1].split(",")
                            if parts and parts[0]:
                                result["company_name"] = parts[0]
                    except Exception:
                        pass
            except ImportError:
                pass

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
            await ctx.set_progress(phase_name, int((i / total_phases) * 100),
                             f"开始 {phase_name}")

            if phase_cfg.parallel:
                await self._run_parallel(ctx, phase_name, phase_cfg.agents)
            else:
                await self._run_serial(ctx, phase_name, phase_cfg, phase_cfg.agents)

        await ctx.set_progress("complete", 100, "报告生成完成")
        return ctx.state

    async def _run_parallel(self, ctx: AgentContext, phase: str, agent_names: list[str]):
        """Execute agents in parallel."""
        tasks = [self._run_agent(ctx, name, phase) for name in agent_names]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_serial(self, ctx: AgentContext, phase: str, phase_cfg, agent_names: list[str]):
        """Execute agents serially, respecting debate_rounds for debate phases."""
        rounds = max(1, getattr(phase_cfg, 'debate_rounds', 1) or 1)
        for _ in range(rounds):
            for name in agent_names:
                await self._run_agent(ctx, name, phase)

    async def _run_agent(self, ctx: AgentContext, agent_name: str, phase: str):
        """Execute an agent — dispatches to real implementations or logs stub."""
        agent_cfg = self.config.agents.get(agent_name)
        if not agent_cfg:
            ctx.errors.append({"agent": agent_name, "error": "unknown agent"})
            return

        logger.info(f"[{ctx.task_id}] Running agent: {agent_name} (phase={phase})")
        pct = ctx.state.get("_internal_pct", 0)
        await ctx.set_progress(phase, min(pct, 100), f"执行 {agent_name}")

        # ── Dispatch to real agent implementations ──
        result = await self._dispatch_agent(ctx, agent_name)
        ctx.state[agent_name] = {"status": "completed", "phase": phase, "result": result}

        ctx.state["_internal_pct"] = min(ctx.state.get("_internal_pct", 0) + 10, 100)

    async def _dispatch_agent(self, ctx: AgentContext, agent_name: str) -> dict:
        """Route to concrete agent implementation if available."""
        # Phase 1: Data agents
        # Phase 1: Data agents
        if agent_name == "financial_data":
            from agents.data.financial_agent import run_financial_agent
            return await run_financial_agent(
                ticker=ctx.ticker, company_name=ctx.company_name,
                financials=ctx.state.get("_financials", []),
            )
        if agent_name == "price_data":
            from agents.data.price_agent import run_price_agent
            return await run_price_agent(
                ticker=ctx.ticker, company_name=ctx.company_name,
                prices=ctx.state.get("_prices", []),
            )

        # Phase 2: Analysis agents
        if agent_name == "valuation":
            from agents.analysis.valuation_agent import run_valuation_agent
            return await run_valuation_agent(
                ticker=ctx.ticker, company_name=ctx.company_name,
                financials=ctx.state.get("_financials", []),
                prices=ctx.state.get("_prices", []),
            )

        # Phase 3a: Value investing perspective agents (段永平 + 芒格)
        if agent_name == "duan_case":
            from agents.analysis.duan_agent import run_duan_agent
            return await run_duan_agent(
                ticker=ctx.ticker, company_name=ctx.company_name,
                financial_analysis=ctx.state.get("financial_analysis", {}),
                valuation=ctx.state.get("valuation", {}),
                price_data=ctx.state.get("price_data", {}),
                corporate_governance=ctx.state.get("corporate_governance", {}),
                industry_competition=ctx.state.get("industry_competition", {}),
            )
        if agent_name == "munger_case":
            from agents.analysis.munger_agent import run_munger_agent
            return await run_munger_agent(
                ticker=ctx.ticker, company_name=ctx.company_name,
                financial_analysis=ctx.state.get("financial_analysis", {}),
                valuation=ctx.state.get("valuation", {}),
                price_data=ctx.state.get("price_data", {}),
                corporate_governance=ctx.state.get("corporate_governance", {}),
                industry_competition=ctx.state.get("industry_competition", {}),
            )
        if agent_name == "value_judge":
            from agents.analysis.value_judge_agent import run_value_judge
            duan_w = ctx.state.get("duan_case", {})
            munger_w = ctx.state.get("munger_case", {})
            val_w = ctx.state.get("valuation", {})
            fa_w = ctx.state.get("financial_analysis", {})
            return await run_value_judge(
                ticker=ctx.ticker, company_name=ctx.company_name,
                duan_result=duan_w.get("result", duan_w),
                munger_result=munger_w.get("result", munger_w),
                valuation=val_w.get("result", val_w),
                financial_analysis=fa_w.get("result", fa_w),
            )

        # Phase 3: Debate agents
        if agent_name == "bull_case":
            from agents.debate.bull_agent import run_bull_agent
            return await run_bull_agent(
                ticker=ctx.ticker, company_name=ctx.company_name,
                financial_analysis=ctx.state.get("financial_analysis", {}),
                valuation=ctx.state.get("valuation", {}),
                price_data=ctx.state.get("price_data", {}),
            )
        if agent_name == "bear_case":
            from agents.debate.bear_agent import run_bear_agent
            return await run_bear_agent(
                ticker=ctx.ticker, company_name=ctx.company_name,
                financial_analysis=ctx.state.get("financial_analysis", {}),
                valuation=ctx.state.get("valuation", {}),
                price_data=ctx.state.get("price_data", {}),
            )
        if agent_name == "risk_judge":
            from agents.debate.judge_agent import run_judge_agent
            # Unwrap agent result wrapper: {"status", "phase", "result": {...}}
            bull_w = ctx.state.get("bull_case", {})
            bear_w = ctx.state.get("bear_case", {})
            val_w = ctx.state.get("valuation", {})
            return await run_judge_agent(
                ticker=ctx.ticker, company_name=ctx.company_name,
                bull_result=bull_w.get("result", bull_w),
                bear_result=bear_w.get("result", bear_w),
                valuation=val_w.get("result", val_w),
            )

        # Phase 2: Analysis agents
        if agent_name == "financial_analysis":
            from agents.analysis.financial_analysis_agent import run_financial_analysis_agent
            return await run_financial_analysis_agent(
                ticker=ctx.ticker, company_name=ctx.company_name,
                financials=ctx.state.get("_financials", []),
                prices=ctx.state.get("_prices", []),
            )
        if agent_name == "industry_competition":
            from agents.analysis.industry_agent import run_industry_agent
            return await run_industry_agent(
                ticker=ctx.ticker, company_name=ctx.company_name,
                financials=ctx.state.get("_financials", []),
                prices=ctx.state.get("_prices", []),
            )
        if agent_name == "corporate_governance":
            from agents.analysis.governance_agent import run_governance_agent
            return await run_governance_agent(
                ticker=ctx.ticker, company_name=ctx.company_name,
                financials=ctx.state.get("_financials", []),
                prices=ctx.state.get("_prices", []),
            )

        # Phase 1: Remaining data agents
        if agent_name == "news_data":
            from agents.data.news_agent import run_news_agent
            return await run_news_agent(ticker=ctx.ticker, company_name=ctx.company_name)
        if agent_name == "macro_data":
            from agents.data.macro_agent import run_macro_agent
            return await run_macro_agent(ticker=ctx.ticker, company_name=ctx.company_name)

        # Quick scan agents
        if agent_name == "tech_indicators":
            from agents.data.tech_indicators_agent import run_tech_indicators
            return await run_tech_indicators(
                ticker=ctx.ticker, company_name=ctx.company_name,
                prices=ctx.state.get("_prices", []),
            )
        if agent_name == "fund_flow":
            from agents.data.fund_flow_agent import run_fund_flow
            return await run_fund_flow(
                ticker=ctx.ticker, company_name=ctx.company_name,
                prices=ctx.state.get("_prices", []),
            )
        if agent_name == "quick_summary":
            from agents.assembly.quick_summary_agent import run_quick_summary
            return await run_quick_summary(
                ticker=ctx.ticker, company_name=ctx.company_name,
                ctx_state=ctx.state,
            )

        # Phase 4: Assembly agents
        if agent_name == "section_writer":
            from agents.assembly.section_writer_agent import run_section_writer
            return await run_section_writer(
                ticker=ctx.ticker, company_name=ctx.company_name,
                ctx_state=ctx.state,
                template_id=ctx.template_id,
            )
        if agent_name == "chart_generator":
            from agents.assembly.chart_agent import run_chart_agent
            return await run_chart_agent(
                ticker=ctx.ticker, company_name=ctx.company_name,
                prices=ctx.state.get("_prices", []),
                financials=ctx.state.get("_financials", []),
                ctx_state=ctx.state,
            )
        if agent_name == "title_summary":
            from agents.assembly.summary_agent import run_summary_agent
            return await run_summary_agent(
                ticker=ctx.ticker, company_name=ctx.company_name,
                ctx_state=ctx.state,
            )

        return {"note": f"Agent '{agent_name}' not yet implemented (stub)"}


# ── Top-level entry point ──

_orchestrator: Optional[Orchestrator] = None


def get_orchestrator(config: Optional[Config] = None) -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator(config)
    return _orchestrator
