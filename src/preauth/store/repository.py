from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from preauth.store.models import Quarantine, Run


async def create_run(
    session: AsyncSession,
    *,
    run_id: str,
    correlation_id: str,
    request_payload: dict[str, Any],
) -> Run:
    run = Run(
        id=run_id,
        status="queued",
        correlation_id=correlation_id,
        request_payload=request_payload,
        prompt_versions={},
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def get_run(session: AsyncSession, run_id: str) -> Run | None:
    return await session.scalar(select(Run).where(Run.id == run_id))


async def update_run(
    session: AsyncSession,
    run_id: str,
    *,
    status: str,
    result: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> Run | None:
    run = await get_run(session, run_id)
    if run is None:
        return None
    run.status = status
    run.result = result
    run.error_message = error_message
    now = datetime.now(timezone.utc)
    if status == "running":
        run.started_at = now
    if status in {"completed", "escalated", "failed", "degraded"}:
        run.completed_at = now
    await session.commit()
    await session.refresh(run)
    return run


async def create_quarantine(
    session: AsyncSession,
    *,
    quarantine_id: str,
    correlation_id: str,
    client_id: str | None,
    raw_payload: dict[str, Any],
    errors: list[dict[str, Any]],
    contract_version: str,
) -> Quarantine:
    record = Quarantine(
        id=quarantine_id,
        correlation_id=correlation_id,
        client_id=client_id,
        raw_payload=raw_payload,
        errors=errors,
        contract_version=contract_version,
    )
    session.add(record)
    await session.commit()
    return record
