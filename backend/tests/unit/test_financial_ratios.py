"""T07: Financial ratios calculator tests (TDD)."""

import pytest
from calculators.financial_ratios import (
    calculate_roe, calculate_roa, calculate_roic,
    calculate_gross_margin, calculate_operating_margin, calculate_net_margin,
    calculate_debt_to_equity, calculate_interest_coverage,
    calculate_current_ratio, calculate_quick_ratio,
    yoy_growth, cagr,
    calculate_all_ratios,
)


class TestProfitability:
    def test_roe_basic(self):
        assert calculate_roe(net_income=100, avg_equity=500) == 0.20

    def test_roe_negative_ni(self):
        assert calculate_roe(net_income=-100, avg_equity=500) == -0.20

    def test_roe_zero_equity_returns_none(self):
        assert calculate_roe(100, 0) is None

    def test_roe_none_ni_returns_none(self):
        assert calculate_roe(None, 500) is None

    def test_roa_basic(self):
        assert calculate_roa(net_income=100, avg_total_assets=1000) == 0.10

    def test_roa_none(self):
        assert calculate_roa(None, 1000) is None

    def test_roic_basic(self):
        assert calculate_roic(nopat=120, invested_capital=600) == 0.20

    def test_roic_zero_capital(self):
        assert calculate_roic(120, 0) is None

    def test_gross_margin(self):
        assert calculate_gross_margin(revenue=1000, cogs=400) == 0.60

    def test_gross_margin_zero_revenue(self):
        assert calculate_gross_margin(0, 400) is None

    def test_operating_margin(self):
        assert calculate_operating_margin(operating_income=200, revenue=1000) == 0.20

    def test_net_margin(self):
        assert calculate_net_margin(net_income=150, revenue=1000) == 0.15


class TestGrowth:
    def test_yoy_growth_positive(self):
        assert yoy_growth(120, 100) == 0.20

    def test_yoy_growth_negative(self):
        assert yoy_growth(80, 100) == pytest.approx(-0.20)

    def test_yoy_previous_zero(self):
        assert yoy_growth(100, 0) is None

    def test_cagr_3y(self):
        # 100 → 133.1 over 3 years → ~10% CAGR
        assert cagr(start=100, end=133.1, years=3) == pytest.approx(0.10, rel=0.01)

    def test_cagr_zero_years(self):
        assert cagr(100, 150, 0) is None

    def test_cagr_negative_start(self):
        assert cagr(-100, 100, 3) is None


class TestFinancialHealth:
    def test_debt_to_equity(self):
        assert calculate_debt_to_equity(total_liabilities=200, total_equity=800) == 0.25

    def test_debt_to_equity_zero_equity(self):
        assert calculate_debt_to_equity(200, 0) is None

    def test_interest_coverage(self):
        assert calculate_interest_coverage(ebit=500, interest_expense=25) == 20.0

    def test_interest_coverage_zero_interest(self):
        result = calculate_interest_coverage(500, 0)
        assert result == float("inf")

    def test_current_ratio(self):
        assert calculate_current_ratio(current_assets=300, current_liabilities=150) == 2.0

    def test_quick_ratio(self):
        assert calculate_quick_ratio(current_assets=300, inventory=60, current_liabilities=150) == 1.6


class TestCalculateAllRatios:
    def test_all_none_inputs(self):
        """Given: all empty dicts
           When: calculate_all_ratios
           Then: returns dict with all None values, no exception"""
        result = calculate_all_ratios({}, {}, {}, {})
        assert result is not None
        assert isinstance(result, dict)

    def test_partial_data(self):
        """Given: income statement only
           When: calculate_all_ratios
           Then: IS-based ratios computed, BS/CF-based ratios are None"""
        income = {"revenue": 1000, "cogs": 400, "operating_income": 200, "net_income": 150}
        result = calculate_all_ratios(income, {}, {}, {})
        assert result["gross_margin"] == 0.60
        assert result["net_margin"] == 0.15
        assert result["debt_to_equity"] is None
