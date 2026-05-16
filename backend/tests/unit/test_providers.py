"""T04: Provider layer tests (TDD — test first)."""

from datetime import date
from unittest.mock import AsyncMock, patch
import pytest

from providers.base import DataProvider
from providers.manager import ProviderManager


class StubProvider(DataProvider):
    """A concrete test implementation of DataProvider ABC."""
    provider_name = "stub"
    _healthy = True
    _prices = []
    _financials = []
    _news = []
    _supported_markets = ["CN", "US"]

    async def health_check(self) -> bool:
        return self._healthy

    async def get_prices(self, ticker, start_date, end_date):
        if not self._healthy:
            raise ConnectionError("stub unhealthy")
        return self._prices

    async def get_financials(self, ticker, years=5):
        return self._financials

    async def get_news(self, ticker, days=30):
        return self._news

    def supports_market(self, market):
        return market in self._supported_markets


class TestDataProviderABC:
    def test_cannot_instantiate_abstract_provider(self):
        """Given: incomplete abstract subclass
           When: instantiate
           Then: TypeError"""
        class IncompleteProvider(DataProvider):
            provider_name = "incomplete"
            async def health_check(self): pass
            async def get_prices(self, *args): pass

        with pytest.raises(TypeError):
            IncompleteProvider()  # type: ignore

    def test_concrete_provider_instantiates(self):
        """Given: complete concrete implementation
           When: instantiate
           Then: success"""
        p = StubProvider()
        assert p.provider_name == "stub"


class TestProviderManager:
    def test_routes_to_highest_priority_healthy_provider(self):
        high = StubProvider()
        high.provider_name = "high_priority"
        low = StubProvider()
        low.provider_name = "low_priority"

        mgr = ProviderManager(
            providers=[(high, 1), (low, 2)],
            fallback_chains={"CN": ["high_priority", "low_priority"]},
        )
        # Sync select without health check for priority test
        assert mgr._select_provider("CN").provider_name == "high_priority"

    @pytest.mark.asyncio
    async def test_falls_back_when_primary_unhealthy(self):
        primary = StubProvider()
        primary.provider_name = "bad"
        primary._healthy = False
        fallback = StubProvider()
        fallback.provider_name = "good"

        mgr = ProviderManager(
            providers=[(primary, 1), (fallback, 2)],
            fallback_chains={"CN": ["bad", "good"]},
        )
        provider = await mgr._select_healthy_provider("CN")
        assert provider is not None
        assert provider.provider_name == "good"

    @pytest.mark.asyncio
    async def test_all_unhealthy_raises_error(self):
        p1 = StubProvider()
        p1.provider_name = "bad1"
        p1._healthy = False
        p2 = StubProvider()
        p2.provider_name = "bad2"
        p2._healthy = False

        mgr = ProviderManager(
            providers=[(p1, 1), (p2, 2)],
            fallback_chains={"CN": ["bad1", "bad2"]},
        )
        with pytest.raises(RuntimeError, match="No healthy provider"):
            await mgr._select_healthy_provider("CN")

    def test_circuit_breaker(self):
        """Given: provider fails 5 times consecutively
           When: 6th attempt
           Then: circuit breaker activates, skip this provider"""
        from providers.health import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=5, reset_timeout_seconds=3600)

        # 5 consecutive failures
        for _ in range(5):
            cb.record_failure()

        assert cb.is_open() is True

        # Reset after timeout
        cb.last_failure_time = 0  # force timeout
        assert cb.is_open() is False

    def test_circuit_breaker_resets_on_success(self):
        """Given: some failures but then success
           When: record_success()
           Then: circuit stays closed, failure count resets"""
        from providers.health import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=5, reset_timeout_seconds=3600)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.is_open() is False
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_market_routing(self):
        cn_prov = StubProvider()
        cn_prov.provider_name = "cn_prov"
        cn_prov._supported_markets = ["CN"]

        us_prov = StubProvider()
        us_prov.provider_name = "us_prov"
        us_prov._supported_markets = ["US"]

        mgr = ProviderManager(
            providers=[(cn_prov, 1), (us_prov, 2)],
            fallback_chains={"CN": ["cn_prov"], "US": ["us_prov"]},
        )
        assert (await mgr._select_healthy_provider("US")).provider_name == "us_prov"
        assert (await mgr._select_healthy_provider("CN")).provider_name == "cn_prov"
