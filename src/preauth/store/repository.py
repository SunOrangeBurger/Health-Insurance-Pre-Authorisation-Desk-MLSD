from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from preauth.store.models import CostLedger, Feedback, Quarantine, Run, RunStep


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
    prompt_versions: dict[str, str] | None = None,
) -> Run | None:
    run = await get_run(session, run_id)
    if run is None:
        return None
    run.status = status
    run.result = result
    run.error_message = error_message
    if prompt_versions is not None:
        run.prompt_versions = prompt_versions
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


async def add_run_steps(session: AsyncSession, run_id: str, events: list[dict[str, Any]]) -> None:
    for sequence, event in enumerate(events, start=1):
        session.add(
            RunStep(
                run_id=run_id,
                sequence=sequence,
                agent=event["agent"],
                kind=event["kind"],
                payload=event.get("payload", {}),
            )
        )
    await session.commit()


async def get_run_steps(session: AsyncSession, run_id: str) -> list[RunStep]:
    result = await session.scalars(
        select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.sequence)
    )
    return list(result)


async def add_cost_entry(
    session: AsyncSession,
    *,
    run_id: str,
    step_name: str,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    notional_cost_usd: float,
) -> None:
    session.add(
        CostLedger(
            run_id=run_id,
            step_name=step_name,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            notional_cost_usd=notional_cost_usd,
        )
    )
    await session.commit()


async def get_cost_entries(session: AsyncSession, run_id: str) -> list[CostLedger]:
    result = await session.scalars(
        select(CostLedger).where(CostLedger.run_id == run_id).order_by(CostLedger.id)
    )
    return list(result)


async def create_feedback(
    session: AsyncSession,
    *,
    feedback_id: str,
    run_id: str,
    satisfactory: bool,
    reason: str | None,
) -> Feedback:
    item = Feedback(
        id=feedback_id,
        run_id=run_id,
        satisfactory=satisfactory,
        reason=reason,
    )
    session.add(item)
    await session.commit()
    return item
