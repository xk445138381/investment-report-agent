"""Duan Yongping Perspective Agent — 段永平式价值投资评估."""

import logging, random, asyncio, json, os, requests
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


def _call_deepseek_sync(base_url: str, api_key: str, model: str, prompt: str, timeout: int) -> str | None:
    """Synchronous DeepSeek API call using requests (avoids httpx async issues)."""
    try:
        r = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_tokens": 4000,
            },
            timeout=timeout,
        )
        if r.status_code == 200:
            data = r.json()
            return data["choices"][0]["message"]["content"]
        logger.warning(f"DeepSeek HTTP {r.status_code}: {r.text[:200]}")
        return None
    except requests.Timeout:
        raise
    except Exception as e:
        logger.warning(f"DeepSeek sync call error: {e}")
        return None


async def run_duan_agent(ticker, company_name, financial_analysis=None, valuation=None,
                           price_data=None, corporate_governance=None, industry_competition=None):
    """Evaluate through Duan Yongping's lens: business model, 本分, cash flow certainty."""
    # Build context
    fa = _unwrap(financial_analysis)
    val = _unwrap(valuation)
    gov = _unwrap(corporate_governance)
    ind = _unwrap(industry_competition)
    price = _unwrap(price_data) if price_data else {}

    ctx = {
        "ticker": ticker, "company_name": company_name,
        "financials": _summarize_fa(fa),
        "valuation": _summarize_val(val),
        "governance": _summarize_gov(gov),
        "industry": _summarize_ind(ind),
        "price": _summarize_price(price),
    }

    # Try LLM via direct HTTP call (bypasses httpx async issues on Windows)
    try:
        from config.loader import load_config
        config = load_config()
        agent_cfg = config.agents.get("duan_case", {})
        timeout = agent_cfg.get("timeout_seconds", 300)
        provider_id = agent_cfg.llm if agent_cfg else "provider_quick"
        provider_cfg = config.llm_providers.get(provider_id, config.llm_providers.get("provider_quick"))
    except Exception:
        logger.info("Duan agent: config unavailable, using fallback")
        return _duan_fallback(ticker, company_name, ctx)

    prompt = _build_duan_prompt(ctx)
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
    base_url = provider_cfg.base_url or "https://api.deepseek.com/v1"

    for attempt in range(3):
        try:
            text = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, lambda: _call_deepseek_sync(base_url, api_key, provider_cfg.model, prompt, 60)
                ),
                timeout=timeout // 2
            )
            if text:
                return _parse_duan_response(text, ticker, company_name)
        except asyncio.TimeoutError:
            logger.warning(f"Duan agent({ticker}): LLM timeout attempt {attempt+1}/3")
            await asyncio.sleep(2)
        except Exception as e:
            logger.warning(f"Duan agent({ticker}): LLM error attempt {attempt+1}/3: {e}")
            await asyncio.sleep(2)

    logger.warning(f"Duan agent({ticker}): All 3 LLM attempts failed, using fallback")
    return _duan_fallback(ticker, company_name, ctx)


def _build_duan_prompt(ctx):
    return f"""你是段永平（大道），中国最成功的价值投资者之一。你用常识和商业直觉判断一家公司是否值得投资。

核心原则：
- 买股票就是买公司。买公司就是买未来现金流的折现。
- 第一看商业模式。不懂的不投。
- 第二看企业文化。"本分"——做对的事，然后把事做对。
- 第三看价格。好公司 + 好价格 = 好投资。顺序不能乱。
- "敢为天下后"——不急着追风口，等到看懂了再出手。
- 投资如种田——播种后耐心等待，不天天挖出来看。

现在分析这家公司：

股票代码: {ctx["ticker"]}
公司名称: {ctx["company_name"]}

【财务数据】
{ctx["financials"]}

【估值数据】
{ctx["valuation"]}

【公司治理】
{ctx["governance"]}

【行业数据】
{ctx["industry"]}

【价格数据】
{ctx["price"]}

请用段永平的视角，分四个维度评估（用中文，语气务实直接）：

1. 商业模式清晰度：这家公司的生意你懂吗？它怎么赚钱？十年后还能赚钱吗？用段永平三问来回答。

2. 企业文化与本分：管理层是否在做对的事？资本配置是否合理（回购/分红/并购）？

3. 现金流确定性：利润里有几分真金白银？未来的现金流可预测吗？

4. 价格是否合理：当前价格相对未来现金流折现，有安全边际吗？

最后给出：
- 综合判断（用段永平的语气写 50-100 字）
- 买价区间：低于多少会考虑买入

请直接输出，不要客套，不要免责声明。"""


def _parse_duan_response(text, ticker, company_name):
    return {
        "ticker": ticker, "company_name": company_name,
        "perspective": "段永平",
        "analysis": text,
        "length": len(text),
    }


def _duan_fallback(ticker, company_name, ctx):
    """Rule-based fallback: score business model dimensions from available data."""
    scores = {"business_clarity": 60, "culture_benfen": 60, "cash_certainty": 60, "price_fair": 60}
    fa_text = ctx["financials"]
    val_text = ctx["valuation"]

    # Boost scores based on data signals
    if "ROE" in fa_text:
        try:
            # Extract ROE %
            parts = fa_text.split("ROE:")
            if len(parts) > 1:
                roe_str = parts[1].split("%")[0].strip()
                roe = float(roe_str)
                if roe > 20: scores["business_clarity"] = 85
                elif roe > 15: scores["business_clarity"] = 75
                elif roe > 10: scores["business_clarity"] = 65
        except: pass

    if "FCF/净利润" in fa_text:
        try:
            parts = fa_text.split("FCF/净利润:")
            if len(parts) > 1:
                fcf_str = parts[1].split("\n")[0].strip()
                fcf = float(fcf_str)
                if fcf > 0.8: scores["cash_certainty"] = 90
                elif fcf > 0.5: scores["cash_certainty"] = 75
        except: pass

    if "负债权益比" in fa_text:
        try:
            parts = fa_text.split("负债权益比:")
            if len(parts) > 1:
                de_str = parts[1].split("\n")[0].strip()
                de = float(de_str)
                if de < 0.3: scores["culture_benfen"] = 85
                elif de < 0.7: scores["culture_benfen"] = 70
        except: pass

    # Price fairness from valuation
    upside = 0
    if "上行" in val_text:
        try:
            parts = val_text.split("上行")[1].split("%")[0]
            upside = float(parts.replace("+", "").replace("空间 ", "").strip())
        except: pass
    if upside > 30: scores["price_fair"] = 85
    elif upside > 10: scores["price_fair"] = 70
    elif upside > -10: scores["price_fair"] = 60
    else: scores["price_fair"] = 45

    overall = sum(scores.values()) / len(scores)

    # Narrative
    narratives = {
        (True, True): "这生意我看得懂。现金流扎实，企业文化也不错。现在这个价格——如果跌到我说的区间，我会买。不急。",
        (True, False): "生意模式还行，但价格不够便宜。好东西也要等好价钱。放着，继续看。",
        (False, True): "这生意我不太懂。不管多便宜，不懂的东西不碰。这是纪律。",
        (False, False): "这盘生意有硬伤。不投。不管别人赚多少，跟我没关系。",
    }
    biz_ok = scores["business_clarity"] >= 70
    price_ok = scores["price_fair"] >= 65
    key = (biz_ok, price_ok)
    narrative = narratives.get(key, narratives[(False, False)])

    return {
        "ticker": ticker, "company_name": company_name,
        "perspective": "段永平（fallback）",
        "scores": scores,
        "overall_score": round(overall),
        "business_clarity": scores["business_clarity"],
        "culture_benfen": scores["culture_benfen"],
        "cash_certainty": scores["cash_certainty"],
        "price_fairness": scores["price_fair"],
        "analysis": narrative,
        "verdict": "买" if biz_ok and price_ok else "不买" if not biz_ok else "等",
    }


def _unwrap(v):
    if isinstance(v, dict): return v.get("result", v)
    return v or {}


def _summarize_fa(fa):
    s = fa.get("financial_health_score", {})
    ratios = fa.get("ratios", {})
    lines = []
    if s: lines.append(f"财务健康: {s.get('rating','?')} ({s.get('total',0)}/32)")
    if ratios.get("roe"): lines.append(f"ROE: {ratios['roe']*100:.1f}%")
    if ratios.get("debt_to_equity"): lines.append(f"负债权益比: {ratios['debt_to_equity']:.2f}")
    if ratios.get("fcf_to_net_income"): lines.append(f"FCF/净利润: {ratios['fcf_to_net_income']:.2f}")
    if ratios.get("revenue_growth_yoy"): lines.append(f"营收增长 YoY: {ratios['revenue_growth_yoy']*100:.1f}%")
    return "\n".join(lines) or str(fa)[:500]


def _summarize_val(val):
    lines = []
    if val.get("weighted_value"): lines.append(f"加权目标价: {val['weighted_value']:.2f}")
    if val.get("weighted_upside_pct"): lines.append(f"上行空间: {val['weighted_upside_pct']:+.1f}%")
    if val.get("signal"): lines.append(f"估值信号: {val['signal']}")
    return "\n".join(lines) or str(val)[:500]


def _summarize_gov(gov):
    o = gov.get("ownership_structure", "")
    return str(o) if o and "待补充" not in o else "治理数据待补充"


def _summarize_ind(ind):
    l1 = ind.get("shenwan_l1", "") or ind.get("industry", "")
    l2 = ind.get("shenwan_l2", "")
    return f"{l1} / {l2}" if l1 else "行业数据待补充"


def _summarize_price(price):
    ps = price.get("price_summary", {})
    if ps:
        return f"最新价: {ps.get('latest_price','?')}"
    return str(price)[:200]
