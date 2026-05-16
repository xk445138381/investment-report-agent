"""DataProvider abstract base class."""

from abc import ABC, abstractmethod
from datetime import date


class DataProvider(ABC):
    """All data providers must implement this interface."""

    provider_name: str

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the data source is currently reachable."""
        ...

    @abstractmethod
    async def get_prices(self, ticker: str, start_date: date, end_date: date) -> list:
        """Get daily OHLCV price data."""
        ...

    @abstractmethod
    async def get_financials(self, ticker: str, years: int = 5) -> list:
        """Get financial statements for the given number of years."""
        ...

    @abstractmethod
    async def get_news(self, ticker: str, days: int = 30) -> list:
        """Get recent news and announcements."""
        ...

    @abstractmethod
    def supports_market(self, market: str) -> bool:
        """Check if this provider supports the given market (CN, US, HK)."""
        ...
