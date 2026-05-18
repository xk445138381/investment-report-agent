"""QVeris data provider — routes through QVeris API to cn_financial_pro / Hang Seng PolySource / Caidazi."""

import os
import json
import logging
import time
from datetime import date, datetime
from collections import defaultdict

import httpx

from providers.base import DataProvider

logger = logging.getLogger(__name__)

BASE_URL = "https://qveris.ai/api/v1"
EXECUTE_URL = f"{BASE_URL}/tools/execute"

# Pre-discovered tool IDs
TICK_TOOL = "hangseng_polysource.stock.tickquote.query.v2.e224ffde"
HISTORY_TOOL = "cn_financial_pro.history_quotation.v1"
NEWS_TOOL = "caidazi.news.query.v1.e76b9116"
MACRO_TOOL = "cn_financial_pro.macro_china.v1"

# Simple in-memory TTL cache to reduce QVeris credit usage
_cache: dict[str, tuple[float, any]] = {}
CACHE_TTL = {"prices": 300, "financials": 3600, "news": 600, "macro": 3600}

def _get_cached(key: str, ttl: int, factory):
    now = time.time()
    if key in _cache:
        expiry, val = _cache[key]
        if now < expiry:
            return val
    val = factory()
    _cache[key] = (now + ttl, val)
    return val
FINANCIALS_TOOL = "cn_financial_pro.financial_statements.v1"

def _market(ticker: str) -> str:
    if ".SH" in ticker.upper() or ".SZ" in ticker.upper(): return "CN"
    if ".HK" in ticker.upper(): return "HK"
    return "US"

TICKER_MAP = {
    "600519.SH": "600519.SH", "600519": "600519.SH",
    "000858.SZ": "000858.SZ", "000858": "000858.SZ",
    "300750.SZ": "300750.SZ", "300750": "300750.SZ",
    "000001.SZ": "000001.SZ",
    "AAPL": "AAPL",
    "0700.HK": "0700.HK", "0700": "0700.HK",
}


class QverisProvider(DataProvider):
    """Stock data via QVeris → Hang Seng PolySource (tick) + cn_financial_pro (fundamentals)."""

    provider_name = "qveris"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.getenv("QVERIS_API_KEY", "")
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def health_check(self) -> bool:
        if not self._api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False) as c:
                r = await c.post(
                    f"{EXECUTE_URL}?tool_id={TICK_TOOL}",
                    headers=self._headers,
                    json={"parameters": {"stockObject": ["600519.SH"], "pageSize": 1}},
                )
                return r.status_code == 200
        except Exception:
            return False

    def supports_market(self, market: str) -> bool:
        return market in ("CN", "US", "HK")

    async def get_prices(self, ticker: str, start_date: date, end_date: date) -> list:
        cache_key = f"prices:{ticker}:{start_date}:{end_date}"
        now = time.time()
        if cache_key in _cache:
            expiry, val = _cache[cache_key]
            if now < expiry:
                return val
        result = await self._fetch_prices(ticker, start_date, end_date)
        _cache[cache_key] = (now + CACHE_TTL["prices"], result)
        return result

    async def _fetch_prices(self, ticker: str, start_date: date, end_date: date) -> list:
        code = TICKER_MAP.get(ticker, ticker)
        market = _market(ticker)
        try:
            if market == "US":
                # Use Alpha Vantage for US stocks
                data = await self._call_tool("alphavantage.time_series.daily.v1", {
                    "symbol": code, "function": "TIME_SERIES_DAILY",
                })
                return self._parse_alphavantage_prices(data, ticker, start_date, end_date)
            else:
                data = await self._call_tool(HISTORY_TOOL, {
                    "codes": code,
                    "startdate": start_date.isoformat(),
                    "enddate": end_date.isoformat(),
                    "indicators": "stock_common",
                    "interval": "D",
                })
                return self._parse_history_prices(data, ticker)
        except Exception as e:
            logger.warning(f"QVeris prices({ticker}): {e}")
            return []

    async def get_financials(self, ticker: str, years: int = 5) -> list:
        cache_key = f"financials:{ticker}:{years}"
        now = time.time()
        if cache_key in _cache:
            expiry, val = _cache[cache_key]
            if now < expiry:
                return val
        result = await self._fetch_financials(ticker, years)
        _cache[cache_key] = (now + CACHE_TTL["financials"], result)
        return result

    async def _fetch_financials(self, ticker: str, years: int = 5) -> list:
        import asyncio as _asyncio
        if _market(ticker) != "CN":
            return await self._fetch_us_financials(ticker)

    async def _fetch_us_financials(self, ticker: str) -> list:
        """Fetch US stock financials via Alpha Vantage (3 parallel calls)."""
        import asyncio as _asyncio
        US_IS = "alphavantage.income_statement.list.v1.467a92c0"
        US_BS = "alphavantage.balance_sheet.retrieve.v1.7aca3c4a"
        US_CF = "alphavantage.cash_flow.retrieve.v1.467a92c0"

        async def fetch(tool: str, fn: str):
            try: return await self._call_tool(tool, {"symbol": ticker, "function": fn})
            except Exception: return {}

        is_d, bs_d, cf_d = await _asyncio.gather(
            fetch(US_IS, "INCOME_STATEMENT"), fetch(US_BS, "BALANCE_SHEET"),
            fetch(US_CF, "CASH_FLOW"), return_exceptions=True)

        is_r = (is_d.get("annualReports", []) if isinstance(is_d, dict) else [])
        bs_r = (bs_d.get("annualReports", []) if isinstance(bs_d, dict) else [])
        cf_r = (cf_d.get("annualReports", []) if isinstance(cf_d, dict) else [])
        if not is_r: return []

        def g(r, *keys):
            for k in keys:
                v = r.get(k)
                if v is not None and str(v) not in ("", "None"):
                    try: return abs(float(v))
                    except: pass
            return None

        results = []
        for i, inc in enumerate(is_r[:5]):
            try:
                d_str = inc.get("fiscalDateEnding", ""); d = date.fromisoformat(d_str[:10]) if d_str else date.today()
                bs, cf = (bs_r[i] if i < len(bs_r) else {}), (cf_r[i] if i < len(cf_r) else {})
                results.append({"_report_date": d, "report_date": d,
                    "fiscal_year": d.year, "fiscal_quarter": 4, "currency": "USD",
                    "revenue": g(inc, "totalRevenue"),
                    "operating_income": g(inc, "operatingIncome"),
                    "net_income": g(inc, "netIncome"), "eps_basic": g(inc, "eps"),
                    "eps_diluted": g(inc, "eps"), "ebit": g(inc, "ebit"), "ebitda": g(inc, "ebitda"),
                    "total_assets": g(bs, "totalAssets"),
                    "total_liabilities": g(bs, "totalLiabilities"),
                    "total_equity": g(bs, "totalShareholderEquity"),
                    "current_assets": g(bs, "totalCurrentAssets"),
                    "current_liabilities": g(bs, "totalCurrentLiabilities"),
                    "cash_and_equivalents": g(bs, "cashAndCashEquivalentsAtCarryingValue"),
                    "_shares_outstanding": g(bs, "commonStockSharesOutstanding"),
                    "operating_cash_flow": g(cf, "operatingCashflow"),
                    "capex": g(cf, "capitalExpenditures"),
                    "free_cash_flow": None,  # computed below
                })
                # Compute FCF = OCF - Capex
                ocf = results[-1].get("operating_cash_flow")
                capex = results[-1].get("capex")
                if ocf is not None:
                    results[-1]["free_cash_flow"] = ocf - (capex or 0)
            except Exception: continue
        logger.info(f"US financials({ticker}): {len(results)} annual reports")
        return results
        mapping = TICKER_MAP.get(ticker)
        if not mapping:
            return []
        code = mapping

        _PERIOD_MAP = {"0331": (3, 31), "0630": (6, 30), "0930": (9, 30), "1231": (12, 31)}
        current_year = date.today().year

        async def fetch_one(year: int, period: str):
            """Fetch income + balance sheet for one quarter."""
            try:
                month, day = _PERIOD_MAP[period]
                inc = await self._call_tool("cn_financial_pro.income_statement.v1", {
                    "codes": code, "year": str(year), "period": period, "type": "1",
                })
                rows = inc.get("rows", [])
                if rows:
                    report_d = date(year, month, day)
                    for row in rows:
                        row["_report_date"] = report_d

                    try:
                        bs = await self._call_tool("cn_financial_pro.balance_sheet.v1", {
                            "codes": code, "year": str(year), "period": period, "type": "1",
                        })
                        bs_rows = bs.get("rows", [])
                        if bs_rows:
                            for i, row in enumerate(rows):
                                if i < len(bs_rows):
                                    row.update({k: v for k, v in bs_rows[i].items()
                                               if v is not None and k != "_report_date"})
                    except Exception:
                        pass
                    # Merge cash flow statement
                    try:
                        cf = await self._call_tool("cn_financial_pro.cash_flow_statement.v1", {
                            "codes": code, "year": str(year), "period": period, "type": "1",
                        })
                        cf_rows = cf.get("rows", [])
                        if cf_rows:
                            for i, row in enumerate(rows):
                                if i < len(cf_rows):
                                    row.update({k: v for k, v in cf_rows[i].items()
                                               if v is not None and k != "_report_date"})
                    except Exception:
                        pass
                    # Compute FCF if not provided: FCF = OCF - Capex
                    for row in rows:
                        ocf = row.get("ths_ncf_from_oa_stock")
                        capex = row.get("ths_cash_paid_for_assets_stock")
                        if ocf is not None and capex is not None and "ths_free_cash_flow_stock" not in row:
                            row["ths_free_cash_flow_stock"] = ocf - capex
                    return rows
            except Exception:
                pass
            return []

        # Fire all queries in parallel
        tasks = []
        for year in range(current_year - years, current_year + 1):
            for period in _PERIOD_MAP:
                tasks.append(fetch_one(year, period))

        results = await _asyncio.gather(*tasks, return_exceptions=True)
        all_rows = []
        for r in results:
            if isinstance(r, list):
                all_rows.extend(r)

        if not all_rows:
            return []
        return self._parse_financial_rows(all_rows, ticker)

    async def get_news(self, ticker: str, days: int = 30) -> list:
        cache_key = f"news:{ticker}:{days}"
        now = time.time()
        if cache_key in _cache:
            expiry, val = _cache[cache_key]
            if now < expiry:
                return val
        result = await self._fetch_news(ticker, days)
        _cache[cache_key] = (now + CACHE_TTL["news"], result)
        return result

    async def _fetch_news(self, ticker: str, days: int) -> list:
        try:
            data = await self._call_tool(NEWS_TOOL, {"input": ticker})
            # Caidazi response: {"code": 200, "data": {"hits": [...]}}
            hits = data.get("data", {}).get("hits", data.get("hits", []))
            if isinstance(data, list):
                hits = data
            results = []
            for r in (hits or [])[:8]:
                try:
                    s = r.get("source", r)
                    highlights = r.get("bodySegHighlight", [])
                    results.append({
                        "title": str(s.get("title", "")),
                        "source": str(s.get("siteName", s.get("source", ""))),
                        "date": str(s.get("publishTime", s.get("effectiveTime", "")))[:10],
                        "summary": str(highlights[0] if highlights else r.get("body", "")),
                        "url": str(s.get("s3Url", "")),
                    })
                except Exception:
                    continue
            if results:
                logger.info(f"Got {len(results)} news items for {ticker}")
            return results
        except Exception as e:
            logger.debug(f"QVeris news({ticker}): {e}")
            return []

    async def get_macro(self) -> dict:
        cache_key = "macro:latest"
        now = time.time()
        if cache_key in _cache:
            expiry, val = _cache[cache_key]
            if now < expiry:
                return val
        result = await self._fetch_macro()
        _cache[cache_key] = (now + CACHE_TTL["macro"], result)
        return result

    async def _fetch_macro(self) -> dict:
        try:
            data = await self._call_tool(MACRO_TOOL, {"limit": 10})
            rows = data.get("rows", data.get("data", []))
            if isinstance(data, list):
                rows = data
            return {"indicators": rows if rows else [], "source": "cn_financial_pro.macro_china"}
        except Exception:
            return {"indicators": [], "source": "fallback"}

    # ── QVeris API ──

    async def _call_tool(self, tool_id: str, params: dict) -> dict:
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            r = await client.post(
                f"{EXECUTE_URL}?tool_id={tool_id}",
                headers=self._headers,
                json={"parameters": params},
            )
            if r.status_code != 200:
                raise RuntimeError(f"Tool {tool_id}: HTTP {r.status_code}")
            raw = r.json()
            result = raw.get("result", {})
            data = result.get("data")

            # cn_financial_pro returns data as nested list: [[{row}]]
            if isinstance(data, list):
                flat = []
                for page in data:
                    if isinstance(page, list):
                        flat.extend(page)
                    elif isinstance(page, dict):
                        flat.append(page)
                if flat:
                    return {"rows": flat}
                return {"rows": data}

            # tick tools return data as dict with rows
            tc = result.get("truncated_content", "")
            if tc:
                try:
                    return json.loads(tc)
                except json.JSONDecodeError:
                    pass

            # For large responses, download full content from OSS URL
            full_url = result.get("full_content_file_url", "")
            if full_url and (not data or data == []):
                try:
                    async with httpx.AsyncClient(timeout=30, trust_env=False) as c2:
                        fr = await c2.get(full_url)
                        if fr.status_code == 200:
                            full = fr.json()
                            if isinstance(full, list):
                                # Flatten nested lists: [[[page1]], [[page2]]]
                                flat = []
                                for item in full:
                                    if isinstance(item, list):
                                        for inner in item:
                                            if isinstance(inner, list):
                                                flat.extend(inner)
                                            elif isinstance(inner, dict):
                                                flat.append(inner)
                                    elif isinstance(item, dict):
                                        flat.append(item)
                                return {"rows": flat}
                            return full
                except Exception:
                    pass
            return data if data else {}

    # ── Parsers ──

    def _parse_history_prices(self, data: dict, ticker: str) -> list:
        """Parse cn_financial_pro history_quotation response into daily OHLCV dicts."""
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            rows = data.get("rows", data.get("data", []))
        else:
            return []
        if not rows:
            return []

        results = []
        for r in rows:
            try:
                d_str = str(r.get("time", r.get("trade_date", r.get("date", ""))))
                if not d_str or d_str == "None":
                    continue
                d = date.fromisoformat(d_str[:10])
                c = float(r.get("close", 0) or 0)
                if c <= 0:
                    continue
                results.append({
                    "date": d,
                    "open": float(r.get("open", c) or c),
                    "high": float(r.get("high", c) or c),
                    "low": float(r.get("low", c) or c),
                    "close": c,
                    "volume": int(float(r.get("volume", 0) or 0)),
                })
            except (ValueError, TypeError):
                continue

        logger.info(f"Parsed {len(results)} daily price rows for {ticker}")
        return sorted(results, key=lambda x: x["date"])

    def _parse_alphavantage_prices(self, data: dict, ticker: str,
                                    start_date: date, end_date: date) -> list:
        """Parse Alpha Vantage TIME_SERIES_DAILY response."""
        ts = data.get("Time Series (Daily)", data.get("data", {}))
        if not ts and isinstance(data, list):
            return self._parse_history_prices(data, ticker)
        results = []
        for d_str, ohlc in sorted(ts.items()):
            try:
                d = date.fromisoformat(d_str)
                if d < start_date or d > end_date:
                    continue
                results.append({
                    "date": d,
                    "open": float(ohlc.get("1. open", 0) or 0),
                    "high": float(ohlc.get("2. high", 0) or 0),
                    "low": float(ohlc.get("3. low", 0) or 0),
                    "close": float(ohlc.get("4. close", 0) or 0),
                    "volume": int(float(ohlc.get("5. volume", 0) or 0)),
                })
            except (ValueError, TypeError):
                continue
        logger.info(f"Parsed {len(results)} US daily prices for {ticker}")
        return sorted(results, key=lambda x: x["date"])

    def _parse_ticks_to_daily(self, data: dict, ticker: str,
                              start_date: date, end_date: date) -> list:
        """Parse Hang Seng PolySource tick data, aggregate into daily OHLCV bars."""
        rows = []
        # Navigate: data.data.rows (common for this tool)
        for key in ("data", "rows", "records"):
            candidate = data.get(key, data)
            if isinstance(candidate, dict):
                inner = candidate.get("data", candidate)
                if isinstance(inner, dict):
                    rows = inner.get("rows", inner.get("records", []))
                    if rows:
                        break
            elif isinstance(candidate, list):
                rows = candidate
                break

        if not rows:
            logger.info(f"No tick rows for {ticker}")
            return []

        # Group ticks by date → collect prices
        day_data = defaultdict(list)
        for r in rows:
            try:
                ts = r.get("tradingTimestamp", r.get("timestamp", r.get("date", "")))
                if not ts:
                    continue
                d = date.fromisoformat(str(ts)[:10])
                if d < start_date or d > end_date:
                    continue

                px = float(r.get("latestPrice", r.get("close", r.get("price", 0))) or 0)
                vol = int(float(r.get("turnoverVolumeLot", r.get("volume", 0)) or 0))
                if px > 0:
                    day_data[d].append((px, vol))
            except (ValueError, TypeError):
                continue

        results = []
        for d in sorted(day_data):
            ticks = day_data[d]
            if not ticks:
                continue
            prices = [t[0] for t in ticks]
            total_vol = sum(t[1] for t in ticks)
            results.append({
                "date": d,
                "open": prices[0],
                "high": max(prices),
                "low": min(prices),
                "close": prices[-1],
                "volume": total_vol,
            })

        logger.info(f"Parsed {len(results)} daily bars for {ticker} (from {len(rows)} ticks)")
        return results

    # THS iFinD → standard field mapping (income + balance sheet)
    _THS_FIELDS = {
        "revenue": ("ths_operating_total_revenue_stock", "ths_revenue_stock"),
        "operating_income": ("ths_op_stock", "ths_operating_profit_stock"),
        "net_income": ("ths_np_atoopc_stock", "ths_np_stock"),
        "eps_basic": ("ths_basic_eps_stock",),
        "eps_diluted": ("ths_dlt_earnings_per_share_stock",),
        # Balance sheet fields (actual THS names)
        "total_assets": ("ths_total_assets_stock",),
        "total_liabilities": ("ths_total_liab_stock", "ths_total_liabilities_stock"),
        "total_equity": ("ths_total_owner_equity_stock", "ths_total_equity_stock",
                         "ths_equity_atoopc_stock"),
        "current_assets": ("ths_total_current_assets_stock", "ths_current_assets_stock"),
        "current_liabilities": ("ths_total_current_liab_stock", "ths_current_liabilities_stock"),
        "cash_and_equivalents": ("ths_cash_and_equivalents_stock", "ths_cash_stock"),
        "goodwill": ("ths_goodwill_stock",),
        "intangible_assets": ("ths_intangible_assets_stock", "ths_intangible_asset_stock"),
        # Cash flow fields (cn_financial_pro.cash_flow_statement)
        "operating_cash_flow": ("ths_ncf_from_oa_stock", "ths_operating_cash_flow_stock",
                                "ths_ocf_stock", "ths_net_cf_operating_stock"),
        "capex": ("ths_cash_paid_for_assets_stock", "ths_capex_stock"),
        "free_cash_flow": ("ths_free_cash_flow_stock", "ths_fcf_stock"),
    }

    def _parse_financial_rows(self, rows: list, ticker: str) -> list:
        """Parse THS iFinD rows into standard statement dicts."""
        results = []
        for r in rows:
            # Date is set by the caller as _report_date
            d = r.get("_report_date")
            if not d:
                continue

            stmt = {"_report_date": d, "report_date": d, "fiscal_year": d.year,
                    "fiscal_quarter": ((d.month - 1) // 3) + 1, "currency": "CNY"}

            for our_key, ths_keys in self._THS_FIELDS.items():
                for tk in ths_keys:
                    v = r.get(tk)
                    if v is not None and str(v) not in ("", "None", "null"):
                        try:
                            stmt[our_key] = abs(float(v))
                            break
                        except (ValueError, TypeError):
                            pass

            if stmt.get("revenue") or stmt.get("net_income"):
                results.append(stmt)

        logger.info(f"Parsed {len(results)} financial statements for {ticker}")
        return results


def _partial_parse(text: str) -> dict:
    """Attempt to salvage partial JSON by closing unclosed structures."""
    # Count open/close braces
    text = text.strip()
    if not text:
        return {}
    # Find the last valid JSON object close
    depth = 0
    last_valid = 0
    for i, ch in enumerate(text):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                last_valid = i + 1
    if last_valid > 0:
        try:
            return json.loads(text[:last_valid])
        except json.JSONDecodeError:
            pass
    return {}
