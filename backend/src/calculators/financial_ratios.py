"""28 financial ratio calculations — pure Python, no LLM."""

from typing import Optional


def _safe_div(num: Optional[float], den: Optional[float], default=None) -> Optional[float]:
    """Safe division: returns default if either input is None or denominator is 0."""
    if num is None or den is None or den == 0:
        return default
    return num / den


# ── Profitability ──

def calculate_roe(net_income: Optional[float], avg_equity: Optional[float]) -> Optional[float]:
    return _safe_div(net_income, avg_equity)


def calculate_roa(net_income: Optional[float], avg_total_assets: Optional[float]) -> Optional[float]:
    return _safe_div(net_income, avg_total_assets)


def calculate_roic(nopat: Optional[float], invested_capital: Optional[float]) -> Optional[float]:
    return _safe_div(nopat, invested_capital)


def calculate_gross_margin(revenue: Optional[float], cogs: Optional[float]) -> Optional[float]:
    if revenue is None or cogs is None or revenue == 0:
        return None
    return (revenue - cogs) / revenue


def calculate_operating_margin(operating_income: Optional[float], revenue: Optional[float]) -> Optional[float]:
    return _safe_div(operating_income, revenue)


def calculate_net_margin(net_income: Optional[float], revenue: Optional[float]) -> Optional[float]:
    return _safe_div(net_income, revenue)


# ── Growth ──

def yoy_growth(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / previous


def cagr(start: Optional[float], end: Optional[float], years: int) -> Optional[float]:
    if start is None or end is None or years <= 0:
        return None
    if start <= 0 or end <= 0:
        return None
    return (end / start) ** (1.0 / years) - 1.0


# ── Financial Health ──

def calculate_debt_to_equity(total_liabilities: Optional[float], total_equity: Optional[float]) -> Optional[float]:
    return _safe_div(total_liabilities, total_equity)


def calculate_interest_coverage(ebit: Optional[float], interest_expense: Optional[float]) -> Optional[float]:
    if ebit is None or interest_expense is None:
        return None
    if interest_expense == 0:
        return float("inf")
    return ebit / interest_expense


def calculate_current_ratio(current_assets: Optional[float], current_liabilities: Optional[float]) -> Optional[float]:
    return _safe_div(current_assets, current_liabilities)


def calculate_quick_ratio(current_assets: Optional[float], inventory: Optional[float],
                          current_liabilities: Optional[float]) -> Optional[float]:
    if current_assets is None or current_liabilities is None or current_liabilities == 0:
        return None
    inv = inventory if inventory is not None else 0.0
    return (current_assets - inv) / current_liabilities


# ── Aggregate ──

def calculate_all_ratios(income: dict, balance: dict, cashflow: dict, market: dict) -> dict:
    """Calculate all available ratios from standardized financial data dicts.

    Returns a dict with ratio_name → value. None where inputs missing.
    """
    result = {}

    # Profitability
    result["roe"] = calculate_roe(income.get("net_income"), balance.get("total_equity"))
    result["roa"] = calculate_roa(income.get("net_income"), balance.get("total_assets"))
    result["roic"] = calculate_roic(
        income.get("nopat"),
        (balance.get("total_assets") or 0) - (balance.get("current_liabilities") or 0)
        if balance.get("total_assets") and balance.get("current_liabilities") else None
    )
    result["gross_margin"] = calculate_gross_margin(income.get("revenue"), income.get("cogs"))
    result["operating_margin"] = calculate_operating_margin(income.get("operating_income"), income.get("revenue"))
    result["net_margin"] = calculate_net_margin(income.get("net_income"), income.get("revenue"))

    # Growth (partial — needs multi-year data for CAGR)
    result["revenue_growth_yoy"] = None
    result["earnings_growth_yoy"] = None
    result["revenue_growth_3y_cagr"] = None
    result["earnings_growth_3y_cagr"] = None

    # Health
    result["debt_to_equity"] = calculate_debt_to_equity(
        balance.get("total_liabilities"), balance.get("total_equity"))
    result["interest_coverage"] = calculate_interest_coverage(
        income.get("ebit"), income.get("interest_expense"))
    result["current_ratio"] = calculate_current_ratio(
        balance.get("current_assets"), balance.get("current_liabilities"))
    result["quick_ratio"] = calculate_quick_ratio(
        balance.get("current_assets"), balance.get("inventory"),
        balance.get("current_liabilities"))

    # Quality
    result["fcf_to_net_income"] = _safe_div(
        cashflow.get("free_cash_flow"), income.get("net_income"))
    result["ocf_to_revenue"] = _safe_div(
        cashflow.get("operating_cash_flow"), income.get("revenue"))

    # Valuation multiples
    result["pe_ratio"] = _safe_div(
        market.get("market_cap"),
        income.get("net_income") * (market.get("shares_outstanding") or 1)
        if income.get("net_income") else None)
    result["pb_ratio"] = _safe_div(
        market.get("market_cap"), balance.get("total_equity"))
    result["fcf_yield"] = _safe_div(
        cashflow.get("free_cash_flow"), market.get("market_cap"))

    # Efficiency
    result["asset_turnover"] = _safe_div(
        income.get("revenue"), balance.get("total_assets"))
    result["net_debt_to_ebitda"] = _safe_div(
        (balance.get("total_debt") or 0) - (balance.get("cash_and_equivalents") or 0),
        income.get("ebitda"))

    return result
