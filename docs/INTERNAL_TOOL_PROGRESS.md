# Internal tool expansion progress

Updated: 2026-11-15 (Asia/Calcutta)

**Verified completion: 85%.** This measures the new scope independently of the original project.

| Checkpoint | Weight | Status | Evidence |
|---|---:|---|---|
| Scope and plan | 5% | Complete | INTERNAL_TOOL_PLAN.md |
| Authentication and migrations | 15% | Complete | Session/CSRF/role tests; seeded PostgreSQL deployment |
| Hospital/reviewer workflow | 20% | Complete | 24 focused tests; deployed Edge browser and PostgreSQL API acceptance |
| Ollama recommendations | 15% | Complete | Restored index; grounded acceptance, outage, model/resource and token-ledger evidence |
| Precedent eligibility and semantic evaluation | 5% | Complete | Guards pass; calibration-only threshold search and held-out artifact |
| Precedent automation integration | 15% | Complete | Real-model/PostgreSQL automatic approval/rejection; reviewer controls; safety and rollback tests |
| Deployment and telemetry smoke | 5% | Complete | Eight running services; four healthy scrape targets; provisioned Grafana and Jaeger traces |
| Multiworker deployment validation | 5% | Complete | Three replica scrape histories, real Redis mutex check, restart/readiness and persisted-case recovery |
| Performance validation and handover | 15% | In progress | Locust workload/launcher written; actual runs pending |

## 40% checkpoint evidence

- Focused regression: 24 tests passed covering authentication, expiry/logout, CSRF, hospital isolation, validation, idempotency, approval/rejection, clarification/resubmission, status filtering, and precedent guards.
- Real Edge browser: hospital form submission -> asynchronous review-ready -> reviewer clarification -> hospital revision 2 -> human approval visible to hospital. Zero page JavaScript errors; desktop and 390px mobile screenshots inspected, no horizontal overflow.
- Real PostgreSQL API: forged hospital identity replaced with authenticated identity; cross-hospital case/run reads return 404; duplicate request returns existing case; competing reviewer decisions return exactly one 200 and one 409.
- API, worker, PostgreSQL and Redis are healthy on standalone Ubuntu WSL Docker Engine. API readiness returns ready. Corrected image build succeeds without a redundant final setuptools download.
- Artifacts: docs/evidence/workflow-browser.json, workflow-api.json, hospital-case.png, hospital-case-mobile.png. Reproduction: scripts/verify_workflow_browser.py and scripts/verify_workflow_api.py.

## 60% checkpoint evidence (2026-11-15)

- Restored 109 policy chunks with MiniLM embeddings; expected PDF checksum confirmed by the ingestion manifest.
- Selected installed qwen2.5-coder:7b Q4_K_M after llama3.2:3b produced inaccurate policy explanations. Neither a larger model nor a download was needed.
- Grounded deployed cases: waiting served -> approve recommendation with B.1.1/C.1.b citations; waiting unserved -> human review; unsupported procedure -> human review; injection -> blocked before model access.
- Provider outage test -> degraded human review with citations preserved; real endpoint restored afterwards.
- Fixed Ollama grammar compiler limits by omitting large maximum-length constraints only from the provider grammar. Pydantic continues validating full schema/length constraints. Meaningful minimum content remains constrained.
- Model explanations remain imperfect. The UI displays the verified policy explanation; generated rationale is retained separately for audit. This is hybrid decision support, not unconstrained model adjudication. Conservative waiting-period review is intentional; automatic rejection quality is not claimed.
- Warm inference samples approximately 3.8–4.2 seconds; first 7B comparison inference 11.44 seconds including loading. Latest sequential case times and token ledger are in docs/evidence/grounded-model.json. These are acceptance samples, not load percentiles.
- Resource sample: GPU around 5.2 GB of 6 GB, worker around 325 MiB; exact model digest and RAM/container samples in docs/evidence/model-resources.json. Samples are not peaks; no capacity/soak claim.
- Semantic threshold 0.72 selected using a declared calibration-only 0.01 grid. Held-out results: zero false matches out of two negatives, one true match out of two positives (50% recall). The small synthetic fixture is insufficient for production validation.
- 35 focused security/workflow/model/reliability tests pass; 38 existing agent/retrieval/guardrail/reliability/traffic tests also pass. Reliability tests overlap across these runs; counts are not additive.
- Assessment model, prompt version, inference time, token counts and zero notional local-provider cost are persisted and traceable.
- Added WSL Ollama launcher and dynamic gateway handling to the Compose wrapper. Persistent image rebuilt; real Ollama endpoint restored.

## 80% checkpoint evidence (2026-11-15)

- Real Ollama/PostgreSQL flow passed: human approval -> semantic-paraphrase automatic approval; human rejection -> semantic-paraphrase automatic rejection. Notes and changed costs force human review. Revocation prevents future reuse. Human override changes the decision, retains history and disables its precedent.
- Reviewer browser acceptance passed: reusable-decision inspection/disable, automatic-decision override, human outcome display, no JavaScript errors and no mobile horizontal overflow. Screenshots were inspected.
- Automated integration tests cover conflicts, revoked precedents, changed policy version/wording, material facts, model disagreement, missing calibration and embedding changes. Additional code gates enforce review for pre-existing conditions, emergencies, deluxe rooms and notes regardless of model flags.
- Automatic case decisions now flush into the same transaction as the terminal run result; rollback protection was tested. Automatically decided cases never become new precedents themselves.
- 52 focused security/workflow/model/automation/reliability tests pass. 38 existing agent/retrieval/guardrail/reliability/traffic tests pass separately; these counts overlap.
- Persistent image build passed; API and worker were redeployed. Eight services are running: API, worker, PostgreSQL, Redis, Prometheus, Grafana, Jaeger and Redis exporter.
- Prometheus has four healthy configured targets (API, worker, Redis and itself). The desk profile excludes disabled stub/cAdvisor targets. Grafana provisioning and database health pass; its dashboard renders in Edge. Jaeger contains API and worker services and actual worker traces.
- Worker processing p50/p95/p99 chart added, explicitly excluding queue wait. Worker/provider histograms now cover local-model latencies through 120/90 seconds. Case submissions feed intake metrics; local inference records zero notional provider cost.
- Published OpenAPI contract refreshed. Evidence: docs/evidence/precedent-flow.json, precedent-browser.json, monitoring-smoke.json and corresponding PNGs. Reproduction scripts: verify_precedent_flow.py, verify_precedent_browser.py, verify_monitoring.py.

## Important boundary

Guarded automation is enabled in the local synthetic desk Compose profile after acceptance. Base application settings remain opt-in; PRECEDENT_AUTOMATION_ENABLED=false disables it. Human reviewers explicitly authorize reusable precedents; unqualified/exceptional or conflicting cases still require review. All synthetic acceptance precedents were disabled by the revocation/override tests, so a new matching scenario first requires a new reusable human decision.

The 10% deployment checkpoint is now split into 5% verified telemetry/deployment smoke and 5% pending multiworker deployment validation. Total scope/weight is unchanged. No actual load, stress, soak or scaling-capacity claim is made. The small semantic fixture still has only 50% positive recall on its held-out set; matching remains intentionally conservative.

## Environment and recovery

- Host: 16 GB RAM, i7-13620H, RTX 4050 Laptop GPU (6 GB VRAM).
- Installed llama3.2:3b previously returned needs_information for missing evidence; cold request was 27.36 seconds including 19.36 seconds loading. Not a quality/capacity benchmark.
- Docker Desktop failed on stale Windows sockets even after factory reset/reboot. Replaced its execution path with official Docker Engine 29.9.3 and Compose in existing Ubuntu 24.04 WSL2. hello-world passed.
- Keep Ubuntu active during use. Background systemd services alone did not keep this WSL distro alive between commands. Added restart policies and scripts/compose_wsl.ps1.
- Preserved pre-existing shell/Python script modifications.

## Next checkpoint: 90%

Resume staged load/stress only after host RAM is above the configured reserve. Current benchmark was interrupted by the RAM guard, so 90% has not been earned. See BENCHMARK_LOCAL.md and raw evidence. Soak and handover remain pending.

## Update convention

Earn checkpoint weights only after all exit checks pass. Record actual evidence and limitations at each checkpoint. Do not treat written code or planned tests as verified completion.

## 85% checkpoint and capacity blocker

- Three worker endpoints were observed healthy by Prometheus. Real independent Redis lock clients confirmed maximum one simultaneous inference-slot holder. Single-worker restart recovered health/readiness and preserved historical case data; queue depth before restart was zero.
- Evidence: worker-replica-history.json and worker-recovery.json.
- Locust was stopped by the RAM guard. First run: three completed observations, zero observed failures, one unobserved assessment. Recovery: two completed observations, zero observed failures, one unobserved assessment. Both stopped; neither is a capacity pass.
- Returned to one worker. Benchmark supervisor now refuses both initial and recovery load below the reserve; guard regression test passes.
- Application implementation committed as 1ed9eb8 and pushed to GitHub branch codex/internal-policy-desk. Benchmark evidence and supervisor correction follow in a separate commit. Pre-existing script permission changes remain unstaged.
