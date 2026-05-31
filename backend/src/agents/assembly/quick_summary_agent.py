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

    # Build minimal context
    signals = tech.get("signals", {})
    ps = price.get("price_summary", {})
    latest = ps.get("latest_price", signals.get("latest_price", 0))
    trend = signals.get("trend", "?")
    rsi = signals.get("rsi", 0)
    rsi_s = signals.get("rsi_signal", "?")
    vol_s = signals.get("volume_signal", "?")

    price_str = f"价格 {latest}" if latest else ""
    tech_str = f"趋势{trend} RSI{rsi}({rsi_s}) {vol_s}" if trend else ""
    fund_str = str(fund.get("flow", {}))[:200] if fund else ""

    prompt = f"""你是段永平的简化版助手。用一句话（不超过50字）评估这只股票，要包含：生意模式能不能看懂 + 当前价格位置 + 一句话买卖建议。

股票: {ticker} {company_name}
{price_str}
{tech_str}
资金面: {fund_str}

直接输出一句话，不要解释。"""

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
