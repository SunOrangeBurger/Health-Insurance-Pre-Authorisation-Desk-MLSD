import time
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from preauth.agents.models import AgentTraceEvent, CoverageResult, EvidenceBundle
from preauth.agents.researcher import PolicyResearchAgent
from preauth.agents.tools import PolicyTools
from preauth.agents.verifier import VerifierRouterAgent
from preauth.config import Settings
from preauth.rag.embeddings import Embedder
from preauth.rag.retriever import HybridRetriever


class AgentState(TypedDict, total=False):
    request: dict[str, Any]
    admission_class: str
    bundle: EvidenceBundle
    result: CoverageResult
    replan_count: int
    retry_directive: str | None
    trace: list[AgentTraceEvent]
    tool_calls: int
    steps: int
    started_at: float


class PreauthAgentSystem:
    def __init__(self, retriever: HybridRetriever, settings: Settings) -> None:
        self.retriever = retriever
        self.settings = settings
        self.researcher = PolicyResearchAgent()
        self.verifier = VerifierRouterAgent()
        graph = StateGraph(AgentState)
        graph.add_node("classify", self._classify)
        graph.add_node("research", self._research)
        graph.add_node("verify_and_route", self._verify)
        graph.add_edge(START, "classify")
        graph.add_edge("classify", "research")
        graph.add_edge("research", "verify_and_route")
        graph.add_conditional_edges("verify_and_route", self._next, {"retry": "research", "done": END})
        self.graph = graph.compile()

    @classmethod
    def from_index(cls, index_dir: Path, embedder: Embedder, settings: Settings) -> "PreauthAgentSystem":
        return cls(HybridRetriever(index_dir, embedder), settings)

    def _guard(self, state: AgentState) -> None:
        if state.get("steps", 0) >= self.settings.max_steps:
            raise RuntimeError("agent step limit reached")
        if time.perf_counter() - state["started_at"] > self.settings.run_timeout_s:
            raise TimeoutError("agent wall-clock limit reached")

    def _classify(self, state: AgentState) -> dict[str, Any]:
        self._guard(state)
        admission_class = state["request"].get("admission_type", "unknown")
        event = AgentTraceEvent(agent="intake-classifier", kind="classification", payload={"admission_class": admission_class})
        return {"admission_class": admission_class, "steps": state.get("steps", 0) + 1, "trace": state.get("trace", []) + [event]}

    def _research(self, state: AgentState) -> dict[str, Any]:
        self._guard(state)
        tools = PolicyTools(
            self.retriever,
            state["request"],
            max_tool_calls=self.settings.max_tool_calls,
            timeout_seconds=self.settings.tool_timeout_s,
            initial_calls=state.get("tool_calls", 0),
        )
        bundle = self.researcher.run(state["request"], tools, state.get("retry_directive"))
        return {
            "bundle": bundle,
            "tool_calls": tools.calls,
            "steps": state.get("steps", 0) + 1,
            "trace": state.get("trace", []) + tools.trace + [AgentTraceEvent(agent="policy-research", kind="handoff", payload={"passages": len(bundle.passages), "passage_ids": [item.chunk_id for item in bundle.passages], "incomplete": bundle.incomplete, "prompt_version": self.researcher.prompt_version})],
            "retry_directive": None,
        }

    def _verify(self, state: AgentState) -> dict[str, Any]:
        self._guard(state)
        replan_count = state.get("replan_count", 0)
        result = self.verifier.run(state["request"], state["bundle"], allow_retry=replan_count < self.settings.max_replans)
        event = AgentTraceEvent(agent="verifier-router", kind="verification", payload={"passed": result.verification.passed, "route": result.route, "checks": result.verification.checks, "prompt_version": self.verifier.prompt_version})
        retry = result.verification.retry_directive
        return {
            "result": result,
            "steps": state.get("steps", 0) + 1,
            "trace": state.get("trace", []) + [event],
            "retry_directive": retry,
            "replan_count": replan_count + (1 if retry else 0),
        }

    def _next(self, state: AgentState) -> str:
        if state.get("retry_directive") and state.get("replan_count", 0) <= self.settings.max_replans and state.get("tool_calls", 0) < self.settings.max_tool_calls:
            return "retry"
        return "done"

    async def run(self, request: dict[str, Any]) -> tuple[CoverageResult, list[AgentTraceEvent]]:
        initial: AgentState = {
            "request": request,
            "replan_count": 0,
            "trace": [],
            "tool_calls": 0,
            "steps": 0,
            "started_at": time.perf_counter(),
        }
        state = self.graph.invoke(initial, {"recursion_limit": self.settings.max_steps + 2})
        return state["result"], state["trace"]
