from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from preauth.api.middleware import CorrelationIdMiddleware
from preauth.api.schemas import (
    CONTRACT_VERSION,
    PreauthRequest,
    QuarantineResponse,
    RunResponse,
    SubmissionResponse,
)
from preauth.config import get_settings
from preauth.obs.logging import configure_logging, get_logger
from preauth.store.database import close_database, get_session, init_database
from preauth.store.repository import create_quarantine, create_run, get_run, update_run

configure_logging()
logger = get_logger(__name__)
settings = get_settings()
SUBMISSIONS = Counter("preauth_submissions_total", "Accepted pre-authorisation submissions")
QUARANTINED = Counter("preauth_quarantine_total", "Rejected pre-authorisation submissions")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_database()
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
    run_id = str(uuid4())
    correlation_id = request.state.correlation_id
    stored_payload = payload.model_dump(mode="json")
    stored_payload["validation_flags"] = payload.validation_flags
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


app.mount("/", StaticFiles(directory="web", html=True), name="web")
