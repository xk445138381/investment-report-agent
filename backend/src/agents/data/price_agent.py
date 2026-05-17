"""Price Data Agent — fetch market data, compute technical indicators."""

import logging
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)


async def run_price_agent(
    ticker: str,
    company_name: str,
    prices: list,
) -> dict:
    """Execute price/market data agent.

    Args:
        ticker: Stock ticker
        company_name: Company name
        prices: List of PriceData from provider

    Returns:
        dict with price_summary and technical_signals
    """
    if not prices:
        return {"ticker": ticker, "error": "no_price_data"}

    latest = prices[-1]
    closes = [p.close for p in prices]
    # Use Pandas-style operations on raw lists
    price_summary = {
        "latest_price": latest.close,
        "currency": latest.currency,
        "52w_high": max(closes[-252:]) if len(closes) >= 252 else max(closes),
        "52w_low": min(closes[-252:]) if len(closes) >= 252 else min(closes),
        "ytd_return_pct": _calc_return(closes, 1),
        "returns": {
            "1m": _calc_return(closes, 22),
            "3m": _calc_return(closes, 66),
            "6m": _calc_return(closes, 132),
            "1y": _calc_return(closes, 252),
        },
        "annualized_volatility": _calc_volatility(closes),
        "max_drawdown_1y": _calc_max_drawdown(closes[-252:]) if len(closes) >= 252 else _calc_max_drawdown(closes),
        "avg_daily_volume": sum(p.volume or 0 for p in prices[-20:]) // max(len(prices[-20:]), 1),
    }

    # Technical signals (simplified)
    ma20 = sum(closes[-20:]) / min(len(closes), 20) if len(closes) >= 20 else closes[-1]
    ma60 = sum(closes[-60:]) / min(len(closes), 60) if len(closes) >= 60 else closes[-1]
    technical = {
        "ma_trend": "多头排列" if ma20 > ma60 else "空头排列" if ma20 < ma60 else "横盘",
        "ma20": round(ma20, 2),
        "ma60": round(ma60, 2),
        "rsi_14": _calc_rsi(closes),
    }

    return {
        "ticker": ticker,
        "company_name": company_name,
        "market": "A股" if ".SH" in ticker or ".SZ" in ticker else "未知",
        "price_summary": price_summary,
        "technical_signals": technical,
        "data_points": len(prices),
    }


def _calc_return(closes, days):
    if len(closes) <= days or closes[-1-days] == 0:
        return None
    return round((closes[-1] / closes[-1-days] - 1) * 100, 1)


def _calc_volatility(closes):
    if len(closes) < 5:
        return None
    import math
    n = min(len(closes), 252)
    returns = [(closes[i] / closes[i-1] - 1) for i in range(-n+1, 0)]
    avg = sum(returns) / len(returns)
    variance = sum((r - avg) ** 2 for r in returns) / (len(returns) - 1)
    return round(math.sqrt(variance) * math.sqrt(252) * 100, 1)


def _calc_max_drawdown(closes):
    peak = closes[0]
    max_dd = 0.0
    for c in closes:
        if c > peak:
            peak = c
        dd = (peak - c) / peak
        if dd > max_dd:
            max_dd = dd
    return round(max_dd * 100, 2)


def _calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(-period, 0):
        delta = closes[i] - closes[i-1]
        gains.append(delta if delta > 0 else 0)
        losses.append(-delta if delta < 0 else 0)
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)
