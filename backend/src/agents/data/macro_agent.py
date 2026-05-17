"""Macro Data Agent."""

async def run_macro_agent(ticker, company_name, prices=None):
    return {"ticker": ticker, "company_name": company_name,
            "macro": {"gdp_growth_yoy": None, "cpi_yoy": None, "pmi": None},
            "note": "宏观数据待接入（Phase 2）"}
