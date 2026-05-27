"""Corporate Governance Agent — ownership via Yahoo Finance (US) + AkShare (CN)."""

import logging

logger = logging.getLogger(__name__)


async def run_governance_agent(ticker, company_name, financials, prices):
    result = {"ticker": ticker, "company_name": company_name,
              "management_quality": "待补充（需管理层履历数据）",
              "ownership_structure": "待补充（需股权结构数据）"}

    # Try Yahoo Finance for US stocks
    if ".SH" not in ticker.upper() and ".SZ" not in ticker.upper() and ".HK" not in ticker.upper():
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
                result["note"] = "股权数据（Yahoo Finance）" if inst is not None else ""
        except Exception as e:
            logger.info(f"Governance via Yahoo: {e}")

    # Try AkShare for CN stocks (A-shares)
    if ".SH" in ticker.upper() or ".SZ" in ticker.upper():
        try:
            import akshare as ak
            code = ticker.split(".")[0]
            # Get top circulating shareholders
            holders_df = ak.stock_circulate_stock_holder(symbol=code)
            if holders_df is not None and not holders_df.empty:
                top3 = holders_df.head(3)
                parts = []
                for _, r in top3.iterrows():
                    name = str(r.iloc[3])[:20]  # shareholder name
                    pct = r.iloc[5]  # percentage
                    ptype = str(r.iloc[6])[:10]  # type (state-owned, institutional, etc.)
                    parts.append(f"{name}: {pct:.1f}% ({ptype})")
                if parts:
                    result["ownership_structure"] = " | ".join(parts)
                    result["note"] = "股权数据（AkShare A股流通股东）"
        except Exception as e:
            logger.info(f"Governance via AkShare: {e}")

    # Try AkShare for HK stocks
    if ".HK" in ticker.upper():
        try:
            import akshare as ak
            code = ticker.replace(".HK", "").lstrip("0") or "700"
            # HK uses company profile for basic info
            profile = ak.stock_hk_company_profile_em(symbol=code)
            if profile is not None and not profile.empty:
                r = profile.iloc[0]
                chairman = r.get("chairman", r.iloc[3] if len(r) > 3 else "")
                employees = r.get("employees", r.iloc[4] if len(r) > 4 else "")
                result["management_quality"] = f"董事长: {chairman}, 员工: {employees}"
                result["note"] = "公司信息（AkShare港股）"
        except Exception as e:
            logger.info(f"HK governance via AkShare: {e}")

    return result
