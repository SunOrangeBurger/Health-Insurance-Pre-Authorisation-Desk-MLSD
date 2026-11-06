import re
from typing import Any

from preauth.agents.models import EvidenceBundle
from preauth.agents.tools import (
    AgentBudgetExceeded,
    GetClauseInput,
    GetRequestFieldsInput,
    PolicyTools,
    SearchCorpusInput,
)
from preauth.rag.models import SearchResult

STOPWORDS = {"with", "right", "left", "eye", "synthetic", "procedure", "surgery", "treatment", "and", "the"}


class PolicyResearchAgent:
    prompt_version = "research/v2"

    def run(self, request: dict[str, Any], tools: PolicyTools, replan_directive: str | None = None) -> EvidenceBundle:
        passages: dict[str, SearchResult] = {}
        searched: list[str] = []
        incomplete = False

        def add(results: list[SearchResult]) -> None:
            for result in results:
                passages[result.chunk_id] = result

        try:
            fields = tools.get_request_fields(
                GetRequestFieldsInput(
                    keys=["admission_type", "diagnosis_text", "procedure_text", "prior_conditions", "policy_start_date", "planned_admission_date", "sum_insured", "estimated_cost"]
                )
            )
            query = f"{fields.get('diagnosis_text', '')} {fields.get('procedure_text', '')}".strip()
            add(tools.search_corpus(SearchCorpusInput(query=f"hospitalization day care cover {query}", provision_type="cover", top_k=3)))
            searched.append("cover")
            add(tools.get_clause(GetClauseInput(clause_id="B.1.1")))
            add(tools.search_corpus(SearchCorpusInput(query=query, provision_type="waiting_period", top_k=4)))
            searched.append("waiting_period")
            if "cataract" in query.lower() or replan_directive:
                add(tools.get_clause(GetClauseInput(clause_id="C.1.b")))
            add(tools.search_corpus(SearchCorpusInput(query=f"exclusion {query}", provision_type="exclusion", top_k=2)))
            searched.append("exclusion")
            add(tools.search_corpus(SearchCorpusInput(query="room rent proportionate deduction", provision_type="room_rent", top_k=2)))
            searched.append("room_rent")
            add(tools.search_corpus(SearchCorpusInput(query=f"sub-limit {query}", provision_type="sublimit", top_k=2)))
            searched.append("sublimit")
        except (AgentBudgetExceeded, TimeoutError):
            fields = request
            incomplete = True

        evidence = list(passages.values())
        query_text = f"{request.get('diagnosis_text', '')} {request.get('procedure_text', '')}".lower()
        significant = {
            token
            for token in re.findall(r"[a-z]{4,}", query_text)
            if token not in STOPWORDS
        }
        evidence_text = " ".join(item.text.lower() for item in evidence if item.provision_type in {"waiting_period", "exclusion", "day_care_list"})
        procedure_supported = any(token in evidence_text for token in significant)
        claimed = [item.chunk_id for item in evidence if item.clause_id in {"B.1.1", "C.1.b"}]
        if request.get("_force_bad_citation"):
            claimed.append("fabricated-citation")
        return EvidenceBundle(
            admission_class=request.get("admission_type", "unknown"),
            entities={
                "diagnosis": request.get("diagnosis_text"),
                "procedure": request.get("procedure_text"),
                "prior_conditions": request.get("prior_conditions", []),
            },
            passages=evidence,
            claimed_citation_ids=list(dict.fromkeys(claimed)),
            searched_provision_types=searched,
            procedure_supported=procedure_supported,
            incomplete=incomplete,
            tool_calls=tools.calls,
        )
