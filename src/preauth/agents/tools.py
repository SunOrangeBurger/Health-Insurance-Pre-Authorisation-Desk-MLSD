import time
from typing import Any

from pydantic import BaseModel, Field

from preauth.agents.models import AgentTraceEvent
from preauth.rag.models import SearchResult
from preauth.rag.retriever import HybridRetriever
from preauth.obs.metrics import AGENT_STEP_LATENCY
from preauth.obs.tracing import span


class SearchCorpusInput(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    provision_type: str | None = None
    top_k: int = Field(default=5, ge=1, le=10)


class GetClauseInput(BaseModel):
    clause_id: str = Field(min_length=1, max_length=64)


class GetRequestFieldsInput(BaseModel):
    keys: list[str] = Field(min_length=1, max_length=20)


class AgentBudgetExceeded(RuntimeError):
    pass


class PolicyTools:
    def __init__(
        self,
        retriever: HybridRetriever,
        request: dict[str, Any],
        *,
        max_tool_calls: int,
        timeout_seconds: float,
        initial_calls: int = 0,
    ) -> None:
        self.retriever = retriever
        self.request = request
        self.max_tool_calls = max_tool_calls
        self.timeout_seconds = timeout_seconds
        self.calls = initial_calls
        self.trace: list[AgentTraceEvent] = []

    def _before(self, name: str, arguments: dict[str, Any]) -> float:
        if self.calls >= self.max_tool_calls:
            raise AgentBudgetExceeded(f"tool-call limit {self.max_tool_calls} reached")
        self.calls += 1
        self.trace.append(AgentTraceEvent(agent="policy-research", kind="tool_call", payload={"tool": name, "arguments": arguments, "call": self.calls}))
        return time.perf_counter()

    def _after(self, name: str, started: float, count: int, result_ids: list[str] | None = None) -> None:
        elapsed = time.perf_counter() - started
        if elapsed > self.timeout_seconds:
            raise TimeoutError(f"{name} exceeded {self.timeout_seconds}s")
        self.trace.append(AgentTraceEvent(agent="policy-research", kind="tool_result", payload={"tool": name, "result_count": count, "result_ids": result_ids or [], "elapsed_ms": round(elapsed * 1000, 3), "trust": "untrusted_policy_data"}))

    def search_corpus(self, arguments: SearchCorpusInput) -> list[SearchResult]:
        started = self._before("search_corpus", arguments.model_dump())
        with span("tool.search_corpus", provision_type=arguments.provision_type, top_k=arguments.top_k):
            results = self.retriever.search(arguments.query, arguments.provision_type, arguments.top_k)
        self._after("search_corpus", started, len(results), [result.chunk_id for result in results])
        AGENT_STEP_LATENCY.labels("policy-research", "search_corpus").observe(time.perf_counter() - started)
        return results

    def get_clause(self, arguments: GetClauseInput) -> list[SearchResult]:
        started = self._before("get_clause", arguments.model_dump())
        with span("tool.get_clause", clause_id=arguments.clause_id):
            results = self.retriever.get_clause(arguments.clause_id)
        self._after("get_clause", started, len(results), [result.chunk_id for result in results])
        return results

    def get_request_fields(self, arguments: GetRequestFieldsInput) -> dict[str, Any]:
        started = self._before("get_request_fields", arguments.model_dump())
        result = {key: self.request.get(key) for key in arguments.keys}
        self._after("get_request_fields", started, len(result))
        return result

    def list_sections(self) -> list[str]:
        started = self._before("list_sections", {})
        result = sorted({chunk.section for chunk in self.retriever.chunks})
        self._after("list_sections", started, len(result))
        return result
