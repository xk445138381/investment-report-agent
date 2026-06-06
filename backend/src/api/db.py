"""MongoDB persistence for reports — reuses TradingAgents-CN's MongoDB instance.

Environment variables (same as TradingAgents-CN):
    MONGODB_HOST     (default: localhost)
    MONGODB_PORT     (default: 27017)
    MONGODB_DATABASE (default: tradingagents)
"""

import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_db = None


async def get_reports_collection():
    """Get the investment_reports MongoDB collection, creating it lazily.

    Creates indexes on first call. Safe to call multiple times.
    """
    global _client, _db
    if _client is None:
        host = os.getenv("MONGODB_HOST", "localhost")
        port = int(os.getenv("MONGODB_PORT", "27017"))
        database = os.getenv("MONGODB_DATABASE", "tradingagents")
        _client = AsyncIOMotorClient(
            f"mongodb://{host}:{port}",
            serverSelectionTimeoutMS=3000,
        )
        _db = _client[database]

        # Ensure indexes for common queries
        col = _db["investment_reports"]
        await col.create_index("created_at", background=True)
        await col.create_index("ticker", background=True)
        logger.info("MongoDB connected: %s:%d/%s", host, port, database)
    return _db["investment_reports"]


async def close_db():
    """Close the MongoDB connection. Safe to call even if not initialized."""
    global _client
    if _client:
        _client.close()
        _client = None
        logger.info("MongoDB connection closed")
