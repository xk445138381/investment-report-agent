"""Financial Analysis Agent — comprehensive health scoring."""

import logging
from calculators.financial_ratios import calculate_all_ratios

logger = logging.getLogger(__name__)


async def run_financial_analysis_agent(ticker, company_name, financials, prices):
    """Four-dimension scoring with normalization by available dimensions."""
    if not financials:
        return {"ticker": ticker, "error": "no_financial_data"}

    latest = financials[-1]
    prev = financials[-2] if len(financials) >= 2 else None

    income = _to_income(latest)
    balance = _to_balance(latest)
    cashflow = _to_cashflow(latest)
    market = _to_market(prices)

    ratios = calculate_all_ratios(income, balance, cashflow, market)

    # Compute YoY growth from financials list
    if prev and latest.revenue and prev.revenue and prev.revenue > 0:
        ratios["revenue_growth_yoy"] = (latest.revenue / prev.revenue) - 1
    if prev and latest.net_income and prev.net_income and prev.net_income > 0:
        ratios["earnings_growth_yoy"] = (latest.net_income / prev.net_income) - 1

    score = _score(ratios)
    return {
        "ticker": ticker, "company_name": company_name,
        "financial_health_score": score,
        "ratios": {k: round(v, 4) if isinstance(v, (int, float)) else None
                   for k, v in ratios.items() if v is not None},
        "key_strengths": _strengths(ratios, score),
        "key_weaknesses": _weaknesses(ratios),
    }


def _to_income(fs):
    return {"revenue": fs.revenue, "cogs": None, "operating_income": fs.operating_income,
            "net_income": fs.net_income, "eps_basic": fs.eps_basic, "eps_diluted": fs.eps_diluted,
            "ebit": fs.operating_income, "ebitda": fs.operating_income,  # TODO: refine when D&A fields available
            "interest_expense": None, "tax_rate": 0.25}


def _to_balance(fs):
    return {"total_assets": fs.total_assets, "total_liabilities": fs.total_liabilities,
            "total_equity": fs.total_equity, "current_assets": fs.current_assets,
            "current_liabilities": fs.current_liabilities,
            "cash_and_equivalents": fs.cash_and_equivalents,
            "total_debt": fs.total_liabilities,  # TODO: refine when interest-bearing debt available
            "goodwill": fs.goodwill, "intangible_assets": fs.intangible_assets}


def _to_cashflow(fs):
    return {"operating_cash_flow": fs.operating_cash_flow, "capex": fs.capex,
            "free_cash_flow": fs.free_cash_flow}


def _to_market(prices):
    if not prices: return {}
    return {"current_price": prices[-1].close if prices else None, "market_cap": None}


def _score(r):
    earned = 0
    available = 0

    # Profitability: ROE always available if NI>0; margins only if cogs known
    if r.get("roe") is not None:
        available += 10
        if r["roe"] > 0.20: earned += 10
        elif r["roe"] > 0.10: earned += 7
        elif r["roe"] > 0: earned += 4
    if r.get("net_margin") is not None:
        available += 4
        if r["net_margin"] > 0.15: earned += 4
        elif r["net_margin"] > 0.05: earned += 2

    # Health
    if r.get("debt_to_equity") is not None:
        available += 5
        if r["debt_to_equity"] < 0.3: earned += 5
        elif r["debt_to_equity"] < 0.7: earned += 3
        elif r["debt_to_equity"] < 1.5: earned += 1
    if r.get("interest_coverage") is not None:
        available += 3
        if r["interest_coverage"] > 20: earned += 3

    # Quality
    if r.get("fcf_to_net_income") is not None:
        available += 4
        if r["fcf_to_net_income"] > 0.8: earned += 4
        elif r["fcf_to_net_income"] > 0.5: earned += 2
    if r.get("ocf_to_revenue") is not None:
        available += 3
        if r["ocf_to_revenue"] > 0.2: earned += 3

    # Growth (only scored if YoY data available from multi-year financials)
    if r.get("revenue_growth_yoy") is not None:
        available += 5
        if r["revenue_growth_yoy"] > 0.15: earned += 5
        elif r["revenue_growth_yoy"] > 0.05: earned += 3
        elif r["revenue_growth_yoy"] > 0: earned += 1
    if r.get("earnings_growth_yoy") is not None:
        available += 4
        if r["earnings_growth_yoy"] > 0.15: earned += 4
        elif r["earnings_growth_yoy"] > 0.05: earned += 2

    if available > 0:
        normalized = (earned / available) * 32
    else:
        normalized = 0
        available = 32

    rating = "EXCELLENT" if normalized >= 26 else "GOOD" if normalized >= 18 else "FAIR" if normalized >= 10 else "POOR"
    return {"total": round(normalized, 1), "max": 32, "available_dimensions": available,
            "raw_earned": earned, "rating": rating}


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
