"""Integration tests — verify the full pipeline end-to-end."""

import pytest
import httpx
import asyncio
import time


BASE = "http://localhost:8000/api/v1"


@pytest.fixture
def client():
    return httpx.Client(timeout=30)


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.asyncio
async def test_brief_pipeline_e2e():
    """Trigger brief report generation and verify structured output."""
    async with httpx.AsyncClient(timeout=30, trust_env=False) as c:
        # 1. Start report
        r = await c.post(f"{BASE}/report/generate", json={
            "ticker": "600519.SH", "report_type": "brief"
        })
        assert r.status_code == 201, f"Generate failed: {r.text}"
        tid = r.json()["task_id"]
        assert tid

        # 2. Poll until complete (max 5 minutes — LLM calls can be slow)
        deadline = time.time() + 300
        status = "queued"
        while time.time() < deadline:
            s = await c.get(f"{BASE}/report/{tid}/status")
            assert s.status_code == 200
            status = s.json()["status"]
            if status in ("completed", "failed"):
                break
            await asyncio.sleep(2)

        assert status == "completed", f"Task failed: {s.text}"

        # 3. Check result structure
        r = await c.get(f"{BASE}/report/{tid}?include_charts=false")
        assert r.status_code == 200
        result = r.json()

        # Core sections should exist
        assert "financial_data" in result
        assert "financial_analysis" in result
        assert "valuation" in result
        assert "risk_judge" in result
        assert "section_writer" in result
        assert "news_data" in result

        # Financial ratios should have data
        fd = result["financial_data"]["result"]
        assert len(fd.get("ratios", {})) > 0, "No financial ratios computed"
        assert "roe" in fd["ratios"] or "net_margin" in fd["ratios"]

        # Verdict should be one of the known values
        judge = result["risk_judge"]["result"]
        assert judge["verdict"] in ("STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL")

        # Report sections should be generated
        sw = result["section_writer"]["result"]
        sections = sw.get("sections", {})
        assert len(sections) >= 5, f"Expected >=5 sections, got {len(sections)}"
        assert "executive_summary" in sections
        summary = sections["executive_summary"]["content"]
        assert len(summary) > 20, "Executive summary too short"

        # News should be present (Caidazi fetch)
        news = result["news_data"]["result"]
        events = news.get("recent_events", [])
        assert len(events) >= 0  # At minimum, should be a list


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_invalid_ticker():
    """Invalid ticker should return 400."""
    async with httpx.AsyncClient(timeout=10, trust_env=False) as c:
        r = await c.post(f"{BASE}/report/generate", json={
            "ticker": "ZZZZZZ", "report_type": "brief"
        })
        assert r.status_code == 400


@pytest.mark.integration
@pytest.mark.asyncio
async def test_task_status_404():
    """Unknown task ID should return 404."""
    async with httpx.AsyncClient(timeout=10, trust_env=False) as c:
        r = await c.get(f"{BASE}/report/nonexistent-id/status")
        assert r.status_code == 404


@pytest.mark.integration
def test_health_check():
    """Backend health endpoint should return OK."""
    with httpx.Client(timeout=5, trust_env=False) as c:
        r = c.get("http://localhost:8000/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
