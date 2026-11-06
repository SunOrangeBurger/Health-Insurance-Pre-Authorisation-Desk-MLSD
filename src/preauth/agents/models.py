from typing import Any, Literal

from pydantic import BaseModel, Field

from preauth.rag.models import SearchResult


class AgentTraceEvent(BaseModel):
    agent: str
    kind: str
    payload: dict[str, Any]


class EvidenceBundle(BaseModel):
    admission_class: str
    entities: dict[str, Any]
    passages: list[SearchResult] = Field(default_factory=list)
    claimed_citation_ids: list[str] = Field(default_factory=list)
    searched_provision_types: list[str] = Field(default_factory=list)
    procedure_supported: bool = False
    incomplete: bool = False
    tool_calls: int = 0


class VerificationResult(BaseModel):
    passed: bool
    checks: list[str]
    retry_directive: str | None = None


class CoverageResult(BaseModel):
    admission_class: str
    entities: dict[str, Any]
    coverage_position: str
    indicative_limit: dict[str, Any]
    route: Literal["approve-recommended", "query-to-hospital", "medical-review"]
    route_reason: str
    citations: list[dict[str, Any]]
    verification: VerificationResult
    disclaimer: str = "This is a recommendation aid; a medical officer makes the final decision."
    prompt_versions: dict[str, str] = Field(default_factory=dict)
