from prometheus_client import Counter, Gauge, Histogram


AGENT_RUNS = Counter("agent_runs_total", "Agent runs", ["outcome", "route"])
AGENT_STEPS = Histogram("agent_steps", "Graph steps per run", buckets=(1, 2, 3, 5, 8, 12, 20))
AGENT_TOOL_CALLS = Histogram("agent_tool_calls", "Tool calls per run", buckets=(1, 2, 4, 6, 8, 10, 12))
AGENT_STEP_LATENCY = Histogram("agent_step_seconds", "Agent step latency", ["agent", "kind"])
AGENT_REPLANS = Counter("agent_replans_total", "Verifier requested replans")
RATE_LIMITED = Counter("preauth_rate_limited_total", "Submissions rejected by client rate limit")
GUARDRAIL_HITS = Counter("guardrail_findings_total", "Guardrail findings", ["category", "field"])
WORKER_UP = Gauge("preauth_worker_up", "Worker process is running")
COST_USD = Counter("llm_notional_cost_usd_total", "Configured notional LLM cost", ["provider", "step"])

