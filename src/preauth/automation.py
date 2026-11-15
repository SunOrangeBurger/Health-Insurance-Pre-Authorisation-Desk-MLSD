"""Precedent reuse is fail-closed until a matching calibration artifact exists."""
import asyncio
import json
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select
from preauth.precedents import choose_precedent, description, eligible, material_facts
from preauth.store.models import Case, CaseEvent, Precedent


async def apply_precedent(session, run_id, request, evidence, embedder):
    artifact = Path("evals/precedent_calibration.json")
    if not artifact.exists() or not eligible(request, evidence):
        return
    try:
        config = json.loads(artifact.read_text())
        threshold = float(config["threshold"])
    except (OSError, ValueError, TypeError, KeyError):
        return
    if config.get("passed") is not True or not 0 <= threshold <= 1 or config.get("embedding_model") != embedder.name:
        return
    case = await session.scalar(select(Case).where(Case.run_id == run_id).with_for_update())
    if case is None or case.status != "processing":
        return
    candidates = list((await session.scalars(select(Precedent).where(
        Precedent.active.is_(True), Precedent.policy_version == case.policy_version
    ).order_by(Precedent.id).with_for_update())).all())
    if not candidates:
        return
    vectors = await asyncio.to_thread(embedder.encode, [description(request)] + [p.description for p in candidates])
    scores = vectors[1:] @ vectors[0]
    match = choose_precedent(material_facts(request, evidence), candidates, scores, threshold)
    expected = {"approve": "approved", "reject": "rejected"}[evidence["ai_assessment"]["recommendation"]]
    if match is None or match.outcome != expected:
        return
    case.status = match.outcome
    case.decision = {"outcome": match.outcome, "source": "precedent", "precedent_id": match.id,
                     "reason": evidence["ai_assessment"]["rationale"], "revision": case.revision}
    session.add(CaseEvent(id=str(uuid4()), case_id=case.id, revision=case.revision,
                          actor="automation", kind="automatic_decision", payload=case.decision))
    # The worker commits the automatic outcome with the terminal run result.
    # A crash cannot publish a final case decision without its assessment.
    await session.flush()
