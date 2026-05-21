"""Macro Data Agent — fetches China macro via Caidazi macro analysis."""

import logging

logger = logging.getLogger(__name__)


async def run_macro_agent(ticker, company_name, prices=None):
    """Fetch China macro economic analysis from Caidazi."""
    result = {"ticker": ticker, "company_name": company_name,
              "macro": {"gdp_growth_yoy": None, "cpi_yoy": None, "pmi": None, "analysis": ""}}
    try:
        from providers.qveris_provider import QverisProvider
        qv = QverisProvider()
        data = await qv.get_macro()
        if isinstance(data, dict):
            # Caidazi macro returns AI-generated analysis text
            analysis = data.get("result", data.get("analysis", ""))
            if not analysis:
                truncated = data.get("truncated_content", "")
                if truncated:
                    import json
                    try:
                        inner = json.loads(truncated)
                        analysis = inner.get("result", "") or inner.get("analysis", "")
                    except Exception:
                        analysis = truncated
            result["macro"]["analysis"] = str(analysis)[:2000] if analysis else ""
            # Try to extract GDP/CPI/PMI from text
            text = str(analysis)
            import re
            gdp_m = re.search(r'GDP[^0-9]*?([0-9.]+)\s*%', text)
            cpi_m = re.search(r'CPI[^0-9]*?([0-9.]+)\s*%', text)
            if gdp_m: result["macro"]["gdp_growth_yoy"] = float(gdp_m.group(1))
            if cpi_m: result["macro"]["cpi_yoy"] = float(cpi_m.group(1))
            result["note"] = "宏观数据已接入（Caidazi AI 宏观分析）" if analysis else "宏观分析返回空"
    except Exception as e:
        logger.info(f"Macro via QVeris: {e}")
        result["note"] = "宏观数据待接入（Phase 2）"
    return result
