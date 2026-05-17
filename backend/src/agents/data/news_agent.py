"""News Data Agent."""

async def run_news_agent(ticker, company_name, prices=None):
    return {"ticker": ticker, "company_name": company_name,
            "recent_events": [], "sentiment_summary": {"overall": 0},
            "note": "新闻源待接入（Phase 2）"}
