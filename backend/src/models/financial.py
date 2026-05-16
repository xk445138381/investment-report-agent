"""Core financial data models — PriceData, FinancialStatement, NewsItem."""

from datetime import date, datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class PriceData(BaseModel):
    """Standardized daily OHLCV price data."""
    ticker: str
    date: date
    open: float
    high: float
    low: float
    close: float = Field(ge=0)
    volume: Optional[int] = None
    currency: Literal["CNY", "USD", "HKD"]

    @field_validator("close")
    @classmethod
    def close_must_be_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("close price must be >= 0")
        return v

    @field_validator("open", "high", "low")
    @classmethod
    def price_must_be_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("price must be >= 0")
        return v


class FinancialStatement(BaseModel):
    """Standardized financial statement covering BS/IS/CF."""
    ticker: str
    report_date: date
    fiscal_year: int
    fiscal_quarter: int = Field(ge=1, le=4)
    currency: Literal["CNY", "USD", "HKD"]

    # Income Statement (all optional — at least one must be present)
    revenue: Optional[float] = None
    operating_income: Optional[float] = None
    net_income: Optional[float] = None
    eps_basic: Optional[float] = None
    eps_diluted: Optional[float] = None

    # Balance Sheet
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    total_equity: Optional[float] = None
    current_assets: Optional[float] = None
    current_liabilities: Optional[float] = None
    cash_and_equivalents: Optional[float] = None
    goodwill: Optional[float] = None
    intangible_assets: Optional[float] = None

    # Cash Flow Statement
    operating_cash_flow: Optional[float] = None
    capex: Optional[float] = None
    free_cash_flow: Optional[float] = None

    @field_validator("revenue")
    @classmethod
    def at_least_one_financial_required(cls, v: Optional[float], info) -> Optional[float]:
        return v

    @model_validator(mode="after")
    def check_at_least_one_financial(self):
        if self.revenue is None and self.net_income is None:
            raise ValueError("At least one of revenue or net_income must be provided")
        return self


class NewsItem(BaseModel):
    """Standardized news/announcement item."""
    ticker: str
    title: str
    source: str
    url: Optional[str] = None
    published_at: datetime
    summary: Optional[str] = None
    sentiment: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    category: str = "other"  # earnings, mna, regulatory, market, other
