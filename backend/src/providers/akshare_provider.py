"""AkShare data provider — A-share stock data (prices, financials, news)."""

import logging
from datetime import date
from typing import Optional

import akshare as ak

from .base import DataProvider

logger = logging.getLogger(__name__)

# ── Ticker parsing ──

def _parse_cn_ticker(ticker: str) -> tuple[str, str]:
    """Parse '600519.SH' → ('600519', 'sh') or '000858.SZ' → ('000858', 'sz')."""
    if "." in ticker:
        code, market = ticker.split(".")
        return code, market.lower()
    return ticker, "sh"


# ── Helper — safe AkShare call with timeout ──

async def _safe_ak_call(func, *args, **kwargs):
    """Wrap akshare sync calls to catch common errors."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    except Exception as e:
        logger.warning(f"AkShare call failed: {func.__name__} — {e}")
        raise


class AkShareProvider(DataProvider):
    """AkShare data provider for China A-share market."""

    @property
    def provider_name(self) -> str:
        return "akshare"

    async def health_check(self) -> bool:
        try:
            await _safe_ak_call(
                ak.stock_zh_a_hist,
                symbol="600519", period="daily",
                start_date="20260101", end_date="20260517", adjust="",
            )
            return True
        except Exception:
            return False

    def supports_market(self, market: str) -> bool:
        return market.upper() == "CN"

    async def get_prices(self, ticker: str, start_date: date, end_date: date) -> list:
        """Get daily OHLCV for an A-share stock."""
        code, _ = _parse_cn_ticker(ticker)
        df = await _safe_ak_call(
            ak.stock_zh_a_hist,
            symbol=code,
            period="daily",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            adjust="qfq",
        )
        if df is None or df.empty:
            return []

        from models.financial import PriceData as PD

        return [
            PD(
                ticker=ticker,
                date=date.fromisoformat(str(row["日期"])[:10]),
                open=float(row["开盘"]),
                high=float(row["最高"]),
                low=float(row["最低"]),
                close=float(row["收盘"]),
                volume=int(row["成交量"]),
                currency="CNY",
            )
            for _, row in df.iterrows()
        ][-500:]  # limit to last 500 days

    async def get_financials(self, ticker: str, years: int = 5) -> list:
        """Get financial indicators for an A-share stock."""
        code, _ = _parse_cn_ticker(ticker)
        try:
            df = await _safe_ak_call(
                ak.stock_financial_analysis_indicator,
                symbol=code,
            )
        except Exception:
            logger.info(f"No financial indicators via analysis_indicator for {ticker}")
            return []

        if df is None or df.empty:
            return []

        from models.financial import FinancialStatement as FS

        results = []
        for _, row in df.iterrows():
            try:
                fs = FS(
                    ticker=ticker,
                    report_date=_parse_date(str(row.get("日期", ""))),
                    fiscal_year=int(str(row.get("日期", ""))[:4]) if row.get("日期") else 2025,
                    fiscal_quarter=4,
                    currency="CNY",
                    revenue=_safe_float(row.get("营业总收入")),
                    net_income=_safe_float(row.get("净利润")),
                    eps_basic=_safe_float(row.get("基本每股收益")),
                    eps_diluted=_safe_float(row.get("稀释每股收益")),
                    total_assets=_safe_float(row.get("资产总计")),
                    total_liabilities=_safe_float(row.get("负债合计")),
                    total_equity=_safe_float(row.get("归属母公司股东权益合计")),
                )
                results.append(fs)
            except Exception:
                continue

        return results[-years * 4:]  # ~4 quarters per year

    async def get_news(self, ticker: str, days: int = 30) -> list:
        """A-share news via AkShare (returns empty — news via separate source)."""
        return []  # AkShare news API unstable; use dedicated news provider


def _parse_date(s: str) -> date:
    """Parse various Chinese date formats."""
    for fmt in ["%Y%m%d", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"]:
        try:
            from datetime import datetime as dt
            return dt.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return date.today()


def _safe_float(v) -> Optional[float]:
    """Convert to float, returning None for invalid values."""
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None
