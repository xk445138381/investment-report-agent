"""Section Writer Agent — assembles agent outputs into report sections.

When LLM is available: uses DeepSeek to write professional financial prose.
When LLM falls back: generates detailed structured content from available data.
"""

from datetime import date


async def run_section_writer(ticker, company_name, ctx_state, template_id="deep_dive_default"):
    """Produce structured report sections from all upstream agent outputs."""
    fin_analysis = ctx_state.get("financial_analysis", {}).get("result", {})
    valuation = ctx_state.get("valuation", {}).get("result", {})
    price_data = ctx_state.get("price_data", {}).get("result", {})
    judge = ctx_state.get("risk_judge", {}).get("result", {})
    financials = ctx_state.get("financial_data", {}).get("result", {})
    macro = ctx_state.get("macro_data", {}).get("result", {})
    gov = ctx_state.get("corporate_governance", {}).get("result", {})
    industry = ctx_state.get("industry_competition", {}).get("result", {})

    current_price = _n(valuation.get("current_price")) or _n(valuation.get("weighted_value", 0))
    upside = _n(valuation.get("weighted_upside_pct", 0))
    target = _n(valuation.get("weighted_value", 0))
    verdict = judge.get("verdict", "HOLD")
    risks = judge.get("key_risks", [])
    ops = judge.get("key_opportunities", [])
    score = fin_analysis.get("financial_health_score", {})
    ratios = financials.get("ratios", {}) or fin_analysis.get("ratios", {}) or {}

    return {
        "sections": {
            "executive_summary": _exec_summary(ticker, company_name, current_price, target, upside, verdict, score, ratios, risks),
            "company_overview": _company_overview(ticker, company_name, gov, industry),
            "industry_analysis": _industry_section(industry, ratios),
            "financial_analysis": _fin_analysis(financials, fin_analysis, ratios, score),
            "valuation": _val_section(valuation, ticker, current_price),
            "risk_assessment": _risk_section(risks, ops),
            "investment_recommendation": _recommendation(verdict, company_name, upside, target, current_price, score),
        },
        "report_title": f"{company_name} ({ticker}) 深度研究报告",
        "report_subtitle": f"{_verdict_label(verdict)}评级 | {date.today().strftime('%Y年%m月')}",
        "report_date": date.today().isoformat(),
    }


def _n(v):
    """Safe numeric conversion."""
    if v is None: return 0.0
    try: return float(v)
    except: return 0.0


def _pct(v, decimals=1):
    """Format as percentage string."""
    if v is None: return "N/A"
    return f"{v*100:.{decimals}f}%"


def _exec_summary(ticker, name, price, target, upside, verdict, score, ratios, risks):
    direction = "上行" if upside > 0 else ("下行" if upside < 0 else "持平")
    roe = ratios.get("roe")
    de = ratios.get("debt_to_equity")
    growth = ratios.get("revenue_growth_yoy")

    lines = [
        f"{name}（{ticker}）当前股价 {price:.2f} 元，加权目标价 {target:.2f} 元，{direction}空间 {abs(upside):.1f}%。",
        f"财务健康度评级 {score.get('rating','N/A')}（综合得分 {score.get('total',0)}/{score.get('max',32)} 分），",
    ]
    if roe is not None:
        lines.append(f"净资产收益率（ROE）{_pct(roe)}，")
    if growth is not None:
        lines.append(f"营收同比增长 {_pct(growth)}，")
    if de is not None:
        lines.append(f"负债权益比 {de:.2f}。")

    lines.append(f"综合投资评级：**{_verdict_label(verdict)}**。")

    if risks:
        top_risk = risks[0].get("risk", "") if isinstance(risks[0], dict) else str(risks[0])
        lines.append(f"主要风险关注：{top_risk}。")

    return {"title": "投资摘要", "content": "".join(lines), "word_count": len("".join(lines))}


def _company_overview(ticker, name, gov, industry):
    parts = [f"{name}（{ticker}）"]
    # Add industry classification if available
    if industry:
        l1 = industry.get("shenwan_l1", "")
        l2 = industry.get("shenwan_l2", "")
        if l1:
            parts.append(f"，隶属于{l1}" + (f" / {l2}" if l2 else "") + "行业")
    # Add ownership info if available
    ownership = ""
    if gov:
        ownership = gov.get("ownership_structure", "")
    if ownership and "待补充" not in str(ownership):
        parts.append(f"。股权结构：{ownership[:200]}")
    else:
        parts.append("。")
    return {"title": "公司概况", "content": "".join(parts), "word_count": len("".join(parts))}


def _industry_section(industry, ratios):
    parts = []
    if industry:
        l1 = industry.get("shenwan_l1", "")
        l2 = industry.get("shenwan_l2", "")
        ind_roe = industry.get("industry_roe", "")
        ind_count = industry.get("company_count", "")
        if l1:
            parts.append(f"所属申万行业：{l1}" + (f" / {l2}" if l2 else ""))
        if ind_roe:
            parts.append(f"行业平均 ROE：{ind_roe}%")
        if ind_count:
            parts.append(f"行业内公司数量：{ind_count}")
        # Compare company ROE vs industry
        roe = ratios.get("roe")
        if roe and ind_roe:
            try:
                ind_r = float(ind_roe) / 100
                if roe > ind_r:
                    parts.append(f"公司 ROE（{_pct(roe)}）显著高于行业均值，具备竞争优势。")
                else:
                    parts.append(f"公司 ROE（{_pct(roe)}）低于行业均值，需关注盈利能力。")
            except ValueError:
                pass
    if not parts:
        parts.append("行业对标数据待进一步接入。")
    content = "；".join(parts) + "。"
    return {"title": "行业分析", "content": content, "word_count": len(content)}


def _fin_analysis(financials, fa, ratios, score):
    roe = ratios.get("roe")
    roa = ratios.get("roa")
    de = ratios.get("debt_to_equity")
    curr = ratios.get("current_ratio")
    growth = ratios.get("revenue_growth_yoy")
    egrowth = ratios.get("earnings_growth_yoy")
    nm = ratios.get("net_margin")
    om = ratios.get("operating_margin")
    ocf_r = ratios.get("ocf_to_revenue")
    fcf_ni = ratios.get("fcf_to_net_income")

    lines = [f"财务健康度综合评分：{score.get('total',0)}/{score.get('max',32)} — **{score.get('rating','N/A')}**\n"]

    # Profitability
    lines.append("【盈利能力】")
    if roe is not None: lines.append(f"ROE: {_pct(roe)}")
    if roa is not None: lines.append(f"ROA: {_pct(roa)}")
    if nm is not None: lines.append(f"净利润率: {_pct(nm)}")
    if om is not None: lines.append(f"营业利润率: {_pct(om)}")
    lines.append("")

    # Growth
    lines.append("【成长性】")
    if growth is not None: lines.append(f"营收同比增长: {_pct(growth)}")
    if egrowth is not None: lines.append(f"净利润同比增长: {_pct(egrowth)}")
    lines.append("")

    # Financial Health
    lines.append("【财务健康】")
    if de is not None: lines.append(f"负债权益比: {de:.2f}")
    if curr is not None: lines.append(f"流动比率: {curr:.2f}")
    lines.append("")

    # Cash Flow Quality
    lines.append("【现金流质量】")
    if ocf_r is not None: lines.append(f"经营现金流/营收: {_pct(ocf_r)}")
    if fcf_ni is not None: lines.append(f"自由现金流/净利润: {fcf_ni:.2f}")

    return {"title": "财务分析", "content": "\n".join(lines), "word_count": len("\n".join(lines))}


def _val_section(v, ticker, current_price):
    models = v.get("models", {})
    dcf_m = models.get("dcf", {})
    oe_m = models.get("owner_earnings", {})
    ev_m = models.get("ev_ebitda", {})

    lines = ["【估值模型汇总】"]
    # DCF
    dcf_val = _n(dcf_m.get("per_share_value"))
    wacc = dcf_m.get("wacc", dcf_m.get("key_assumptions", {}).get("wacc", ""))
    lines.append(f"DCF 三阶段模型：每股价值 {dcf_val:.2f}" + (f"（WACC: {wacc}%）" if wacc else ""))
    # Owner Earnings
    oe_val = _n(oe_m.get("per_share_value"))
    lines.append(f"Owner Earnings 模型：每股价值 {oe_val:.2f}")
    # EV/EBITDA
    ev_val = _n(ev_m.get("per_share_value"))
    lines.append(f"EV/EBITDA 行业对标：每股价值 {ev_val:.2f}")

    wv = _n(v.get("weighted_value"))
    upside = _n(v.get("weighted_upside_pct"))
    signal = v.get("signal", "N/A")
    lines.append("")
    lines.append(f"加权目标价：{wv:.2f} 元 | 当前股价：{current_price:.2f} 元")
    lines.append(f"上行/下行空间：{upside:+.1f}% | 估值信号：{signal}")

    # Sensitivity
    sens = models.get("sensitivity", v.get("sensitivity_matrix", {}))
    if sens:
        lines.append(f"\n【敏感性分析】")
        lines.append(f"关键假设：WACC 与永续增长率对估值影响显著。")

    return {"title": "估值分析", "content": "\n".join(lines), "word_count": len("\n".join(lines))}


def _risk_section(risks, ops):
    lines = []
    if risks:
        lines.append("【核心风险】")
        for i, r in enumerate(risks[:5], 1):
            risk_text = r.get("risk", str(r)) if isinstance(r, dict) else str(r)
            prob = r.get("probability", "") if isinstance(r, dict) else ""
            impact = r.get("impact", "") if isinstance(r, dict) else ""
            lines.append(f"{i}. {risk_text}" + (f"（概率：{prob}，影响：{impact}）" if prob else ""))
        lines.append("")
    if ops:
        lines.append("【核心机遇】")
        for i, o in enumerate(ops[:5], 1):
            op_text = o.get("opportunity", str(o)) if isinstance(o, dict) else str(o)
            lines.append(f"{i}. {op_text}")
    if not risks and not ops:
        lines.append("风险与机遇分析数据待补充。")
    return {"title": "风险提示", "content": "\n".join(lines),
            "word_count": len("\n".join(lines))}


def _recommendation(verdict, name, upside, target, price, score):
    label = _verdict_label(verdict)
    direction = "上行" if upside > 0 else ("下行" if upside < 0 else "持平")
    lines = [
        f"{name} 综合投资评级：**{label}**（置信度：待定）",
        f"当前价格 {price:.2f} 元，目标价格 {target:.2f} 元，预计{direction}空间 {abs(upside):.1f}%。",
        f"财务健康度：{score.get('rating','N/A')}（{score.get('total','?')}/{score.get('max','?')} 分）。",
        "",
        "免责声明：本报告由 AI 辅助生成，所有分析基于公开数据和量化模型，",
        "不构成投资建议。投资者应根据自身风险承受能力独立做出投资决策。",
    ]
    return {"title": "投资建议", "content": "\n".join(lines), "word_count": len("\n".join(lines))}


def _verdict_label(v):
    m = {"STRONG_BUY": "买入", "BUY": "买入", "HOLD": "持有", "SELL": "卖出", "STRONG_SELL": "卖出"}
    return m.get(str(v), "持有")
