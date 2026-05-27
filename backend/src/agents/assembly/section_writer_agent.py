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

    # Route to value investing template
    if "value_investor" in template_id:
        return _render_value_template(ticker, company_name, ctx_state, fin_analysis, valuation, gov, industry, financials)

    # Original deep_dive template
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


def _render_value_template(ticker, company_name, ctx_state, fin_analysis, valuation, gov, industry, financials):
    """Render the 8-section value investing report template."""
    duan = ctx_state.get("duan_case", {}).get("result", {})
    munger = ctx_state.get("munger_case", {}).get("result", {})
    vjudge = ctx_state.get("value_judge", {}).get("result", {})
    price_data = ctx_state.get("price_data", {}).get("result", {})
    score = fin_analysis.get("financial_health_score", {})
    ratios = financials.get("ratios", {}) or fin_analysis.get("ratios", {}) or {}

    current_price = _n(valuation.get("current_price", 0)) or _n(price_data.get("price_summary", {}).get("latest_price", 0))
    upside = _n(valuation.get("weighted_upside_pct", 0))
    target = _n(valuation.get("weighted_value", 0))
    verdict = vjudge.get("verdict", "HOLD")
    verdict_conf = vjudge.get("verdict_confidence", 50)

    label = "Yes（可买）" if verdict in ("Yes", "STRONG_BUY", "BUY") else (
        "No（不买）" if verdict in ("No", "SELL", "STRONG_SELL") else "Too Hard（太难）")

    return {
        "sections": {
            "executive_summary": {
                "title": "一句话投资摘要",
                "content": _val_one_liner(ticker, company_name, current_price, target, upside, label, verdict_conf, score, duan),
                "word_count": 150,
            },
            "business_model": {
                "title": "商业模式：它怎么赚钱，为什么能持续",
                "content": _val_business_model(duan, ratios, industry, score),
                "word_count": 300,
            },
            "corporate_character": {
                "title": "企业文化与本分",
                "content": _val_culture_section(gov, duan, ratios),
                "word_count": 200,
            },
            "financial_health": {
                "title": "财务健康与现金流",
                "content": _val_financial_health(ratios, score, financials, fin_analysis),
                "word_count": 300,
            },
            "valuation": {
                "title": "估值与安全边际",
                "content": _val_safety_margin(valuation, current_price),
                "word_count": 300,
            },
            "inversion_checklist": {
                "title": "逆向风险清单：这笔投资怎么死",
                "content": _val_inversion_checklist(munger, ratios, score, duan),
                "word_count": 300,
            },
            "dual_verdict": {
                "title": "双重视角裁决",
                "content": _val_dual_verdict(vjudge, duan, munger),
                "word_count": 300,
            },
            "final_judgment": {
                "title": "综合判定",
                "content": _val_final_judgment(verdict, label, verdict_conf, target, upside, company_name, vjudge),
                "word_count": 200,
            },
        },
        "report_title": f"{company_name} ({ticker}) — 价值投资视角",
        "report_subtitle": f"段永平 × 芒格 双重视角 | {date.today().strftime('%Y年%m月')}",
        "report_date": date.today().isoformat(),
    }


def _val_business_model(duan, ratios, industry, score):
    """Business model section: LLM text if rich, otherwise data-driven fallback."""
    duan_text = duan.get("analysis", "")
    # If LLM produced real content (not fallback), use it
    if duan_text and len(duan_text) > 100 and "fallback" not in str(duan.get("perspective", "")):
        return duan_text[:1200]

    # Data-driven fallback
    lines = ["## 商业模式分析（数据驱动）\n"]
    roe = ratios.get("roe")
    gm = ratios.get("_gross_margin") or ratios.get("gross_margin")
    nm = ratios.get("net_margin")
    fcf_ni = ratios.get("fcf_to_net_income")
    de = ratios.get("debt_to_equity")
    growth = ratios.get("revenue_growth_yoy")

    # Profitability signals
    if roe and roe > 0.20:
        lines.append(f"高 ROE（{_pct(roe)}）表明公司具备可持续竞争优势——这是段永平最看重的指标。能用很少的资本产生很高的回报，意味着这盘生意不需要持续大量投入就能赚钱。")
    elif roe and roe > 0.10:
        lines.append(f"ROE {_pct(roe)}，处于合理水平。需要进一步分析：回报是否来自真正的竞争优势，还是周期性因素。")

    if gm and gm > 0.50:
        lines.append(f"毛利率 {_pct(gm)}，说明产品或服务有定价权——客户离不开你。这是护城河的重要证据。")
    elif nm and nm > 0.20:
        lines.append(f"净利润率 {_pct(nm)}，盈利能力强。但要区分：是行业普遍好还是公司特别好？后者才是护城河。")

    # Cash flow quality
    if fcf_ni and fcf_ni > 0.8:
        lines.append(f"FCF/净利润 = {fcf_ni:.2f}，利润几乎全部转化为现金。这是段永平最放心的公司类型——赚的不是纸上利润，是真钱。")
    elif fcf_ni is not None and fcf_ni < 0.5:
        lines.append(f"⚠ FCF/净利润仅 {fcf_ni:.2f}，利润质量存疑。段永平会问：钱去哪了？为什么赚了利润却没有现金？")

    # Capital efficiency
    if de is not None and de < 0.3:
        lines.append(f"几乎零负债（D/E = {de:.2f}）。公司不需要借钱就能运营和增长，财务极其保守——说明管理层不赌。")

    # Growth check
    if growth is not None:
        direction = "增长" if growth > 0.05 else "放缓" if growth < 0 else "平稳"
        lines.append(f"营收{direction}（YoY {_pct(growth)}）。段永平不追求高增长，他追求确定性。低速但确定 > 高速但不稳。")

    if len(lines) == 1:
        lines.append("数据不足，无法从财务角度评估商业模式。请参考段永平视角的完整分析。")

    return "\n\n".join(lines)


def _val_inversion_checklist(munger, ratios, score, duan):
    """Inversion checklist: LLM text if rich, otherwise structured risk analysis."""
    munger_text = munger.get("analysis", "")
    if munger_text and len(munger_text) > 100 and "fallback" not in str(munger.get("perspective", "")):
        return munger_text[:1200]

    # Data-driven inversion checklist
    lines = ["## 逆向风险清单（数据驱动）\n"]
    de = ratios.get("debt_to_equity")
    growth = ratios.get("revenue_growth_yoy")
    fcf_ni = ratios.get("fcf_to_net_income")
    curr = ratios.get("current_ratio")
    roe = ratios.get("roe")

    risks_found = 0

    # 1. Leverage risk
    if de is not None and de > 1.0:
        lines.append(f"**死法 1：杠杆爆雷。** 负债权益比 {de:.2f}，高杠杆意味着容错空间极小。一旦盈利下滑或融资收紧，债务利息就会变成致命负担。芒格说过：杠杆+愚蠢=灾难。")
        risks_found += 1
    elif de is not None and de > 0.5:
        lines.append(f"**风险：中度杠杆。** 负债权益比 {de:.2f}，虽不算危险，但经济下行时会放大损失。逆向想：如果营收下滑 30%，还能还债吗？")
        risks_found += 1

    # 2. Growth reversal
    if growth is not None and growth < 0.05:
        lines.append(f"**死法 2：增长神话破灭。** 营收增长仅 {_pct(growth)}。如果市场此前给了高估值，一旦增长故事讲不下去，戴维斯双杀。芒格会问：你确定不是因为FOMO才关注这只股票？")
        risks_found += 1

    # 3. Cash flow quality
    if fcf_ni is not None and fcf_ni < 0.5:
        lines.append(f"**死法 3：现金断流。** FCF/净利润仅 {fcf_ni:.2f}。如果应收账款暴雷或存货贬值，纸面利润瞬间蒸发。记住：利润是意见，现金是事实。")
        risks_found += 1

    # 4. Business model vulnerability
    biz_score = duan.get("business_clarity", 50) if duan.get("business_clarity") else 50
    if biz_score < 60:
        lines.append(f"**死法 4：看不懂的生意。** 商业模式清晰度评分 {biz_score}/100。芒格：如果你不能在两分钟内讲清楚这家公司怎么赚钱，你就是不懂。不懂的东西别碰。")
        risks_found += 1

    # 5. Lollapalooza check
    if risks_found >= 2:
        lines.append(f"**Lollapalooza 警告：** 已识别 {risks_found} 个风险因子。多种风险同时发力会相互强化——单个风险可控，组合起来可能是毁灭性的。")
    elif risks_found == 0:
        lines.append("**初步排查未发现明显致命风险。** 但芒格会提醒：你的检查清单本身可能有盲点。最大的风险往往是你没想到的那个。")
        lines.append("系统性风险清单：竞争颠覆 / 技术替代 / 监管突变 / 管理层失德 / 宏观黑天鹅。每一项都应该认真想过。")

    return "\n\n".join(lines)


def _val_one_liner(ticker, name, price, target, upside, label, conf, score, duan):
    direction = "上行" if upside > 0 else "下行"
    biz_ok = duan.get("business_clarity", 50) if duan.get("business_clarity") else 50
    parts = [
        f"{name}（{ticker}）当前 {price:.2f} 元。",
        f"判定：**{label}**（置信度 {conf}%）。" if conf else f"判定：**{label}**。",
    ]
    if target > 0 and upside != 0:
        parts.append(f"估计内在价值 {target:.2f} 元，{direction}空间 {abs(upside):.1f}%。")
    if score.get("rating"):
        parts.append(f"财务底子：{score.get('rating', '?')}。")
    if biz_ok >= 70:
        parts.append("商业模式清晰，看得懂。")
    return " ".join(parts)


def _val_culture_section(gov, duan, ratios):
    parts = []
    o = gov.get("ownership_structure", "")
    if o and "待补充" not in str(o):
        parts.append(f"股权结构：{o[:150]}")
    if duan.get("culture_benfen"):
        parts.append(f"本分评分：{duan['culture_benfen']}/100")
    if ratios.get("debt_to_equity"):
        de = ratios["debt_to_equity"]
        if de < 0.3:
            parts.append("财务保守（低杠杆），管理层不赌——好信号。")
        elif de > 1.5:
            parts.append("高杠杆运营，管理层在放大风险——减分。")
    if duan.get("analysis"):
        # Extract the culture/management part of Duan's analysis
        analysis = duan.get("analysis", "")
        if "企业文化" in analysis or "本分" in analysis or "管理" in analysis:
            parts.append(analysis[analysis.find("企业"):analysis.find("企业")+300] if "企业" in analysis else "")
    return "\n\n".join(p for p in parts if p) or "管理层数据待补充。"


def _val_financial_health(ratios, score, financials, fa):
    r = ratios
    lines = [f"财务健康综合评分：{score.get('total','?')}/{score.get('max','?')} — **{score.get('rating','?')}**"]
    lines.append("")
    lines.append("| 指标 | 数值 | 评价 |")
    lines.append("|------|------|------|")
    if r.get("roe"): lines.append(f"| ROE | {r['roe']*100:.1f}% | {'优秀' if r['roe']>0.2 else '良好' if r['roe']>0.15 else '一般'} |")
    if r.get("fcf_to_net_income"): lines.append(f"| FCF/净利润 | {r['fcf_to_net_income']:.2f} | {'现金机器' if r['fcf_to_net_income']>0.8 else '一般' if r['fcf_to_net_income']>0.5 else '需关注'} |")
    if r.get("debt_to_equity"): lines.append(f"| 负债权益比 | {r['debt_to_equity']:.2f} | {'低杠杆' if r['debt_to_equity']<0.3 else '中等' if r['debt_to_equity']<0.7 else '高杠杆'} |")
    if r.get("revenue_growth_yoy"): lines.append(f"| 营收增长 YoY | {r['revenue_growth_yoy']*100:+.1f}% | {'强劲' if r['revenue_growth_yoy']>0.15 else '稳健' if r['revenue_growth_yoy']>0.05 else '放缓'} |")
    if r.get("ocf_to_revenue"): lines.append(f"| 经营现金流/营收 | {r['ocf_to_revenue']*100:.1f}% | {'优质' if r['ocf_to_revenue']>0.2 else '需关注'} |")
    lines.append("")
    lines.append("底线：这盘生意的财务底子" + ("好。" if score.get('total',0) >= 20 else "一般，需要更厚的安全边际。" if score.get('total',0) >= 10 else "有问题。不买。"))
    return "\n".join(lines)


def _val_safety_margin(valuation, current_price):
    lines = []
    models = valuation.get("models", {})
    dcf = models.get("dcf", {}).get("per_share_value", 0) or 0
    oe = models.get("owner_earnings", {}).get("per_share_value", 0) or 0
    ev = models.get("ev_ebitda", {}).get("per_share_value", 0) or 0
    wv = _n(valuation.get("weighted_value", 0))
    upside = _n(valuation.get("weighted_upside_pct", 0))

    if wv > 0:
        lines.append(f"**内在价值估算：{wv:.2f} 元/股**（当前价格 {current_price:.2f}，{'+' if upside>0 else ''}{upside:.1f}% 空间）")
        lines.append("")
        if dcf > 0: lines.append(f"- DCF 三阶段模型：{dcf:.2f}")
        if oe > 0: lines.append(f"- Owner Earnings：{oe:.2f}")
        if ev > 0: lines.append(f"- EV/EBITDA 对标：{ev:.2f}")

        safety = (wv - current_price) / wv * 100 if wv > 0 else 0
        lines.append("")
        if safety > 30:
            lines.append(f"安全边际：{safety:.0f}%（>30%，足够厚）。")
            lines.append(f"合理买价区间：低于 {wv*0.7:.0f} 元开始买入，低于 {wv*0.5:.0f} 元可重仓。")
        elif safety > 10:
            lines.append(f"安全边际：{safety:.0f}%（尚可但不厚）。")
            lines.append("当前价格不算贵，但也谈不上便宜。小仓位试探，等更好的价格。")
        else:
            lines.append("安全边际不足。好东西也要等好价钱。放着，不急。")
    else:
        lines.append("估值数据不足，无法给出具体买价区间。")
    return "\n".join(lines)


def _val_dual_verdict(vjudge, duan, munger):
    lines = []
    duan_v = duan.get("verdict", "?")
    munger_v = munger.get("verdict", "?")
    consensus = vjudge.get("consensus", "")
    disagreement = vjudge.get("disagreement", "")

    lines.append("### 段永平的判断")
    duan_text = duan.get("analysis", "")
    # Get the concluding paragraph
    if duan_text:
        para = duan_text.split("\n")[-1] if "\n" in duan_text else duan_text[-200:]
        lines.append(para[:300] if len(para) > 300 else para)
    else:
        lines.append(f"总体评估：{duan.get('overall_score','?')}/100 → {duan_v}")
    lines.append("")

    lines.append("### 芒格的判断")
    munger_text = munger.get("analysis", "")
    if munger_text:
        para = munger_text.split("\n")[-1] if "\n" in munger_text else munger_text[-200:]
        lines.append(para[:300] if len(para) > 300 else para)
    else:
        lines.append(f"风险评估：{munger.get('overall_risk','?')}/100 → {munger_v}")
    lines.append("")

    if consensus:
        lines.append(f"### 共识\n{consensus}")
    if disagreement:
        lines.append(f"\n### 分歧\n{disagreement}")

    return "\n".join(lines)


def _val_final_judgment(verdict, label, conf, target, upside, name, vjudge):
    lines = [
        f"## {label}",
        f"",
        f"{name} — {verdict}（置信度 {conf}%）。",
    ]
    price_range = vjudge.get("price_range", "")
    position = vjudge.get("position_sizing", "")
    if price_range:
        lines.append(f"买价参考：{price_range}。")
    if position:
        lines.append(f"仓位建议：{position}。")
    lines.append("")
    lines.append("---")
    lines.append("*免责声明：本报告由 AI 辅助生成，分析框架基于段永平和查理·芒格的价值投资思想。所有结论均来自公开数据推算，不构成投资建议。独立思考，独立决策。*")
    return "\n".join(lines)


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
