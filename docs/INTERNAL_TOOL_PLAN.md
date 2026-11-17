# Hospital–Insurer Desk implementation plan

Date: 2026-11-13. Status: planned; implementation and new benchmarks pending.

## Product and boundaries

Build a synthetic-data pre-authorisation workspace with two roles: **Hospital Staff** and **Claims Reviewer**. One insurer and seeded accounts for two hospitals demonstrate access isolation. No public registration, real insurer integration, payment settlement, or document uploads in this iteration. Preserve the existing policy corpus and backend engineering demonstrations.

Hospital Staff submit a structured case, track progress, answer clarification requests, and read the final decision and reasons. Claims Reviewers inspect AI recommendations and cited evidence, approve/reject/request information, and control whether a decision may be reused. The UI must distinguish AI recommendation, human decision, and automatic decision based on a human precedent.

Defaults for unanswered questions: include clarification/resubmission; reviewer decisions default to reusable with an explicit one-off control. On November 17 the user shortened the required soak to five minutes due to time constraints. Keep optional 30-minute and two-hour profiles. The five-minute result only establishes short-term stability.

## Application and contracts

- Extend the existing static frontend with modular JavaScript and CSS served by FastAPI: login, hospital case dashboard, grouped submission form, case details/history, reviewer inbox, review details, and precedent management. Use accessible labels, inline validation, loading/empty/error states, and responsive layouts. Avoid adding a separate frontend runtime.
- Form covers existing policy, patient demographics, diagnosis/procedure, admission, requested room, estimated cost, prior conditions, and notes. Add policy product/version selection from the configured corpus. Derive hospital identity from the session rather than trusting submitted identity.
- Add users, server-side sessions, cases, immutable case revisions, review decisions, precedents, and audit events. A case revision links to its existing processing run. Separate processing status from business status: processing, awaiting review, information requested, approved, rejected. Keep model failures visible and route them to review.
- Add password-hashed seeded accounts and opaque HttpOnly session cookies; SameSite protection, CSRF validation for mutations, expiration, logout revocation, and login rate limiting. Roles and hospital ownership are enforced on every API read/write, not just navigation. Reviewers belong to the insurer and see its cases.
- Introduce `/v1/auth/login`, `/logout`, `/me`; `/v1/cases` list/create; case detail, resubmit, and decision endpoints; reviewer precedent list/disable endpoints. Lists are paginated and filterable by status. Protect existing run, trace, feedback, and submission routes with equivalent ownership checks; migrate demos/load clients to authenticated use.
- Require a case revision/version when deciding or resubmitting. Transactional conflict checks prevent duplicate or stale decisions; idempotency prevents retry submissions from creating extra cases. Persist audit actor, revision, reason, model/prompt/policy versions, evidence, and decision source.
- Add versioned database migrations instead of relying on create_all for upgrades. Preserve old runs as legacy records inaccessible to hospital accounts unless explicitly mapped. Seed scripts must be idempotent and passwords configurable locally.

## AI recommendations and precedent reuse

- Make Ollama produce a schema-validated recommendation: approve, reject, or needs information, with rationale, clause IDs, material facts, and exception flags. Validate cited clauses against retrieved evidence. The recommendation is advisory until a human decides or an eligible precedent authorizes automation.
- Store versioned system prompts describing policy constraints, incomplete evidence, waiting periods, exclusions, pre-existing conditions, cost/room limits, emergencies, conflicting facts, novel procedures, policy changes, conflicting decisions, and prompt injection. Unknown or ambiguous circumstances require review. Mirror mandatory gates in executable logic; prompt text alone cannot authorize an outcome.
- Human final decisions can create precedents; automated decisions never create further precedents. Require a reason and validated policy evidence for reusable precedents; one-off overrides remain visible but cannot authorize automation. Reviewers can disable precedents prospectively without rewriting historical decisions.
- Use existing embeddings to retrieve semantically similar human-reviewed cases after filtering insurer and exact policy product/version. Match clinical/procedure meaning, not literal wording. Compare structured material conditions: admission/procedure category, waiting-period eligibility, exclusions/PED, room entitlement, cost/coverage bands, and evidence completeness. Similarity alone is insufficient. Recompute limits for the new case rather than copying an old amount.
- Require semantic match, equivalent material conditions, verified current citations, no exception, and agreement with the current recommendation. Conflicting eligible precedents or uncertain extraction force review. Both approval and rejection may be reused, according to the human precedent.
- Calibrate the similarity threshold on labeled positive paraphrases and negative near-matches; select maximum recall subject to zero false automatic decisions on the calibration set, then evaluate a separate held-out set. If no threshold passes, disable automatic reuse and report the limitation. Record threshold, embedding version, test evidence, and matched precedent for reproducibility.
- Avoid exposing another hospital's patient/case details in returned precedent explanations. Show the applicable policy basis and decision provenance without copying the source payload.

## Ollama and deployment

- Inspect available RAM, CPU, GPU/VRAM, Docker limits, and installed Ollama models first. Previous sandbox hardware/network probes were blocked; do not infer hardware from that failure. Verify current official Ollama documentation and model metadata before selecting/download.
- Benchmark an installed suitable model first; otherwise evaluate a small quantized instruction model (approximately 3–4B class) before any larger candidate. Select the smallest candidate passing structured-output and decision-quality fixtures. Record exact model digest, quantization, context/output limits, memory peaks, and inference times. If none passes within resource limits, document the blocker rather than claiming readiness.
- Use host Ollama with Docker-to-host connectivity on Windows; document Linux host-gateway configuration. Add an explicit Ollama adapter and readiness/model checks. Keep stub mode for deterministic regression/infrastructure tests, clearly separated from real-model performance evidence.
- Start with one global inference slot and one loaded model. Coordinate the inference budget across replicated workers using Redis, with expiring leases and bounded waiting. Bound context, output, queue depth, retries, and timeouts; expose overload instead of accumulating unlimited work. Offload synchronous retrieval/graph execution so event-loop blocking does not invalidate timeout handling.
- Update Dockerfile/Compose, dependencies, migrations, environment examples, health checks, resource limits, and PowerShell/Linux launch and test scripts. Preserve volumes during rebuilds. Enforce LF shell line endings. Rebuild images and verify both roles end-to-end on the local Docker deployment.
- Preserve existing user changes in scripts; inspect diffs before altering them.

## Performance and acceptance

- Extend Locust rather than introduce k6. Authenticate virtual hospital/reviewer users. Exercise submissions, list/detail reads, polling, reviewer decisions, clarification, paraphrased precedent hits, novel cases, exceptions, and invalid requests. Simulated reviewer timing must be reported separately from machine processing.
- Report p50/p95/p99 for API latency, queue wait, retrieval, Ollama inference, submission-to-recommendation/review-ready, and automatic final decision. Separately report human turnaround, completed throughput, errors, timeouts, overload responses, queue depth/age, automatic-decision accuracy, precedent hit/escalation rates, CPU/RAM, and GPU/VRAM where available.
- Never count degraded/failed jobs as successful decisions. Report sample counts and incomplete jobs; low-volume p99 is explicitly qualified. Keep model cold-start measurements separate from warmed steady state.
- Execute smoke, staged load (1, 2, 4, 8, then 16 users if safe), bounded stress through first saturation, recovery, and five-minute soak (user-adjusted on November 17) at 60% of measured sustainable arrival throughput. Stress stages last three minutes and stop after sustained overload or resource guard activation. Provide an optional two-hour soak.
- Resource guard: stop new load if available system RAM falls below max(2 GiB, 15% physical RAM) for 30 seconds, if workers/model crash, or queue age exceeds twice the configured processing deadline. Observe recovery and preserve results. Resource safety outranks reaching a user-count target.
- Initial acceptance targets: non-inference API p95 <= 1 second and p99 <= 2 seconds; machine processing p95 <= 30 seconds and p99 <= 60 seconds at the declared sustainable workload; unexpected errors < 1%; no crashes, sustained queue growth, or >10% service-memory growth between comparable post-warmup soak windows. Failure is documented, not hidden by relaxing targets after measurement.
- Compare one versus three workers under the same global inference budget and workload. Report actual bottlenecks; more workers need not improve a single-model bottleneck. Keep real Ollama and stub results in separate artifacts.
- Functional tests cover login/session expiry/CSRF, hospital isolation, role enforcement, validation, reviewer overrides, concurrent decisions, duplicate retries, immutable revisions, clarification, paraphrases, materially different near-matches, conflicting/revoked precedents, policy-version changes, unsupported citations, injection, malformed model output, outage/overload, and migration from existing data.
- Browser verification demonstrates hospital submission -> reviewer decision -> semantically equivalent automatic response -> exception returned to review, for both approval and rejection precedents.

## Checkpoints and documentation

Track this expansion separately from the original project's completed milestones. Update INTERNAL_TOOL_PROGRESS.md after every checkpoint with verified completion percentage, evidence, limitations, and next steps. Percentages are earned by passing the stated exit checks, not by elapsed time or files changed.

| Checkpoint | Weight | Cumulative | Exit evidence |
|---|---:|---:|---|
| Scope and implementation plan | 5% | 5% | Plan and progress tracker written |
| Authentication and migrations | 15% | 20% | Upgrade, session, role and isolation tests |
| Hospital and reviewer workflow | 20% | 40% | Submission, review, clarification and browser checks |
| Ollama recommendations | 15% | 55% | Hardware/model benchmark and grounded-output tests |
| Precedent eligibility and semantic evaluation | 5% | 60% | Material-fact/exception guards; calibration and held-out evidence; automation disabled by default |
| Precedent automation integration | 15% | 75% | Human precedent controls, automatic outcomes, conflict/revocation end-to-end tests |
| Deployment and telemetry smoke | 5% | 80% | Persistent rebuild, service health, live targets, dashboard and traces |
| Multiworker deployment validation | 5% | 85% | Replica readiness, restart/recovery, shared inference budget and runbook |
| Load, stress, soak and handover | 15% | 100% | Actual test artifacts, resource/scaling analysis and runbook |

Checkpoint completion requires all its exit checks. Final handover updates README, demo guide, architecture, operational runbook, and performance report with measured limitations.
