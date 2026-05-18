"""Macro Data Agent — fetches China macro indicators via QVeris (cn_financial_pro)."""

import logging

logger = logging.getLogger(__name__)


async def run_macro_agent(ticker, company_name, prices=None):
    """Fetch China macro economic data."""
    result = {"ticker": ticker, "company_name": company_name,
              "macro": {"gdp_growth_yoy": None, "cpi_yoy": None, "pmi": None}}
    try:
        from providers.qveris_provider import QverisProvider
        qv = QverisProvider()
        macro = await qv.get_macro()
        indicators = macro.get("indicators", [])
        if indicators:
            # Map known indicator names
            for ind in indicators:
                name = str(ind.get("name", ind.get("indicator_name", ""))).lower()
                val = ind.get("value", ind.get("latest_value"))
                if val is not None:
                    result["macro"]["last_updated"] = str(ind.get("date", ind.get("period", "")))
                if "gdp" in name and val is not None:
                    result["macro"]["gdp_growth_yoy"] = float(val)
                elif "cpi" in name and val is not None:
                    result["macro"]["cpi_yoy"] = float(val)
                elif "pmi" in name and val is not None:
                    result["macro"]["pmi"] = float(val)
            result["note"] = f"宏观数据已接入: {len(indicators)} 项指标"
    except Exception as e:
        logger.info(f"Macro via QVeris not available: {e}")
        result["note"] = "宏观数据待接入（Phase 2）"
    return result
