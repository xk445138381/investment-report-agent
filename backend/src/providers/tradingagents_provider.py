"""TradingAgents-astock CN data provider — wraps a_stock.py for CN market.

Uses direct HTTP APIs (mootdx, Tencent, EastMoney, Sina, 10jqka, CLS)
with zero third-party data dependencies. Falls back to QVeris if needed.
"""

import logging
import os
import sys
from datetime import date, datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Add TradingAgents to path
_TA_PATH = r"H:\TradingAgents-astock-0.2.11"
if _TA_PATH not in sys.path:
    sys.path.insert(0, _TA_PATH)

from providers.base import DataProvider


class TradingAgentsProvider(DataProvider):
    """A-stock data via TradingAgents-astock direct HTTP APIs."""

    provider_name = "tradingagents_astock"

    def __init__(self):
        self._available = None

    async def health_check(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            from tradingagents.dataflows.a_stock import resolve_ticker
            code = resolve_ticker("贵州茅台")
            self._available = bool(code and len(str(code)) == 6)
            return self._available
        except Exception as e:
            logger.warning(f"TradingAgents health check failed: {e}")
            self._available = False
            return False

    def supports_market(self, market: str) -> bool:
        return market == "CN"

    async def get_prices(self, ticker: str, start_date: date, end_date: date) -> list:
        try:
            from tradingagents.dataflows.a_stock import get_stock_data, _normalize_ticker
            code = _normalize_ticker(ticker)
            raw = get_stock_data(code, start_date, end_date)
            return _parse_price_csv(raw)
        except Exception as e:
            logger.warning(f"TradingAgents prices({ticker}): {e}")
            return []

    async def get_financials(self, ticker: str, years: int = 5) -> list:
        try:
            from tradingagents.dataflows.a_stock import (
                _normalize_ticker, get_balance_sheet, get_cashflow, get_income_statement
            )
            code = _normalize_ticker(ticker)
            results = []

            # Get income statement (quarterly)
            inc_raw = get_income_statement(code, "quarterly")
            inc_df = _parse_fin_csv(inc_raw)
            if inc_df is None:
                # Try annual
                inc_raw = get_income_statement(code, "annual")
                inc_df = _parse_fin_csv(inc_raw)

            # Get balance sheet
            bs_raw = get_balance_sheet(code)
            bs_df = _parse_fin_csv(bs_raw)

            # Get cash flow
            cf_raw = get_cashflow(code)
            cf_df = _parse_fin_csv(cf_raw)

            # Build results from income statement rows (primary)
            if inc_df is not None and not inc_df.empty:
                for idx, row in inc_df.iterrows():
                    try:
                        rd = _parse_report_date(row)
                        if rd is None or rd.year < date.today().year - years:
                            continue
                        # Match BS row by date
                        bs_row = bs_df.loc[idx] if bs_df is not None and idx in bs_df.index else {}
                        cf_row = cf_df.loc[idx] if cf_df is not None and idx in cf_df.index else {}

                        stmt = {
                            "report_date": rd, "fiscal_year": rd.year,
                            "fiscal_quarter": (rd.month - 1) // 3 + 1, "currency": "CNY",
                            "revenue": _sf(inc_df, idx, ["营业总收入", "营业收入"]),
                            "operating_income": _sf(inc_df, idx, ["营业利润"]),
                            "net_income": _sf(inc_df, idx, ["净利润", "归属于母公司所有者的净利润"]),
                            "eps_basic": _sf(inc_df, idx, ["基本每股收益"]),
                            "eps_diluted": _sf(inc_df, idx, ["稀释每股收益"]),
                            "total_assets": _sf(bs_df, idx, ["资产总计", "总资产"]),
                            "total_liabilities": _sf(bs_df, idx, ["负债合计", "总负债"]),
                            "total_equity": _sf(bs_df, idx, ["股东权益合计", "归属于母公司所有者权益合计"]),
                            "current_assets": _sf(bs_df, idx, ["流动资产合计"]),
                            "current_liabilities": _sf(bs_df, idx, ["流动负债合计"]),
                            "cash_and_equivalents": _sf(bs_df, idx, ["货币资金"]),
                            "operating_cash_flow": _sf(cf_df, idx, ["经营活动产生的现金流量净额"]),
                            "capex": None, "free_cash_flow": None,
                        }
                        if stmt.get("revenue") or stmt.get("net_income"):
                            results.append(stmt)
                    except Exception:
                        continue

            logger.info(f"TradingAgents financials({ticker}): {len(results)} records")
            return sorted(results, key=lambda x: x["report_date"]) if results else []
        except Exception as e:
            logger.warning(f"TradingAgents financials({ticker}): {e}")
            return []

    async def get_news(self, ticker: str, days: int = 30) -> list:
        try:
            from tradingagents.dataflows.a_stock import _normalize_ticker, get_news
            code = _normalize_ticker(ticker)
            news_data = get_news(code, days)
            if isinstance(news_data, list):
                return news_data[:10]
            return []
        except Exception:
            return []


def _parse_price_csv(raw: str) -> list:
    """Parse TradingAgents get_stock_data CSV output into OHLCV dicts."""
    if not raw or not isinstance(raw, str):
        return []
    try:
        import io
        # Skip comment lines starting with #
        lines = [l for l in raw.strip().split("\n") if not l.startswith("#") and l.strip()]
        if len(lines) < 2:
            return []
        reader = _csv.reader(io.StringIO("\n".join(lines)))
        header = next(reader, None)
        if not header:
            return []
        results = []
        for row in reader:
            try:
                if len(row) < 6:
                    continue
                results.append({
                    "date": date.fromisoformat(row[0].strip()),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": int(float(row[5])),
                })
            except (ValueError, IndexError):
                continue
        return results
    except Exception:
        return []


def _parse_fin_csv(raw: str):
    """Parse TradingAgents financial statement CSV output into DataFrame."""
    if not raw or not isinstance(raw, str) or "No " in raw[:50]:
        return None
    try:
        import io
        lines = [l for l in raw.strip().split("\n") if not l.startswith("#") and l.strip()]
        if len(lines) < 2:
            return None
        df = pd.read_csv(io.StringIO("\n".join(lines)))
        if df.empty:
            return None
        # Set the first column as index (usually report_date or similar)
        first_col = df.columns[0]
        if "报告期" in str(first_col) or "date" in str(first_col).lower():
            df = df.set_index(first_col)
        return df
    except Exception:
        return None


def _parse_report_date(row) -> Optional[date]:
    """Extract report date from DataFrame row or index."""
    try:
        # Try index name first
        idx_val = row.name if hasattr(row, "name") else row
        if isinstance(idx_val, (date, datetime)):
            return idx_val if isinstance(idx_val, date) else idx_val.date()
        if isinstance(idx_val, str):
            # Try various date formats
            for fmt in ["%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"]:
                try:
                    return datetime.strptime(idx_val[:10], fmt).date()
                except ValueError:
                    continue
        # Try '报告期' column
        for col_name in ["报告期", "报表日期", "date", "Date"]:
            if hasattr(row, "get"):
                v = row.get(col_name)
            elif col_name in row.index:
                v = row[col_name]
            else:
                continue
            if v:
                return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except Exception:
        pass
    return None


def _sf(df, idx, keys: list[str]) -> Optional[float]:
    """Safely extract float from DataFrame by index and column name candidates."""
    if df is None:
        return None
    try:
        row = df.loc[idx]
        for k in keys:
            if k in df.columns:
                v = row.get(k) if hasattr(row, "get") else row[k]
                if v is not None and str(v) not in ("", "None", "nan"):
                    return abs(float(v))
    except Exception:
        pass
    return None


import csv as _csv
import pandas as pd  # noqa
