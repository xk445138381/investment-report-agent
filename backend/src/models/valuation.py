"""Valuation models — ValuationParams, ValuationResult."""

from typing import Optional, Literal
from pydantic import BaseModel, Field


class ValuationParams(BaseModel):
    """Configurable valuation parameters (overrideable in config.json)."""
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


class ValuationResult(BaseModel):
    """Aggregated valuation analysis output."""
    ticker: str
    current_price: float = Field(ge=0)
    market_cap: float = Field(ge=0)
    models: dict = Field(default_factory=dict)
    weighted_value: float = Field(ge=0)
    weighted_upside_pct: float
    sensitivity_matrix: dict = Field(default_factory=dict)
    signal: Literal["undervalued", "fair", "overvalued"]
