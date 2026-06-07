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
SEARCH_URL = f"{BASE_URL}/search"

# Pre-discovered tool IDs
HISTORY_TOOL = "cn_financial_pro.history_quotation.v1"
HK_LIVE_TOOL = "hangseng_polysource.quote.hkshares.live.v2.dec427af"
HK_DAILY_TOOL = "hangseng_polysource.hk_stock.daily.quote.create.v2.dd094924"
NEWS_TOOL = "caidazi.news.query.v1.e76b9116"
MACRO_TOOL = "caidazi.get_macro_analysis.execute.v1.7a43f96e"
INDUSTRY_TOOL = "caidazi.get_sw_l1_fina_indic.execute.v1.7a43f96e"
HOLDERS_TOOL = "yahoo_finance.finance_holders.v1"

# Simple in-memory TTL cache to reduce QVeris credit usage
_cache: dict[str, tuple[float, any]] = {}
CACHE_TTL = {"prices": 300, "financials": 3600, "news": 600, "macro": 3600}

FINANCIALS_TOOL = "cn_financial_pro.financial_statements.v1"

def _market(ticker: str) -> str:
    if ".SH" in ticker.upper() or ".SZ" in ticker.upper(): return "CN"
    if ".HK" in ticker.upper() or ticker.startswith("0"): return "HK"
    return "US"


def _cn_financial_code(ticker: str) -> str | None:
    mapped = TICKER_MAP.get(ticker)
    if mapped:
        return mapped
    upper = ticker.upper()
    if "." in upper:
        code, suffix = upper.split(".", 1)
        if len(code) == 6 and code.isdigit() and suffix in {"SH", "SZ"}:
            return f"{code}.{suffix}"
    if len(upper) == 6 and upper.isdigit():
        return upper + (".SH" if upper.startswith("6") else ".SZ")
    return None

# Ticker → standardized code
TICKER_MAP = {
    "600519.SH": "600519.SH", "600519": "600519.SH",
    "000858.SZ": "000858.SZ", "000858": "000858.SZ",
    "300750.SZ": "300750.SZ", "300750": "300750.SZ",
    "000001.SZ": "000001.SZ",
    "AAPL": "AAPL",
    "0700.HK": "00700", "0700": "00700", "00700": "00700",
}
# Ticker → company name (for report titles)
COMPANY_NAMES = {
    "600519.SH": "贵州茅台", "600519": "贵州茅台",
    "000858.SZ": "五粮液", "000858": "五粮液",
    "300750.SZ": "宁德时代", "300750": "宁德时代",
    "000001.SZ": "平安银行",
    "AAPL": "Apple Inc.",
    "0700.HK": "腾讯控股", "0700": "腾讯控股", "00700": "腾讯控股",
}
# HK ticker → Chinese company name (required by hangseng_polysource daily tool)
HK_NAME_MAP = {
    "00700": "腾讯控股", "0700": "腾讯控股", "0700.HK": "腾讯控股",
    "09988": "阿里巴巴-SW", "9988": "阿里巴巴-SW", "9988.HK": "阿里巴巴-SW",
    "00388": "香港交易所", "0388": "香港交易所", "0388.HK": "香港交易所",
    "01299": "友邦保险", "1299": "友邦保险", "1299.HK": "友邦保险",
    "00005": "汇丰控股", "0005": "汇丰控股", "0005.HK": "汇丰控股",
    "03690": "美团-W", "3690": "美团-W", "3690.HK": "美团-W",
    "01810": "小米集团-W", "1810": "小米集团-W", "1810.HK": "小米集团-W",
    "02318": "中国平安", "2318": "中国平安", "2318.HK": "中国平安",
    "00941": "中国移动", "0941": "中国移动", "0941.HK": "中国移动",
    "03968": "招商银行", "3968": "招商银行", "3968.HK": "招商银行",
    "01211": "比亚迪股份", "1211": "比亚迪股份", "1211.HK": "比亚迪股份",
    "02269": "药明生物", "2269": "药明生物", "2269.HK": "药明生物",
    "02020": "安踏体育", "2020": "安踏体育", "2020.HK": "安踏体育",
    "09618": "京东集团-SW", "9618": "京东集团-SW", "9618.HK": "京东集团-SW",
    "09999": "网易-S", "9999": "网易-S", "9999.HK": "网易-S",
    "00027": "银河娱乐", "0027": "银河娱乐", "0027.HK": "银河娱乐",
    "00175": "吉利汽车", "0175": "吉利汽车", "0175.HK": "吉利汽车",
    "02382": "舜宇光学科技", "2382": "舜宇光学科技", "2382.HK": "舜宇光学科技",
    "00016": "新鸿基地产", "0016": "新鸿基地产", "0016.HK": "新鸿基地产",
    "00011": "恒生银行", "0011": "恒生银行", "0011.HK": "恒生银行",
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
                r = await c.post(SEARCH_URL, headers=self._headers,
                                 json={"query": "stock", "limit": 1})
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
        result = await self._fetch_prices(ticker, start_date, end_date) or []
        _cache[cache_key] = (now + CACHE_TTL["prices"], result)
        return result

    async def _fetch_prices(self, ticker: str, start_date: date, end_date: date) -> list:
        code = TICKER_MAP.get(ticker, ticker)
        market = _market(ticker)
        try:
            if market == "US":
                data = await self._call_tool("alphavantage.time_series.daily.v1", {
                    "symbol": code, "function": "TIME_SERIES_DAILY",
                })
                return self._parse_alphavantage_prices(data, ticker, start_date, end_date)
            elif market == "HK":
                # Try daily history first, fall back to live quote
                data = await self._fetch_hk_daily(ticker, start_date, end_date)
                if data:
                    return data
                # Fallback: live quote as single-day snapshot
                data = await self._call_tool(HK_LIVE_TOOL, {
                    "stockObject": [code.replace(".HK", "")], "pageNo": 1, "pageSize": 1,
                })
                return self._parse_hk_live(data, ticker)
            else:
                # Request in 3-month chunks to avoid OSS truncation (OSS URLs expire)
                import asyncio as _asyncio
                from datetime import timedelta
                from functools import partial

                async def _fetch_chunk(start_d, end_d):
                    try:
                        d = await self._call_tool(HISTORY_TOOL, {
                            "codes": code, "startdate": start_d.isoformat(),
                            "enddate": end_d.isoformat(),
                            "indicators": "stock_common", "interval": "D",
                        })
                        return self._parse_history_prices(d, ticker)
                    except Exception:
                        return []

                tasks = []
                current = start_date
                while current < end_date:
                    chunk_end = min(current + timedelta(days=90), end_date)
                    tasks.append(_fetch_chunk(current, chunk_end))
                    current = chunk_end + timedelta(days=1)

                chunks = await _asyncio.gather(*tasks)
                all_rows = []
                for c in chunks:
                    if isinstance(c, list): all_rows.extend(c)
                return sorted(all_rows, key=lambda x: x["date"])
        except Exception as e:
            logger.warning(f"QVeris prices({ticker}): {e}")
            return []

    async def _fetch_hk_daily(self, ticker: str, start_date: date, end_date: date) -> list:
        """Fetch HK daily OHLCV history via hangseng_polysource daily quote tool."""
        code = TICKER_MAP.get(ticker, ticker).replace(".HK", "")
        # The tool requires Chinese company names, not stock codes
        hk_name = HK_NAME_MAP.get(code, HK_NAME_MAP.get(ticker, ""))
        stock_obj = hk_name if hk_name else code
        try:
            data = await self._call_tool(HK_DAILY_TOOL, {
                "stockObject": [stock_obj],
                "beginDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
            })
            return self._parse_hk_daily(data, ticker)
        except Exception as e:
            logger.warning(f"HK daily({ticker}): {e}, trying live quote fallback")
            return []

    def _parse_hk_daily(self, data: dict, ticker: str) -> list:
        """Parse hangseng_polysource daily quote rows into standard OHLCV dicts."""
        rows = data.get("data", {}).get("data", {}).get("rows", [])
        if not rows and isinstance(data, dict):
            # Try deeper nesting paths
            for path in [
                ["data", "data", "data", "rows"],
                ["data", "rows"],
                ["rows"],
            ]:
                d = data
                for key in path:
                    d = d.get(key, {}) if isinstance(d, dict) else {}
                if isinstance(d, list) and d:
                    rows = d
                    break
        if not rows:
            return []

        results = []
        for r in rows:
            try:
                d_str = str(r.get("tradingday", ""))
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

        logger.info(f"Parsed {len(results)} HK daily prices for {ticker}")
        return sorted(results, key=lambda x: x["date"])

    async def get_financials(self, ticker: str, years: int = 5) -> list:
        cache_key = f"financials:{ticker}:{years}"
        now = time.time()
        if cache_key in _cache:
            expiry, val = _cache[cache_key]
            if now < expiry:
                return val
        result = await self._fetch_financials(ticker, years) or []
        _cache[cache_key] = (now + CACHE_TTL["financials"], result)
        return result

    async def _fetch_financials(self, ticker: str, years: int = 5) -> list:
        import asyncio as _asyncio
        market = _market(ticker)
        if market == "HK":
            return await self._fetch_hk_financials(ticker, years)
        if market != "CN":
            return await self._fetch_us_financials(ticker)
        code = _cn_financial_code(ticker)
        if not code: return []
        _PERIOD_MAP = {"0331": (3, 31), "0630": (6, 30), "0930": (9, 30), "1231": (12, 31)}
        current_year = date.today().year

        async def fetch_one(year: int, period: str):
            try:
                month, day = _PERIOD_MAP[period]
                inc = await self._call_tool("cn_financial_pro.income_statement.v1",
                    {"codes": code, "year": str(year), "period": period, "type": "1"})
                rows = inc.get("rows", [])
                if rows:
                    report_d = date(year, month, day)
                    for row in rows: row["_report_date"] = report_d
                    try:
                        bs = await self._call_tool("cn_financial_pro.balance_sheet.v1",
                            {"codes": code, "year": str(year), "period": period, "type": "1"})
                        bs_rows = bs.get("rows", [])
                        if bs_rows:
                            for i, row in enumerate(rows):
                                if i < len(bs_rows):
                                    row.update({k: v for k, v in bs_rows[i].items()
                                               if v is not None and k != "_report_date"})
                    except Exception: pass
                    try:
                        cf = await self._call_tool("cn_financial_pro.cash_flow_statement.v1",
                            {"codes": code, "year": str(year), "period": period, "type": "1"})
                        cf_rows = cf.get("rows", [])
                        if cf_rows:
                            for i, row in enumerate(rows):
                                if i < len(cf_rows):
                                    row.update({k: v for k, v in cf_rows[i].items()
                                               if v is not None and k != "_report_date"})
                    except Exception: pass
                    for row in rows:
                        ocf = row.get("ths_ncf_from_oa_stock")
                        capex = row.get("ths_cash_paid_for_assets_stock")
                        if ocf is not None and capex is not None and "ths_free_cash_flow_stock" not in row:
                            row["ths_free_cash_flow_stock"] = ocf - capex
                    return rows
            except Exception: return []
            return []

        tasks = [fetch_one(year, period)
                 for year in range(current_year - years, current_year + 1)
                 for period in _PERIOD_MAP]
        results = await _asyncio.gather(*tasks, return_exceptions=True)
        all_rows = []
        for r in results:
            if isinstance(r, list): all_rows.extend(r)
        if not all_rows: return []
        return self._parse_financial_rows(all_rows, ticker)

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

    async def _fetch_hk_financials(self, ticker: str, years: int = 5) -> list:
        """Fetch HK financials via AkShare stock_financial_hk_analysis_indicator_em."""
        code = TICKER_MAP.get(ticker, ticker).replace(".HK", "")
        try:
            import akshare as ak
            df = ak.stock_financial_hk_analysis_indicator_em(symbol=code)
            if df is None or df.empty:
                logger.warning(f"HK financials({ticker}): AkShare returned empty")
                return []
            # Filter to recent years, keep annual reports only (DATE_TYPE_CODE=001)
            df_annual = df[df["DATE_TYPE_CODE"] == "001"].copy()
            if df_annual.empty:
                # Fallback to all rows if no annual filter
                df_annual = df
            results = []
            for _, r in df_annual.iterrows():
                try:
                    d_str = str(r.get("REPORT_DATE", ""))
                    if not d_str or d_str == "None":
                        continue
                    rd = date.fromisoformat(d_str[:10])
                    if rd.year < date.today().year - years:
                        continue
                    net_income = _float(r, "HOLDER_PROFIT")
                    revenue = _float(r, "OPERATE_INCOME")
                    # Derive balance sheet from ratios (AkShare only gives ratios, not absolute BS)
                    roe_pct = (_float(r, "ROE_AVG") or 0) / 100
                    debt_pct = (_float(r, "DEBT_ASSET_RATIO") or 0) / 100
                    curr_debt_pct = (_float(r, "CURRENTDEBT_DEBT") or 0) / 100
                    curr_ratio = _float(r, "CURRENT_RATIO")
                    bps_val = _float(r, "BPS")
                    total_equity = net_income / roe_pct if net_income and roe_pct > 0 else None
                    total_assets = total_equity / (1 - debt_pct) if total_equity and debt_pct < 1 else None
                    total_liabilities = total_assets - total_equity if total_assets and total_equity else None
                    current_liabilities = total_liabilities * curr_debt_pct if total_liabilities and curr_debt_pct else None
                    current_assets = current_liabilities * curr_ratio if current_liabilities and curr_ratio else None
                    # AkShare provides per-share values; derive absolutes from ratios
                    tax_rate = (_float(r, "TAX_EBT") or 15) / 100
                    gross_profit = _float(r, "GROSS_PROFIT")
                    ocf_sales_ratio = (_float(r, "OCF_SALES") or 0) / 100
                    operating_income = net_income / (1 - tax_rate) if net_income and tax_rate < 1 else gross_profit
                    operating_cash_flow = revenue * ocf_sales_ratio if revenue and ocf_sales_ratio else None
                    results.append({
                        "report_date": rd, "fiscal_year": rd.year,
                        "fiscal_quarter": 4, "currency": "HKD",
                        "revenue": revenue,
                        "operating_income": operating_income,
                        "net_income": net_income,
                        "eps_basic": _float(r, "BASIC_EPS"),
                        "eps_diluted": _float(r, "DILUTED_EPS"),
                        "total_assets": total_assets,
                        "total_liabilities": total_liabilities,
                        "total_equity": total_equity,
                        "current_assets": current_assets, "current_liabilities": current_liabilities,
                        "cash_and_equivalents": None,  # Not available in ratio data
                        "operating_cash_flow": operating_cash_flow,
                        "capex": None, "free_cash_flow": None,
                        # Extra fields for analysis
                        "_roe": _float(r, "ROE_AVG"),
                        "_roa": _float(r, "ROA"),
                        "_gross_margin": _float(r, "GROSS_PROFIT_RATIO"),
                        "_net_margin": _float(r, "NET_PROFIT_RATIO"),
                        "_debt_ratio": _float(r, "DEBT_ASSET_RATIO"),
                        "_current_ratio": curr_ratio,
                        "_ocf_sales": _float(r, "OCF_SALES"),
                        "_revenue_yoy": _float(r, "OPERATE_INCOME_YOY"),
                        "_profit_yoy": _float(r, "HOLDER_PROFIT_YOY"),
                        "_derived_bs": True,  # flag: balance sheet derived from ratios
                    })
                except Exception:
                    continue
            logger.info(f"HK financials({ticker}): {len(results)} annual reports via AkShare")
            results.sort(key=lambda x: x["report_date"])  # ascending = oldest first
            return results
        except Exception as e:
            logger.warning(f"HK financials({ticker}): AkShare failed: {e}")
            return []

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

    async def get_industry(self, ticker: str) -> dict:
        """Fetch 申万 L1 industry financial indicators for comparison."""
        try:
            data = await self._call_tool(INDUSTRY_TOOL, {"symbol": ticker})
            return data if isinstance(data, dict) else {"raw": str(data)}
        except Exception as e:
            logger.debug(f"Industry data({ticker}): {e}")
            return {}

    async def get_holders(self, ticker: str) -> dict:
        """Fetch institutional ownership data via Yahoo Finance."""
        try:
            data = await self._call_tool(HOLDERS_TOOL, {
                "symbol": ticker, "holder_type": "institutional", "max_results": 5
            })
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

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

    def _parse_hk_live(self, data: dict, ticker: str) -> list:
        """Parse HK live quote into a single PriceData dict."""
        rows = data.get("data", {}).get("data", {}).get("rows", [])
        if not rows and isinstance(data, dict):
            inner = data.get("data", {})
            if isinstance(inner, dict):
                rows = inner.get("data", {}).get("rows", [])
        if not rows:
            return []
        r = rows[0]
        today = date.today()
        try:
            return [{
                "date": today,
                "open": float(r.get("openPrice", 0) or 0),
                "high": float(r.get("highPrice", 0) or 0),
                "low": float(r.get("lowPrice", 0) or 0),
                "close": float(r.get("latestPrice", 0) or 0),
                "volume": int(float(r.get("turnoverVolumeLot", 0) or 0)),
            }]
        except (ValueError, TypeError):
            return []

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


def _float(row, key: str):
    """Safely extract float from a DataFrame row by key."""
    try:
        v = row.get(key)
        if v is None or (isinstance(v, float) and v != v):  # NaN check
            return None
        return float(v)
    except (ValueError, TypeError):
        return None


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
