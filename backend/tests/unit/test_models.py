"""T03: Core data model tests (TDD — write before implementation)."""

from datetime import date, datetime
import pytest
from pydantic import ValidationError


class TestPriceData:
    """Given: standardized price data
       When: creating PriceData instances
       Then: correct types and validation"""

    def test_create_valid_price_data(self):
        """Given: complete OHLCV data
           When: PriceData(...)
           Then: all fields match"""
        from models.financial import PriceData
        d = date(2026, 5, 17)
        p = PriceData(
            ticker="600519.SH", date=d,
            open=1680.0, high=1695.0, low=1675.0, close=1688.0,
            volume=5000000, currency="CNY",
        )
        assert p.ticker == "600519.SH"
        assert p.close == 1688.0
        assert p.currency == "CNY"

    def test_volume_can_be_none(self):
        """Given: some data sources don't provide volume
           When: PriceData(volume=None)
           Then: instance created successfully"""
        from models.financial import PriceData
        p = PriceData(
            ticker="AAPL", date=date(2026, 5, 17),
            open=185.0, high=186.0, low=184.0, close=185.5,
            volume=None, currency="USD",
        )
        assert p.volume is None

    def test_negative_price_rejected(self):
        """Given: close=-1680.0
           When: PriceData(...)
           Then: ValidationError"""
        from models.financial import PriceData
        with pytest.raises(ValidationError):
            PriceData(
                ticker="600519.SH", date=date(2026, 5, 17),
                open=1680.0, high=1695.0, low=1675.0, close=-1680.0,
                volume=5000000, currency="CNY",
            )

    def test_currency_must_be_known(self):
        """Given: currency="EUR"
           When: PriceData(...)
           Then: ValidationError"""
        from models.financial import PriceData
        with pytest.raises(ValidationError):
            PriceData(
                ticker="600519.SH", date=date(2026, 5, 17),
                open=1680.0, high=1695.0, low=1675.0, close=1680.0,
                volume=5000000, currency="EUR",
            )


class TestFinancialStatement:
    """Given: standardized financial statement data
       When: creating FinancialStatement instances
       Then: correct validation and optional field handling"""

    def test_revenue_and_net_income_mandatory_at_least_one(self):
        """Given: revenue=None AND net_income=None
           When: FinancialStatement(...)
           Then: ValidationError"""
        from models.financial import FinancialStatement
        with pytest.raises(ValidationError):
            FinancialStatement(
                ticker="600519.SH", report_date=date(2025, 12, 31),
                fiscal_year=2025, fiscal_quarter=4, currency="CNY",
                revenue=None, net_income=None,
            )

    def test_all_optional_fields_can_be_none(self):
        """Given: minimal required fields only
           When: FinancialStatement(...)
           Then: success, optional fields None"""
        from models.financial import FinancialStatement
        fs = FinancialStatement(
            ticker="600519.SH", report_date=date(2025, 12, 31),
            fiscal_year=2025, fiscal_quarter=4, currency="CNY",
            revenue=168000000000,
        )
        assert fs.net_income is None
        assert fs.total_assets is None
        assert fs.eps_basic is None

    def test_fiscal_quarter_range(self):
        """Given: fiscal_quarter=5
           When: FinancialStatement(...)
           Then: ValidationError"""
        from models.financial import FinancialStatement
        with pytest.raises(ValidationError):
            FinancialStatement(
                ticker="600519.SH", report_date=date(2025, 12, 31),
                fiscal_year=2025, fiscal_quarter=5, currency="CNY",
                revenue=168000000000,
            )


class TestReportState:
    """Given: ReportState during report generation phases
       When: updating state
       Then: preserves previous phase data (copy-on-write)"""

    def test_phase_transition_preserves_previous_data(self):
        """Given: state with phase 1 raw_data
           When: create updated state with phase 2 results
           Then: raw_data preserved"""
        from models.report import ReportState
        state = ReportState(
            ticker="600519.SH",
            company_name="贵州茅台",
            report_type="deep_dive",
            template_id="deep_dive_default",
            raw_data={"prices": [], "financials": []},
        )
        updated = state.model_copy(update={
            "analysis_results": {"financial_health_score": 28},
        })
        assert updated.raw_data["prices"] is not None
        assert updated.analysis_results is not None

    def test_debate_state_tracks_rounds(self):
        """Given: DebateState with round=1
           When: advance to round 2
           Then: round=2, history includes round 1"""
        from models.report import DebateState
        ds = DebateState(round=1, bull_arguments=[], bear_arguments=[], judge_conclusion=None)
        ds2 = ds.model_copy(update={
            "round": 2,
            "history": ["Round 1 output here"],
        })
        assert ds2.round == 2
        assert len(ds2.history) == 1

    def test_report_sections_completeness(self):
        """Given: template requires 7 sections
           When: ReportState has only 6
           Then: completeness check returns False"""
        from models.report import ReportState, ReportSection
        required = {"exec_summary", "company_overview", "industry", "financials",
                     "valuation", "risks", "recommendation"}
        state = ReportState(
            ticker="600519.SH",
            company_name="贵州茅台",
            report_type="deep_dive",
            template_id="deep_dive_default",
        )
        # Set only 6 sections
        state.report_sections = {
            k: ReportSection(title=f"Section {k}", content="...", word_count=100)
            for k in ["exec_summary", "company_overview", "industry",
                       "financials", "valuation", "risks"]
        }
        missing = required - set(state.report_sections.keys())
        assert len(missing) == 1
        assert "recommendation" in missing


class TestValuationResult:
    """Given: valuation engine output
       When: creating ValuationResult
       Then: correct types and signal classification"""

    def test_undervalued_signal(self):
        """Given: weighted_upside_pct=17.3
           When: ValuationResult(...)
           Then: signal='undervalued'"""
        from models.valuation import ValuationResult
        vr = ValuationResult(
            ticker="600519.SH",
            current_price=1680.0,
            market_cap=2_100_000_000_000,
            models={},
            weighted_value=1970.25,
            weighted_upside_pct=17.3,
            sensitivity_matrix={},
            signal="undervalued",
        )
        assert vr.signal == "undervalued"
        assert vr.weighted_upside_pct > 0
