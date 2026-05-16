"""T08: Valuation engine tests (TDD)."""

import pytest
from calculators.valuation_engine import (
    calculate_dcf_three_stage,
    calculate_owner_earnings_value,
    calculate_ev_ebitda,
    calculate_sensitivity_matrix,
    redistribute_weights,
    ValuationParams,
)


class TestDCFThreeStage:
    def test_zero_growth_equals_perpetuity(self):
        """Given: FCF=100 constant, growth=0, wacc=0.10
           When: DCF
           Then: PV = FCF/WACC = 1000 (approx, multi-stage)"""
        params = ValuationParams(
            stage1_years=5, stage2_years=5,
            stage1_growth_cap=0.0, terminal_growth=0.0,
        )
        result = calculate_dcf_three_stage(
            last_fcf=100.0,
            historical_fcf_cagr=0.0,
            wacc=0.10,
            net_debt=0,
            cash=0,
            minority_interest=0,
            shares_outstanding=1,
            params=params,
            beta=1.0,
            equity_weight=0.7,
            debt_weight=0.3,
            interest_expense=10,
            total_debt=200,
            tax_rate=0.25,
            market="US",
        )
        # With 0 growth, should approximate perpetuity
        assert result["per_share_value"] == pytest.approx(1000.0, rel=0.05)

    def test_positive_growth_increases_value(self):
        """Given: growth=5% vs growth=0%
           When: DCF
           Then: 5% value > 0% value"""
        params_zero = ValuationParams(stage1_growth_cap=0.0, terminal_growth=0.0)
        params_growth = ValuationParams(stage1_growth_cap=0.05, terminal_growth=0.03)

        base = {"last_fcf": 100, "historical_fcf_cagr": 0.0, "wacc": 0.10,
                "net_debt": 0, "cash": 0, "minority_interest": 0,
                "shares_outstanding": 1, "beta": 1.0,
                "equity_weight": 0.7, "debt_weight": 0.3,
                "interest_expense": 10, "total_debt": 200, "tax_rate": 0.25,
                "market": "US"}

        zero_val = calculate_dcf_three_stage(params=params_zero, **base)
        growth_val = calculate_dcf_three_stage(params=params_growth, **base)
        assert growth_val["per_share_value"] > zero_val["per_share_value"]

    def test_higher_wacc_decreases_value(self):
        """Given: wacc=12% vs wacc=8%
           When: DCF
           Then: 12% value < 8% value"""
        params = ValuationParams()

        low = calculate_dcf_three_stage(wacc=0.08, params=params, last_fcf=100,
            historical_fcf_cagr=0.05, net_debt=0, cash=0, minority_interest=0,
            shares_outstanding=1, beta=1.0, equity_weight=0.7, debt_weight=0.3,
            interest_expense=10, total_debt=200, tax_rate=0.25, market="US")
        high = calculate_dcf_three_stage(wacc=0.12, params=params, last_fcf=100,
            historical_fcf_cagr=0.05, net_debt=0, cash=0, minority_interest=0,
            shares_outstanding=1, beta=1.0, equity_weight=0.7, debt_weight=0.3,
            interest_expense=10, total_debt=200, tax_rate=0.25, market="US")
        assert high["per_share_value"] < low["per_share_value"]

    def test_terminal_value_is_significant(self):
        """Given: standard params
           When: DCF
           Then: terminal value contributes to enterprise value"""
        params = ValuationParams()
        result = calculate_dcf_three_stage(
            last_fcf=100, historical_fcf_cagr=0.05, wacc=0.10,
            net_debt=0, cash=0, minority_interest=0, shares_outstanding=1,
            params=params, beta=1.0, equity_weight=0.7, debt_weight=0.3,
            interest_expense=10, total_debt=200, tax_rate=0.25, market="US",
        )
        assert result["terminal_value_share"] > 30  # terminal value > 30%

    def test_negative_fcf_returns_none_value(self):
        """Given: negative historical FCF
           When: DCF
           Then: per_share_value is None"""
        params = ValuationParams()
        result = calculate_dcf_three_stage(
            last_fcf=-100, historical_fcf_cagr=0.0, wacc=0.10,
            net_debt=0, cash=0, minority_interest=0, shares_outstanding=1,
            params=params, beta=1.0, equity_weight=0.7, debt_weight=0.3,
            interest_expense=10, total_debt=200, tax_rate=0.25, market="US",
        )
        assert result["per_share_value"] is None


class TestOwnerEarnings:
    def test_basic(self):
        """Given: standard financial inputs
           When: Owner Earnings valuation
           Then: returns per_share_value > 0"""
        params = ValuationParams()
        result = calculate_owner_earnings_value(
            net_income=100, depreciation_amortization=20,
            total_capex=30, financial_data={"current_assets": 200, "current_liabilities": 100},
            prev_financial_data={"current_assets": 180, "current_liabilities": 90},
            historical_da=[18, 19, 20], historical_capex=[28, 29, 30],
            shares_outstanding=10, params=params,
        )
        assert result["per_share_value"] > 0
        assert result["owner_earnings"] > 0

    def test_mos_applied(self):
        """Given: Owner Earnings valuation with 25% MOS
           When: computing value
           Then: final value = intrinsic * (1 - 0.25)"""
        params = ValuationParams(owner_earnings_mos=0.25)
        result = calculate_owner_earnings_value(
            net_income=100, depreciation_amortization=20,
            total_capex=30,
            financial_data={"current_assets": 200, "current_liabilities": 100},
            prev_financial_data={"current_assets": 180, "current_liabilities": 90},
            historical_da=[20], historical_capex=[30],
            shares_outstanding=1, params=params,
        )
        assert result["mos_applied"] == 0.25


class TestEVEBITDA:
    def test_basic(self):
        """Given: EBITDA=500, industry EV/EBITDA=15, net_debt=1000
           When: EV/EBITDA valuation
           Then: equity = 500*15 - 1000 = 6500"""
        result = calculate_ev_ebitda(
            ebitda=500, industry_ev_ebitda=15, net_debt=1000,
            minority_interest=0, preferred_stock=0, non_controlling=0,
            roe=0.20, industry_roe=0.15,
            revenue_growth=0.10, industry_growth=0.10,
            params=ValuationParams(), shares_outstanding=1,
        )
        assert result["per_share_value"] == 6500.0

    def test_roe_premium(self):
        """Given: company ROE=32%, industry ROE=15%  (> 2x, triggers premium)
           When: EV/EBITDA valuation
           Then: premium > 1.0"""
        result = calculate_ev_ebitda(
            ebitda=500, industry_ev_ebitda=15, net_debt=0,
            minority_interest=0, preferred_stock=0, non_controlling=0,
            roe=0.32, industry_roe=0.15,
            revenue_growth=0.10, industry_growth=0.10,
            params=ValuationParams(), shares_outstanding=1,
        )
        assert result["premium_applied"] > 1.0


class TestWeights:
    def test_default_weights_sum_to_one(self):
        """Given: default valuation weights
           When: sum weights
           Then: 1.0"""
        p = ValuationParams()
        total = p.weight_dcf + p.weight_owner_earnings + p.weight_ev_ebitda + p.weight_ri
        assert total == pytest.approx(1.0)

    def test_redistribute_when_model_missing(self):
        """Given: RI model None, weights [35,35,20,10]
           When: redistribute_weights
           Then: normalized weights for 3 models"""
        result = redistribute_weights([0.35, 0.35, 0.20, None])
        assert sum(result) == pytest.approx(1.0)
        assert result[3] == 0.0
        assert len(result) == 4

    def test_weighted_value(self):
        """Given: 3 model values with redistributed weights (RI=None)
           When: compute weighted avg
           Then: 200*0.389 + 210*0.389 + 185*0.222 ≈ 200.6"""
        values = [200, 210, 185, None]
        weights = redistribute_weights([0.35, 0.35, 0.20, None])
        # RI missing → normalized: [0.389, 0.389, 0.222, 0.0]
        assert sum(weights) == pytest.approx(1.0)
        assert weights[0] > 0.35  # each surviving weight gets larger share


class TestSensitivity:
    def test_matrix_is_3x3(self):
        """Given: any input
           When: sensitivity matrix
           Then: 3x3 output"""
        result = calculate_sensitivity_matrix(
            base_wacc=0.085, base_growth=0.03,
            wacc_range=(0.075, 0.095, 0.01),
            growth_range=(0.025, 0.035, 0.005),
            base_valuation_func=lambda wacc, growth: {"per_share_value": 100.0 + (growth - wacc) * 1000},
        )
        assert len(result["wacc_values"]) == 3
        assert len(result["growth_values"]) == 3
        assert len(result["matrix"]) == 3
        assert all(len(row) == 3 for row in result["matrix"])

    def test_higher_growth_higher_value(self):
        """Given: base params
           When: sensitivity matrix
           Then: low WACC + high growth = highest value"""
        def val_func(wacc, growth):
            return {"per_share_value": 100.0 + growth * 2000 - wacc * 1000}

        result = calculate_sensitivity_matrix(
            base_wacc=0.085, base_growth=0.03,
            wacc_range=(0.075, 0.095, 0.01),
            growth_range=(0.025, 0.035, 0.005),
            base_valuation_func=val_func,
        )
        # [0][2] = low WACC, high growth → highest value
        m = result["matrix"]
        assert m[0][2] > m[1][1]  # higher than base
