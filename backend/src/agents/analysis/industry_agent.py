"""Industry Competition Agent — market position and competitive analysis."""

async def run_industry_agent(ticker, company_name, financials, prices):
    ratios = {}
    if financials:
        latest = financials[-1]
        ratios = {"roe": None, "revenue": latest.revenue, "net_income": latest.net_income}

    return {
        "ticker": ticker, "company_name": company_name,
        "industry": {"shenwan_l1": "待补充", "shenwan_l2": "待补充"},
        "market_position": {"market_share": None, "rank": None, "competitive_landscape": "行业数据待接入"},
        "porter_five_forces": {"overall_attractiveness": 5.0, "note": "待接入行业数据库后细化"},
        "moat_assessment": {"overall_moat_width": "WIDE" if (ratios.get("roe") or 0) > 0.20 else "NARROW"},
    }
