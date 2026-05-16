"""ProviderManager — routes queries to the best available data provider.

Handles: priority ordering, fallback chains, health checking, circuit breaking.
"""

import logging
from datetime import date
from typing import Optional

from .base import DataProvider
from .health import CircuitBreaker, ProviderHealthMonitor

logger = logging.getLogger(__name__)


class ProviderManager:
    """Manages multiple DataProviders with priority-based routing and fallback."""

    def __init__(
        self,
        providers: list[tuple[DataProvider, int]],
        fallback_chains: dict[str, list[str]],
    ):
        """Initialise the manager.

        Args:
            providers: List of (provider_instance, priority) tuples.
            fallback_chains: {market: [provider_name, ...]} ordered fallback lists.
        """
        self._providers: dict[str, DataProvider] = {}
        self._priorities: dict[str, int] = {}
        self._health: dict[str, ProviderHealthMonitor] = {}
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._fallback_chains = fallback_chains

        for provider, priority in providers:
            name = provider.provider_name
            self._providers[name] = provider
            self._priorities[name] = priority
            self._health[name] = ProviderHealthMonitor(name)
            self._circuit_breakers[name] = CircuitBreaker()

    def _select_provider(self, market: str) -> DataProvider:
        """Select the best available provider for a given market."""
        chain = self._fallback_chains.get(market, [])
        for name in chain:
            if name in self._providers and not self._circuit_breakers[name].is_open():
                return self._providers[name]
        raise RuntimeError(f"No healthy provider available for market {market}")

    async def _select_healthy_provider(self, market: str) -> DataProvider:
        """Select a healthy provider, skipping those with open circuit breakers
        or failing health checks."""
        chain = self._fallback_chains.get(market, [])
        errors = []
        for name in chain:
            if name not in self._providers:
                errors.append(f"{name}: unknown provider")
                continue
            if self._circuit_breakers[name].is_open():
                errors.append(f"{name}: circuit breaker open")
                continue
            provider = self._providers[name]
            try:
                if await provider.health_check():
                    return provider
                else:
                    errors.append(f"{name}: health check returned False")
            except Exception as e:
                errors.append(f"{name}: health check error: {e}")

        raise RuntimeError(
            f"No healthy provider available for market {market}. Errors: {errors}"
        )

    async def get_prices(self, ticker: str, start_date: date, end_date: date, market: str):
        """Get prices with fallback."""
        provider = await self._select_healthy_provider(market)
        cb = self._circuit_breakers[provider.provider_name]
        try:
            result = await provider.get_prices(ticker, start_date, end_date)
            cb.record_success()
            return result
        except Exception as e:
            cb.record_failure()
            logger.warning(f"Provider {provider.provider_name} failed: {e}")
            raise

    async def get_financials(self, ticker: str, market: str, years: int = 5):
        """Get financial statements with fallback."""
        provider = await self._select_healthy_provider(market)
        cb = self._circuit_breakers[provider.provider_name]
        try:
            result = await provider.get_financials(ticker, years)
            cb.record_success()
            return result
        except Exception as e:
            cb.record_failure()
            logger.warning(f"Provider {provider.provider_name} failed: {e}")
            raise

    async def get_news(self, ticker: str, market: str, days: int = 30):
        """Get news with fallback."""
        provider = await self._select_healthy_provider(market)
        cb = self._circuit_breakers[provider.provider_name]
        try:
            result = await provider.get_news(ticker, days)
            cb.record_success()
            return result
        except Exception as e:
            cb.record_failure()
            logger.warning(f"Provider {provider.provider_name} failed: {e}")
            raise
