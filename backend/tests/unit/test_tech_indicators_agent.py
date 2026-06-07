from types import SimpleNamespace

import pytest

from agents.data.tech_indicators_agent import run_tech_indicators


@pytest.mark.asyncio
async def test_rsi_uses_most_recent_prices():
    closes = list(range(100, 116)) + list(range(115, 100, -1))
    prices = [
        SimpleNamespace(close=close, volume=1000 + idx)
        for idx, close in enumerate(closes)
    ]

    result = await run_tech_indicators("TEST", "Test Co", prices)

    assert result["signals"]["rsi"] < 30
    assert result["signals"]["rsi_signal"] == "超卖"
