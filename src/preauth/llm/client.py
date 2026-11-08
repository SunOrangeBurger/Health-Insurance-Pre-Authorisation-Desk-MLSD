import asyncio
import random
from typing import Any

import httpx
from prometheus_client import Counter, Histogram

from preauth.api.schemas import LLMRequest, LLMResponse
from preauth.config import Settings
from preauth.llm.circuit_breaker import CircuitBreaker, CircuitOpenError


LLM_CALLS = Counter("llm_calls_total", "LLM provider calls", ["provider", "outcome"])
LLM_RETRIES = Counter("llm_retries_total", "LLM provider retries", ["provider"])
LLM_LATENCY = Histogram("llm_call_seconds", "LLM provider call latency", ["provider"])


class ProviderUnavailable(RuntimeError):
    pass


class ProviderResponseError(RuntimeError):
    pass


class ResilientLLMClient:
    def __init__(self, settings: Settings, breaker: CircuitBreaker | None = None) -> None:
        self.settings = settings
        self.breaker = breaker or CircuitBreaker(
            settings.llm_provider,
            settings.circuit_failure_threshold,
            settings.circuit_cooldown_s,
        )

    async def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            await self.breaker.before_call()
        except CircuitOpenError:
            LLM_CALLS.labels(self.settings.llm_provider, "short_circuit").inc()
            raise

        last_error: Exception | None = None
        for attempt in range(self.settings.llm_max_attempts):
            try:
                with LLM_LATENCY.labels(self.settings.llm_provider).time():
                    response = await self._request(request)
                await self.breaker.record_success()
                LLM_CALLS.labels(self.settings.llm_provider, "success").inc()
                return response
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
                last_error = exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 429 and exc.response.status_code < 500:
                    await self.breaker.record_failure()
                    raise
                last_error = exc
            except (ValueError, KeyError, ProviderResponseError) as exc:
                last_error = exc
            if attempt + 1 < self.settings.llm_max_attempts:
                LLM_RETRIES.labels(self.settings.llm_provider).inc()
                delay = self.settings.retry_base_delay_s * (2**attempt)
                await asyncio.sleep(delay + random.uniform(0, max(delay * 0.2, 0.001)))

        await self.breaker.record_failure()
        LLM_CALLS.labels(self.settings.llm_provider, "error").inc()
        raise ProviderUnavailable("LLM provider unavailable after bounded retries") from last_error

    async def _request(self, request: LLMRequest) -> LLMResponse:
        headers = {"Content-Type": "application/json"}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"
        timeout = httpx.Timeout(self.settings.llm_timeout_s)
        async with httpx.AsyncClient(timeout=timeout) as client:
            if self.settings.llm_provider == "stub":
                response = await client.post(
                    f"{self.settings.llm_base_url.rstrip('/')}/v1/complete",
                    json=request.model_dump(),
                    headers=headers,
                )
                response.raise_for_status()
                try:
                    return LLMResponse.model_validate(response.json())
                except (ValueError, KeyError) as exc:
                    raise ProviderResponseError("invalid stub response") from exc

            payload: dict[str, Any] = {
                "model": self.settings.llm_model,
                "messages": request.messages,
                "temperature": request.temperature,
            }
            response = await client.post(
                f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            try:
                data = response.json()
            except ValueError as exc:
                raise ProviderResponseError("provider returned invalid JSON") from exc
            usage = data.get("usage", {})
            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )
