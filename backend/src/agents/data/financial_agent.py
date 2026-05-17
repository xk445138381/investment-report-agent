"""Financial Data Agent — fetch financials, compute ratios, generate analysis."""

import json
import logging
from datetime import date
from typing import Optional

from config.loader import load_config, LLMRegistry
from calculators.financial_ratios import calculate_all_ratios

logger = logging.getLogger(__name__)


async def run_financial_agent(
    ticker: str,
    company_name: str,
    financials: list,
    market: str = "CN",
    llm_override: Optional[str] = None,
) -> dict:
    """Execute the financial data agent.

    Steps:
      1. Convert raw financial statements to calculator input dicts
      2. Run Python calculator (28 ratios)
      3. Format results for LLM consumption
      4. Call LLM to generate narrative analysis
      5. Return structured output

    Args:
        ticker: Stock ticker (e.g., '600519.SH')
        company_name: Company display name
        financials: List of FinancialStatement objects from provider
        market: 'CN', 'US', or 'HK'
        llm_override: Override LLM provider (for testing)

    Returns:
        dict with keys: ticker, ratios, narrative, data_quality
    """
    # Step 1+2: Compute ratios from raw financials
    latest = financials[-1] if financials else None
    if latest is None:
        return {"ticker": ticker, "error": "no_financial_data", "ratios": {}, "narrative": ""}

    income = {
        "revenue": latest.revenue,
        "cogs": _estimate_cogs(latest),
        "operating_income": latest.operating_income,
        "net_income": latest.net_income,
        "ebit": latest.operating_income,   # approximation
        "ebitda": latest.operating_income,  # approximation
        "interest_expense": None,
    }
    balance = {
        "total_assets": latest.total_assets,
        "total_liabilities": latest.total_liabilities,
        "total_equity": latest.total_equity,
        "current_assets": latest.current_assets,
        "current_liabilities": latest.current_liabilities,
        "cash_and_equivalents": latest.cash_and_equivalents,
        "total_debt": latest.total_liabilities,
        "goodwill": latest.goodwill,
        "intangible_assets": latest.intangible_assets,
        "inventory": None,
        "accounts_receivable": None,
        "accounts_payable": None,
    }
    cashflow = {
        "operating_cash_flow": latest.operating_cash_flow,
        "free_cash_flow": latest.free_cash_flow,
        "capex": latest.capex,
    }
    market_data = {
        "market_cap": None,
        "enterprise_value": None,
        "shares_outstanding": None,
        "current_price": None,
    }

    ratios = calculate_all_ratios(income, balance, cashflow, market_data)

    # Step 3+4: LLM narrative
    quality = _assess_data_quality(latest)
    config = load_config()
    registry = LLMRegistry(config)
    model = registry.get_model("financial_data") if not llm_override else None

    narrative = "（LLM 分析待接入 DeepSeek API）" if model is None else await _llm_narrative(
        model, ticker, company_name, ratios, quality)

    return {
        "ticker": ticker,
        "company_name": company_name,
        "data_quality": quality,
        "ratios": ratios,
        "narrative": narrative,
    }


async def _llm_narrative(model, ticker, company_name, ratios, quality) -> str:
    """Generate financial analysis narrative via LLM."""
    from langchain_core.messages import HumanMessage

    prompt = f"""你是一位资深财务分析师。请基于以下数据，对 {company_name} ({ticker}) 做简要财务分析。

财务比率：
{json.dumps({k: v for k, v in ratios.items() if v is not None}, ensure_ascii=False, indent=2)}

数据质量：{json.dumps(quality, ensure_ascii=False)}

请用中文输出 3-5 句话，涵盖盈利能力、财务健康度和关键亮点/风险。不超过 200 字。"""

    try:
        response = model.invoke([HumanMessage(content=prompt)])
        return response.content[:500]
    except Exception as e:
        logger.warning(f"LLM call failed: {e}")
        return "（LLM 调用失败，请检查 API Key 和网络）"


def _assess_data_quality(fs) -> dict:
    """Assess the quality/completeness of financial data."""
    fields = ["revenue", "net_income", "total_assets", "total_equity",
              "total_liabilities", "eps_basic"]
    present = sum(1 for f in fields if getattr(fs, f) is not None)
    return {
        "completeness_score": round(present / len(fields) * 100),
        "years_covered": 1,
        "missing_fields": [f for f in fields if getattr(fs, f) is None],
    }


def _estimate_cogs(fs) -> Optional[float]:
    """Estimate COGS when not directly available (A-share data often has this)."""
    if fs.revenue and fs.operating_income:
        return fs.revenue - fs.operating_income
    return None
