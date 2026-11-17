# Health Insurance Pre-Authorisation Desk

Technical design, implementation and measured evaluation

Version 1.0 | 17 November 2026 | Synthetic internal-tool demonstration

## 1. Executive technical summary

Policy Desk is an internal workspace connecting hospital accounts staff with an insurer's claims reviewer. Hospital Staff submit structured pre-authorisation cases. A local processing service retrieves policy evidence, verifies applicable conditions and asks a local Ollama model for a schema-constrained recommendation. Claims Reviewers make the initial final decision. A reviewer may explicitly authorize reuse of an eligible decision; later materially equivalent cases may then receive an automatic response grounded in that human precedent.

The project combines a browser frontend, authenticated FastAPI APIs, PostgreSQL state, Redis/ARQ job processing, a bounded LangGraph research/verification graph, hybrid retrieval and an Ollama assessment adapter. Prometheus, Grafana and Jaeger provide operational visibility. The active Windows deployment runs Docker Engine in Ubuntu WSL rather than Docker Desktop. The model server runs on the Windows host and is reached from the containers through the WSL gateway.

The model is Qwen3 4B in Q4_K_M quantization. It runs with thinking disabled, a 4096-token context, a 512-token output cap, one loaded model and one global inference slot. The runner's host prompt cache is disabled because diverse prompts otherwise caused substantial RAM growth. The local recommendation is one worker: adding three workers did not improve measured throughput and produced a degraded assessment under the shared model budget.

The November 17 real-model evaluation completed two-, four-, eight- and sixteen-user stages, recovery, a matched worker comparison and a five-minute mixed stability run. Eight users passed the declared latency targets at approximately 0.310 assessments/second. Sixteen users exceeded the p95 target. The short stability run completed 56 assessments without errors or missing observations, including 34 precedent approvals and 20 exceptional cases returned to human review. Seventy-six targeted regression checks passed for the base handover. The reviewer-summary/v2 extension subsequently passed 77 regression checks and real-model/browser acceptance; frontend convenience additions also received deployed browser checks.

Completion means the revised synthetic demonstration scope is implemented and checked. It does not establish production, clinical, legal or insurer-operational readiness. A five-minute stability run is not long-duration reliability evidence. The semantic evaluation is tiny, model prose remains imperfect and the three-worker error target failed. This document describes those limits as part of the engineering result.

### Reading guide and evidence hierarchy

Current source code and retained machine-readable acceptance artifacts take precedence over older target-design documents. Earlier reports describe a Linux/Podman and stub-provider phase; their statements do not automatically describe the current Windows desk. Source references in square brackets refer to the repository reference register in Chapter 20. Measurements are attributed to specific real-model runs rather than combined with stub results. All dates in this document use the project date, 17 November 2026, unless explicitly historical.

## 2. Product scope and actors

### Operational problem

A hospital accounts worker needs to ask whether an intended admission or procedure can proceed under a patient's insurance policy. An insurer reviewer needs a structured request, the applicable policy evidence and a clear explanation of the recommendation. Without a common workspace, requests, clarification and decisions can become disconnected from the policy provisions that justified them. The project therefore emphasizes a traceable request-to-decision workflow rather than a patient-facing insurance marketplace.

| Actor | Permitted work | Important boundary |
| Hospital Staff | Create cases, view their hospital's cases, inspect reasons/history, respond to clarification | Hospital identity comes from the authenticated session |
| Claims Reviewer | Read insurer-side cases, approve/reject/request information, authorize reuse, disable precedents, override automatic decisions | Current demonstration has one insurer; it is not a general multi-insurer tenant model |
| Processing worker | Retrieve and verify evidence, obtain recommendations, evaluate precedent reuse | Cannot create a human authorization or learn a new precedent from an automatic outcome |
| Operator | Start services, seed synthetic accounts, inspect telemetry, run tests, preserve evidence | Resource guards and local hardware capacity constrain the deployment |

### Included behavior

The frontend includes sign-in, role-specific dashboards, case filtering, a structured request form, case detail/history, review actions and reusable-decision management. The hospital can revise a case after a request for information. The reviewer can make a one-off decision or permit reuse when the case is eligible. Automatic decisions remain distinguishable from human decisions, and an override disables the originating precedent for future use.

Two convenience features support demonstrations. The sign-in page offers Hospital Staff and Claims Reviewer (Insurer) buttons using the public synthetic account credentials through the normal login endpoint. The hospital form offers Fill sample claim, which supplies valid synthetic cataract data and dates relative to today. Autofill does not submit; the user reviews the fields and submits explicitly. The policy-number field supplies a valid example and browser-side format validation. [R1, R2, R3]

### Explicit exclusions

This iteration has no public registration, document-upload workflow, payment settlement, real insurer integration, clinical records integration, production identity provider or real patient processing. It does not implement full policy administration, fraud adjudication or every possible procedure. The supported corpus is a single configured policy version. Broader enterprise controls and long-duration reliability remain future work, not implied capabilities.

## 3. System architecture and deployment boundaries

[[architecture]]

### Request and processing planes

The browser is a static HTML/CSS/JavaScript application served by FastAPI. It calls same-origin JSON APIs and uses an HttpOnly session cookie plus a CSRF token for mutations. There is no separate frontend development server required in the deployed profile. FastAPI performs authentication, role/ownership enforcement, validation, case persistence and job admission. A successful submission returns promptly while the worker performs the expensive processing asynchronously.

Redis provides the ARQ queue, rate-limit state and distributed locks. PostgreSQL holds durable business and audit records. Workers load the local policy index and execute the research/verification graph. Ollama is a separately bounded model-serving process. This separation lets the API remain responsive while GPU inference is serialized. It also makes the bottleneck explicit: increasing worker count does not increase the number of simultaneous model inferences.

| Component | Implementation | Persistent or operational role |
| Browser UI | Static HTML, modular JavaScript, CSS | User interaction and polling; server enforces permissions |
| API | FastAPI, Uvicorn, Pydantic | Validation, sessions, cases, review endpoints and readiness |
| Worker | ARQ and LangGraph | Research, verification, assessment and guarded automation |
| Database | PostgreSQL 16, SQLAlchemy async, asyncpg | Cases, runs, revisions, decisions, ownership and audit state |
| Queue/control | Redis 7 and ARQ | Queued/running job accounting, locks and rate limits |
| Retrieval | MiniLM, FAISS, BM25 | Dense/sparse clause discovery and exact clause lookup |
| Model | Windows Ollama, Qwen3 4B | Structured advisory recommendation |
| Telemetry | Prometheus, Grafana, Jaeger | Metrics, dashboards and distributed traces |

### Current runtime versus original project

The original project ran on Linux with Podman-compatible Compose commands. On Windows, Docker Desktop repeatedly failed around stale local Unix-socket paths. The working replacement is standalone Docker Engine inside the existing Ubuntu 24.04 WSL distribution. Compose configuration remains the deployment contract; the PowerShell wrapper translates the repository path and discovers the current WSL gateway. This avoids hard-coding a Windows user path or assuming the gateway remains unchanged after a restart. [R4, R5]

Eight long-running project containers were captured in final deployment evidence: API, worker, PostgreSQL, Redis, Prometheus, Grafana, Jaeger and Redis exporter. The indexer is a one-shot service, not an always-running application component. Ollama is a host process rather than a ninth container. The API, worker, database and Redis expose health checks; the monitoring services have additional live acceptance evidence rather than all exposing Docker health labels. [E1]

## 4. End-to-end case lifecycle

[[workflow]]

### Submission and assessment

The hospital worker signs in and opens New request. The form collects policy, patient, admission, diagnosis, procedure, financial and exception information. The server derives hospital ownership from the session rather than trusting a hospital identifier supplied by the browser. A case is created with revision 1, a linked processing run and a submitted event. The asynchronous job operates on that run's request payload. The UI polls until the effective business state changes from processing.

Processing state and business state are separate. A run may be queued, running, completed, escalated, degraded or failed. A case can be processing, awaiting_review, information_requested, approved or rejected. When a stored case is still processing but its run has reached a terminal state, the API presents awaiting_review unless an automatic decision already changed the case. Consequently, a degraded model response remains visible and actionable instead of disappearing from the review inbox.

| Trigger | Business result | Audit consequence |
| Initial submission | processing | New run and submitted event |
| Terminal run without automatic decision | awaiting_review, computed by API | Evidence and processing outcome retained |
| Reviewer asks for clarification | information_requested | Human reason and revision recorded |
| Hospital resubmits current revision | processing, revision incremented | New run; old revision reachable through history |
| Human approves or rejects | approved or rejected | Human source, reviewer and reason recorded |
| Eligible human precedent matches | approved or rejected | Precedent source and identifier recorded |
| Reviewer overrides automatic result | Human final outcome | Source precedent disabled; prior decision retained in event |

### Revision and concurrency rules

Review and resubmission operations require the current revision. The server locks the relevant case row and rejects stale or duplicate actions with 409. A resubmission is allowed only when information is requested, and its policy version cannot change. It creates a new immutable processing run rather than replacing the old request payload. A repeated initial request with the same request ID and same normalized data returns the existing case; changing the data under the same key is a conflict.

History is an application-maintained audit sequence, not a cryptographically tamper-evident ledger. Case rows represent the current revision, while historical events point to previous runs. The persisted evidence supports diagnosis and reviewer accountability, but enterprise retention, archival and audit-signing controls are outside this demonstration. [R2, R6]

## 5. Request contract and frontend validation

### Structured input

| Field | Type / validation | Purpose |
| policy_number | 6-32 uppercase letters, digits or hyphens; first character alphanumeric | Synthetic policy reference |
| policy_issue_date | Date; not in the future | Initial policy issuance |
| policy_start_date | Date; on/after issue date | Waiting-period tenure reference |
| sum_insured | Integer INR 100,000-10,000,000; multiple of 1,000 | Coverage context |
| patient_age | Integer 0-100 | Material eligibility fact |
| patient_gender | F, M or O | Structured demographic fact |
| admission_type | planned_surgical, day_care, emergency or maternity | Research and validation route |
| planned_admission_date | Date subject to admission-specific rules | Intended or emergency admission date |
| diagnosis_text | Trimmed text, 3-500 characters | Clinical description for retrieval |
| procedure_text | Trimmed text, 3-300 characters | Procedure description for retrieval/similarity |
| procedure_code | Optional 2-20 letters, digits, dots or hyphens | Required for precedent eligibility |
| room_category_requested | general, shared, single or deluxe | Room entitlement context |
| estimated_cost | Positive number, maximum INR 5,000,000 | Indicative financial context |
| prior_conditions | Up to 20 entries; each 3-100 characters | Declared prior conditions |
| notes | Optional trimmed text, maximum 1,000 characters | Mitigating or exceptional circumstances |
| hospital_id | SYN-HOSP- prefix format; normalized by server | Ownership is ultimately session-derived |
| request_id | Optional 8-64 letters, digits or hyphens | Submission idempotency |

The case envelope adds policy_version, currently restricted to optima-secure-v1. Extra request fields are forbidden. Non-emergency admission dates cannot be in the past. Emergency dates cannot be more than one day old. Admission cannot precede policy start. Maternity requests reject incompatible male gender and ages below 12. An estimated cost above 150% of sum insured creates a validation flag; that flag blocks precedent eligibility rather than silently changing the requested amount. [R7]

### Valid example and reported error

The user's observed policy-number error came from the server pattern ^[A-Z0-9][A-Z0-9-]{5,31}$. A value such as SYN-POL-0001 satisfies it; lowercase letters, spaces and short identifiers do not. Browser validation now uses an equivalent expression compatible with modern HTML pattern parsing. Server validation remains authoritative even if client-side checks are bypassed.

Fill sample claim supplies a 44-year-old female patient, day-care cataract surgery, INR 500,000 sum insured, INR 75,000 estimated cost, single room, no prior conditions and no exception notes. Policy dates are 900 days before today and admission is seven days ahead. A fresh request ID is generated when the sample is filled. This creates an eligible demonstration candidate, not a guaranteed final approval: current evidence, the model recommendation and the presence of a human-authorized precedent still govern the result. [E2]

## 6. API reference and response semantics

### Authentication and case endpoints

| Method / path | Role and input | Result / notable errors |
| POST /v1/auth/login | Public login with email/password and X-Requested-With: desk | Session cookie, public user and CSRF token; 401 invalid credentials, 429 rate limit |
| GET /v1/auth/me | Authenticated cookie | Current public user and CSRF token |
| POST /v1/auth/logout | Authenticated, CSRF | 204; session revoked and cookie deleted |
| POST /v1/cases | Hospital Staff; request and policy_version | 202 case; retry returns existing case or 409 conflict |
| GET /v1/cases | Authenticated; offset, limit, optional status | Paginated cases scoped to hospital or reviewer |
| GET /v1/cases/{id} | Authenticated and authorized | Current case plus revision/event history |
| POST /v1/cases/{id}/resubmit | Hospital Staff; revision query and request | 202 new revision; 409 stale/invalid state |
| POST /v1/cases/{id}/decision | Reviewer; revision, outcome, reason, reusable | Human decision; 409 stale/ineligible reusable outcome |
| POST /v1/cases/{id}/override | Reviewer; current automatic case, one-off final outcome | Human override and source-precedent disable |

Case lists use offset 0 and limit 25 by default; limit is constrained to 1-100. Supported status filters match the business states. Case detail includes ID, revision, effective status, hospital, policy version, current request, linked run, recommendation, decision, processing status and reusable eligibility. History is added on the detail endpoint. A 404 for an unauthorized hospital read deliberately avoids disclosing whether another hospital's identifier exists.

### Precedents, legacy runs and operations

| Method / path | Purpose | Boundary |
| GET /v1/precedents/config | Report whether automation is enabled | Reviewer only |
| GET /v1/precedents | List reusable decisions and active status | Reviewer only; current implementation limits listing to 100 |
| POST /v1/precedents/{id}/disable | Disable future reuse, retain history | Reviewer plus CSRF |
| POST /v1/preauth | Legacy structured run submission | Authentication/ownership added; queue failure returns 503 |
| GET /v1/runs/{id} | Run result, timings and error | Ownership checked |
| GET /v1/runs/{id}/trace | Persisted steps and cost/token ledger | Ownership checked |
| GET /healthz, /readyz | Liveness and dependency readiness | Operational checks |

### Failure interpretation

A desk case can be accepted into the business workflow even when the processing queue is full or unavailable. It then has a failed assessment, explicit medical-review routing and no reusable eligibility. This preserves the user's request for human handling. It must not be counted as a successful machine assessment. The legacy run submission endpoint reports queue failure as 503. This difference is intentional: case persistence and successful model processing are different success criteria.

The frontend sends JSON with X-Requested-With and X-CSRF-Token. A login returns the CSRF token while the session token stays in the HttpOnly cookie. Example bodies use enum names exactly as defined; UI labels convert underscores to spaces for readability. API contracts and source should be consulted when extending the client, since this PDF is a versioned snapshot rather than a replacement for the generated OpenAPI schema. [R1, R2, R8]

## 7. Persistence, migrations and consistency

### Logical data model

| Table | Main responsibility | Important fields / relationship |
| runs | Immutable processing input with mutable run lifecycle/result | id, status, request_payload, result, prompt_versions, timestamps |
| run_steps | Ordered agent/tool trace | run_id, sequence, agent, kind, payload |
| cost_ledger | Provider/model usage accounting | run_id, step, tokens, model, notional cost |
| quarantine / feedback | Legacy contract rejection and run feedback | Correlation, raw validation evidence / feedback actor context |
| desk_users | Seeded accounts and role | email, scrypt password_hash, role, hospital_id, active |
| desk_sessions | Revocable server sessions | Hashed token primary key, user_id, CSRF token, expiry |
| desk_run_owners | Authorization mapping | run_id primary key, hospital_id, user_id |
| desk_cases | Current business revision | Current unique run_id, revision, status, policy_version, decision |
| desk_case_events | Revision and action history | case_id, revision, actor, kind, payload, created_at |
| desk_precedents | Human-authorized reusable result | case/revision, facts, description, policy_version, outcome, active |
| desk_submission_keys | Retry identity and payload integrity | Hashed hospital/request key, case_id, normalized payload digest |

Relationships are represented by indexed identifiers and ORM/application logic. The present models do not declare a comprehensive database foreign-key graph. That distinction matters for future migrations: application checks and transaction boundaries must not be mistaken for complete referential-integrity enforcement by PostgreSQL.

### Schema evolution

Startup runs additive versioned migrations. A desk_schema_versions table records applied versions. Version 1 introduces legacy processing tables; version 2 adds users, sessions and ownership; version 3 adds cases/events; version 4 adds precedents; version 5 adds submission keys. PostgreSQL advisory transaction locking serializes migration startup across API and worker processes. Existing unowned legacy runs are not automatically granted to hospital users. Tests run migration repeatedly to check idempotence. This is a small explicit migration system, not a claim of full Alembic downgrade support. [R6]

### Consistency guarantees and limits

Case decisions use row locks plus revision checks. Submission keys include hospital identity and request ID, with a digest of normalized content to distinguish retries from conflicting changes. A duplicate-key race is handled by rolling back and reading the existing key. Automatic case finalization and the terminal run result are committed together so the UI cannot observe an automatic final decision without its associated assessment.

Database commit and Redis enqueue are separate operations. Queue failures are caught and made visible, but there is no transactional outbox providing exactly-once cross-system delivery. An abrupt process loss between database commit and enqueue is a remaining reliability gap. Durable reconciliation/outbox processing belongs in a production extension. Audit events preserve application history but are not immutable against direct database administration.

## 8. Authentication, authorization and security controls

### Password and session handling

Passwords are hashed with scrypt using a random 16-byte hexadecimal salt, n=16384, r=8 and p=1. Verification uses constant-time comparison. A dummy hash is used when a user is missing so the login path still performs password-hashing work. Session tokens are generated with 32 bytes of URL-safe randomness and stored only as SHA-256 hashes in the database. Each session has a separately generated CSRF token and an eight-hour lifetime.

The desk_session cookie is HttpOnly, SameSite=Strict, path=/ and has an eight-hour max age. Secure is enabled when environment is production. Login replaces a prior session supplied by the same browser, and logout deletes the server-side session before clearing the cookie. Expired sessions and inactive accounts fail authentication. Login rate limiting uses a shared client-host key with capacity five and refill 0.1/second. [R1, R9]

### Permission enforcement

Hospital identity is attached to the authenticated user and used in case/run ownership checks. The frontend hides irrelevant controls, but server dependencies enforce hospital versus reviewer permissions independently. Non-safe authenticated methods compare the submitted CSRF token to the session token. Login requires a custom same-origin request header; permissive CORS is not installed. A reviewer can view the single insurer's cases, while each hospital can access only its own cases.

| Threat | Implemented mitigation | Remaining consideration |
| Forged hospital ID | Server normalizes identity from session | General insurer tenancy is not implemented |
| Stolen database session values | Only token hashes are stored | Browser/device compromise remains outside this control |
| Cross-site mutation | SameSite cookie, CSRF check, custom header | Production origin/TLS policy still needs deployment hardening |
| Stale concurrent decision | Row lock and revision conflict | Administrative database changes can bypass application rules |
| Prompt injection | Input detector, untrusted-data framing and executable reuse gates | Heuristic detection is not exhaustive |
| Reuse feedback loop | Only human decisions create precedents | Reviewer mistakes can still authorize a bad precedent |
| Demo credential exposure | Explicit public synthetic accounts | Remove shortcuts and rotate accounts before any non-demo use |

Public demo shortcuts are intentionally convenience wrappers around ordinary authentication; they do not create an unauthenticated role-switch endpoint. The static asset includes the published sample passwords. Production deployment must replace that convenience with appropriate account provisioning and identity controls. This is an implementation boundary, not a claim that publishing demo credentials is suitable for private business data.

## 9. Policy ingestion and hybrid retrieval

### Corpus identity

The configured corpus is HDFC ERGO my: Optima Secure, UIN HDFHLIP26058V082526, represented by a 69-page text-layer PDF in the repository manifest. The recorded SHA-256 is 195eb0499db969c6789472e7f87ef1c72da110e2a8c7761ecb5add378fe964c1. These identifiers describe the project's frozen input, not a statement about the insurer's current offerings. The restored deployed index contains 109 chunks. Raw policy text is not reproduced in full in this document. [R10]

Ingestion extracts and chunks policy wording, tracks document/chunk hashes, embeds with local all-MiniLM-L6-v2 and publishes index artifacts. Stable hashes support reuse of unchanged embeddings. The index includes FAISS data, chunk metadata and a manifest identifying the index version. Workers load a published index rather than indexing user requests. An unavailable index prevents a confident automated recommendation and is represented as degraded human review.

### Search algorithm

HybridRetriever combines dense vector search and BM25 lexical rankings. Candidates are filtered by provision type when specified. Dense fetch depth is max(6 x top_k, 20), capped by the corpus size. Both dense and sparse rankings contribute reciprocal-rank scores using 1/(60+rank). If every normalized query token occurs in a chunk's text, that chunk receives an additional exact-match bonus of 0.05. The highest fused scores are returned with their rank-source labels.

Direct get_clause lookup returns chunks by exact clause identifier. The in-process LRU retrieval cache keys on normalized query, provision type, top_k and index version. It returns deep copies and has a default maximum of 512 entries. A manifest/version change changes the cache key space. Each worker has its own cache; this is not a Redis-shared embedding cache. Microsecond retrieval figures in the measured run reflect a warmed, tiny repeated workload and must not be generalized to arbitrary cold corpora. [R11]

### Evidence verification

The reference cataract scenario uses B.1.1 for hospitalization/day-care coverage and C.1.b for the specific waiting period. The manifest also identifies C.1.a for pre-existing disease waiting and C.1.c for initial waiting. Research gathers relevant passages; verification checks the supplied evidence and applicable waiting conditions before selecting a route. Clause-level evidence is displayed to the reviewer. Policy changes require re-ingestion/version discipline and invalidate exact material-fact/evidence matches rather than silently preserving old automation.

## 10. Bounded agent graph and local model assessment

### Research and verification graph

The compiled LangGraph has classify, research and verify_and_route nodes. Classification reads the admission type. Research uses explicit tools such as search_corpus, get_clause and get_request_fields. Verification returns a coverage result or a retry directive. Conditional edges return to research only while replan, tool and step budgets allow. The graph is a bounded program with typed state and trace events; it is not an unconstrained autonomous conversation.

The graph state contains the request, admission class, evidence bundle, result, trace, retry directive, replan count, tool count, step count and start time. Defaults include 12 steps, 10 tool calls, two replans, 90 seconds run timeout and five seconds per tool. Synchronous graph work is offloaded with asyncio.to_thread so it does not directly block the event loop. Timing out the awaiting coroutine does not forcibly terminate a Python worker thread; internal step/tool guards remain important. The worker's ARQ job timeout is also 90 seconds, a separate outer constraint. [R12]

### Ollama structured assessment

For the Ollama profile, deterministic research runs before the structured assessment. The model receives a versioned system prompt and JSON containing the request and verified evidence. Expected fields are case_summary (a required factual narrative of 10-700 characters), recommendation (approve, reject or needs_information), rationale, clause_ids and exception_flags. The provider receives a shape/enum decoding schema with string/item length bounds removed to avoid grammar compiler problems; full Pydantic validation still applies after decoding. The application tolerates a surrounding JSON code fence, then validates the parsed object.

Returned clause IDs must be nonempty and a subset of the supplied evidence IDs. Failed deterministic verification or unsupported citations force needs_information. For known waiting-period positions, an inconsistent model recommendation becomes model_policy_conflict and routes to human review. Any exception flag prevents an approve/reject recommendation from authorizing reuse. The original generated rationale is retained as model_rationale for audit, while the UI explanation uses the verified policy route reason. This is an important hybrid-design boundary: the current model's prose can misstate policy details even when the high-level outcome is correct. [R13]

### Reviewer summary and accepting a suggestion

The reviewer detail view now shows an AI case summary generated from the submitted facts, separate from the verified policy rationale and approve/reject recommendation. The v2 prompt asks for two concise sentences without invented patient facts or policy interpretations. Amounts are denominated in INR by contract; generated dollar/USD notation is normalized to INR. This normalization does not prove the entire narrative is factually correct, so the UI asks the reviewer to check it against the submitted request. Historical v1 cases retain their existing evidence and do not gain a fabricated AI summary.

Accept AI suggestion is available only to a reviewer on an awaiting-review case with a completed/escalated run, passed verification, an approve/reject assessment and no model exception flags. Clicking it fills the corresponding human outcome and verified policy reason and submits the existing review form. The current reuse-checkbox choice applies; the operation remains a human decision and uses the same CSRF, revision and authorization checks. It is not shown for needs-information, guardrail, degraded, failed or already-final cases. A reviewer can still record a different manual decision. Deployed browser acceptance verifies both approval and rejection as source=human, plus hidden acceptance on an injection case. [E9]

The recorded load and stability results used the earlier v1 prompt without case_summary. The v2 prompt adds generation work and has functional acceptance but has not received a repeated capacity/soak matrix. The earlier throughput figures therefore describe the measured v1 workload, not a certified v2 performance envelope.

### Prompt responsibilities

The current claims-reviewer/v2 prompt treats request fields and retrieved passages as untrusted evidence. It asks the model to check policy/version, procedure meaning, admission, continuity, waiting periods, prior conditions, exclusions, room entitlement, insured amount, sublimits, costs and conflicting/missing facts. It identifies emergencies, portability/continuity ambiguity, uncertain exclusions, unsupported procedures, unexplained high costs and injection as reasons for review. Prompt instructions supplement executable gates; they cannot independently enable automation or override an ineligible case.

## 11. Human precedents and guarded automatic decisions

### Authorization model

A reviewer decision can create a precedent only when the evidence is eligible and the chosen final outcome agrees with the current recommendation. The API requires a reason and a current revision. Reusable defaults in the eligible review screen are a UI convenience; the backend decision model defaults reusable to false, so an API caller must explicitly request it. A one-off decision remains valid business history but does not authorize future automatic decisions.

The reuse evaluator first requires a calibration artifact, eligibility and an associated current case. It filters active candidates to the same policy version, locks candidate rows, embeds the new and prior clinical descriptions and compares their similarity. The calibrated threshold is 0.72. Numeric and structured eligibility are not inferred from semantic closeness: material facts must match exactly. If multiple otherwise matching precedents disagree on outcome, no precedent is selected. The selected outcome must also agree with the current AI assessment. [R14, R15]

### Material facts compared exactly

The fact object contains admission type, procedure code, patient age/gender, requested room, sum insured, estimated cost, sorted normalized prior conditions, policy age in days at admission, coverage position, sorted clause identifiers and a SHA-256 digest of the sorted citation text. The clinical description combines diagnosis and procedure for semantic matching. Exact cost and age matching are deliberately conservative; the implementation does not use broad cost bands despite earlier planning language. Any change to relevant citation text changes the evidence digest.

| Gate | Must be true for reuse |
| Verified evidence | Passed deterministic verification and nonempty citations |
| Recommendation | approve or reject, with no exception flags |
| Input | No guardrail findings or validation flags; procedure code present |
| Circumstances | No emergency, prior conditions, deluxe room or nonempty notes |
| Coverage position | Known waiting-period served or not-served position |
| Precedent identity | Active and same policy version |
| Comparison | Exact fact equality and semantic score at/above threshold |
| Agreement | No conflicting matching outcomes; chosen outcome agrees with current assessment |

### Revocation and override

Automatic outcomes record source=precedent and the precedent ID. They do not create further precedents. Disabling a precedent is prospective and does not rewrite already completed decisions. Overriding an automatic result records a human outcome and an event containing the previous decision, while disabling the source precedent. These operations keep the causal link visible. Revocation and semantic approval/rejection were verified against the deployed PostgreSQL/Ollama path, not only in mocks. [E3]

The held-out semantic fixture had zero false matches among two negatives and one true match among two positives: 50% positive recall. That sample is far too small to estimate clinical safety or generalization. Conservative gating trades recall and automation coverage for a narrower demonstration envelope. A future rollout needs a much larger, independently labeled evaluation set and explicit error-cost analysis.

## 12. Queue admission, inference budget and overload

### Bounded admission

QUEUE_CAPACITY defaults to 64 and is validated in the range 1-1000. enqueue_bounded acquires the shared Redis lock desk:queue:admission, checks ZCARD on arq:queue and enqueues only below the configured capacity. The lock has a 30-second lease and five-second acquisition wait. ARQ retains running jobs in that sorted set until completion, so the budget covers queued and currently running work. Concurrent-admission regression uses two contenders for one available slot and verifies that exactly one is admitted.

This cap is implemented above the largest measured queue depth of sixteen. It was added after the reported performance measurements and tested separately, including real Redis rejection/lock release and deployed workflow acceptance. The read-only live probe used an explicit zero limit so no synthetic job had to be inserted into the real queue; the default 64 threshold is covered by the application regression fixture. Under abnormal Redis partitions or lease expiration, behavior still requires operational investigation; this is not a proof of exactly-once processing under arbitrary failures. [R16, E4]

### Global model serialization

All worker replicas acquire desk:ollama:inference before the structured assessment. The processing profile uses a 40-second provider timeout and one provider attempt; the assessment budget adds 30 seconds, and the lock lease adds a further 30 seconds. The lock's acquisition wait is ten seconds. Ollama itself also runs one parallel inference and one loaded model. These controls prevent replica count from silently multiplying model/GPU demand.

Three workers can therefore move waiting time from the ARQ queue into inference-lock contention. In the measured comparison, one case degraded without a model call, consistent with timing out while acquiring the shared slot. Existing logging did not preserve the exception class for that inner failure, so contention remains an evidence-based inference rather than a confirmed stack-trace diagnosis. The recommended local configuration is one worker. Safe escalation is useful failure behavior, but it still counts as a performance failure.

### Resource guards in tests

The supervisor refuses new load below max(2 GiB, 15% of physical RAM). During a run it stops after the reserve has been breached for 30 seconds, after queue age exceeds 180 seconds, or when essential queue/resource monitoring fails. It records CPU, host available RAM, model RSS, service RSS, queue depth/age and sampled GPU data. Owned load-process trees are terminated on a guard stop to avoid orphaned Windows virtualenv subprocesses. An initial missing-password attempt led to a CLI credential preflight; that attempt is retained as invalid evidence rather than treated as a completed stage. [R17]

## 13. Model selection and memory investigation

### Selected serving profile

| Setting | Current local choice | Reason |
| Model | qwen3:4b, Q4_K_M | Structured/grounded acceptance within local budget |
| Context | 4096 tokens | Bound KV/context footprint |
| Output | 512 tokens | Bound generation length and latency |
| Thinking | Disabled | Use concise structured output rather than extended reasoning |
| Loaded models / parallel | 1 / 1 | Predictable GPU and host demand |
| Host prompt cache | LLAMA_ARG_CACHE_RAM=0 | Prevent diverse-prompt host snapshot accumulation |
| mmap option | Disabled in desk profile | Retained profile setting; not the demonstrated root-cause fix |
| Global inference slot | 1 across replicas | Enforce serving budget at application boundary |

The host has 16 GB RAM, an Intel i7-13620H and an RTX 4050 Laptop GPU with 6 GB VRAM. Earlier attempts used an installed 7B model and smaller alternatives. Changing model size, mapping or output grammar alone did not establish stable memory under varied inputs. The final selection is justified by measured resource behavior and acceptance, not by assuming a larger model is automatically better.

### Root-cause finding

Diverse prompts caused runner resident memory to grow, while repeated identical prompts initially looked stable. The host prompt snapshot cache default was approximately 8192 MiB, and distinct prompts added roughly 363 MiB each in the investigated profile. Disabling that cache produced a ten-distinct-case probe with RSS near 769 MB, and later capacity stages held the runner around 700-721 MiB sampled RSS. The incident history retains the unsuccessful hypotheses and guard-stopped attempts rather than erasing them.

The PowerShell launcher binds Ollama to the WSL gateway interface, sets the bounded environment and records an owned server PID/state file in the user's temporary directory. It refuses to silently reuse an unmanaged listening server. A restart is allowed only for the recorded owned service. Gateway discovery and state checks matter because Windows/WSL addresses and process ownership can change between sessions. Final measurements include roughly 3.3 GB sampled GPU memory, below the physical 6 GB, but other host applications still affect available RAM. [R4, R18, E5]

## 14. Observability and diagnostic evidence

### Metrics, logs and traces

Prometheus scrapes the API, worker, Redis exporter and Prometheus itself in the desk profile. Grafana has a provisioned preauth-overview dashboard with p99 panels. OpenTelemetry exports API and worker traces to Jaeger. Structured logs bind correlation and run IDs so an accepted request can be followed through job processing. Persisted run steps complement ephemeral logs; the token ledger records model/provider identity and usage with zero configured notional local-provider cost, which should not be interpreted as zero hardware/energy cost.

| Signal | Interpretation | Caution |
| Worker run histogram | Worker processing duration | Excludes time before worker pickup |
| LLM call histogram | Provider call latency | May not include inference-lock wait |
| Agent step histograms | Classification, research, verification timings | Histogram buckets approximate quantiles |
| ARQ queue depth and age | Backlog including running jobs | Must use a consistent clock domain |
| Service RSS | Process resident memory | Per-worker replicas and Prometheus scrape timing matter |
| Host RAM / CPU | Total-machine pressure | Includes unrelated user applications |
| GPU memory/utilization/temperature | Sampled nvidia-smi telemetry | Not a continuous maximum or isolated model attribution |
| Case event history | Human/automatic decision sequence | Application audit record, not tamper-proof storage |

### Clock and attribution correction

Windows and WSL clocks differed during the resumed run. Earlier one-worker queue-age samples used the host clock against Redis scores and understated age. The supervisor was corrected to use Redis TIME when calculating queue age. Component reports identify exact case IDs captured by Locust and join those IDs to database runs, avoiding attribution by unsynchronized cross-host time windows. Database queue durations remain valid because both timestamps originate in the database clock domain.

The five-second resource sampler covered approximately 297 seconds of the 300-second stability workload; the supervisor elapsed time was 302.5 seconds including startup/drain. A final sample need not land exactly on process exit. The evaluator therefore checks runtime separately from sampling coverage and retains the coverage gap explicitly. It does not manufacture an extra end-boundary sample. [R17, R19]

## 15. Test strategy and acceptance evidence

### Verification layers

Unit and application integration fixtures cover authentication, session expiry/logout, CSRF, role enforcement, ownership, validation, idempotency, revisions, conflicting decisions, precedence eligibility, malformed assessment output, citation conflicts, guardrails, reliability and benchmark safeguards. SQLite-backed test fixtures are useful for application rules; they do not substitute for PostgreSQL lock behavior. Deployed acceptance therefore separately verifies concurrent reviews against PostgreSQL, expecting exactly one 200 and one 409.

Real-model tests verify grounded output, safe outage behavior, semantic automatic approval/rejection, mitigating notes, material cost changes, revocation and override. Browser acceptance exercises the actual role-specific interface, clarification/resubmission, history and responsive layouts. The latest frontend shortcuts and sample-fill additions received their own Edge browser checks, including normal session roles, 390px viewport fit, valid form values, invalid policy-number rejection, no automatic submission and HTTP 202 API acceptance. [E2, E3, E6]

| Evidence | Recorded result | Meaning |
| regression-2026-11-17.json | 76 targeted tests passed | Application, queue-race and benchmark-evaluator regression snapshot |
| workflow-api.json | Isolation/idempotency and concurrent 200/409 | Real PostgreSQL endpoint acceptance |
| precedent-flow.json | Approval/rejection, mitigation, revoke and override | Real Ollama and human-precedent workflow |
| precedent-browser.json | Browser automation workflow | UI integration evidence from prior acceptance |
| monitoring-smoke.json | Four scrape targets up, Grafana and Jaeger checks | Telemetry is live; not performance proof by itself |
| final-deployment-2026-11-17.json | Eight services running, ready API, image identity | Final handover snapshot before later UI rebuilds |
| demo-login.json / sample-claim.json | Role shortcuts and valid submission | Deployed browser checks for subsequent UI additions |

The reviewer-summary extension has a separate reviewer-regression.json snapshot with 77 passing tests and reviewer-suggestion.json covering both human acceptance outcomes and guardrail suppression. The historical 76-test handover artifact is retained rather than rewritten.

### Test evidence interpretation

A successful POST is not a successful assessment. Locust records a separate machine-assessment event only after terminal visibility and counts degraded/failed outcomes as failures. It reports accepted but unobserved assessments when a run is interrupted. Final CSV is written after Locust task draining; periodic CSV can miss the last in-flight observation. Earlier RAM-guard stops, a user-interrupted run and the missing-credential attempt remain in separate result directories.

Tests do not demonstrate every security property or model behavior. There is no independent clinical labeling program, no enterprise penetration test and no completed multi-hour soak. The test count is a specific selected suite, not a count of all repository tests or a code-coverage percentage. UI convenience changes were checked through browser acceptance rather than increasing that regression count artificially.

## 16. Measured load, stress and worker scaling

### Method and declared targets

Locust 2.29 uses authenticated synthetic Hospital Staff sessions. The staged workload mixes browse and submit tasks, waits one to three seconds and polls processing results. Virtual users share one seeded hospital login so login rate limiting is excluded from processing-capacity measurements. Each load stage sends work for three minutes, then allows active assessments to drain. These are exploratory single runs, not repeated statistical experiments with confidence intervals.

Targets declared in the internal-tool plan are machine p95 at most 30 seconds, p99 at most 60 seconds, unexpected errors below 1%, API p95 at most one second and API p99 at most two seconds. The stable workload must also avoid crashes, sustained backlog growth and more than 10% comparable-window service-memory growth. The model was warm; these stages do not measure cold-start loading. Human review turnaround and reviewer throughput are excluded.

[[loadtable]]

### Saturation analysis

The two-, four- and eight-user one-worker stages passed the observed SLO checks, with no missing observations. Eight users achieved approximately 0.310 assessments/second. Sixteen users reached only about 0.318/s while p95 rose to 47 seconds, a clear sign that added demand mostly increased queueing rather than useful capacity. Recovery returned p95 to 5.1 seconds. Fewer than 100 observations per stage make p99 particularly weak evidence; the table records sample size to avoid implying strong tail reliability.

At eight users, database phase percentiles show queue wait p50 12.737s/p95 20.757s/p99 22.104s, versus model assessment p50 2.686s/p95 3.170s/p99 3.890s. This supports queueing as the dominant end-to-end tail. Locust histogram percentiles and database interpolated percentiles use different estimators and include different boundaries, so they should not be expected to match exactly.

[[latencychart]]

### Matched worker comparison

At four virtual users, one worker observed 53 assessments, zero errors, p95 10 seconds and throughput 0.291/s. Three workers observed 52 assessments with one degraded result, p95 11 seconds and throughput 0.279/s. The approximately 1.9% failure rate exceeds the target. Three-worker recovery produced four observations without errors. No throughput advantage is demonstrated. The older 3.22x worker scaling result belongs to a different stub-provider experiment and is not applicable to real Ollama capacity. [R20]

## 17. Five-minute mixed stability evaluation

### Scope and traffic

The user explicitly reduced the originally planned 30-minute soak to five minutes because of time constraints. The executed test is therefore a short stability check. Optional 30-minute and two-hour profiles remain available but unverified. Its target rate was 0.1859 assessments/second, approximately 60% of the passing eight-user observed rate, using two paced virtual users and a mixed scenario distribution.

One synthetic human-approved nominal precedent was created for the test and revoked afterward. Nominal cataract cases were mixed with unserved waiting periods, unsupported procedures and injection notes. This tests both automatic reuse and exception escalation without simulating a human reviewer queue. The achieved rate including supervisor startup/drain was 0.1851/s; Locust's own reported rate uses its measurement interval and is slightly different.

| Result | Value | Interpretation |
| Total observations | 56 | All accepted assessments observed |
| Failures / missing | 0 / 0 | No degraded/failed assessment or lost client observation |
| End-to-end p50 / p95 / p99 | 4.1s / 7.1s / 7.2s | Histogram estimates; small p99 sample |
| Precedent approvals | 34 | Matching synthetic nominal cases |
| Exception cases reviewed | 20 | 9 waiting-period, 7 unsupported-procedure, 4 injection |
| Other nominal cases reviewed | 2 | Conservative non-automatic handling |
| Exception approvals | 0 | Observed fixture result, not general safety estimate |
| Queue maximum depth / age | 2 / 8.19s | No sustained backlog growth observed |
| Minimum available host RAM | 3.88 GiB | Above configured reserve |
| Sampled GPU memory / CPU peaks | 3301 MiB / 23.4% host CPU | Includes sampling and host-attribution caveats |

### Memory and component timings

The evaluator compares mean RSS in seconds 60-120 with the final sampled minute for unchanged service instances. API mean RSS increased approximately 0.017%, worker mean RSS 0.102%, and Ollama runner RSS decreased. These are resident working-set observations, not proof of a bounded allocator heap for arbitrary requests. All declared short-test checks passed, including outcome evidence, no exception approval, queue age/growth and stable service instances.

[[phasetable]]

Database timings use exact case IDs. Automatic-final has 34 observations. Inference has 52 because four injection cases were blocked before model access. Retrieval has 357 observations because it counts individual tool calls. Automatic-final database p95 can be higher than the aggregate client histogram p95 because it is a different subset and estimator. The evidence does not include multi-hour memory behavior, repeated failure recovery or sustained external traffic. [E7]

## 18. Deployment and operational procedures

### Prerequisites and startup

The verified route requires Windows with Ubuntu WSL, standalone Docker Engine/Compose inside Ubuntu, Windows Ollama with the selected model, the raw policy PDF and project Python tooling for acceptance scripts. Keep Ubuntu active during use; background systemd services alone did not keep the distribution alive in the observed environment. Docker Desktop is not required for this route. Protect the existing database and index volumes when rebuilding.

```powershell
$env:DESK_HOSPITAL_PASSWORD = 'Hospital-demo-2026'
$env:DESK_REVIEWER_PASSWORD = 'Reviewer-demo-2026'
./scripts/demo_desk.ps1 -SkipIngest
# Omit -SkipIngest when a valid index must be created.
```

The launcher checks credentials and the corpus path, starts bounded Ollama, builds the image, starts PostgreSQL/Redis, optionally ingests, starts API/worker, seeds accounts idempotently and starts monitoring. WSLENV forwards password variables by name rather than embedding values in a docker exec command line. The quoted passwords are deliberately public synthetic demo credentials; the demo shortcut buttons expect those defaults.

| Interface | Local URL | Purpose |
| Application | http://localhost:8000/ | Hospital/reviewer workspace |
| Readiness | http://localhost:8000/readyz | API dependency readiness |
| Grafana | http://localhost:3000/d/preauth-overview | Provisioned service dashboard |
| Prometheus | http://localhost:9090/ | Metrics queries and target health |
| Jaeger | http://localhost:16686/ | API and worker trace inspection |

### Common operations

```powershell
./scripts/compose_wsl.ps1 ps
./scripts/compose_wsl.ps1 logs --tail 100 api worker
./scripts/compose_wsl.ps1 build api worker
./scripts/compose_wsl.ps1 up -d --no-deps --wait api worker
./scripts/compose_wsl.ps1 --profile observability stop
```

Stopping project containers preserves their named volumes. Do not use down -v as a routine stop operation. Do not stop shared Docker/containerd services or unrelated user applications as part of a project shutdown. The Ollama launcher records the owned process so it can be distinguished from another user's model service. A backup/restore procedure should include PostgreSQL data, policy provenance, index artifacts and configuration; a tested production disaster-recovery objective is not supplied by this demo.

### Configuration priorities

The desk Compose override selects Ollama, model limits, worker concurrency one and guarded automation enabled. Base Settings leave precedent automation disabled. The API has a 512 MiB container limit, worker 2 GiB, and monitoring services have bounded limits in the desk override. Configuration changes must be followed by health checks and appropriate acceptance; adding replicas under an unchanged inference budget is not a capacity upgrade. [R4, R5, R21]

## 19. Failure handling, troubleshooting and future work

| Symptom | First checks | Safe next action |
| Invalid policy number | Uppercase, digits/hyphens, 6-32 chars | Use Fill sample claim or SYN-POL-0001; keep server validation |
| Sign-in shortcut fails | Seeded accounts/password defaults, API logs | Use normal form for changed credentials; seed deliberately |
| API not ready | Database, Redis, index status and service health | Restore missing dependency; do not bypass readiness |
| Cases remain processing | ARQ depth/age, worker health, model connection | Inspect run IDs and logs before retrying |
| Model unavailable | WSL gateway, managed listener, installed model | Restore bounded launcher; keep results in human review |
| Host RAM guard stops load | Available RAM and other applications | Free resources with operator involvement; retain stopped evidence |
| Three-worker degradation | Shared inference slot and acquisition wait | Return to one worker on this hardware |
| No automatic match | Current evidence, exact facts, notes and active precedent | Explain the failing gate; do not lower threshold ad hoc |
| Queue full | Depth including running jobs and capacity setting | Human review/overload handling; investigate arrival rate |
| Citation conflict | Corpus version, clause IDs and model assessment | Require human review and preserve evidence |

### Important residual risks

The deployment uses public synthetic accounts and lacks enterprise SSO, MFA, comprehensive tenant boundaries, retention governance and clinical integration. Cross-system database-to-queue delivery has no transactional outbox. The semantic fixture is too small for risk estimation, and only a narrow policy/procedure envelope is evaluated. Historical logs do not always retain inner exception classes. Saturation testing was local and single-run, and the five-minute check cannot establish long-term stability. Resource telemetry is sampled and includes other host activity.

The next engineering priorities are an outbox/reconciler for durable dispatch, richer error classification, independent labeled model/precedent evaluation, larger corpus/version tests, long soak runs, backup/restore drills and production identity/tenant controls. Before raising local throughput targets, increase or change model-serving capacity and repeat the matched benchmark with multiple runs and confidence intervals. Review whether exact age/cost/day matching is an acceptable business tradeoff; broadening it requires new safety evaluation rather than just lowering the similarity threshold.

### Demonstration sequence

For a presentation, start the bounded stack, show the two demo-role buttons, sign in as Hospital Staff and fill a sample claim. Submit and inspect the cited recommendation as Claims Reviewer. Record an eligible reusable human decision, then submit an equivalent new case to show source=precedent. Add an exception note or change a material fact to show human escalation. Demonstrate disable/override and finish with the performance table, explicitly explaining why three workers did not improve the single-model bottleneck. Existing synthetic cases accumulate in the demo database; use their history as evidence, not as real customer records.

## 20. Reproduction commands and repository reference register

### Acceptance and benchmark commands

```powershell
# Set the synthetic account variables shown in Chapter 18.
.venv/Scripts/python.exe scripts/verify_workflow_api.py
.venv/Scripts/python.exe scripts/verify_precedent_flow.py
.venv/Scripts/python.exe scripts/verify_precedent_browser.py
.venv/Scripts/python.exe scripts/verify_monitoring.py

# Scale actual workers before changing the --workers label.
.venv/Scripts/python.exe scripts/benchmark_desk.py `
  --workers 1 --users 2 4 8 16 `
  --output-dir loadtest/results/desk/new-capacity-run

# Authorize temporary fixture; revoke it after the test.
.venv/Scripts/python.exe scripts/seed_soak_precedent.py
.venv/Scripts/python.exe scripts/benchmark_desk.py `
  --workers 1 --soak-minutes 5 --soak-rps 0.1859 `
  --output-dir loadtest/results/desk/new-soak-run
.venv/Scripts/python.exe scripts/seed_soak_precedent.py --disable

.venv/Scripts/python.exe scripts/summarize_desk.py
.venv/Scripts/python.exe scripts/summarize_soak.py `
  loadtest/results/desk/new-soak-run/workers1-soak.json
```

Use a fresh output directory for each run. The 0.1859/s example reproduces this machine's measured short-test rate; it must be recalculated after meaningful hardware, model or deployment changes. A --workers value is a report label and does not scale containers. Do not run a seed script twice without resolving any prior active fixture; revoke temporary precedents in cleanup even if a test fails.

### Source references

| ID | Repository source | What it establishes |
| R1 | src/preauth/api/auth.py; src/preauth/security.py | Login, sessions, CSRF and roles |
| R2 | src/preauth/api/cases.py | Case lifecycle, review, retry, resubmit and ownership |
| R3 | web/index.html; web/desk.js; web/desk.css | Current UI, role shortcuts and autofill |
| R4 | scripts/start_ollama_wsl.ps1; scripts/compose_wsl.ps1 | Managed model and gateway/path wrapper |
| R5 | Dockerfile; docker-compose.yml; docker-compose.desk.yml | Image and current deployment profile |
| R6 | src/preauth/store/models.py; migrations.py; repository.py | Persistence and schema versioning |
| R7 | src/preauth/api/schemas.py | Input and response contracts |
| R8 | src/preauth/api/main.py; api/precedents.py | Legacy API and precedent controls |
| R9 | tests/test_auth.py; test_security.py | Auth/ownership regression fixtures |
| R10 | corpus/MANIFEST.md | Frozen policy provenance and clause locations |
| R11 | src/preauth/rag/retriever.py; embeddings.py | Hybrid ranking and local embeddings |
| R12 | src/preauth/agents/graph.py; tools.py; worker.py | Bounded graph and processing execution |
| R13 | src/preauth/llm/assessment.py; client.py; prompts/claims_reviewer_v2.txt (v1 retained) | Structured model and validation |
| R14 | src/preauth/precedents.py; automation.py | Exact facts and guarded reuse |
| R15 | evals/precedent_calibration.json | Semantic threshold and small held-out evaluation |
| R16 | src/preauth/queue.py; tests/test_queue_capacity.py | Bounded job admission |
| R17 | scripts/benchmark_desk.py; loadtest/desk.py | Real-model load client and resource guard |
| R18 | docs/MODEL_SELECTION.md; docs/INCIDENTS.md | Model/memory investigation history |
| R19 | scripts/summarize_soak.py; collect_benchmark_phases.py | Evaluation and exact-ID phase attribution |
| R20 | docs/INTERNAL_TOOL_PERFORMANCE.md; loadtest/results/desk | Measured current capacity and limitations |
| R21 | docs/INTERNAL_TOOL_DEMO.md; RUNBOOK.md | Reproduction and operator procedures |

### Evidence references

| ID | Evidence paths | Notes |
| E1 | docs/evidence/final-deployment-2026-11-17.json | Point-in-time deployment before convenience UI rebuilds |
| E2 | docs/evidence/sample-claim.json; sample-claim.png | Valid browser form and accepted synthetic claim |
| E3 | docs/evidence/precedent-flow.json; precedent-browser.json | Semantic reuse, exceptions, revocation and override |
| E4 | docs/evidence/queue-capacity-live.json | Real Redis zero-limit rejection and lock release |
| E5 | docs/evidence/model-memory-cache0.json; model-qwen3.json | Memory probe and selected-model metadata |
| E6 | docs/evidence/regression-2026-11-17.json; workflow-api.json; demo-login.json | Regression and deployed workflow/UI checks |
| E7 | loadtest/results/desk/2026-11-17-soak5 | Raw short-run CSV/JSON, outcomes, phase and evaluation sidecars |
| E8 | loadtest/results/desk/2026-11-17-freed; 2026-11-17-workers3 | Completed capacity, recovery and worker comparison |
| E9 | docs/evidence/reviewer-suggestion.json; reviewer-suggestion-approved.png; reviewer-suggestion-rejected.png | Model summary and human acceptance of approve/reject suggestions |

The source snapshot follows commit 997f31f, including the reviewer-summary/v2 extension, on top of dacc1f9 for sample-claim autofill. Earlier implementation checkpoints include f5819dd (handover), 294352d (role shortcuts), ee1661b (load/scaling) and 4db9723 (short stability and queue cap). Subsequent documentation commits do not retroactively change the date or conditions of recorded measurements. The configured remote is SunOrangeBurger/Health-Insurance-Pre-Authorisation-Desk-MLSD, branch codex/internal-policy-desk.

## Appendix A. Interface examples and state interpretation

[[loginimage]]

The sign-in shortcuts authenticate the same seeded roles as the manual form. They are intentionally visible in the synthetic demonstration and should be removed or replaced before any deployment involving private business data. Signing out revokes the current server-side session rather than simply hiding the dashboard.

[[sampleimage]]

The sample form uses valid policy syntax and relative dates. Optional empty prior-conditions and notes fields are intentional: adding notes or prior conditions is an exception gate and should change the automation behavior. Autofill is a convenience for repeatable presentation; the reviewer still owns the first reusable authorization.

### Reviewer decision assistance

[[reviewerimage]]

Figure 6 shows the model case summary alongside the explicit AI suggestion and verified policy explanation. The reviewer checks the request and citations before accepting or recording a different outcome. The acceptance action records a human decision; it does not relabel the model as the authorizing person.

## Appendix B. Glossary

| Term | Meaning in this implementation |
| Pre-authorisation | A request to assess intended treatment against policy evidence; the demo is not a real insurer authorization |
| Case | Business workflow entity with current revision, linked run and final decision |
| Run | Processing record for one immutable request revision |
| Recommendation | Advisory structured output; distinct from final human/precedent decision |
| Precedent | Explicitly reusable human decision with facts and policy/evidence context |
| Escalated | Processing intentionally routes to human review, including guardrail/uncertainty cases |
| Degraded | Processing dependency or reasoning failure prevents a confident recommendation |
| RAG | Retrieval-augmented generation; evidence is retrieved before model assessment |
| RRF | Reciprocal-rank fusion of dense and sparse retrieval rankings |
| p50 / p95 / p99 | Estimated response-time percentiles; sample size and estimator matter |
| RSS | Resident set size; current physical working set rather than all allocated memory |
| Soak | Sustained stability workload; this execution was shortened to five minutes |
| WSL | Windows Subsystem for Linux, hosting the current standalone Docker Engine |
| CSRF | Cross-site request forgery; mutations require the session-bound token |
| Idempotency | Retrying an identical keyed submission returns its existing case |
| Fail-closed reuse | Missing evidence, conflict or exception prevents an automatic decision |
