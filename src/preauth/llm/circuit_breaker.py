import asyncio
from enum import IntEnum
import time

from prometheus_client import Gauge


BREAKER_STATE = Gauge(
    "llm_circuit_breaker_state",
    "LLM circuit breaker state: 0 closed, 1 open, 2 half-open",
    ["provider"],
)


class CircuitState(IntEnum):
    CLOSED = 0
    OPEN = 1
    HALF_OPEN = 2


class CircuitOpenError(RuntimeError):
    pass


class CircuitBreaker:
    def __init__(self, provider: str, failure_threshold: int = 5, cooldown_seconds: float = 30) -> None:
        self.provider = provider
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.opened_at = 0.0
        self._half_open_probe = False
        self._lock = asyncio.Lock()
        self._publish()

    def _publish(self) -> None:
        BREAKER_STATE.labels(provider=self.provider).set(int(self.state))

    async def before_call(self) -> None:
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if time.monotonic() - self.opened_at < self.cooldown_seconds:
                    raise CircuitOpenError("provider circuit is open")
                self.state = CircuitState.HALF_OPEN
                self._half_open_probe = False
                self._publish()
            if self.state == CircuitState.HALF_OPEN:
                if self._half_open_probe:
                    raise CircuitOpenError("provider half-open probe already in progress")
                self._half_open_probe = True

    async def record_success(self) -> None:
        async with self._lock:
            self.state = CircuitState.CLOSED
            self.failures = 0
            self._half_open_probe = False
            self._publish()

    async def record_failure(self) -> None:
        async with self._lock:
            self.failures += 1
            self._half_open_probe = False
            if self.state == CircuitState.HALF_OPEN or self.failures >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.opened_at = time.monotonic()
            self._publish()
