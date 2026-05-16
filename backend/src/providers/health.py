"""Circuit breaker and health monitoring for data providers."""

import time


class CircuitBreaker:
    """Circuit breaker pattern: after N consecutive failures, stop calling the
    provider for a cooldown period to let it recover."""

    def __init__(self, failure_threshold: int = 5, reset_timeout_seconds: int = 300):
        self.failure_threshold = failure_threshold
        self.reset_timeout_seconds = reset_timeout_seconds
        self.failure_count = 0
        self.last_failure_time: float = 0
        self.total_failures = 0
        self.total_successes = 0

    def record_success(self):
        """Record a successful call — resets failure count and closes circuit."""
        self.failure_count = 0
        self.total_successes += 1

    def record_failure(self):
        """Record a failed call."""
        self.failure_count += 1
        self.total_failures += 1
        self.last_failure_time = time.time()

    def is_open(self) -> bool:
        """Check if the circuit is open (provider should be skipped)."""
        if self.failure_count < self.failure_threshold:
            return False
        elapsed = time.time() - self.last_failure_time
        return elapsed < self.reset_timeout_seconds

    def is_half_open(self) -> bool:
        """Check if circuit is in half-open state (cooled down, ready to retry)."""
        if self.failure_count < self.failure_threshold:
            return False
        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.reset_timeout_seconds

    @property
    def success_rate(self) -> float:
        total = self.total_successes + self.total_failures
        if total == 0:
            return 1.0
        return self.total_successes / total


class ProviderHealthMonitor:
    """Tracks health metrics for a data provider."""

    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.circuit_breaker = CircuitBreaker()
        self.consecutive_timeouts = 0
        self.last_latency_ms: float = 0

    def record_latency(self, latency_ms: float):
        self.last_latency_ms = latency_ms

    def is_healthy(self) -> bool:
        return not self.circuit_breaker.is_open()
