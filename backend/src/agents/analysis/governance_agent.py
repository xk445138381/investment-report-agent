"""Corporate Governance Agent — ownership via Yahoo Finance holders."""

import logging

logger = logging.getLogger(__name__)


async def run_governance_agent(ticker, company_name, financials, prices):
    result = {"ticker": ticker, "company_name": company_name,
              "management_quality": "待补充（需管理层履历数据）",
              "ownership_structure": "待补充（需股权结构数据）"}

    # Try Yahoo Finance holders data
    try:
        from providers.qveris_provider import QverisProvider
        qv = QverisProvider()
        holders = await qv.get_holders(ticker)
        if isinstance(holders, dict):
            ownership = holders.get("ownership_info", {})
            inst = ownership.get("institutional_ownership_percent")
            insider = ownership.get("insider_ownership_percent")
            shares = ownership.get("shares_outstanding")
            if inst is not None:
                result["ownership_structure"] = (
                    f"机构持股: {inst*100:.1f}%, "
                    f"内部人持股: {(insider or 0)*100:.1f}%, "
                    f"总股本: {shares/1e9:.2f}B 股" if shares else
                    f"机构持股: {inst*100:.1f}%"
                )
                result["institutional_ownership"] = inst
                result["insider_ownership"] = insider
            if shares:
                result["shares_outstanding"] = shares
            result["note"] = "股权数据（Yahoo Finance）" if inst is not None else "股权数据返回空"
    except Exception as e:
        logger.info(f"Governance via QVeris: {e}")

    return result
