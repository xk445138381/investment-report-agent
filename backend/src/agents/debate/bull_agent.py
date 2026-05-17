"""Bull Case Agent — argues the optimistic investment thesis."""

import json
import logging

logger = logging.getLogger(__name__)

BULL_PROMPT = """你是一位资深看涨分析师。请基于以下数据，为{company_name} ({ticker}) 撰写看涨论点。

## 可用数据
- 财务分析: {financial_analysis}
- 估值分析: {valuation}
- 行情数据: {price_data}
- 辩论历史: {debate_history}

## 要求
1. 提出 3-5 个核心看涨论点，每个附带具体证据（数据/事实）
2. 每个论点标注置信度 (0-100)
3. 如果这是第 2 轮辩论，必须引用并反驳空方的具体论点

## 输出格式（严格 JSON）
{{
  "side": "bull",
  "round": {round_num},
  "arguments": [
    {{
      "id": "bull_arg_1",
      "thesis": "论点标题",
      "evidence": ["证据1", "证据2"],
      "confidence": 85,
      "rebuttal_to": "bear_arg_X（仅第2轮填写）",
      "rebuttal_text": "反驳理由（仅第2轮填写）"
    }}
  ],
  "key_narrative": "一句话总结看涨逻辑"
}}"""


async def run_bull_agent(
    ticker: str,
    company_name: str,
    financial_analysis: dict,
    valuation: dict,
    price_data: dict,
    debate_history: list = None,
    round_num: int = 1,
) -> dict:
    """Generate bull case arguments."""
    if debate_history is None:
        debate_history = []

    prompt = BULL_PROMPT.format(
        company_name=company_name,
        ticker=ticker,
        financial_analysis=json.dumps(financial_analysis, ensure_ascii=False, indent=2),
        valuation=json.dumps(valuation, ensure_ascii=False, indent=2),
        price_data=json.dumps(price_data, ensure_ascii=False, indent=2),
        debate_history=json.dumps(debate_history, ensure_ascii=False, indent=2),
        round_num=round_num,
    )

    # When LLM is available, call it. For now, return template-based output.
    return await _generate_bull_arguments(company_name, financial_analysis, valuation, price_data, round_num)


async def _generate_bull_arguments(company_name, fin, val, price, round_num):
    """Generate bull arguments from data without LLM (fallback)."""
    arguments = []
    idx = 1

    # Revenue/profitability thesis
    ratios = fin.get("ratios", {})
    if ratios.get("roe") and ratios["roe"] > 0.15:
        arguments.append({
            "id": f"bull_arg_{idx}", "thesis": "超高 ROE 支撑估值溢价",
            "evidence": [f"ROE {ratios['roe']*100:.1f}%", "显著高于资本成本"],
            "confidence": 80, "rebuttal_to": None, "rebuttal_text": None,
        })
        idx += 1

    # Valuation thesis
    if val.get("signal") == "undervalued":
        arguments.append({
            "id": f"bull_arg_{idx}", "thesis": f"当前估值偏低，{val.get('weighted_upside_pct', 0):.1f}% 上行空间",
            "evidence": [f"加权目标价 {val.get('weighted_value', 0):.2f} vs 现价 {val.get('current_price', 0):.2f}"],
            "confidence": 75, "rebuttal_to": None, "rebuttal_text": None,
        })
        idx += 1

    # Financial health thesis
    if ratios.get("debt_to_equity") is not None and ratios["debt_to_equity"] < 0.5:
        arguments.append({
            "id": f"bull_arg_{idx}", "thesis": "财务结构稳健，低杠杆运营",
            "evidence": [f"负债权益比 {ratios['debt_to_equity']:.2f}"],
            "confidence": 70, "rebuttal_to": None, "rebuttal_text": None,
        })
        idx += 1

    # Growth thesis
    price_summary = price.get("price_summary", {})
    returns = price_summary.get("returns", {})
    if returns.get("1y") and returns["1y"] > 0:
        arguments.append({
            "id": f"bull_arg_{idx}", "thesis": "近期股价动能积极",
            "evidence": [f"1年回报 {returns['1y']}%"],
            "confidence": 60, "rebuttal_to": None, "rebuttal_text": None,
        })
        idx += 1

    # Always include at least 3 arguments
    while len(arguments) < 3:
        arguments.append({
            "id": f"bull_arg_{len(arguments)+1}",
            "thesis": f"公司{company_name}具备行业领先地位",
            "evidence": ["品牌/技术/市场份额优势"],
            "confidence": 65, "rebuttal_to": None, "rebuttal_text": None,
        })

    return {
        "side": "bull",
        "round": round_num,
        "arguments": arguments,
        "key_narrative": f"{company_name} 基本面强劲，估值合理偏低，具备中长期投资价值",
    }
