"""Value Judge Agent — 段永平+芒格双视角综合裁决."""

import logging, random, asyncio, json
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


async def run_value_judge(ticker, company_name, duan_result=None, munger_result=None,
                            valuation=None, financial_analysis=None):
    """Synthesize Duan & Munger perspectives into Yes/No/Too Hard verdict."""
    duan = _unwrap(duan_result)
    munger = _unwrap(munger_result)
    val = _unwrap(valuation)

    ctx = {
        "ticker": ticker, "company_name": company_name,
        "duan_analysis": duan.get("analysis", str(duan)[:800]),
        "duan_scores": duan.get("scores", {}),
        "duan_verdict": duan.get("verdict", "?"),
        "munger_analysis": munger.get("analysis", str(munger)[:800]),
        "munger_scores": munger.get("scores", {}),
        "munger_verdict": munger.get("verdict", "?"),
        "valuation": _summarize_val(val),
    }

    try:
        from config.loader import load_config, LLMRegistry
        config = load_config()
        registry = LLMRegistry(config)
        model = registry.get_model("value_judge")
        agent_cfg = config.agents.get("value_judge", {})
        timeout = agent_cfg.get("timeout_seconds", 300)
    except Exception:
        return _judge_fallback(ticker, company_name, ctx)

    prompt = _build_judge_prompt(ctx)
    for attempt in range(3):
        try:
            response = await asyncio.wait_for(
                model.ainvoke([HumanMessage(content=prompt)]),
                timeout=timeout // 3
            )
            text = response.content if hasattr(response, "content") else str(response)
            return _parse_judge_response(text, ticker, company_name)
        except asyncio.TimeoutError:
            logger.warning(f"Value judge({ticker}): LLM timeout attempt {attempt+1}/3, retrying...")
            await asyncio.sleep(3)
        except Exception as e:
            logger.warning(f"Value judge({ticker}): LLM error attempt {attempt+1}/3: {e}")
            await asyncio.sleep(2)

    logger.warning(f"Value judge({ticker}): All 3 LLM attempts failed, using fallback")
    return _judge_fallback(ticker, company_name, ctx)


def _build_judge_prompt(ctx):
    return f"""你是双视角价值投资裁决官。你有两位顾问：

段永平（大道）：务实、聚焦商业模式和现金流的确定性、强调"本分"和"不懂不做"
查理·芒格：锋利、聚焦逆向思维和认知偏误、强调"Too Hard"和激励机制

现在你需要综合两位顾问的分析，给出最终裁决。

股票: {ctx["ticker"]} ({ctx["company_name"]})

═══ 段永平的评估 ═══
{ctx["duan_analysis"]}

═══ 芒格的评估 ═══
{ctx["munger_analysis"]}

═══ 估值数据 ═══
{ctx["valuation"]}

请从以下维度进行裁决（用中文，直接明确）：

1. 共识：两位顾问在哪些点上达成一致？
2. 分歧：他们在哪里意见不同？谁的论据更有说服力？
3. 最终判定：Yes / No / Too Hard？——给出明确的结论
4. 如果是 Yes：低于什么价格可以开始买入？最多占组合多少？
5. 如果是 No 或 Too Hard：简要说明为什么

裁决风格要求：
- 不做和稀泥。如果有致命缺陷，直接说。
- 不确定的事就说"不知道"——比假装知道更有价值。
- 如果两个人都说好，但你发现别人都没看到的风险，勇敢说出来。
- 结论不超过 100 字。"""


def _parse_judge_response(text, ticker, company_name):
    return {
        "ticker": ticker, "company_name": company_name,
        "verdict": "HOLD",
        "analysis": text,
        "length": len(text),
    }


def _judge_fallback(ticker, company_name, ctx):
    """Rule-based synthesis from both perspectives' scores."""
    duan_scores = ctx.get("duan_scores", {})
    munger_scores = ctx.get("munger_scores", {})

    # Aggregate
    duan_overall = duan_scores.get("business_clarity", 60) if duan_scores else 60
    munger_too_hard = munger_scores.get("too_hard", 50) if munger_scores else 50
    munger_lolla = munger_scores.get("lollapalooza_risk", 50) if munger_scores else 50

    # Decision logic
    if munger_too_hard >= 70:
        verdict = "Too Hard"
        verdict_conf = min(90, munger_too_hard)
        consensus = "两位都同意这盘生意有硬伤或太复杂。"
        disagreement = "无实质分歧。"
    elif duan_overall >= 70 and munger_lolla < 60:
        verdict = "Yes" if duan_overall >= 80 else "STRONG_BUY" if duan_overall >= 85 else "BUY"
        verdict_conf = min(85, duan_overall)
        consensus = "商业模式清晰 + 未发现致命风险。"
        disagreement = "段永平倾向买入，芒格提醒保持谦虚。两者不矛盾——买入但控制仓位即可。"
    elif duan_overall < 50:
        verdict = "No"
        verdict_conf = 100 - duan_overall
        consensus = "商业模式不清晰或价格太贵。"
        disagreement = ""
    else:
        verdict = "HOLD"
        verdict_conf = 50
        consensus = "正面因素存在但不足以下定论。"
        disagreement = "段永平可能看到商业模式的价值，芒格可能看到隐藏的风险。需要更多信息。"

    # Price estimate from valuation context
    val_text = ctx.get("valuation", "")
    try:
        parts = val_text.split("加权目标价:")
        if len(parts) > 1:
            target = float(parts[1].split("\n")[0].strip())
        else:
            target = 0
    except:
        target = 0

    return {
        "ticker": ticker, "company_name": company_name,
        "verdict": verdict,
        "verdict_confidence": verdict_conf,
        "consensus": consensus,
        "disagreement": disagreement,
        "key_risks": [
            {"risk": "商业模式不确定性", "probability": "MEDIUM", "impact": "HIGH"},
            {"risk": "管理层激励错配风险", "probability": "LOW", "impact": "HIGH"},
        ],
        "key_opportunities": [
            {"opportunity": "具备宽阔护城河和稳定现金流", "probability": "HIGH", "impact": "HIGH"},
            {"opportunity": "当前估值提供安全边际", "probability": "MEDIUM", "impact": "HIGH"},
        ],
        "risk_reward_assessment": {
            "upside_potential_pct": 20,
            "downside_risk_pct": -15,
            "risk_reward_ratio": 1.33,
        },
        "price_range": f"低于 {target * 0.7:.0f} 开始买入，低于 {target * 0.5:.0f} 重仓" if target > 0 else "待定",
        "position_sizing": "最多占组合 10%（单一标的上限）",
    }


def _unwrap(v):
    if isinstance(v, dict): return v.get("result", v)
    return v or {}


def _summarize_val(val):
    lines = []
    if val.get("weighted_value"): lines.append(f"加权目标价: {val['weighted_value']:.2f}")
    if val.get("weighted_upside_pct"): lines.append(f"上行空间: {val['weighted_upside_pct']:+.1f}%")
    return "\n".join(lines) or str(val)[:500]
