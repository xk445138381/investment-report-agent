"""Valuation engine — DCF, Owner Earnings, EV/EBITDA (pure Python, no LLM).

All financial math lives here. LLM only interprets the results.
"""

from typing import Optional, Callable
from dataclasses import dataclass


@dataclass
class ValuationParams:
    """Configurable valuation parameters."""
    risk_free_rate_cn: float = 0.0172
    risk_free_rate_us: float = 0.0425
    risk_free_rate_hk: float = 0.0350
    equity_risk_premium_cn: float = 0.06
    equity_risk_premium_us: float = 0.05
    equity_risk_premium_hk: float = 0.065
    terminal_growth: float = 0.03
    stage1_years: int = 5
    stage1_growth_cap: float = 0.15
    stage2_years: int = 5
    owner_earnings_discount: float = 0.09
    owner_earnings_mos: float = 0.25
    premium_for_roe_2x: float = 0.15
    premium_for_growth_edge: float = 0.10
    ri_mos: float = 0.20
    weight_dcf: float = 0.35
    weight_owner_earnings: float = 0.35
    weight_ev_ebitda: float = 0.20
    weight_ri: float = 0.10


def _select_rf_erp(market: str, params: ValuationParams) -> tuple[float, float]:
    """Select risk-free rate and equity risk premium based on market."""
    if market == "CN":
        return params.risk_free_rate_cn, params.equity_risk_premium_cn
    elif market == "HK":
        return params.risk_free_rate_hk, params.equity_risk_premium_hk
    return params.risk_free_rate_us, params.equity_risk_premium_us


def calculate_dcf_three_stage(
    last_fcf: float,
    historical_fcf_cagr: float,
    wacc: float,
    net_debt: float,
    cash: float,
    minority_interest: float,
    shares_outstanding: float,
    params: ValuationParams,
    beta: float = 1.0,
    equity_weight: float = 0.7,
    debt_weight: float = 0.3,
    interest_expense: float = 0,
    total_debt: float = 0,
    tax_rate: float = 0.25,
    market: str = "US",
) -> dict:
    """Three-stage Discounted Cash Flow model.

    Stage 1: High growth (stage1_years)
    Stage 2: Transition (linear decay to terminal growth, stage2_years)
    Stage 3: Terminal value (perpetuity)

    Returns dict with keys: per_share_value, wacc, stage1_growth, terminal_value_share, ...
    """
    if last_fcf <= 0:
        return {"per_share_value": None, "error": "negative_last_fcf",
                "reason": f"Last FCF ({last_fcf}) is not positive"}

    if wacc <= params.terminal_growth:
        return {"per_share_value": None, "error": "wacc_le_growth",
                "reason": f"WACC ({wacc:.4f}) <= terminal growth ({params.terminal_growth:.4f})"}

    # Stage 1 growth capped
    stage1_growth = min(max(historical_fcf_cagr * 0.8, 0.0), params.stage1_growth_cap)

    # Stage 1 projections
    fcf = [last_fcf]
    for t in range(1, params.stage1_years + 1):
        fcf.append(fcf[-1] * (1 + stage1_growth))

    # Stage 2 projections (linear decay)
    stage2_start = params.stage1_years + 1
    for t in range(stage2_start, stage2_start + params.stage2_years):
        progress = (t - params.stage1_years) / params.stage2_years
        growth = stage1_growth + progress * (params.terminal_growth - stage1_growth)
        fcf.append(fcf[-1] * (1 + growth))

    # Terminal value
    terminal_fcf = fcf[-1] * (1 + params.terminal_growth)
    terminal_value = terminal_fcf / (wacc - params.terminal_growth)

    # Discount all cash flows
    all_cf = fcf[1:]  # skip current FCF
    pv_sum = sum(cf / (1 + wacc) ** (i + 1) for i, cf in enumerate(all_cf[:-params.stage2_years]))
    # Add stage 2
    for i in range(params.stage2_years):
        idx = params.stage1_years + i
        pv_sum += all_cf[idx] / (1 + wacc) ** (idx + 1)

    pv_terminal = terminal_value / (1 + wacc) ** (params.stage1_years + params.stage2_years)
    enterprise_value = pv_sum + pv_terminal
    equity_value = enterprise_value - net_debt + cash - minority_interest

    if shares_outstanding <= 0:
        return {"per_share_value": None, "error": "zero_shares"}

    return {
        "per_share_value": round(equity_value / shares_outstanding, 2),
        "wacc": round(wacc * 100, 2),
        "stage1_growth": round(stage1_growth * 100, 2),
        "terminal_value_share": round(pv_terminal / enterprise_value * 100, 1),
        "enterprise_value": round(enterprise_value, 2),
        "equity_value": round(equity_value, 2),
    }


def calculate_owner_earnings_value(
    net_income: float,
    depreciation_amortization: float,
    total_capex: float,
    financial_data: dict,
    prev_financial_data: dict,
    historical_da: list[float],
    historical_capex: list[float],
    shares_outstanding: float,
    params: ValuationParams,
) -> dict:
    """Buffett-style Owner Earnings valuation.

    Owner Earnings = NI + D&A - Maintenance Capex - Δ Net Working Capital
    Maintenance Capex = median of 3 estimation methods.
    """
    # Maintenance capex: 3 methods, take median
    method1 = total_capex * 0.85
    method2 = depreciation_amortization
    ratios = [d / c for d, c in zip(historical_da, historical_capex) if c > 0]
    avg_ratio = sum(ratios) / len(ratios) if ratios else 1.0
    method3 = total_capex * avg_ratio
    maintenance_capex = sorted([method1, method2, method3])[1]  # median

    # Net working capital change
    nwc_current = financial_data.get("current_assets", 0) - financial_data.get("current_liabilities", 0)
    nwc_prior = prev_financial_data.get("current_assets", 0) - prev_financial_data.get("current_liabilities", 0)
    delta_nwc = nwc_current - nwc_prior

    owner_earnings = net_income + depreciation_amortization - maintenance_capex - delta_nwc

    discount = params.owner_earnings_discount
    terminal_growth = params.terminal_growth

    # 5-year DCF
    projections = [owner_earnings * (1 + terminal_growth) ** t for t in range(1, 6)]
    terminal_value = projections[-1] * (1 + terminal_growth) / (discount - terminal_growth)

    pv_projections = sum(oe / (1 + discount) ** (i + 1) for i, oe in enumerate(projections))
    pv_terminal = terminal_value / (1 + discount) ** 5

    intrinsic = (pv_projections + pv_terminal) * (1 - params.owner_earnings_mos)
    per_share = round(intrinsic / shares_outstanding, 2) if shares_outstanding > 0 else None

    return {
        "per_share_value": per_share,
        "owner_earnings": round(owner_earnings, 2),
        "maintenance_capex": round(maintenance_capex, 2),
        "mos_applied": params.owner_earnings_mos,
    }


def calculate_ev_ebitda(
    ebitda: float,
    industry_ev_ebitda: float,
    net_debt: float,
    minority_interest: float,
    preferred_stock: float,
    non_controlling: float,
    roe: float,
    industry_roe: float,
    revenue_growth: float,
    industry_growth: float,
    params: ValuationParams,
    shares_outstanding: float = 1.0,
) -> dict:
    """EV/EBITDA relative valuation with quality-based premium/discount adjustments."""
    premium = 1.0
    if industry_roe > 0 and roe > industry_roe * 2:
        premium += params.premium_for_roe_2x
    if revenue_growth > industry_growth:
        premium += params.premium_for_growth_edge

    adjusted_multiple = industry_ev_ebitda * premium
    enterprise_value = ebitda * adjusted_multiple
    equity_value = enterprise_value - net_debt + minority_interest + preferred_stock - non_controlling

    return {
        "per_share_value": round(equity_value / shares_outstanding, 2) if shares_outstanding > 0 else None,
        "premium_applied": round(premium, 4),
        "adjusted_multiple": round(adjusted_multiple, 2),
        "shares_outstanding": shares_outstanding,
    }


def redistribute_weights(weights: list[Optional[float]]) -> list[float]:
    """Redistribute weights when some models are unavailable.

    Example: [0.35, 0.35, 0.20, None] → [0.389, 0.389, 0.222, 0.0]
    """
    result = [w if w is not None else 0.0 for w in weights]
    total = sum(result)
    if total > 0:
        result = [r / total for r in result]
    return result


def calculate_sensitivity_matrix(
    base_wacc: float,
    base_growth: float,
    wacc_range: tuple[float, float, float],
    growth_range: tuple[float, float, float],
    base_valuation_func: Callable[[float, float], dict],
) -> dict:
    """3×3 sensitivity matrix: WACC ± step × Growth ± step."""
    wacc_values = [base_wacc + i * wacc_range[2] for i in [-1, 0, 1]]
    growth_values = [base_growth + i * growth_range[2] for i in [-1, 0, 1]]

    matrix = []
    for w in wacc_values:
        row = []
        for g in growth_values:
            val = base_valuation_func(wacc=w, growth=g)
            row.append(round(val.get("per_share_value", 0.0) or 0.0, 2))
        matrix.append(row)

    return {
        "wacc_values": [round(w * 100, 2) for w in wacc_values],
        "growth_values": [round(g * 100, 2) for g in growth_values],
        "matrix": matrix,
    }
