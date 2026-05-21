"""Macro Data Agent — fetches China macro via Caidazi macro analysis."""

import logging

logger = logging.getLogger(__name__)


async def run_macro_agent(ticker, company_name, prices=None):
    """Fetch China macro economic analysis from Caidazi."""
    result = {"ticker": ticker, "company_name": company_name,
              "macro": {"gdp_growth_yoy": None, "cpi_yoy": None, "pmi": None, "analysis": ""}}
    try:
        from providers.qveris_provider import QverisProvider
        import json, re
        qv = QverisProvider()
        raw = await qv.get_macro()
        text = ""
        if isinstance(raw, dict):
            # Caidazi returns {"success": true, "result": "analysis text..."} or truncated_content
            text = str(raw.get("result", raw.get("analysis", "")))
            if not text or text == "None":
                tc = raw.get("truncated_content", "")
                if tc:
                    try:
                        inner = json.loads(tc)
                        text = str(inner.get("result", "")) or str(inner.get("analysis", ""))
                    except Exception:
                        text = tc
            if not text or text == "None":
                text = str(raw)
        result["macro"]["analysis"] = text[:2000] if text and text != "None" else ""
        if text and text != "None":
            gdp_m = re.search(r'GDP\D*?([0-9.]+)\s*%', text)
            cpi_m = re.search(r'CPI\D*?([0-9.]+)\s*%', text)
            m2_m = re.search(r'M2\D*?([0-9.]+)\s*%', text)
            pmi_m = re.search(r'PMI\D*?([0-9.]+)', text)
            if gdp_m: result["macro"]["gdp_growth_yoy"] = float(gdp_m.group(1))
            if cpi_m: result["macro"]["cpi_yoy"] = float(cpi_m.group(1))
            if m2_m: result["macro"]["m2_growth_yoy"] = float(m2_m.group(1))
            if pmi_m: result["macro"]["pmi"] = float(pmi_m.group(1))
            result["note"] = "宏观数据已接入（Caidazi AI 宏观分析）"
        else:
            result["note"] = "宏观分析返回空"
    except Exception as e:
        logger.info(f"Macro via QVeris: {e}")
        result["note"] = "宏观数据待接入（Phase 2）"
    return result
