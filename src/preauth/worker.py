import asyncio

import structlog.contextvars
from arq import run_worker
from arq.connections import RedisSettings
from prometheus_client import Counter, Histogram, start_http_server

from preauth.config import get_settings
from preauth.obs.logging import configure_logging, get_logger
from preauth.store.database import close_database, init_database, session_factory
from preauth.store.repository import update_run

configure_logging()
logger = get_logger(__name__)
settings = get_settings()
RUNS = Counter("preauth_worker_runs_total", "Worker runs", ["status"])
RUN_TIME = Histogram("preauth_worker_run_seconds", "Placeholder worker run duration")


async def startup(ctx) -> None:
    await init_database()
    start_http_server(settings.worker_metrics_port)
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
            await asyncio.sleep(0.05)
            result = {
                "admission_class": "pending_agent_classification",
                "entities": {},
                "coverage_position": "not_assessed",
                "indicative_limit": {
                    "amount": None,
                    "basis": "Phase 1 walking skeleton only",
                    "caveats": ["Policy research and verification are not implemented yet."],
                },
                "route": "medical-review",
                "route_reason": "Automated policy research is not available in the walking skeleton.",
                "citations": [],
                "verification": {
                    "passed": False,
                    "checks": ["No unverified coverage recommendation returned."],
                },
                "disclaimer": "This is a recommendation aid; a medical officer makes the final decision.",
            }
            await update_run(session, run_id, status="completed", result=result)
            RUNS.labels(status="completed").inc()
            logger.info("run_completed")


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
