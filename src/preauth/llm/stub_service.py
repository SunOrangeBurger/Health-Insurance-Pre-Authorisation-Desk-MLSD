import asyncio
import random

from fastapi import FastAPI, HTTPException
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from starlette.responses import Response

from preauth.api.schemas import LLMRequest, LLMResponse
from preauth.config import get_settings

settings = get_settings()
app = FastAPI(title="Pre-Authorisation LLM Stub", version="1.0")
CALLS = Counter("llm_stub_calls_total", "Stub LLM calls", ["outcome"])


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/complete", response_model=LLMResponse)
async def complete(payload: LLMRequest) -> LLMResponse:
    delay = settings.stub_delay_ms + random.randint(0, settings.stub_jitter_ms)
    if settings.fault_mode == "slow":
        delay *= 10
    await asyncio.sleep(delay / 1000)
    if settings.fault_mode == "provider_down":
        CALLS.labels(outcome="error").inc()
        raise HTTPException(status_code=503, detail="stub provider unavailable")
    content = "{\"status\":\"stubbed\",\"recommendation\":\"medical-review\"}"
    if settings.fault_mode == "garbage":
        content = "not-json"
    CALLS.labels(outcome="success").inc()
    prompt_tokens = sum(len(message.get("content", "").split()) for message in payload.messages)
    return LLMResponse(content=content, prompt_tokens=prompt_tokens, completion_tokens=len(content.split()))
