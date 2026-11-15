from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from preauth.api.auth import current_user
from preauth.store.database import get_session
from preauth.store.models import CaseEvent, Precedent, User
from preauth.config import get_settings

router = APIRouter(prefix="/v1/precedents", tags=["precedents"])


@router.get("/config")
async def configuration(user: User = Depends(current_user)):
    if user.role != "reviewer":
        raise HTTPException(403, "Claims Reviewer access required")
    return {"automation_enabled": get_settings().precedent_automation_enabled}


@router.get("")
async def list_precedents(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    if user.role != "reviewer":
        raise HTTPException(403, "Claims Reviewer access required")
    rows = (await session.scalars(select(Precedent).order_by(Precedent.id).limit(100))).all()
    return {"items": [{"id": p.id, "case_id": p.case_id, "outcome": p.outcome,
                       "reason": p.reason, "active": p.active, "policy_version": p.policy_version,
                       "conditions": p.facts, "description": p.description} for p in rows]}


@router.post("/{precedent_id}/disable")
async def disable(precedent_id: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    if user.role != "reviewer":
        raise HTTPException(403, "Claims Reviewer access required")
    p = await session.scalar(select(Precedent).where(Precedent.id == precedent_id).with_for_update())
    if not p:
        raise HTTPException(404, "Precedent not found")
    p.active = False
    session.add(CaseEvent(id=str(uuid4()), case_id=p.case_id, revision=p.revision, actor=user.id,
                          kind="precedent_disabled", payload={"precedent_id": p.id}))
    await session.commit()
    return {"id": p.id, "active": False}
