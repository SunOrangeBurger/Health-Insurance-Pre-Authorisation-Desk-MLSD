# Architecture & Design Decisions

This document logs significant technical decisions made throughout the project, including the context, decision, alternatives considered, and rationale.

---

## ADR-001: Multi-Agent Reasoning Layer with LangGraph
- **Status:** Accepted
- **Context:** Need explicit control over agent execution loops, step bounds, tool calls, and structured hand-off between Policy Research and Verifier/Router agents.
- **Decision:** Use LangGraph with typed state transitions (`EvidenceBundle`, `VerificationResult`).
- **Rejected Alternatives:** CrewAI was rejected because it offers less granular control over explicit state passing, loop termination bounds, and determinism. Custom loop functions were rejected because LangGraph provides native graph checkpointing and recovery.

## ADR-002: Async Job Queue via Redis + arq
- **Status:** Accepted
- **Context:** The ingestion API (`POST /v1/preauth`) must accept requests with immediate 202 status and return a `run_id`, offloading long-running multi-agent reasoning to asynchronous workers.
- **Decision:** Use Redis + `arq` (async-native, lightweight Python job queue).
- **Rejected Alternatives:** Celery was rejected due to heavier setup footprint and historical synchronization friction with native `asyncio`. RQ was evaluated but `arq` is fully native to Python `async`/`await`.

## ADR-003: Vector Index with FAISS + Local MiniLM Embeddings
- **Status:** Accepted
- **Context:** Retrieval must run locally without recurring external API embedding costs or network bottlenecks. Need incremental re-embedding by chunk hash.
- **Decision:** `sentence-transformers/all-MiniLM-L6-v2` with FAISS (`IndexIDMap2` or `IndexFlatL2` with metadata mapping) combined with BM25 for hybrid search.
- **Rejected Alternatives:** Paid embedding APIs (OpenAI `text-embedding-3`, Cohere) rejected per Project Rule 10. Heavy vector databases (e.g. Milvus/Weaviate) rejected as over-engineered for a single-policy corpus volume.

## ADR-004: Persistent State Storage with PostgreSQL
- **Status:** Accepted
- **Context:** Need robust storage for runs, step telemetry, quarantine records, feedback, and cost tracking across concurrent workers and API instances.
- **Decision:** PostgreSQL 16 with `asyncpg` and SQLAlchemy async.
- **Rejected Alternatives:** SQLite rejected due to file locking issues with multiple worker containers writing concurrently.
