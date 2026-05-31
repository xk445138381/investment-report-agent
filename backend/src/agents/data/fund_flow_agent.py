"""Fund Flow Agent — Northbound + institutional capital flow for A-stocks."""

import logging, sys
logger = logging.getLogger(__name__)

_TA_PATH = r"H:\TradingAgents-astock-0.2.11"
if _TA_PATH not in sys.path:
    sys.path.insert(0, _TA_PATH)


async def run_fund_flow(ticker, company_name, prices=None):
    """Fetch northbound and institutional fund flow data for CN stocks."""
    result = {"ticker": ticker, "company_name": company_name, "flow": {}}
    if ".SH" not in ticker.upper() and ".SZ" not in ticker.upper():
        result["flow"]["note"] = "资金流向仅支持A股"
        return result

    try:
        from tradingagents.dataflows.a_stock import (
            _normalize_ticker, get_fund_flow, get_northbound_flow
        )
        code = _normalize_ticker(ticker)

        # Fund flow
        try:
            ff = get_fund_flow(code)
            if isinstance(ff, str) and ff:
                lines = ff.strip().split("\n")
                result["flow"]["fund_flow_summary"] = lines[:3] if lines else []
        except Exception as e:
            logger.info(f"Fund flow({ticker}): {e}")

        # Northbound flow (北向资金)
        try:
            nb = get_northbound_flow(code)
            if isinstance(nb, str) and nb:
                lines = nb.strip().split("\n")
                result["flow"]["northbound"] = lines[:3] if lines else []
        except Exception as e:
            logger.info(f"Northbound({ticker}): {e}")

        result["note"] = "资金面数据已接入（TradingAgents-astock）"
    except Exception as e:
        logger.info(f"Fund flow({ticker}): {e}")
        result["note"] = "资金面数据待接入"

    return result
