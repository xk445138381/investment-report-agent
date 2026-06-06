import pytest

from providers.qveris_provider import QverisProvider


@pytest.mark.asyncio
async def test_cn_financials_accept_unmapped_valid_a_share_ticker(monkeypatch):
    provider = QverisProvider(api_key="test-key")
    seen_codes = []

    async def fake_call_tool(tool_id, params):
        seen_codes.append(params.get("codes"))
        if params.get("period") != "1231":
            return {"rows": []}
        if "income_statement" in tool_id:
            return {
                "rows": [{
                    "ths_operating_total_revenue_stock": 1000,
                    "ths_np_atoopc_stock": 200,
                    "ths_basic_eps_stock": 1.2,
                }]
            }
        if "balance_sheet" in tool_id:
            return {
                "rows": [{
                    "ths_total_assets_stock": 5000,
                    "ths_total_liab_stock": 2000,
                    "ths_total_owner_equity_stock": 3000,
                }]
            }
        if "cash_flow_statement" in tool_id:
            return {
                "rows": [{
                    "ths_ncf_from_oa_stock": 300,
                    "ths_cash_paid_for_assets_stock": 80,
                }]
            }
        return {"rows": []}

    monkeypatch.setattr(provider, "_call_tool", fake_call_tool)

    result = await provider._fetch_financials("601318.SH", years=0)

    assert result
    assert set(seen_codes) == {"601318.SH"}
    assert result[-1]["revenue"] == 1000
    assert result[-1]["free_cash_flow"] == 220
