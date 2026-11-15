from typing import Literal
from uuid import uuid4
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, case as sql_case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from preauth.api.auth import current_user, hospital_user
from preauth.api.schemas import PreauthRequest
from preauth.store.database import get_session
from preauth.store.models import Case, CaseEvent, Run, RunOwner, User, Precedent, SubmissionKey
from preauth.api.rate_limit import consume_token
from preauth.precedents import eligible, material_facts, description
from preauth.guardrails.detectors import inspect_request
from preauth.obs.metrics import SUBMISSIONS

router = APIRouter(prefix="/v1/cases", tags=["cases"])


class CaseSubmission(BaseModel):
    request: PreauthRequest
    policy_version: str = Field(default="optima-secure-v1", min_length=1, max_length=128)


class ReviewDecision(BaseModel):
    revision: int = Field(ge=1)
    outcome: Literal["approved", "rejected", "information_requested"]
    reason: str = Field(min_length=10, max_length=3000)
    reusable: bool = False


async def find_case(case_id, user, session, lock=False):
    query = select(Case).where(Case.id == case_id)
    if lock:
        query = query.with_for_update()
    case = await session.scalar(query)
    if case is None or (user.role != "reviewer" and case.hospital_id != user.hospital_id):
        raise HTTPException(404, "Case not found")
    return case


def case_status(case, run):
    if case.status == "processing" and run and run.status in {"completed", "escalated", "degraded", "failed"}:
        return "awaiting_review"
    return case.status


async def detail(case, session):
    run = await session.get(Run, case.run_id)
    return {"id": case.id, "revision": case.revision, "status": case_status(case, run),
            "hospital_id": case.hospital_id, "policy_version": case.policy_version,
            "created_at": case.created_at, "decision": case.decision,
            "request": run.request_payload if run else None,
            "recommendation": run.result if run else None, "run_id": case.run_id,
            "reusable_eligible": bool(run and run.result and eligible(run.request_payload, run.result)),
            "processing_status": run.status if run else "unavailable"}


@router.post("", status_code=202)
async def submit(payload: CaseSubmission, request: Request, user: User = Depends(hospital_user), session: AsyncSession = Depends(get_session)):
    if payload.policy_version != "optima-secure-v1":
        raise HTTPException(422, "Unsupported policy version")
    request_key = payload.request.request_id
    key = hashlib.sha256(f"{user.hospital_id}:{request_key}".encode()).hexdigest() if request_key else None
    normalized = payload.model_dump(mode="json")
    normalized["request"]["hospital_id"] = user.hospital_id
    digest = hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()
    if key:
        previous = await session.get(SubmissionKey, key)
        if previous:
            if previous.digest != digest:
                raise HTTPException(409, "Request ID already used with different details")
            return await detail(await find_case(previous.case_id, user, session), session)
    limit = await consume_token(request.app.state.redis, "case:" + user.id, 10, 1)
    if not limit.allowed:
        raise HTTPException(429, "Submission rate exceeded", headers={"Retry-After": str(limit.retry_after)})
    run = make_run(payload, request, user, session)
    case = Case(id=str(uuid4()), hospital_id=user.hospital_id, run_id=run.id,
                revision=1, status="processing", policy_version=payload.policy_version)
    session.add(case)
    if key:
        session.add(SubmissionKey(id=key, case_id=case.id, digest=digest))
    session.add(CaseEvent(id=str(uuid4()), case_id=case.id, revision=1, actor=user.id,
                          kind="submitted", payload={"run_id": run.id}))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        previous = await session.get(SubmissionKey, key) if key else None
        if previous and previous.digest == digest:
            return await detail(await find_case(previous.case_id, user, session), session)
        raise HTTPException(409, "Duplicate request")
    await enqueue(run, request, session)
    SUBMISSIONS.inc()
    return await detail(case, session)


def make_run(payload, request, user, session):
    data = payload.request.model_dump(mode="json")
    data["hospital_id"] = user.hospital_id
    data["validation_flags"] = payload.request.validation_flags
    findings = inspect_request(data)
    if findings:
        data["guardrail_findings"] = [{"field": f.field, "categories": f.categories} for f in findings]
        for finding in findings:
            data[finding.field] = "[BLOCKED BY INPUT GUARDRAIL]"
    run = Run(id=str(uuid4()), status="queued", correlation_id=getattr(request.state, "correlation_id", str(uuid4())), request_payload=data, prompt_versions={})
    session.add(run)
    session.add(RunOwner(run_id=run.id, hospital_id=user.hospital_id, user_id=user.id))
    return run


async def enqueue(run, request, session):
    try:
        await request.app.state.redis.enqueue_job("process_preauth", run.id, run.correlation_id, _job_id=run.id)
    except Exception:
        run.status = "failed"
        run.error_message = "queue unavailable"
        await session.commit()
        # Keep the case visible to the hospital and reviewer instead of losing it.


@router.post("/{case_id}/resubmit", status_code=202)
async def resubmit(case_id: str, payload: CaseSubmission, request: Request, revision: int = Query(..., ge=1), user: User = Depends(hospital_user), session: AsyncSession = Depends(get_session)):
    case = await find_case(case_id, user, session, lock=True)
    if case.revision != revision or case.status != "information_requested":
        raise HTTPException(409, "Case changed or does not require information")
    if payload.policy_version != case.policy_version:
        raise HTTPException(422, "Policy version cannot change on resubmission")
    run = make_run(payload, request, user, session)
    case.revision += 1
    case.run_id = run.id
    case.status = "processing"
    case.decision = None
    session.add(CaseEvent(id=str(uuid4()), case_id=case.id, revision=case.revision,
                          actor=user.id, kind="resubmitted", payload={"run_id": run.id}))
    await session.commit()
    await enqueue(run, request, session)
    SUBMISSIONS.inc()
    return await detail(case, session)


@router.get("")
async def list_cases(user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
                     offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100),
                     status: Literal["processing", "awaiting_review", "information_requested", "approved", "rejected"] | None = None):
    effective_status = sql_case(
        ((Case.status == "processing") & Run.status.in_(["completed", "escalated", "degraded", "failed"]), "awaiting_review"),
        else_=Case.status,
    )
    query = select(Case).join(Run, Run.id == Case.run_id).order_by(Case.created_at.desc(), Case.id)
    if user.role != "reviewer":
        query = query.where(Case.hospital_id == user.hospital_id)
    if status:
        query = query.where(effective_status == status)
    cases = (await session.scalars(query.offset(offset).limit(limit))).all()
    return {"items": [await detail(case, session) for case in cases], "offset": offset, "limit": limit}


@router.get("/{case_id}")
async def get_case(case_id: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    case = await find_case(case_id, user, session)
    result = await detail(case, session)
    events = (await session.scalars(select(CaseEvent).where(CaseEvent.case_id == case_id).order_by(CaseEvent.created_at))).all()
    result["history"] = [{"kind": e.kind, "revision": e.revision, "payload": e.payload, "created_at": e.created_at} for e in events]
    for event in result["history"]:
        previous_run_id = event["payload"].get("run_id")
        if previous_run_id:
            previous_run = await session.get(Run, previous_run_id)
            event["request"] = previous_run.request_payload if previous_run else None
    return result


@router.post("/{case_id}/decision")
async def decide(case_id: str, payload: ReviewDecision, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    if user.role != "reviewer":
        raise HTTPException(403, "Claims Reviewer access required")
    case = await find_case(case_id, user, session, lock=True)
    run = await session.get(Run, case.run_id)
    if case.revision != payload.revision or case_status(case, run) != "awaiting_review":
        raise HTTPException(409, "Case changed or is not awaiting review")
    if payload.reusable:
        evidence = run.result or {}
        expected = {"approve": "approved", "reject": "rejected"}.get(evidence.get("ai_assessment", {}).get("recommendation"))
        if not eligible(run.request_payload, evidence) or payload.outcome != expected:
            raise HTTPException(409, "This decision has exceptions or conflicts and must remain one-off")
        session.add(Precedent(id=str(uuid4()), case_id=case.id, revision=case.revision,
                              policy_version=case.policy_version, outcome=payload.outcome,
                              reason=payload.reason, facts=material_facts(run.request_payload, evidence),
                              description=description(run.request_payload), active=True))
    case.status = payload.outcome
    case.decision = {**payload.model_dump(), "source": "human", "reviewer_id": user.id}
    session.add(CaseEvent(id=str(uuid4()), case_id=case.id, revision=case.revision,
                          actor=user.id, kind="reviewed", payload=case.decision))
    await session.commit()
    return await detail(case, session)


@router.post("/{case_id}/override")
async def override(case_id: str, payload: ReviewDecision, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    if user.role != "reviewer":
        raise HTTPException(403, "Claims Reviewer access required")
    case = await find_case(case_id, user, session, lock=True)
    if case.revision != payload.revision or not case.decision or case.decision.get("source") != "precedent":
        raise HTTPException(409, "Only a current automatic decision can be overridden")
    if payload.reusable or payload.outcome == "information_requested":
        raise HTTPException(422, "An override is a final one-off decision")
    old = dict(case.decision)
    precedent = await session.scalar(select(Precedent).where(Precedent.id == old['precedent_id']).with_for_update())
    if precedent:
        precedent.active = False
    case.status = payload.outcome
    case.decision = {**payload.model_dump(), "source": "human", "reviewer_id": user.id, "overrides": old}
    session.add(CaseEvent(id=str(uuid4()), case_id=case.id, revision=case.revision, actor=user.id,
                          kind="automatic_decision_overridden", payload={"previous": old, "decision": case.decision}))
    await session.commit()
    return await detail(case, session)
