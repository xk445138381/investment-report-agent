"""Title + Summary Agent — generates report metadata."""

from datetime import date


async def run_summary_agent(ticker, company_name, ctx_state):
    judge = ctx_state.get("risk_judge", {}).get("result", {})
    verdict = judge.get("verdict", "HOLD")
    fin_analysis = ctx_state.get("financial_analysis", {}).get("result", {})
    score = fin_analysis.get("financial_health_score", {})

    return {
        "title": f"{company_name} ({ticker}): 深度研究报告",
        "subtitle": date.today().strftime("深度研究报告 | %Y年%m月"),
        "rating": {
            "overall": verdict,
            "financial_health": score.get("rating", "N/A"),
            "valuation": ctx_state.get("valuation", {}).get("result", {}).get("signal", "N/A"),
            "growth": "数据不足",
            "risk": "中等",
        },
        "disclaimer": "本报告由 AI 辅助生成，仅供参考，不构成投资建议。",
        "tags": ["深度研报", "AI生成", company_name[:4]],
    }
