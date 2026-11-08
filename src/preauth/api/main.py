from contextlib import asynccontextmanager
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from preauth.api.middleware import CorrelationIdMiddleware
from preauth.api.rate_limit import consume_token
from preauth.api.schemas import (
    CONTRACT_VERSION,
    PreauthRequest,
    QuarantineResponse,
    RunResponse,
    SubmissionResponse,
)
from preauth.config import get_settings
from preauth.guardrails.detectors import inspect_request
from preauth.obs.logging import configure_logging, get_logger
from preauth.obs.metrics import GUARDRAIL_HITS, RATE_LIMITED
from preauth.obs.tracing import configure_tracing
from preauth.store.database import close_database, get_session, init_database
from preauth.store.repository import create_quarantine, create_run, get_cost_entries, get_run, get_run_steps, update_run

configure_logging()
logger = get_logger(__name__)
settings = get_settings()
SUBMISSIONS = Counter("preauth_submissions_total", "Accepted pre-authorisation submissions")
QUARANTINED = Counter("preauth_quarantine_total", "Rejected pre-authorisation submissions")
INDEX_BUILT = Gauge("index_built_timestamp", "Unix timestamp of the active policy index")
INDEX_CHUNKS = Gauge("index_chunks_total", "Chunks in the active policy index")
INDEX_RATE = Gauge("ingest_chunks_per_second", "Chunk throughput of the latest index build")


def _read_index_manifest() -> dict[str, Any] | None:
    path = Path(settings.index_storage_dir) / "index_manifest.json"
    if not path.exists():
        return None
    manifest = json.loads(path.read_text(encoding="utf-8"))
    INDEX_CHUNKS.set(manifest["n_chunks"])
    INDEX_RATE.set(manifest["chunks_per_second"])
    INDEX_BUILT.set(datetime.fromisoformat(manifest["built_at"]).timestamp())
    return manifest


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_tracing("preauth-api", settings.otel_exporter_endpoint, settings.otel_enabled)
    await init_database()
    _read_index_manifest()
    app.state.redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    yield
    await app.state.redis.close()
    await close_database()


app = FastAPI(
    title="Health Insurance Pre-Authorisation Desk",
    version=CONTRACT_VERSION,
    lifespan=lifespan,
)
app.add_middleware(CorrelationIdMiddleware)
FastAPIInstrumentor.instrument_app(app)


def _serializable_body(body: Any) -> dict[str, Any]:
    return body if isinstance(body, dict) else {"_raw": str(body)}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    quarantine_id = str(uuid4())
    errors = [
        {
            "field": ".".join(str(part) for part in error["loc"] if part != "body") or "body",
            "code": error["type"],
            "message": error["msg"],
        }
        for error in exc.errors()
    ]
    async for session in get_session():
        await create_quarantine(
            session,
            quarantine_id=quarantine_id,
            correlation_id=request.state.correlation_id,
            client_id=request.headers.get("X-Client-ID"),
            raw_payload=_serializable_body(exc.body),
            errors=errors,
            contract_version=CONTRACT_VERSION,
        )
    QUARANTINED.inc()
    logger.warning("request_quarantined", quarantine_id=quarantine_id, errors=errors)
    payload = QuarantineResponse(
        quarantine_id=quarantine_id,
        contract_version=CONTRACT_VERSION,
        errors=errors,
    )
    return JSONResponse(status_code=422, content=payload.model_dump(mode="json"))


@app.get("/healthz", tags=["operations"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz", tags=["operations"])
async def readyz(request: Request, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
        await request.app.state.redis.ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="dependencies unavailable") from exc
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/v1/index/status", tags=["operations"])
async def index_status() -> dict[str, Any]:
    manifest = _read_index_manifest()
    if manifest is None:
        raise HTTPException(status_code=503, detail="policy index unavailable")
    return manifest


@app.post(
    "/v1/preauth",
    response_model=SubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_preauth(
    payload: PreauthRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> SubmissionResponse:
    client_id = request.headers.get("X-Client-ID") or (request.client.host if request.client else "unknown")
    decision = await consume_token(
        request.app.state.redis,
        client_id,
        settings.rate_limit_capacity,
        settings.rate_limit_refill_per_second,
    )
    if not decision.allowed:
        RATE_LIMITED.inc()
        raise HTTPException(
            status_code=429,
            detail="submission rate limit exceeded",
            headers={"Retry-After": str(decision.retry_after)},
        )
    run_id = str(uuid4())
    correlation_id = request.state.correlation_id
    stored_payload = payload.model_dump(mode="json")
    stored_payload["validation_flags"] = payload.validation_flags
    findings = inspect_request(stored_payload) if settings.guardrails_enabled else []
    if findings:
        stored_payload["guardrail_findings"] = [
            {"field": finding.field, "categories": finding.categories} for finding in findings
        ]
        for finding in findings:
            stored_payload[finding.field] = "[BLOCKED BY INPUT GUARDRAIL]"
            for category in finding.categories:
                GUARDRAIL_HITS.labels(category=category, field=finding.field).inc()
    await create_run(
        session,
        run_id=run_id,
        correlation_id=correlation_id,
        request_payload=stored_payload,
    )
    try:
        await request.app.state.redis.enqueue_job(
            "process_preauth",
            run_id,
            correlation_id,
            _job_id=run_id,
        )
    except Exception as exc:
        await update_run(session, run_id, status="failed", error_message="queue unavailable")
        logger.exception("enqueue_failed", run_id=run_id)
        raise HTTPException(status_code=503, detail="queue unavailable") from exc
    SUBMISSIONS.inc()
    logger.info("request_enqueued", run_id=run_id, validation_flags=payload.validation_flags)
    return SubmissionResponse(run_id=run_id, status="queued", poll_url=f"/v1/runs/{run_id}")


@app.get("/v1/runs/{run_id}", response_model=RunResponse)
async def read_run(run_id: str, session: AsyncSession = Depends(get_session)) -> RunResponse:
    run = await get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return RunResponse(
        run_id=run.id,
        status=run.status,
        correlation_id=run.correlation_id,
        result=run.result,
        prompt_versions=run.prompt_versions or {},
        timings={
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        },
        error=run.error_message,
    )


@app.get("/v1/runs/{run_id}/trace")
async def read_run_trace(run_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    run = await get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    steps = await get_run_steps(session, run_id)
    costs = await get_cost_entries(session, run_id)
    return {
        "run_id": run_id,
        "correlation_id": run.correlation_id,
        "steps": [
            {
                "sequence": step.sequence,
                "agent": step.agent,
                "kind": step.kind,
                "payload": step.payload,
                "created_at": step.created_at.isoformat(),
            }
            for step in steps
        ],
        "costs": [
            {
                "step": item.step_name,
                "provider": item.provider,
                "model": item.model,
                "prompt_tokens": item.prompt_tokens,
                "completion_tokens": item.completion_tokens,
                "notional_cost_usd": item.notional_cost_usd,
            }
            for item in costs
        ],
    }


app.mount("/", StaticFiles(directory="web", html=True), name="web")
