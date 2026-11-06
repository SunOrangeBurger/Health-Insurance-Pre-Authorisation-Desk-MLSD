import asyncio
from pathlib import Path

import structlog.contextvars
from arq import run_worker
from arq.connections import RedisSettings
from prometheus_client import Counter, Histogram, start_http_server

from preauth.config import get_settings
from preauth.agents.graph import PreauthAgentSystem
from preauth.rag.embeddings import MiniLMEmbedder
from preauth.obs.logging import configure_logging, get_logger
from preauth.store.database import close_database, init_database, session_factory
from preauth.store.repository import add_run_steps, get_run, update_run

configure_logging()
logger = get_logger(__name__)
settings = get_settings()
RUNS = Counter("preauth_worker_runs_total", "Worker runs", ["status"])
RUN_TIME = Histogram("preauth_worker_run_seconds", "Placeholder worker run duration")


async def startup(ctx) -> None:
    await init_database()
    start_http_server(settings.worker_metrics_port)
    index_dir = Path(settings.index_storage_dir)
    if (index_dir / "index.faiss").exists():
        embedder = MiniLMEmbedder(settings.local_embedding_model)
        ctx["agent_system"] = PreauthAgentSystem.from_index(index_dir, embedder, settings)
        logger.info("agent_system_ready", index_dir=str(index_dir))
    else:
        ctx["agent_system"] = None
        logger.warning("agent_system_unavailable", reason="index missing")
    logger.info("worker_started", metrics_port=settings.worker_metrics_port)


async def shutdown(ctx) -> None:
    await close_database()


async def process_preauth(ctx, run_id: str, correlation_id: str) -> None:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(run_id=run_id, correlation_id=correlation_id)
    with RUN_TIME.time():
        async with session_factory() as session:
            await update_run(session, run_id, status="running")
            logger.info("run_started")
            run = await get_run(session, run_id)
            agent_system = ctx.get("agent_system")
            if run is None or agent_system is None:
                result = {
                    "admission_class": "unavailable",
                    "entities": {},
                    "coverage_position": "not_assessed",
                    "indicative_limit": {"amount": None, "basis": "Index unavailable", "caveats": []},
                    "route": "medical-review",
                    "route_reason": "The policy index is unavailable; automated research was not performed.",
                    "citations": [],
                    "verification": {"passed": False, "checks": ["Policy index unavailable."]},
                    "disclaimer": "This is a recommendation aid; a medical officer makes the final decision.",
                }
                await update_run(session, run_id, status="degraded", result=result)
                RUNS.labels(status="degraded").inc()
                return
            try:
                result_model, trace = await asyncio.wait_for(
                    agent_system.run(run.request_payload), timeout=settings.run_timeout_s
                )
                result = result_model.model_dump(mode="json")
                await add_run_steps(session, run_id, [event.model_dump(mode="json") for event in trace])
                terminal = "escalated" if result_model.route == "medical-review" else "completed"
                await update_run(session, run_id, status=terminal, result=result)
                RUNS.labels(status=terminal).inc()
                logger.info("run_completed", route=result_model.route, verification=result_model.verification.passed)
            except Exception as exc:
                logger.exception("agent_run_failed")
                result = {
                    "admission_class": run.request_payload.get("admission_type", "unknown"),
                    "entities": {},
                    "coverage_position": "degraded",
                    "indicative_limit": {"amount": None, "basis": "Agent failure", "caveats": []},
                    "route": "medical-review",
                    "route_reason": "Automated reasoning failed; a medical officer must review the request.",
                    "citations": [],
                    "verification": {"passed": False, "checks": ["Agent execution failed safely."]},
                    "disclaimer": "This is a recommendation aid; a medical officer makes the final decision.",
                }
                await update_run(session, run_id, status="degraded", result=result, error_message=type(exc).__name__)
                RUNS.labels(status="degraded").inc()


class WorkerSettings:
    functions = [process_preauth]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = settings.worker_concurrency
    job_timeout = 90
    max_tries = 2
    health_check_interval = 10


if __name__ == "__main__":
    run_worker(WorkerSettings)
