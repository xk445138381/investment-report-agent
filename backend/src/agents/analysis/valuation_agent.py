"""Valuation Agent — runs DCF + Owner Earnings + EV/EBITDA models."""

import logging
from typing import Optional

from calculators.valuation_engine import (
    calculate_dcf_three_stage,
    calculate_owner_earnings_value,
    calculate_ev_ebitda,
    calculate_sensitivity_matrix,
    redistribute_weights,
    ValuationParams,
)

logger = logging.getLogger(__name__)


async def run_valuation_agent(
    ticker: str,
    company_name: str,
    financials: list,
    prices: list,
    market: str = "CN",
) -> dict:
    """Execute valuation analysis on a stock.

    Uses 3 models (DCF, Owner Earnings, EV/EBITDA) aggregated with
    dynamic weight redistribution when a model can't be computed.
    """
    if not financials or not prices:
        return {"ticker": ticker, "error": "insufficient_data"}

    params = ValuationParams()
    latest = financials[-1]
    current_price = prices[-1].close if prices else None
    if current_price is None:
        return {"ticker": ticker, "error": "no_price_data"}

    results = {}
    errors = []

    # Model 1: DCF
    fcf = latest.free_cash_flow or (
        (latest.operating_cash_flow or 0) - (latest.capex or 0))
    if fcf and fcf > 0:
        dcf = calculate_dcf_three_stage(
            last_fcf=fcf, historical_fcf_cagr=0.05, wacc=0.10,
            net_debt=_safe_net_debt(latest),
            cash=latest.cash_and_equivalents or 0,
            minority_interest=0, shares_outstanding=_estimate_shares(latest),
            params=params, beta=1.0, equity_weight=0.7, debt_weight=0.3,
            interest_expense=0, total_debt=latest.total_liabilities or 0,
            tax_rate=0.25, market=market,
        )
        if dcf.get("per_share_value"):
            results["dcf"] = dcf
        else:
            errors.append(("dcf", dcf.get("reason", "unknown")))
    else:
        errors.append(("dcf", "negative_or_zero_fcf"))

    # Model 2: Owner Earnings
    if latest.net_income and latest.net_income > 0:
        oe = calculate_owner_earnings_value(
            net_income=latest.net_income,
            depreciation_amortization=_estimate_da(latest),
            total_capex=latest.capex or 0,
            financial_data={"current_assets": latest.current_assets or 0,
                            "current_liabilities": latest.current_liabilities or 0},
            prev_financial_data={"current_assets": 0, "current_liabilities": 0},
            historical_da=[_estimate_da(latest)],
            historical_capex=[latest.capex or 0],
            shares_outstanding=_estimate_shares(latest),
            params=params,
        )
        if oe.get("per_share_value"):
            results["owner_earnings"] = oe
        else:
            errors.append(("owner_earnings", "calculation_failed"))
    else:
        errors.append(("owner_earnings", "negative_ni"))

    # Model 3: EV/EBITDA (simplified — industry multiple not available without peers)
    errors.append(("ev_ebitda", "needs_industry_data"))

    # Aggregate
    raw_weights = [
        params.weight_dcf if "dcf" in results else None,
        params.weight_owner_earnings if "owner_earnings" in results else None,
        params.weight_ev_ebitda if "ev_ebitda" in results else None,
        None,  # RI not implemented
    ]
    weights = redistribute_weights(raw_weights)

    values = [
        results.get("dcf", {}).get("per_share_value"),
        results.get("owner_earnings", {}).get("per_share_value"),
        results.get("ev_ebitda", {}).get("per_share_value"),
        None,
    ]
    valid = [(v, w) for v, w in zip(values, weights) if v is not None and w > 0]
    if valid:
        weighted_value = sum(v * w for v, w in valid)
        upside = ((weighted_value / current_price) - 1) * 100
    else:
        weighted_value = current_price
        upside = 0.0

    # Sensitivity matrix (if DCF available)
    sensitivity = None
    if "dcf" in results:
        base_wacc = results["dcf"].get("wacc", 10) / 100
        base_growth = params.terminal_growth
        def _recalc(wacc, growth):
            return calculate_dcf_three_stage(
                last_fcf=fcf, historical_fcf_cagr=0.05, wacc=wacc,
                net_debt=_safe_net_debt(latest),
                cash=latest.cash_and_equivalents or 0,
                minority_interest=0, shares_outstanding=_estimate_shares(latest),
                params=ValuationParams(terminal_growth=growth),
                beta=1.0, equity_weight=0.7, debt_weight=0.3,
                interest_expense=0, total_debt=latest.total_liabilities or 0,
                tax_rate=0.25, market=market,
            )
        sensitivity = calculate_sensitivity_matrix(
            base_wacc, base_growth,
            wacc_range=(base_wacc-0.01, base_wacc+0.01, 0.01),
            growth_range=(base_growth-0.005, base_growth+0.005, 0.005),
            base_valuation_func=_recalc,
        )

    signal = ("undervalued" if upside > 15 else
              "overvalued" if upside < -15 else "fair")

    return {
        "ticker": ticker,
        "company_name": company_name,
        "current_price": current_price,
        "weighted_value": round(weighted_value, 2),
        "weighted_upside_pct": round(upside, 1),
        "signal": signal,
        "models": {
            name: {"per_share_value": m.get("per_share_value"),
                    "upside_pct": round(((m.get("per_share_value") or current_price) / current_price - 1) * 100, 1)}
            for name, m in results.items()
        },
        "errors": errors,
        "sensitivity_matrix": sensitivity,
    }


def _estimate_shares(fs) -> float:
    if fs.eps_basic and fs.eps_basic > 0 and fs.net_income:
        return abs(fs.net_income / fs.eps_basic)
    return 1e9  # fallback: 1 billion shares


def _estimate_da(fs) -> float:
    if fs.revenue and fs.revenue > 0:
        return fs.revenue * 0.05  # rough: 5% of revenue
    return 0


def _safe_net_debt(fs) -> float:
    debt = fs.total_liabilities or 0
    cash = fs.cash_and_equivalents or 0
    return debt - cash
