import re
from datetime import date
from typing import Any

from preauth.agents.models import CoverageResult, EvidenceBundle, VerificationResult


def resolve_citations(bundle: EvidenceBundle) -> tuple[bool, list[str]]:
    available = {passage.chunk_id for passage in bundle.passages}
    missing = [citation_id for citation_id in bundle.claimed_citation_ids if citation_id not in available]
    return not missing, missing


class VerifierRouterAgent:
    prompt_version = "verifier/v1"
    mandatory_searches = {"cover", "waiting_period", "exclusion", "room_rent", "sublimit"}

    def run(self, request: dict[str, Any], bundle: EvidenceBundle, *, allow_retry: bool) -> CoverageResult:
        checks: list[str] = []
        citations_ok, missing = resolve_citations(bundle)
        checks.append("all citations resolve" if citations_ok else f"missing citations: {', '.join(missing)}")
        missing_searches = sorted(self.mandatory_searches - set(bundle.searched_provision_types))
        checks.append("mandatory provision searches completed" if not missing_searches else f"missing provision searches: {', '.join(missing_searches)}")
        if bundle.incomplete:
            checks.append("research incomplete")
        if not bundle.procedure_supported:
            checks.append("procedure not found in condition-specific corpus text")
        retry = None
        if allow_retry and (not citations_ok or missing_searches):
            retry = "Resolve missing citations with direct clause lookup and repeat mandatory searches"
        verified = citations_ok and not missing_searches and not bundle.incomplete and bundle.procedure_supported
        verification = VerificationResult(passed=verified, checks=checks, retry_directive=retry)
        route = "medical-review"
        position = "unverified"
        reason = "Verification did not pass; a medical officer must review the evidence."
        waiting_months = self._waiting_months(bundle)
        tenure_months = self._tenure_months(request)
        prior_conditions = request.get("prior_conditions") or []
        if verified and prior_conditions:
            position = "possible_pre_existing_condition"
            reason = "A possible pre-existing condition requires medical review under the PED provision."
        elif verified and waiting_months is not None and tenure_months < waiting_months:
            position = "waiting_period_not_served"
            reason = f"The {waiting_months}-month specific waiting period has not been served ({tenure_months:.1f} months elapsed)."
        elif verified:
            position = "waiting_period_served"
            route = "approve-recommended"
            reason = "Retrieved provisions are verified and the applicable specific waiting period is served."
        citations = [
            {
                "id": passage.clause_id,
                "chunk_id": passage.chunk_id,
                "doc": passage.doc_id,
                "section": passage.section,
                "page": passage.page,
                "text": passage.text,
            }
            for passage in bundle.passages
            if passage.chunk_id in bundle.claimed_citation_ids
        ]
        return CoverageResult(
            admission_class=bundle.admission_class,
            entities=bundle.entities,
            coverage_position=position,
            indicative_limit={
                "amount": request.get("sum_insured") if verified else None,
                "basis": "Base Sum Insured; no cataract-specific sub-limit found in this corpus" if verified else "Not computed from unverified evidence",
                "caveats": ["Policy Schedule endorsements and pre-existing disease history require human confirmation."],
            },
            route=route,
            route_reason=reason,
            citations=citations,
            verification=verification,
            prompt_versions={"research": PolicyResearchPrompt.version, "verifier": self.prompt_version},
        )

    @staticmethod
    def _waiting_months(bundle: EvidenceBundle) -> int | None:
        for passage in bundle.passages:
            if passage.clause_id == "C.1.b":
                match = re.search(
                    r"specified disease/procedure.*?expiry of\s+(\d{1,2})\s+months",
                    passage.text,
                    re.IGNORECASE | re.DOTALL,
                )
                if not match:
                    match = re.search(r"expiry of\s+(\d{1,2})\s+months", passage.text, re.IGNORECASE)
                if match:
                    return int(match.group(1))
        return None

    @staticmethod
    def _tenure_months(request: dict[str, Any]) -> float:
        start = date.fromisoformat(str(request["policy_start_date"]))
        admission = date.fromisoformat(str(request["planned_admission_date"]))
        return max((admission - start).days / 30.4375, 0)


class PolicyResearchPrompt:
    version = "research/v2"
