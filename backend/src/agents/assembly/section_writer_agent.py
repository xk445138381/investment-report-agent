"""Section Writer Agent — assembles agent outputs into report sections."""

from datetime import date


async def run_section_writer(ticker, company_name, ctx_state, template_id="deep_dive_default"):
    """Produce structured report sections from all upstream agent outputs."""
    fin_analysis = ctx_state.get("financial_analysis", {}).get("result", {})
    valuation = ctx_state.get("valuation", {}).get("result", {})
    price_data = ctx_state.get("price_data", {}).get("result", {})
    judge = ctx_state.get("risk_judge", {}).get("result", {})
    financials = ctx_state.get("financial_data", {}).get("result", {})

    current_price = valuation.get("current_price", 0) or 0
    upside = valuation.get("weighted_upside_pct", 0) or 0
    target = valuation.get("weighted_value", 0) or 0
    verdict = judge.get("verdict", "HOLD")
    risks = judge.get("key_risks", [])
    ops = judge.get("key_opportunities", [])
    score = fin_analysis.get("financial_health_score", {})

    return {
        "sections": {
            "executive_summary": _exec_summary(ticker, company_name, current_price, target, upside, verdict, score),
            "company_overview": {"title": "公司概况", "content": f"{company_name}（{ticker}）", "word_count": 50},
            "industry_analysis": {"title": "行业分析", "content": "行业数据待接入", "word_count": 50},
            "financial_analysis": _fin_analysis(financials, fin_analysis),
            "valuation": _val_section(valuation, ticker),
            "risk_assessment": _risk_section(risks, ops),
            "investment_recommendation": _recommendation(verdict, company_name, upside),
        },
        "report_title": f"{company_name} ({ticker}) 深度研究报告",
        "report_subtitle": f"{_verdict_label(verdict)}评级 | {date.today().strftime('%Y年%m月')}",
        "report_date": date.today().isoformat(),
    }


def _exec_summary(ticker, name, price, target, upside, verdict, score):
    direction = "上行" if upside > 0 else ("下行" if upside < 0 else "持平")
    content = (
        f"{name}（{ticker}）当前股价 {price:.2f} 元，"
        f"加权目标价 {target:.2f} 元，{direction}空间 {abs(upside):.1f}%。"
        f"财务健康度 {score.get('rating','N/A')}（{score.get('total',0)}/32分）。"
        f"综合评级：{verdict}。"
    )
    return {"title": "投资摘要", "content": content, "word_count": len(content)}


def _fin_analysis(financials, fa):
    ratios = financials.get("ratios", {}) or fa.get("ratios", {})
    roe = ratios.get("roe")
    de = ratios.get("debt_to_equity")
    if roe is not None and de is not None:
        content = f"ROE: {roe*100:.1f}% | 负债权益比: {de:.2f}"
    else:
        content = "财务指标待补充"
    return {"title": "财务分析", "content": content, "word_count": len(content)}


def _fmt_val(v):
    """Format valuation value: float → 2 decimal, else string."""
    if isinstance(v, (int, float)):
        return f"{v:.2f}"
    return str(v) if v else "N/A"


def _val_section(v, ticker):
    dcf = _fmt_val(v.get('models', {}).get('dcf', {}).get('per_share_value'))
    oe = _fmt_val(v.get('models', {}).get('owner_earnings', {}).get('per_share_value'))
    wv = _fmt_val(v.get('weighted_value'))
    content = (
        f"DCF估值: {dcf} "
        f"| Owner Earnings: {oe} "
        f"| 加权目标价: {wv} "
        f"| 评级: {v.get('signal','N/A')}"
    )
    return {"title": "估值分析", "content": content, "word_count": len(content)}


def _verdict_label(v):
    m = {"STRONG_BUY": "买入", "BUY": "买入", "HOLD": "持有", "SELL": "卖出", "STRONG_SELL": "卖出"}
    return m.get(str(v), "持有")


def _risk_section(risks, ops):
    r_text = "；".join([r.get("risk","") for r in risks[:3]]) or "数据不足"
    o_text = "；".join([o.get("opportunity","") for o in ops[:3]]) or "数据不足"
    return {"title": "风险提示",
            "content": f"核心风险: {r_text}\n\n核心机遇: {o_text}", "word_count": 100}


def _recommendation(verdict, name, upside):
    return {"title": "投资建议",
            "content": f"{name} 综合评级: {verdict}（{upside:.1f}%空间）",
            "word_count": 30}
