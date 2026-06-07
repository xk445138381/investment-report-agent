"""Technical Indicators Agent — MACD/RSI/MA from price data."""

import logging
logger = logging.getLogger(__name__)


async def run_tech_indicators(ticker, company_name, prices=None):
    """Compute key technical signals from OHLCV price data."""
    result = {"ticker": ticker, "company_name": company_name, "signals": {}}
    if not prices or len(prices) < 20:
        result["signals"]["error"] = "insufficient_data"
        return result

    try:
        closes = [p.close for p in prices if hasattr(p, "close") and p.close]
        if len(closes) < 20:
            result["signals"]["error"] = "insufficient_data"
            return result

        latest = closes[-1]

        # MA5 / MA10 / MA20
        ma5 = sum(closes[-5:]) / 5
        ma10 = sum(closes[-10:]) / 10
        ma20 = sum(closes[-20:]) / 20

        # Trend
        if latest > ma5 > ma10 > ma20:
            trend = "多头排列"
        elif latest < ma5 < ma10 < ma20:
            trend = "空头排列"
        elif latest > ma20:
            trend = "偏多"
        else:
            trend = "偏空"

        # RSI (14) uses the most recent window; older rows must not skew quick-scan signals.
        rsi_window = closes[-15:]
        gains = [max(rsi_window[i] - rsi_window[i-1], 0) for i in range(1, len(rsi_window))]
        losses = [max(rsi_window[i-1] - rsi_window[i], 0) for i in range(1, len(rsi_window))]
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        rsi = 100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss > 0 else 100

        # MACD
        ema12 = closes[-1]
        ema26 = closes[-1]
        k12 = 2 / 13
        k26 = 2 / 27
        for c in closes[-30:]:
            ema12 = c * k12 + ema12 * (1 - k12)
            ema26 = c * k26 + ema26 * (1 - k26)
        dif = ema12 - ema26
        dea = dif * (2/10) + 0 * (8/10)  # simplified
        macd_signal = "金叉" if dif > 0 and latest > ma20 else "死叉" if dif < 0 else "震荡"

        # Volume trend
        vols = [p.volume for p in prices if hasattr(p, "volume") and p.volume]
        vol_ma5 = sum(vols[-5:]) / 5 if len(vols) >= 5 else 0
        vol_ma20 = sum(vols[-20:]) / 20 if len(vols) >= 20 else vol_ma5
        vol_ratio = vol_ma5 / vol_ma20 if vol_ma20 > 0 else 1
        vol_signal = "放量" if vol_ratio > 1.3 else "缩量" if vol_ratio < 0.7 else "正常"

        result["signals"] = {
            "latest_price": latest, "ma5": round(ma5, 2), "ma20": round(ma20, 2),
            "trend": trend, "rsi": round(rsi, 1),
            "rsi_signal": "超买" if rsi > 70 else "超卖" if rsi < 30 else "中性",
            "macd_signal": macd_signal,
            "volume_signal": vol_signal,
            "vol_ratio": round(vol_ratio, 2),
        }
    except Exception as e:
        logger.warning(f"Tech indicators({ticker}): {e}")
        result["signals"]["error"] = str(e)[:100]

    return result
