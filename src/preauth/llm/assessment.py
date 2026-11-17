import json
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from preauth.api.schemas import LLMRequest


class Assessment(BaseModel):
    case_summary: str = Field(min_length=10, max_length=700, description="Two short factual sentences summarizing the submitted patient, procedure, requested amount and declared circumstances. No policy interpretation or invented facts.")
    recommendation: Literal["approve", "reject", "needs_information"]
    rationale: str = Field(min_length=10, max_length=3000,
                           description="One brief sentence stating the policy reason; at most 60 words, no step-by-step reasoning")
    clause_ids: list[str] = Field(max_length=20)
    exception_flags: list[str] = Field(max_length=20)


async def assess(client, request, evidence):
    started = time.perf_counter()
    prompt = Path("prompts/claims_reviewer_v2.txt").read_text(encoding="utf-8")
    response = await client.complete(LLMRequest(
        messages=[{"role": "system", "content": prompt + "\nRequired output JSON schema:\n" + json.dumps(Assessment.model_json_schema()) + '\nReturn exactly one JSON object, no Markdown or commentary.'},
                  {"role": "user", "content": json.dumps({"request": request, "evidence": evidence})}],
        output_schema=Assessment.model_json_schema(),
    ))
    content = response.content.strip()
    if content.startswith("```") and content.endswith("```"):
        lines = content.splitlines()
        if lines[0] in {"```", "```json"}:
            content = "\n".join(lines[1:-1])
    result = Assessment.model_validate_json(content)
    # Evidence IDs are checked exactly; an invented identifier invalidates the assessment.
    allowed = {str(c.get("id", "")) for c in evidence.get("citations", [])}
    if not result.clause_ids or not set(result.clause_ids).issubset(allowed):
        result.recommendation = "needs_information"
        result.exception_flags.append("missing_or_unverified_citations")
    if not evidence.get("verification", {}).get("passed"):
        result.exception_flags.append("deterministic_verification_failed")
        result.recommendation = "needs_information"
    expected = {"waiting_period_served": "approve", "waiting_period_not_served": "reject"}.get(evidence.get("coverage_position"))
    if expected and result.recommendation != expected:
        result.exception_flags.append("model_policy_conflict")
        result.recommendation = "needs_information"
    if result.exception_flags:
        result.recommendation = "needs_information"
    output = result.model_dump()
    # The request contract denominates all costs in INR; correct generated
    # currency notation without treating the narrative as verified policy evidence.
    output["case_summary"] = output["case_summary"].replace("$", "INR ").replace("USD", "INR")
    # Generated explanations can misstate a clause even when the outcome is
    # correct. Preserve them for audit, but show the verified policy explanation.
    output["model_rationale"] = output["rationale"]
    output["rationale"] = evidence.get("route_reason") or "Policy evidence requires a human review."
    if "model_policy_conflict" in result.exception_flags:
        output["rationale"] += " The model recommendation conflicted with the verified policy position; human review is required."
    return {**output, "prompt_version": "claims-reviewer/v2",
            "model": getattr(getattr(client, "settings", None), "llm_model", "test-double"),
            "inference_seconds": round(time.perf_counter() - started, 4),
            "prompt_tokens": response.prompt_tokens, "completion_tokens": response.completion_tokens}
