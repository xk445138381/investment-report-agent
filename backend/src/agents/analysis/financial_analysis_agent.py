"""Financial Analysis Agent — comprehensive health scoring."""

import logging
from calculators.financial_ratios import calculate_all_ratios

logger = logging.getLogger(__name__)


async def run_financial_analysis_agent(ticker, company_name, financials, prices):
    """Four-dimension scoring: profitability, growth, health, quality."""
    if not financials:
        return {"ticker": ticker, "error": "no_financial_data"}

    latest = financials[-1]
    income = _to_income(latest)
    balance = _to_balance(latest)
    cashflow = _to_cashflow(latest)
    market = _to_market(prices)

    ratios = calculate_all_ratios(income, balance, cashflow, market)

    score = _score(ratios)
    return {
        "ticker": ticker, "company_name": company_name,
        "financial_health_score": score,
        "ratios": {k: round(v, 4) if v else None for k, v in ratios.items()
                   if v is not None},
        "key_strengths": _strengths(ratios, score),
        "key_weaknesses": _weaknesses(ratios),
    }


def _to_income(fs):
    return {"revenue": fs.revenue, "cogs": None, "operating_income": fs.operating_income,
            "net_income": fs.net_income, "eps_basic": fs.eps_basic, "eps_diluted": fs.eps_diluted,
            "ebit": fs.operating_income, "ebitda": fs.operating_income, "interest_expense": None,
            "tax_rate": 0.25}


def _to_balance(fs):
    return {"total_assets": fs.total_assets, "total_liabilities": fs.total_liabilities,
            "total_equity": fs.total_equity, "current_assets": fs.current_assets,
            "current_liabilities": fs.current_liabilities,
            "cash_and_equivalents": fs.cash_and_equivalents,
            "total_debt": fs.total_liabilities, "goodwill": fs.goodwill,
            "intangible_assets": fs.intangible_assets}


def _to_cashflow(fs):
    return {"operating_cash_flow": fs.operating_cash_flow, "capex": fs.capex,
            "free_cash_flow": fs.free_cash_flow}


def _to_market(prices):
    if not prices: return {}
    return {"current_price": prices[-1].close if prices else None, "market_cap": None}


def _score(r):
    p = 0
    # Profitability (max 10)
    if r.get("roe") and r["roe"] > 0.20: p += 4
    elif r.get("roe") and r["roe"] > 0.10: p += 3
    elif r.get("roe"): p += 2
    if r.get("gross_margin") and r["gross_margin"] > 0.60: p += 3
    elif r.get("gross_margin") and r["gross_margin"] > 0.30: p += 2
    if r.get("net_margin") and r["net_margin"] > 0.15: p += 3
    elif r.get("net_margin") and r["net_margin"] > 0.05: p += 2

    # Health (max 8)
    if r.get("debt_to_equity") is not None and r["debt_to_equity"] < 0.3: p += 3
    elif r.get("debt_to_equity") is not None and r["debt_to_equity"] < 0.7: p += 2
    if r.get("interest_coverage") and r["interest_coverage"] > 20: p += 3
    if r.get("current_ratio") and r["current_ratio"] > 2: p += 2

    # Quality (max 6)
    if r.get("fcf_to_net_income") and r["fcf_to_net_income"] > 0.8: p += 3
    if r.get("ocf_to_revenue") and r["ocf_to_revenue"] > 0.2: p += 3

    # Growth (max 8)
    if r.get("revenue_growth_yoy") and r["revenue_growth_yoy"] > 0.15: p += 4
    elif r.get("revenue_growth_yoy") and r["revenue_growth_yoy"] > 0.05: p += 3
    elif r.get("revenue_growth_yoy"): p += 2
    if r.get("earnings_growth_yoy") and r["earnings_growth_yoy"] > 0.15: p += 4
    elif r.get("earnings_growth_yoy") and r["earnings_growth_yoy"] > 0.05: p += 3

    rating = "EXCELLENT" if p >= 26 else "GOOD" if p >= 18 else "FAIR" if p >= 10 else "POOR"
    return {"total": p, "max": 32, "rating": rating}


def _strengths(r, s):
    items = []
    if r.get("roe") and r["roe"] > 0.20:
        items.append(f"高ROE ({r['roe']*100:.1f}%)，盈利能力突出")
    if r.get("debt_to_equity") is not None and r["debt_to_equity"] < 0.3:
        items.append(f"低杠杆运营（负债比 {r['debt_to_equity']:.2f}）")
    if r.get("fcf_to_net_income") and r["fcf_to_net_income"] > 0.8:
        items.append("自由现金流充裕，盈利质量高")
    return items or ["盈利能力稳健"]


def _weaknesses(r):
    items = []
    if r.get("debt_to_equity") is not None and r["debt_to_equity"] > 1.0:
        items.append(f"高杠杆运营（负债比 {r['debt_to_equity']:.2f}）")
    if r.get("revenue_growth_yoy") is not None and r["revenue_growth_yoy"] < 0.05:
        items.append(f"营收增长乏力（YoY {r['revenue_growth_yoy']*100:.1f}%）")
    return items or ["暂无显著财务弱点"]
