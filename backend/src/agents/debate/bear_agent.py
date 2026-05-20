"""Bear Case Agent — argues the pessimistic investment thesis."""

import asyncio, json, logging
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

BEAR_PROMPT = """你是一位资深看跌分析师。请基于以下数据，为{company_name} ({ticker}) 撰写看跌论点。

## 可用数据
- 财务分析: {financial_analysis}
- 估值分析: {valuation}
- 行情数据: {price_data}
- 辩论历史: {debate_history}

## 要求
1. 提出 3-5 个核心看跌论点，每个附带具体证据
2. 每个论点标注置信度 (0-100)
3. 如果这是第 2 轮辩论，必须引用并反驳多方的具体论点

## 输出格式（严格 JSON）
{{
  "side": "bear", "round": {round_num},
  "arguments": [{{
    "id": "bear_arg_1", "thesis": "论点标题", "evidence": ["证据1"],
    "confidence": 75, "rebuttal_to": "bull_arg_X（仅第2轮填写）",
    "rebuttal_text": "反驳理由（仅第2轮填写）"
  }}],
  "key_narrative": "一句话总结看跌逻辑"
}}"""


async def run_bear_agent(ticker, company_name, financial_analysis, valuation, price_data,
                         debate_history=None, round_num=1):
    if debate_history is None: debate_history = []

    prompt = BEAR_PROMPT.format(
        company_name=company_name, ticker=ticker,
        financial_analysis=json.dumps(financial_analysis, ensure_ascii=False, indent=2),
        valuation=json.dumps(valuation, ensure_ascii=False, indent=2),
        price_data=json.dumps(price_data, ensure_ascii=False, indent=2),
        debate_history=json.dumps(debate_history, ensure_ascii=False, indent=2),
        round_num=round_num,
    )

    try:
        from config.loader import load_config, LLMRegistry
        model = LLMRegistry(load_config()).get_model("bear_case")
        if model:
            resp = await asyncio.wait_for(model.ainvoke([HumanMessage(content=prompt)]), timeout=20)
            text = resp.content.strip()
            if text.startswith("```"): text = text.split("\n", 1)[1].rsplit("\n```", 1)[0]
            data = json.loads(text)
            if data.get("arguments"):
                logger.info("Bear agent: LLM generated %d arguments", len(data["arguments"]))
                return data
    except Exception as e:
        logger.warning(f"Bear LLM failed, using fallback: {e}")

    return await _generate_bear_arguments(company_name, financial_analysis, valuation, price_data, round_num)


async def _generate_bear_arguments(company_name, fin, val, price, round_num):
    arguments = []; idx = 1
    ratios = fin.get("ratios", {})
    ps = price.get("price_summary", {})
    if val.get("signal") == "overvalued":
        arguments.append({"id": f"bear_arg_{idx}", "thesis": "当前估值偏高，下行风险显著",
            "evidence": [f"目标价 {val.get('weighted_value',0):.2f} 低于现价 {val.get('current_price',0):.2f}"],
            "confidence": 80, "rebuttal_to": None, "rebuttal_text": None}); idx += 1
    if ratios.get("revenue_growth_yoy") is not None and ratios["revenue_growth_yoy"] < 0.10:
        arguments.append({"id": f"bear_arg_{idx}", "thesis": "收入增速放缓，成长性不足",
            "evidence": [f"营收同比增长仅 {ratios['revenue_growth_yoy']*100:.1f}%"],
            "confidence": 75, "rebuttal_to": None, "rebuttal_text": None}); idx += 1
    if ps.get("returns", {}).get("1y") is not None and ps["returns"]["1y"] < -10:
        arguments.append({"id": f"bear_arg_{idx}", "thesis": "股价处于下行趋势",
            "evidence": [f"1年跌幅 {ps['returns']['1y']}%"],
            "confidence": 70, "rebuttal_to": None, "rebuttal_text": None}); idx += 1
    if ratios.get("debt_to_equity") is not None and ratios["debt_to_equity"] > 1.0:
        arguments.append({"id": f"bear_arg_{idx}", "thesis": "高杠杆运营，财务风险上升",
            "evidence": [f"负债权益比 {ratios['debt_to_equity']:.2f}"],
            "confidence": 75, "rebuttal_to": None, "rebuttal_text": None}); idx += 1
    arguments.append({"id": f"bear_arg_{len(arguments)+1}", "thesis": "宏观经济不确定性与行业监管风险",
        "evidence": ["经济增速放缓", "行业政策变化"],
        "confidence": 55, "rebuttal_to": None, "rebuttal_text": None})
    return {"side": "bear", "round": round_num, "arguments": arguments,
            "key_narrative": f"{company_name} 面临增速放缓、估值压力和外部风险，需谨慎对待"}
