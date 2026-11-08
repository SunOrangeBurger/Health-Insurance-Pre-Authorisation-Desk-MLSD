import time

import httpx
import pytest

from preauth.api.rate_limit import consume_token
from preauth.api.schemas import LLMRequest, LLMResponse
from preauth.config import Settings
from preauth.llm.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState
from preauth.llm.client import ProviderUnavailable, ResilientLLMClient


class FakeRedis:
    def __init__(self, replies):
        self.replies = iter(replies)

    async def eval(self, *args):
        return next(self.replies)


@pytest.mark.asyncio
async def test_rate_limiter_returns_retry_after() -> None:
    redis = FakeRedis([(1, b"2.0"), (0, b"0.25")])
    first = await consume_token(redis, "client-a", 3, 1)
    second = await consume_token(redis, "client-a", 3, 1)
    assert first.allowed is True
    assert second.allowed is False
    assert second.retry_after == 1


@pytest.mark.asyncio
async def test_breaker_open_half_open_close() -> None:
    breaker = CircuitBreaker("test-provider", failure_threshold=2, cooldown_seconds=0.01)
    await breaker.record_failure()
    await breaker.record_failure()
    assert breaker.state == CircuitState.OPEN
    with pytest.raises(CircuitOpenError):
        await breaker.before_call()
    breaker.opened_at = time.monotonic() - 1
    await breaker.before_call()
    assert breaker.state == CircuitState.HALF_OPEN
    await breaker.record_success()
    assert breaker.state == CircuitState.CLOSED


class FailingClient(ResilientLLMClient):
    def __init__(self, settings, failures: int):
        super().__init__(settings)
        self.failures = failures
        self.calls = 0

    async def _request(self, request):
        self.calls += 1
        if self.calls <= self.failures:
            raise httpx.ConnectError("down")
        return LLMResponse(content="ok", prompt_tokens=2, completion_tokens=1)


@pytest.mark.asyncio
async def test_retry_recovers_within_bound() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="stub",
        llm_max_attempts=3,
        retry_base_delay_s=0,
    )
    client = FailingClient(settings, failures=2)
    response = await client.complete(LLMRequest(messages=[{"role": "user", "content": "test"}]))
    assert response.content == "ok"
    assert client.calls == 3


@pytest.mark.asyncio
async def test_retry_exhaustion_opens_breaker() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="stub",
        llm_max_attempts=2,
        retry_base_delay_s=0,
        circuit_failure_threshold=1,
    )
    client = FailingClient(settings, failures=99)
    with pytest.raises(ProviderUnavailable):
        await client.complete(LLMRequest(messages=[{"role": "user", "content": "test"}]))
    assert client.breaker.state == CircuitState.OPEN
