"""Report Engine — LLM-driven report generation with structured context.

Replaces the old if-else template approach.
Each section is written by LLM with full context, then self-reviewed.
"""

import json
import asyncio
import logging
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)


VALUE_SECTION_TITLES = {
    "executive_summary": "投资判定与摘要",
    "business_model": "商业模式分析",
    "corporate_character": "企业文化与本分",
    "financial_health": "财务健康评估",
    "valuation": "估值与安全边际",
    "inversion_checklist": "逆向风险清单",
    "dual_verdict": "双视角裁决",
    "final_judgment": "综合判定",
}


# ── Structured Context ──────────────────────────────────────────

class CompanyContext:
    """All data about a company, structured for LLM consumption."""
    
    def __init__(self, ticker: str, company_name: str):
        self.ticker = ticker
        self.name = company_name
        self.market = "CN" if ".SH" in ticker or ".SZ" in ticker else "HK" if ".HK" in ticker else "US"
        
        # Raw financial data
        self.price_summary: dict = {}
        self.financial_ratios: dict = {}
        self.financial_score: dict = {}
        self.financial_raw: list = []
        self.price_history: list = []
        
        # Valuation data
        self.valuation_models: dict = {}
        self.weighted_value: float = 0
        self.upside_pct: float = 0
        self.current_price: float = 0
        self.sensitivity_matrix: dict = {}
        
        # Industry data
        self.industry_name: str = ""
        self.industry_avg_roe: Optional[float] = None
        self.industry_avg_pe: Optional[float] = None
        self.industry_companies: int = 0
        
        # Governance
        self.ownership: str = ""
        self.management: str = ""
        
        # News & macro
        self.news: list = []
        self.macro: dict = {}
        
        # Agent text outputs (full text)
        self.duan_analysis: str = ""
        self.duan_verdict: str = ""
        self.munger_analysis: str = ""
        self.munger_verdict: str = ""
        self.judge_verdict: str = ""
        self.judge_consensus: str = ""
        self.judge_disagreement: str = ""
        
        # Data quality
        self.data_sources: dict = {}
        self.data_quality: dict = {}
    
    def to_llm_context(self) -> str:
        """Serialize the full context for LLM consumption.
        
        The LLM gets ALL relevant data in a structured format,
        not individual parameters passed to template functions.
        """
        parts = []
        parts.append(f"## 公司概览\n股票: {self.ticker} ({self.name}), 市场: {self.market}")
        
        # Price context
        if self.price_summary:
            p = self.price_summary
            parts.append(f"\n## 市场行情\n"
                        f"最新价: {p.get('latest_price', 'N/A')}\n"
                        f"52周最高: {p.get('52w_high', 'N/A')} | 52周最低: {p.get('52w_low', 'N/A')}\n"
                        f"1月回报: {p.get('returns', {}).get('1m', 'N/A')}%\n"
                        f"1年回报: {p.get('returns', {}).get('1y', 'N/A')}%\n"
                        f"年化波动: {p.get('annualized_volatility', 'N/A')}%\n"
                        f"最大回撤(1年): {p.get('max_drawdown_1y', 'N/A')}%")
        
        # Financial ratios
        if self.financial_ratios:
            r = self.financial_ratios
            lines = ["\n## 核心财务指标"]
            lines.append(f"ROE: {r.get('roe', 'N/A')}")
            lines.append(f"ROA: {r.get('roa', 'N/A')}")
            lines.append(f"毛利率: {r.get('gross_margin', 'N/A')}")
            lines.append(f"净利润率: {r.get('net_margin', 'N/A')}")
            lines.append(f"营收增长 YoY: {r.get('revenue_growth_yoy', 'N/A')}")
            lines.append(f"净利润增长 YoY: {r.get('earnings_growth_yoy', 'N/A')}")
            lines.append(f"FCF/净利润: {r.get('fcf_to_net_income', 'N/A')}")
            lines.append(f"负债权益比: {r.get('debt_to_equity', 'N/A')}")
            lines.append(f"流动比率: {r.get('current_ratio', 'N/A')}")
            lines.append(f"经营现金流/营收: {r.get('ocf_to_revenue', 'N/A')}")
            parts.append("\n".join(lines))
        
        # Financial score
        if self.financial_score:
            s = self.financial_score
            parts.append(f"\n## 财务健康评分\n"
                        f"综合评分: {s.get('total', 'N/A')}/{s.get('max', 'N/A')}\n"
                        f"评级: {s.get('rating', 'N/A')}")
        
        # Valuation
        parts.append(f"\n## 估值分析\n"
                    f"当前价格: {self.current_price}\n"
                    f"加权内在价值: {self.weighted_value}\n"
                    f"上行/下行空间: {self.upside_pct}%\n"
                    f"估值信号: {self.valuation_models.get('signal', 'N/A')}")
        if self.valuation_models:
            models = self.valuation_models
            dcf = models.get('dcf', {}).get('per_share_value', 'N/A')
            oe = models.get('owner_earnings', {}).get('per_share_value', 'N/A')
            ev = models.get('ev_ebitda', {}).get('per_share_value', 'N/A')
            parts.append(f"DCF: {dcf} | Owner Earnings: {oe} | EV/EBITDA: {ev}")
        
        # Industry comparison
        if self.industry_name:
            parts.append(f"\n## 行业对比\n"
                        f"行业: {self.industry_name}\n"
                        f"行业平均 ROE: {self.industry_avg_roe or 'N/A'}\n"
                        f"行业内公司数: {self.industry_companies or 'N/A'}")
        
        # Data quality
        if self.data_sources:
            parts.append(f"\n## 数据源\n"
                        f"行情: {self.data_sources.get('prices', 'unknown')}\n"
                        f"财报: {self.data_sources.get('financials', 'unknown')}")
        
        if self.macro:
            m = self.macro
            items = [f"{k}: {v}" for k, v in m.items() if v is not None and v != ""]
            if items:
                parts.append(f"\n## 宏观环境\n" + "\n".join(items))
        
        if self.news:
            parts.append(f"\n## 近期新闻 ({len(self.news)} 条)\n"
                        + "\n".join([f"- {n.get('title','')} ({n.get('date','')[:10]})" for n in self.news[:5]]))
        
        # Agent perspectives (full text)
        if self.duan_analysis:
            parts.append(f"\n## 段永平视角分析（原文）\n{self.duan_analysis[:1500]}")
        if self.munger_analysis:
            parts.append(f"\n## 芒格视角分析（原文）\n{self.munger_analysis[:1500]}")
        if self.judge_verdict:
            parts.append(f"\n## 双视角裁决\n裁决: {self.judge_verdict}\n"
                        f"共识: {self.judge_consensus}\n"
                        f"分歧: {self.judge_disagreement}")
        
        return "\n\n".join(parts)


# ── Report Writer ────────────────────────────────────────────────

async def write_report(ticker: str, company_name: str, ctx_state: dict, template_id: str = "deep_dive_default") -> dict:
    """Main entry point: write a complete report using LLM.
    
    Unlike the old approach (if-else templates), this builds a structured
    CompanyContext and lets the LLM write each section with full context.
    """
    # Build context
    ctx = _build_context(ticker, company_name, ctx_state)
    context_str = ctx.to_llm_context()
    
    # Route to value template
    if "value_investor" in template_id:
        return await _write_value_report(ctx, context_str, ctx_state)
    
    return await _write_deep_dive_report(ctx, context_str)


def _build_context(ticker: str, name: str, state: dict) -> CompanyContext:
    """Build a CompanyContext from the raw agent state."""
    ctx = CompanyContext(ticker, name)
    
    # Price data
    price_data = state.get("price_data", {}).get("result", {})
    ctx.price_summary = price_data.get("price_summary", {})
    ctx.current_price = ctx.price_summary.get("latest_price", 0)
    ctx.price_history = state.get("_prices", [])
    
    # Financial data
    fin = state.get("financial_data", {}).get("result", {})
    ctx.financial_ratios = fin.get("ratios", {})
    ctx.financial_raw = state.get("_financials", [])
    
    # Financial analysis
    fa = state.get("financial_analysis", {}).get("result", {})
    ctx.financial_score = fa.get("financial_health_score", {})
    if not ctx.financial_ratios:
        ctx.financial_ratios = fa.get("ratios", {})
    
    # Valuation
    val = state.get("valuation", {}).get("result", {})
    ctx.valuation_models = val
    ctx.weighted_value = val.get("weighted_value", 0)
    ctx.upside_pct = val.get("weighted_upside_pct", 0)
    ctx.sensitivity_matrix = val.get("sensitivity_matrix", {})
    if not ctx.current_price:
        ctx.current_price = val.get("current_price", 0)
    
    # Industry
    ind = state.get("industry_competition", {}).get("result", {})
    ctx.industry_name = ind.get("shenwan_l1", "")
    ctx.industry_avg_roe = ind.get("industry_roe")
    ctx.industry_companies = ind.get("company_count", 0)
    
    # Governance
    gov = state.get("corporate_governance", {}).get("result", {})
    ctx.ownership = gov.get("ownership_structure", "")
    
    # News & macro
    ctx.news = state.get("news_data", {}).get("result", {}).get("recent_events", [])
    ctx.macro = state.get("macro_data", {}).get("result", {}).get("macro", {})
    
    # Perspectives
    duan = state.get("duan_case", {}).get("result", {})
    ctx.duan_analysis = duan.get("analysis", "")
    ctx.duan_verdict = duan.get("verdict", "")
    
    munger = state.get("munger_case", {}).get("result", {})
    ctx.munger_analysis = munger.get("analysis", "")
    ctx.munger_verdict = munger.get("verdict", "")
    
    vjudge = state.get("value_judge", {}).get("result", {})
    ctx.judge_verdict = vjudge.get("verdict", "")
    ctx.judge_consensus = vjudge.get("consensus", "")
    ctx.judge_disagreement = vjudge.get("disagreement", "")
    
    # Data sources
    ctx.data_sources = state.get("_data_sources", {})
    ctx.data_quality = state.get("_confidence", {}).get("data_confidence", {})
    
    return ctx


async def _call_llm(prompt: str, timeout: int = 120) -> str:
    """Call LLM via subprocess in a thread pool (non-blocking)."""
    import os
    import asyncio
    from agents.analysis.llm_subprocess import call_llm
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
    if not api_key:
        return ""
    # Run blocking subprocess in thread pool to keep event loop responsive
    result = await asyncio.to_thread(call_llm, api_key, base_url, model, prompt, timeout)
    return result or ""


async def _write_value_report(ctx: CompanyContext, context_str: str, state: dict) -> dict:
    """Write the 8-chapter value investing report using LLM.
    
    Uses 2 LLM calls max: 1 for content, 1 for review (optional).
    Each call has a strict timeout to prevent server lockup.
    """
    # Call 1: Generate complete report (single prompt for all sections)
    full_prompt = _FULL_REPORT_PROMPT.format(
        context=context_str,
        name=ctx.name,
        ticker=ctx.ticker,
        duan=ctx.duan_analysis[:1500],
        munger=ctx.munger_analysis[:1500],
        verdict=ctx.judge_verdict,
    )
    
    full_report = ""
    total_timeout = 180  # 3 min max for the whole generation
    try:
        full_report = await asyncio.wait_for(
            _call_llm(full_prompt, timeout=total_timeout),
            timeout=total_timeout + 10
        )
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning(f"Report generation timeout/error: {e}")
        full_report = f"报告生成超时。使用可用数据生成摘要：\n{ctx.name}({ctx.ticker}) 当前价格 {ctx.current_price}，加权内在价值 {ctx.weighted_value}，{ctx.upside_pct}% 空间。"
    
    # Call 2: Self-review (only if report was generated, short timeout)
    review = ""
    if full_report and len(full_report) > 200:
        try:
            review = await asyncio.wait_for(
                _call_llm(_REVIEW_PROMPT.format(context=context_str[:500], report=full_report[:2000]), timeout=20),
                timeout=25
            )
        except asyncio.TimeoutError:
            review = "⏱ 已跳过"
    
    # Extract structured data
    verdict = "HOLD"
    conf = 50
    import re
    v_match = re.search(r'(Yes|No|Too Hard|STRONG_BUY|BUY|SELL)', full_report)
    if v_match: verdict = v_match.group(1)
    c_match = re.search(r'置信度[：:]\s*(\d+)', full_report)
    if c_match: conf = int(c_match.group(1))
    
    # Parse sections from combined report
    sections = _parse_sections(full_report, ctx)
    
    return {
        "_llm_used": True,
        "_verdict": verdict,
        "_confidence": conf,
        "_review": review,
        "sections": sections,
        "report_title": f"{ctx.name}（{ctx.ticker}）— 价值投资视角",
        "report_subtitle": f"段永平 × 芒格 双重视角 | {date.today().strftime('%Y年%m月')}",
        "report_date": date.today().isoformat(),
    }


def _parse_sections(report: str, ctx: CompanyContext) -> dict:
    """Parse the combined LLM report into structured sections."""
    import re
    
    # Split by numbered markdown headers
    parts = re.split(r'\n(?:#{1,3}\s*|\d+\.\s*\*{0,2})', report)
    parts = [p.strip() for p in parts if len(p.strip()) > 50]
    
    sections = {}
    
    # Try to identify each section by content
    section_map = {
        "executive_summary": ["投资判定", "摘要", "Yes", "No", "Too Hard"],
        "business_model": ["商业", "模式", "护城河", "竞争", "怎么赚钱"],
        "corporate_character": ["文化", "本分", "管理层", "治理", "激励", "资本配置"],
        "financial_health": ["财务", "健康", "现金流", "ROE", "负债"],
        "valuation": ["估值", "安全边际", "买价", "内在价值"],
        "inversion_checklist": ["逆向", "风险", "怎么死", "芒格", "清单"],
        "dual_verdict": ["段永平", "芒格", "裁决", "视角", "共识"],
        "final_judgment": ["综合判定", "判定", "仓位", "重新评估", "买入", "重仓"],
    }
    
    for part in parts:
        best_key = None
        best_score = 0
        for key, keywords in section_map.items():
            score = sum(1 for kw in keywords if kw in part[:200])
            if score > best_score:
                best_score = score
                best_key = key
        
        if best_key and best_score >= 2:
            sections[best_key] = {
                "title": VALUE_SECTION_TITLES.get(best_key, best_key),
                "content": part[:2500],
            }
    
    # Ensure at least executive_summary exists
    if "executive_summary" not in sections and report:
        sections["executive_summary"] = {
            "title": VALUE_SECTION_TITLES["executive_summary"],
            "content": report[:1500],
        }
    
    _ensure_value_sections(sections, ctx)
    return sections


def _ensure_value_sections(sections: dict, ctx: CompanyContext) -> None:
    """Keep the value-investor report contract at 8 sections."""
    for section_id, title in VALUE_SECTION_TITLES.items():
        if section_id in sections:
            continue
        sections[section_id] = {
            "title": title,
            "content": _fallback_value_section(section_id, ctx),
        }


def _fallback_value_section(section_id: str, ctx: CompanyContext) -> str:
    if section_id == "corporate_character":
        ownership = ctx.ownership or "公开数据中未取得完整股权和管理层信息。"
        return (
            f"{ownership}\n\n"
            "本章由系统补齐：LLM 输出未能可靠拆分出独立的企业文化章节。"
            "后续应重点核验管理层资本配置、分红/回购纪律、激励与股东利益是否一致。"
        )
    if section_id == "final_judgment":
        verdict = ctx.judge_verdict or "Too Hard"
        return (
            f"综合判定：{verdict}。\n\n"
            f"当前价格：{ctx.current_price or 'N/A'}；估计内在价值：{ctx.weighted_value or 'N/A'}；"
            f"上行/下行空间：{ctx.upside_pct if ctx.upside_pct is not None else 'N/A'}%。\n\n"
            "本章由系统补齐：LLM 输出未能可靠拆分出独立综合判定章节。"
            "在数据和安全边际不足时，应优先归入 Too Hard。"
        )
    if section_id == "business_model":
        return "LLM 输出未能可靠拆分本章。请结合财务指标、行业对比和段永平视角复核商业模式。"
    if section_id == "financial_health":
        score = ctx.financial_score.get("rating") if ctx.financial_score else None
        return f"LLM 输出未能可靠拆分本章。当前财务健康评级：{score or 'N/A'}。"
    if section_id == "valuation":
        return (
            f"LLM 输出未能可靠拆分本章。当前价格 {ctx.current_price or 'N/A'}，"
            f"估计内在价值 {ctx.weighted_value or 'N/A'}。"
        )
    if section_id == "inversion_checklist":
        return "LLM 输出未能可靠拆分本章。需逆向检查需求下滑、竞争加剧、治理恶化、估值收缩等风险。"
    if section_id == "dual_verdict":
        consensus = ctx.judge_consensus or "未取得明确共识。"
        disagreement = ctx.judge_disagreement or "未取得明确分歧。"
        return f"共识：{consensus}\n\n分歧：{disagreement}"
    return "LLM 输出未能可靠拆分本章，系统按模板补齐章节占位。"


def _extract_verdict(raw: str, ctx: CompanyContext) -> str:
    """Extract or synthesize the one-liner summary."""
    # Try to find it in the LLM output first
    if raw and len(raw) > 50:
        # Look for the key sentence
        lines = raw.strip().split("\n")
        for l in lines:
            if "判定" in l or "Yes" in l or "No" in l or "Too Hard" in l:
                if len(l) > 10:
                    return l[:300]
        return raw[:300]
    
    # Fallback: construct from data
    ups = ctx.upside_pct
    direction = "上行" if ups > 0 else "下行"
    return (f"{ctx.name}（{ctx.ticker}）当前 {ctx.current_price:.2f} 元。"
            f"估计内在价值 {ctx.weighted_value:.2f} 元，{direction}空间 {abs(ups):.1f}%。"
            f"综合判定基于多维度分析，详见正文。")


async def _write_deep_dive_report(ctx: CompanyContext, context_str: str) -> dict:
    """Write standard deep dive report."""
    exec_section = await _call_llm(_DEEP_EXEC_PROMPT.format(context=context_str), timeout=90)
    fin_section = await _call_llm(_DEEP_FIN_PROMPT.format(context=context_str), timeout=90)
    risk_section = await _call_llm(_DEEP_RISK_PROMPT.format(context=context_str), timeout=90)
    
    sections = {
        "executive_summary": {"title": "投资摘要", "content": exec_section[:1500]},
        "financial_analysis": {"title": "财务分析与估值", "content": fin_section[:2000]},
        "risk_assessment": {"title": "风险提示", "content": risk_section[:1500]},
    }
    
    return {
        "_llm_used": True,
        "sections": sections,
        "report_title": f"{ctx.name}（{ctx.ticker}）深度研究报告",
        "report_subtitle": f"{date.today().strftime('%Y年%m月')}",
        "report_date": date.today().isoformat(),
    }


# ── LLM Prompts (Written based on analysis of 48 real research reports) ──

_VERDICT_PROMPT = """你是一位资深价值投资分析师，以段永平和查理·芒格的思维框架进行分析。

请基于以下公司数据，写一份专业的投资判定。你的输出应该：

1. **投资判定** — Yes（可买）/ No（不买）/ Too Hard（太难），并附置信度百分比
2. **一句话理由** — 用一句话说明为什么（不）该买
3. **核心分析** — 从商业模式、财务健康、安全边际、企业文化四个维度简要论证
4. **关键数据** — 引用支持你判定的具体数字

写作要求：
- 用简洁的中文，像专业券商分析师那样写
- 每个数字都要有"这意味着什么"的解读
- 不要用"ROE高，好"这种机械评价
- 要体现"价值投资"思维：买股票=买公司，关注长期竞争优势

公司数据：
{context}

请输出完整的投资判定（不少于 300 字）。"""

_BUSINESS_PROMPT = """你是一位资深价值投资分析师（段永平风格）。

请基于以下公司数据，撰写"商业模式分析"章节。你需要回答段永平最关心的三个问题：
1. 这个生意怎么赚钱？
2. 为什么客户选它不选竞争对手？（护城河）
3. 十年后它还能赚钱吗？（可持续性）

用具体数据支撑你的分析。引用 ROE、毛利率、FCF/净利润等指标，并解释每个数字背后的商业含义。

之前判定的结论：{verdict}

公司完整数据：
{context}

请输出完整的商业模式分析（不少于 500 字）。"""

_FINANCIAL_PROMPT = """你是一位资深财务分析师（查理·芒格风格）。

请基于以下公司数据，撰写"财务健康与现金流"分析章节。你的分析应该：

1. 用表格形式呈现关键指标（ROE、FCF/净利润、负债权益比、营收增长等）
2. 对每个指标给出"好/中/差"的判断，并说明判断依据
3. 重点分析：利润质量（FCF/净利润）、资本效率（ROE）、财务风险（负债水平）
4. 给出综合评估：这盘生意的财务底子好不好？为什么？

写作要求：
- 引用具体数字
- 解释数字背后的含义
- 指出值得关注的异常点（如果有）

公司数据：
{context}

请输出完整的财务分析（不少于 400 字）。"""

_VALUATION_PROMPT = """你是一位估值分析师。

请基于以下公司数据，撰写"估值与安全边际"分析章节。你的分析应该：

1. 列出各估值模型的每股价值（DCF、Owner Earnings、EV/EBITDA）
2. 计算安全边际：当前价格 vs 内在价值
3. 给出合理的买入价格区间
4. 做敏感性分析：如果关键假设变化±10%，估值会怎么变？

写作要求：
- 要有数字依据
- 给出具体的买价建议（"低于X元开始买入，低于Y元可重仓"）
- 区分"好公司"和"好价格"

公司数据：
{context}

请输出完整的估值分析（不少于 400 字）。"""

_INVERSION_PROMPT = """你是一位逆向思考分析师（查理·芒格风格）。

请基于以下公司数据，撰写"逆向风险清单"分析章节。这是芒格最喜欢的思维方式——反过来想。

你的分析应该列出 3-5 种"这笔投资怎么死"的路径，每种路径包含：
1. 死亡路径描述（具体场景）
2. 发生的概率评估（高/中/低）
3. 影响程度（致命/严重/可控）
4. 当前有无预警信号

最后给出 Lollapalooza 检测：多种风险同时发力的场景。

公司数据：
{context}

请输出完整的逆向风险分析（不少于 400 字）。"""

_DUAL_PROMPT = """你是一位投资裁决分析师。

请基于段永平和芒格两位投资大师的分析，撰写"双重视角裁决"章节。

段永平视角：
{duan}

芒格视角：
{munger}

裁决结果：{verdict}
共识点：{consensus}
分歧点：{disagreement}

请分析：
1. 两人在哪些点上达成共识？为什么这些共识重要？
2. 分歧在哪里？谁更可能对？
3. 综合两人的判断，最终的决策是什么？

请输出完整的裁决分析（不少于 300 字）。"""

_REVIEW_PROMPT = """你是一位报告质量审核员。

请审核以下研究报告，检查：

1. **数据准确性** — 报告中的数字与上下文数据是否一致？如果有矛盾，列出差异
2. **逻辑一致性** — 判定结论与正文分析是否一致？（如"判定Yes"但"风险极高"）
3. **完整性** — 是否有重要数据在报告中完全未被引用？
4. **改进建议** — 有哪些具体可以改进的地方？

只需列出问题清单（如果有），不要重写报告。

上下文数据：
{context}

报告全文：
{report}

输出格式：
- 问题 1: [描述]
- 问题 2: [描述]
... 
如果没有问题，输出："✅ 审核通过"
"""

_DEEP_EXEC_PROMPT = """你是一位投资分析师。

请基于以下公司数据，写一份投资摘要。包含：
1. 公司简介（一句话）
2. 核心财务表现（引用 ROE、营收增长、负债水平等）
3. 估值判断（当前价格 vs 目标价，向上/向下空间）
4. 综合投资评级

写作要求：简洁、专业、每个数字都有解读。

公司数据：
{context}"""

_DEEP_FIN_PROMPT = """你是一位财务分析师。

请基于以下公司数据，撰写财务分析与估值章节。包含：
1. 盈利能力分析（ROE、ROA、利润率）
2. 成长性分析（营收增长、利润增长）
3. 财务健康度（负债、流动比率）
4. 现金流质量（FCF/净利润）
5. 估值模型汇总
6. 综合评估

公司数据：
{context}"""

_DEEP_RISK_PROMPT = """你是一位风险分析师。

请基于以下公司数据，撰写风险提示章节。列出核心风险并评估影响。

公司数据：
{context}"""


_FULL_REPORT_PROMPT = """你是一位资深价值投资分析师，以段永平和查理·芒格的思维框架分析。

请基于以下全部数据，生成一份完整的价值投资报告。要求：
1. **投资判定**：Yes（可买）/ No（不买）/ Too Hard（太难）
2. **置信度百分比**
3. **商业模式分析**（护城河、竞争优势）
4. **财务健康评估**（引用关键数据并解释含义）
5. **估值与安全边际**（给出具体的买价区间）
6. **逆向风险清单**
7. **双视角裁决**（段永平vs芒格）
8. **综合操作建议**

写作要求：
- 用专业的中文，每个数字都要有"这意味着什么"的解读
- 不要机械列指标，要做判断
- 段永平视角：{duan}
- 芒格视角：{munger}
- 裁决：{verdict}

公司完整数据：
{context}"""
