"""Scan Card Agent — formats quick_scan results into a compact card."""


async def run_scan_card(ticker, company_name, ctx_state, template_id="quick_scan"):
    """Render quick scan results as a compact card."""
    price = ctx_state.get("price_data", {}).get("result", {})
    tech = ctx_state.get("tech_indicators", {}).get("result", {})
    fund = ctx_state.get("fund_flow", {}).get("result", {})
    fin = ctx_state.get("financial_data", {}).get("result", {})
    qs = ctx_state.get("quick_summary", {}).get("result", {})

    signals = tech.get("signals", {})
    ps = price.get("price_summary", {})

    latest = signals.get("latest_price", ps.get("latest_price", 0))
    trend = signals.get("trend", "?")
    rsi = signals.get("rsi", 0)
    rsi_s = signals.get("rsi_signal", "?")
    macd_s = signals.get("macd_signal", "?")
    vol_s = signals.get("volume_signal", "?")

    # Determine overall signal
    if trend == "多头排列" and rsi_s == "中性":
        overall = "偏多"
        signal_color = "positive"
    elif trend == "空头排列" or rsi_s == "超买":
        overall = "谨慎"
        signal_color = "negative"
    else:
        overall = "中性"
        signal_color = "neutral"

    return {
        "card": {
            "ticker": ticker, "company_name": company_name,
            "price": latest,
            "overall": overall, "signal_color": signal_color,
            "summary": qs.get("summary", "数据不足"),
            "tech": {
                "trend": trend, "rsi": rsi, "rsi_signal": rsi_s,
                "macd": macd_s, "volume": vol_s,
            },
            "fund_flow": str(fund.get("flow", {}))[:200] if fund.get("flow") else "",
            "note": qs.get("note", ""),
        }
    }
