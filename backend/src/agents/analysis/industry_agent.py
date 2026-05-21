"""Industry Competition Agent — 申万 L1 data + moat assessment."""

import logging

logger = logging.getLogger(__name__)


async def run_industry_agent(ticker, company_name, financials, prices):
    # Compute actual ROE from financials
    roe = None
    if financials:
        latest = financials[-1]
        if latest.net_income and latest.total_equity and latest.total_equity > 0:
            roe = latest.net_income / latest.total_equity

    result = {
        "ticker": ticker, "company_name": company_name,
        "industry": {"shenwan_l1": "待补充", "shenwan_l2": "待补充"},
        "market_position": {"market_share": None, "rank": None, "competitive_landscape": "行业数据待接入"},
        "porter_five_forces": {"overall_attractiveness": 5.0, "note": "待接入行业数据库后细化"},
        "moat_assessment": {"overall_moat_width": "WIDE" if (roe or 0) > 0.20 else "NARROW"},
    }

    # Try 申万 L1 industry data via Caidazi
    try:
        from providers.qveris_provider import QverisProvider
        qv = QverisProvider()
        sw_data = await qv.get_industry(ticker)
        if isinstance(sw_data, dict):
            text = str(sw_data.get("result", "") or sw_data.get("truncated_content", ""))
            if text and len(text) > 50:
                import re
                ind_roe = re.search(r'ROE[^0-9.]*?([0-9.]+)', text)
                companies = re.search(r'行业内公司[^0-9]*?(\d+)', text)
                if ind_roe:
                    result["moat_assessment"]["industry_roe"] = float(ind_roe.group(1))
                    result["moat_assessment"]["company_roe"] = round(roe * 100, 1) if roe else None
                if companies:
                    result["market_position"]["industry_companies"] = int(companies.group(1))
                result["market_position"]["competitive_landscape"] = text[:500]
                result["industry"]["note"] = "申万一级行业数据（Caidazi）"
    except Exception as e:
        logger.info(f"Industry via QVeris: {e}")

    return result
