"""Risk Judge Agent — evaluates bull/bear debate, produces risk assessment."""

import asyncio, json, logging
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """你是一位资深投资风险裁判。请评估以下牛熊辩论，输出结构化裁决。

## 看涨论点
{bull_arguments}

## 看跌论点
{bear_arguments}

## 估值数据
{valuation}

## 要求
1. 评估双方论据的可信度和证据强度
2. 输出 3-5 个关键风险和 3-5 个关键机遇
3. 给出最终投资建议倾向 (STRONG_BUY/BUY/HOLD/SELL/STRONG_SELL)
4. 提供风险回报比和置信区间

## 输出格式（严格 JSON）
{{
  "verdict": "BUY",
  "verdict_confidence": 72,
  "key_risks": [
    {{"risk": "风险描述", "probability": "MEDIUM", "impact": "HIGH",
      "time_horizon": "中长期", "mitigation": "缓解因素"}}
  ],
  "key_opportunities": [
    {{"opportunity": "机遇描述", "probability": "HIGH", "impact": "MEDIUM"}}
  ],
  "risk_reward_assessment": {{
    "upside_potential_pct": 17.3,
    "downside_risk_pct": -15.0,
    "risk_reward_ratio": 1.15
  }},
  "confidence_intervals": {{
    "pessimistic_price": 1428,
    "base_price": 1970,
    "optimistic_price": 2520
  }},
  "judge_narrative": "综合评估..."
}}"""


async def run_judge_agent(
    ticker: str,
    company_name: str,
    bull_result: dict,
    bear_result: dict,
    valuation: dict,
) -> dict:
    """Evaluate debate and produce final risk assessment."""

    # Try LLM for richer analysis
    try:
        from config.loader import load_config, LLMRegistry
        model = LLMRegistry(load_config()).get_model("risk_judge")
        if model:
            prompt = JUDGE_PROMPT.format(
                bull_arguments=json.dumps(bull_result.get("arguments", []), ensure_ascii=False, indent=2),
                bear_arguments=json.dumps(bear_result.get("arguments", []), ensure_ascii=False, indent=2),
                valuation=json.dumps(valuation, ensure_ascii=False, indent=2),
            )
            resp = await asyncio.wait_for(model.ainvoke([HumanMessage(content=prompt)]), timeout=20)
            text = resp.content.strip()
            if text.startswith("```"): text = text.split("\n", 1)[1].rsplit("\n```", 1)[0]
            data = json.loads(text)
            if data.get("verdict"):
                logger.info("Judge agent: LLM verdict=%s conf=%s", data.get("verdict"), data.get("verdict_confidence"))
                return data
    except Exception as e:
        logger.warning(f"Judge LLM failed, using rules: {e}")

    # Rule-based fallback
    # Build confidence intervals from valuation
    current = valuation.get("current_price", 0) or 0
    upside = valuation.get("weighted_upside_pct", 0) or 0
    sensitivity = valuation.get("sensitivity_matrix", {})

    pessimistic = current * 0.85  # default -15%
    optimistic = current * 1.25   # default +25%
    base = current * (1 + upside / 100) if current > 0 else current

    if sensitivity and sensitivity.get("matrix"):
        m = sensitivity["matrix"]
        if m and m[0] and m[2]:
            pessimistic = max(m[2][0], current * 0.7)   # high WACC, low growth
            optimistic = min(m[0][2], current * 1.5)     # low WACC, high growth

    # Extract risks and opportunities from debate
    risks = _extract_risks(bear_result, bull_result)
    opportunities = _extract_opportunities(bull_result, bear_result)

    # Verdict logic
    verdict, confidence = _determine_verdict(
        upside, valuation.get("signal", "fair"),
        len(opportunities), len(risks),
    )

    risk_reward = {
        "upside_potential_pct": round(max(0, ((optimistic / current) - 1) * 100), 1) if current > 0 else 0,
        "downside_risk_pct": round(((pessimistic / current) - 1) * 100, 1) if current > 0 else 0,
        "risk_reward_ratio": round(abs(optimistic - current) / abs(current - pessimistic), 2) if current != pessimistic else 1.0,
    }

    return {
        "verdict": verdict,
        "verdict_confidence": confidence,
        "key_risks": risks[:5],
        "key_opportunities": opportunities[:5],
        "risk_reward_assessment": risk_reward,
        "confidence_intervals": {
            "pessimistic_price": round(pessimistic, 2),
            "base_price": round(base, 2),
            "optimistic_price": round(optimistic, 2),
        },
        "judge_narrative": _narrative(verdict, company_name, upside),
    }


def _extract_risks(bear, bull):
    risks = []
    for arg in bear.get("arguments", [])[:3]:
        risks.append({
            "risk": arg.get("thesis", ""),
            "probability": "MEDIUM", "impact": "HIGH",
            "time_horizon": "中长期", "mitigation": "关注行业趋势",
            "source": "bear_" + arg.get("id", ""),
        })
    return risks


def _extract_opportunities(bull, bear):
    opps = []
    for arg in bull.get("arguments", [])[:3]:
        opps.append({
            "opportunity": arg.get("thesis", ""),
            "probability": "HIGH", "impact": "MEDIUM",
            "source": "bull_" + arg.get("id", ""),
        })
    return opps


def _determine_verdict(upside, signal, n_opps, n_risks):
    if signal == "undervalued" and upside > 20:
        return "STRONG_BUY", 80
    elif signal == "undervalued":
        return "BUY", 72
    elif signal == "overvalued" and upside < -15:
        return "SELL", 75
    elif signal == "overvalued":
        return "SELL", 65
    elif n_opps > n_risks + 1:
        return "BUY", 60
    elif n_risks > n_opps + 1:
        return "SELL", 60
    return "HOLD", 50


def _narrative(verdict, company, upside):
    if verdict == "STRONG_BUY":
        return (f"综合牛熊双方论据，{company} 基本面强劲，估值显著偏低"
                f"（{upside:.1f}% 上行空间），建议积极配置。")
    elif verdict == "BUY":
        return (f"{company} 估值具备吸引力（{upside:.1f}%上行空间），"
                "核心风险可控，建议逐步建仓。")
    elif verdict == "SELL":
        return f"{company} 当前估值偏高，风险收益比不理想，建议观望或减仓。"
    return f"{company} 多空因素均衡，当前估值合理，建议持有等待催化剂。"
