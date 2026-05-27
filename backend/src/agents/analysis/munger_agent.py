"""Charlie Munger Perspective Agent — 芒格式逆向思维评估."""

import logging, random, asyncio, json
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


async def run_munger_agent(ticker, company_name, financial_analysis=None, valuation=None,
                             price_data=None, corporate_governance=None, industry_competition=None):
    """Evaluate through Munger's lens: inversion, Lollapalooza, incentives, Too Hard check."""
    fa = _unwrap(financial_analysis)
    val = _unwrap(valuation)
    gov = _unwrap(corporate_governance)
    ind = _unwrap(industry_competition)

    ctx = {
        "ticker": ticker, "company_name": company_name,
        "financials": _summarize_fa(fa),
        "valuation": _summarize_val(val),
        "governance": _summarize_gov(gov),
        "industry": _summarize_ind(ind),
    }

    try:
        from config.loader import load_config, LLMRegistry
        config = load_config()
        registry = LLMRegistry(config)
        model = registry.get_model("munger_case")
        agent_cfg = config.agents.get("munger_case", {})
        timeout = agent_cfg.get("timeout_seconds", 300)
    except Exception:
        return _munger_fallback(ticker, company_name, ctx)

    prompt = _build_munger_prompt(ctx)
    for attempt in range(3):
        try:
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: model.invoke([HumanMessage(content=prompt)])),
                timeout=timeout // 3
            )
            text = response.content if hasattr(response, "content") else str(response)
            return _parse_munger_response(text, ticker, company_name)
        except asyncio.TimeoutError:
            logger.warning(f"Munger agent({ticker}): LLM timeout attempt {attempt+1}/3, retrying...")
            await asyncio.sleep(3)
        except Exception as e:
            logger.warning(f"Munger agent({ticker}): LLM error attempt {attempt+1}/3: {e}")
            await asyncio.sleep(2)

    logger.warning(f"Munger agent({ticker}): All 3 LLM attempts failed, using fallback")
    return _munger_fallback(ticker, company_name, ctx)


def _build_munger_prompt(ctx):
    return f"""你是查理·芒格，伯克希尔·哈撒韦的副主席。你的思考方式以逆向思维、多元模型、和对人类认知偏误的辛辣洞察著称。

核心原则：
- "反过来想，总是反过来想。"——先问怎么死，再问怎么活。
- "告诉我我会死在哪里，我就永远不去那个地方。"
- 激励机制决定一切——看任何系统，先看谁会得到什么。
- Lollapalooza效应——多种偏误同时发力的极端非线性结果。
- "如果一件事太难，我们就换一件。"——大部分投资属于 Too Hard 筐。
- 葡萄干拌屎还是屎——一个致命缺陷污染整体。
- 坐在屁股上不动——高确信度后买入，然后什么都不做。

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

请用芒格的视角，分四个维度评估（用中文，语气锋利，善用类比）：

1. 逆向死法清单：这家公司最可能怎么死？列出3-5种死法，每种标注触发概率。

2. Lollapalooza 检测：有没有多种风险因子同时发力的组合？哪种偏误组合最危险？

3. 激励机制诊断：管理层的激励结构合理吗？谁在赚钱？谁在承担风险？两者对齐吗？

4. Too Hard 判断：这笔投资属于 Yes / No / Too Hard 哪个筐？凭什么不是第三筐？

最后给出一条芒格式的尖锐判断（30-50字），如果有致命缺陷，用"葡萄干拌屎"类比的句式。

直接输出，不要客套。可以粗鲁，但要精确。"""


def _parse_munger_response(text, ticker, company_name):
    return {
        "ticker": ticker, "company_name": company_name,
        "perspective": "芒格",
        "analysis": text,
        "length": len(text),
    }


def _munger_fallback(ticker, company_name, ctx):
    """Rule-based fallback: inversion checklist scoring."""
    scores = {"risks_identified": 60, "lollapalooza_risk": 50, "incentive_ok": 60, "too_hard": 50}
    fa_text = ctx["financials"]

    # Risk detection from financial data
    if "负债权益比" in fa_text:
        try:
            parts = fa_text.split("负债权益比:")
            if len(parts) > 1:
                de_str = parts[1].split("\n")[0].strip()
                de = float(de_str)
                if de > 1.5: scores["risks_identified"] = 90
                elif de > 1.0: scores["risks_identified"] = 75
                elif de < 0.3: scores["risks_identified"] = 40  # low risk
        except: pass

    # Revenue growth check for business risk
    growth_neg = False
    if "营收增长" in fa_text:
        try:
            parts = fa_text.split("营收增长 YoY:")
            if len(parts) > 1:
                g_str = parts[1].split("%")[0].strip().replace("+", "")
                g = float(g_str)
                if g < 0: growth_neg = True
                if g < -10: scores["lollapalooza_risk"] = 80
                elif g < 0: scores["lollapalooza_risk"] = 65
        except: pass

    # FCF check
    if "FCF/净利润" in fa_text:
        try:
            parts = fa_text.split("FCF/净利润:")
            if len(parts) > 1:
                fcf_ni = float(parts[1].split("\n")[0].strip())
                if fcf_ni < 0.3: scores["lollapalooza_risk"] = max(scores["lollapalooza_risk"], 80)
        except: pass

    # Risk check: ROE vs debt
    if "ROE" in fa_text and "负债权益比" in fa_text:
        try:
            roe_parts = fa_text.split("ROE:")
            de_parts = fa_text.split("负债权益比:")
            if len(roe_parts) > 1 and len(de_parts) > 1:
                roe = float(roe_parts[1].split("%")[0].strip())
                de = float(de_parts[1].split("\n")[0].strip())
                if roe > 20 and de < 0.5:
                    scores["incentive_ok"] = 80  # well-run company
                if roe < 5 or de > 2:
                    scores["too_hard"] = 85  # probably Too Hard
        except: pass

    overall_risk = sum(scores.values()) / len(scores)

    # Munger-style verdict
    if scores["too_hard"] >= 70:
        verdict = "Too Hard — 这盘生意太复杂，换一个。"
        narrative = "我活了99岁，学到最重要的事就是：如果一件事太难，我们就换一件。这个案子属于那个筐。"
    elif overall_risk > 65:
        verdict = "有风险但可管理"
        narrative = "人类总是高估自己预测未来的能力。即使这笔投资最后对了，过程中的运气成分可能比你想象的大得多。保持仓位小。"
    else:
        verdict = "值得认真考虑"
        narrative = "反过来说，如果所有明显的死法都检查过了，没有致命缺陷，那你可能找到了一个好标的。但记住：你的检查清单本身可能有盲点。"

    return {
        "ticker": ticker, "company_name": company_name,
        "perspective": "芒格（fallback）",
        "scores": scores,
        "overall_risk": round(overall_risk),
        "analysis": narrative,
        "verdict": verdict,
        "inversion_checklist": [
            "竞争格局恶化（需求消失或替代品涌现）",
            "管理层行为失当（激励错配 → 资源错配）",
            "财务杠杆失控（高负债 + 盈利下滑 = 死亡螺旋）",
            "技术颠覆（护城河被绕开）",
            "宏观黑天鹅（非对称尾部风险）",
        ],
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
    return "\n".join(lines) or str(val)[:500]


def _summarize_gov(gov):
    o = gov.get("ownership_structure", "")
    return str(o) if o and "待补充" not in o else "治理数据待补充"


def _summarize_ind(ind):
    l1 = ind.get("shenwan_l1", "") or ind.get("industry", "")
    return str(l1) if l1 else "行业数据待补充"
