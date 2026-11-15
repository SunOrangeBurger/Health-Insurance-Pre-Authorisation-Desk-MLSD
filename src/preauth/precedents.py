"""Conservative factual eligibility gates, independent of model instructions."""
from datetime import date
import hashlib


def material_facts(request, evidence):
    # Exact amounts/ages are intentionally conservative for v1. Semantic similarity
    # applies to diagnosis/procedure wording, never numeric eligibility boundaries.
    keys = ("admission_type", "procedure_code", "patient_age", "patient_gender",
            "room_category_requested", "sum_insured", "estimated_cost")
    facts = {key: request.get(key) for key in keys}
    facts["prior_conditions"] = sorted(str(x).strip().lower() for x in request.get("prior_conditions", []))
    facts["policy_age_days"] = (date.fromisoformat(request["planned_admission_date"]) - date.fromisoformat(request["policy_start_date"])).days
    facts["coverage_position"] = evidence.get("coverage_position")
    facts["clauses"] = sorted(str(c["id"]) for c in evidence.get("citations", []) if c.get("id"))
    facts["evidence_digest"] = hashlib.sha256("\n".join(sorted(str(c.get("text", "")) for c in evidence.get("citations", []))).encode()).hexdigest()
    return facts


def eligible(request, evidence):
    assessment = evidence.get("ai_assessment", {})
    return bool(
        evidence.get("verification", {}).get("passed")
        and evidence.get("citations")
        and assessment.get("recommendation") in {"approve", "reject"}
        and not assessment.get("exception_flags")
        and not request.get("guardrail_findings")
        and not request.get("validation_flags")
        and request.get("procedure_code")
        and request.get("admission_type") != "emergency"
        and not request.get("prior_conditions")
        and request.get("room_category_requested") != "deluxe"
        and evidence.get("coverage_position") in {"waiting_period_served", "waiting_period_not_served"}
        and not (request.get("notes") or "").strip()
    )


def description(request):
    return f"Diagnosis: {request.get('diagnosis_text', '')}. Procedure: {request.get('procedure_text', '')}"


def choose_precedent(facts, candidates, scores, threshold):
    matches = [p for p, score in zip(candidates, scores) if p.active and p.facts == facts and score >= threshold]
    if not matches or len({p.outcome for p in matches}) != 1:
        return None
    return matches[0]
