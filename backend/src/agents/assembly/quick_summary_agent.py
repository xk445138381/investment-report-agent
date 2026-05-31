"""Quick Summary Agent — one-sentence LLM take for rapid scanning."""

import logging, os, asyncio

logger = logging.getLogger(__name__)


async def run_quick_summary(ticker, company_name, ctx_state=None):
    """Generate a one-sentence investment take using LLM."""
    ctx = ctx_state or {}
    price = ctx.get("price_data", {}).get("result", {})
    tech = ctx.get("tech_indicators", {}).get("result", {})
    fund = ctx.get("fund_flow", {}).get("result", {})
    fin = ctx.get("financial_data", {}).get("result", {})

    # Build context for LLM
    signals = tech.get("signals", {})
    ps = price.get("price_summary", {})
    latest = ps.get("latest_price", signals.get("latest_price", 0))
    trend = signals.get("trend", "?")
    rsi = signals.get("rsi", 0)
    rsi_s = signals.get("rsi_signal", "?")
    vol_s = signals.get("volume_signal", "?")
    macd = signals.get("macd_signal", "?")

    # Include financial data if available
    ratios = fin.get("ratios", {})
    fin_str = ""
    if ratios:
        parts = []
        if ratios.get("roe"): parts.append(f"ROE: {ratios['roe']*100:.1f}%")
        if ratios.get("debt_to_equity"): parts.append(f"负债比: {ratios['debt_to_equity']:.2f}")
        fin_str = " | ".join(parts)

    prompt = f"""你是A股短线分析助手。根据以下数据给这只股票一个100字以内的判断，覆盖三点：1) 技术面位置（趋势+RSI+MACD意味着什么） 2) 财务面（如果有ROE和负债数据） 3) 操作建议方向。

{ticker} {company_name}
价格: {latest} | 趋势: {trend} | RSI: {rsi}({rsi_s}) | MACD: {macd} | 量能: {vol_s}
{fin_str}

只输出一段分析，不要标题和格式。"""

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return {"ticker": ticker, "summary": f"{company_name}（{ticker}）— 数据待补充", "note": "no_llm"}

    for attempt in range(2):
        try:
            from agents.analysis.llm_subprocess import call_llm
            text = await asyncio.get_event_loop().run_in_executor(
                None, lambda: call_llm(api_key, "https://api.deepseek.com/v1", "deepseek-v4-pro", prompt, 60)
            )
            if text and len(text) > 5:
                return {"ticker": ticker, "company_name": company_name, "summary": text.strip()[:100]}
        except Exception as e:
            logger.warning(f"Quick summary({ticker}): attempt {attempt+1} failed: {e}")
            await asyncio.sleep(1)

    return {"ticker": ticker, "company_name": company_name, "summary": f"{company_name}（{ticker}）— LLM不可用", "note": "llm_failed"}
