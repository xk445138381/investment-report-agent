"""News Data Agent — fetches recent news via QVeris (Caidazi)."""

import logging

logger = logging.getLogger(__name__)


async def run_news_agent(ticker, company_name, prices=None):
    """Fetch recent broker research reports for the given ticker via Caidazi."""
    result = {
        "ticker": ticker, "company_name": company_name,
        "recent_events": [], "sentiment_summary": {"overall": 0},
    }
    try:
        from providers.qveris_provider import QverisProvider
        qv = QverisProvider()
        news = await qv.get_news(ticker)
        if news:
            events = []
            for n in news:
                events.append({
                    "date": n.get("date", ""),
                    "title": n.get("title", ""),
                    "source": n.get("source", ""),
                    "summary": n.get("summary", ""),
                })
            result["recent_events"] = events
            result["note"] = f"财达子研报: {len(events)} 篇"
            result["data_quality"] = {"source": "Caidazi", "items_found": len(events), "quality": "high" if len(events) >= 5 else "medium" if len(events) >= 1 else "low"}
    except Exception as e:
        logger.info(f"News via QVeris not available: {e}")
        result["note"] = "新闻源待接入（Phase 2）"
        result["data_quality"] = {"source": "none", "items_found": 0, "quality": "low"}
    return result
