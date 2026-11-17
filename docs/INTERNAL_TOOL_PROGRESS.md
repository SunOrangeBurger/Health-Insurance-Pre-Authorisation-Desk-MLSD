# Internal tool expansion progress

Updated: 2026-11-17 (Asia/Calcutta)

**Verified completion: 100% of the user-adjusted demonstration scope.** This measures the new scope independently of the original project.

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
| Load, stress and worker comparison | 5% | Complete | Completed stages, saturation/recovery and measured three-worker limitation |
| User-adjusted five-minute stability test | 5% | Complete | 56 observations; zero errors/missing cases; automatic and exception outcomes; stable memory |
| Final report and handover | 5% | Complete | 76 tests; rebuilt deployment; repeated real-model acceptance; reports and runbook |

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

## Continued capacity validation

The user freed RAM and testing resumed. Varied prompts still grew runner memory with 7B and 4B models; loading/grammar-only changes did not establish stability. Logs identified the optional 8192 MiB host prompt cache, which grew about 363 MiB per distinct prompt. The project launcher now sets LLAMA_ARG_CACHE_RAM=0. Ten varied real API cases held runner RSS near 769 MB. Qwen3 4B passed grounded/precedent acceptance and is the local default. Sustained reruns are in loadtest/results/desk/cache0; percentage remains 85% until their exit checks pass.

## End-of-day checkpoint — paused by user

**Verified completion remains 85%.** All project workloads stopped at the user's request. Docker volumes, database, index and model downloads were preserved. No queued/running database cases or Redis jobs remained at shutdown.

- Stable cache0 configuration: Qwen3 4B, non-thinking, one inference slot, LLAMA_ARG_CACHE_RAM=0, provider shape-only JSON grammar and full Pydantic/application checks. The earlier memory growth was traced to the runner's default 8192 MiB host prompt cache; changing model size or memory mapping alone was insufficient.
- Completed cache0 one-user 180-second stage: 15 assessments, zero failures, p50 4.1s, p95/p99 5.2s, no unobserved assessments, no resource stop, minimum available RAM about 4.6 GiB.
- Two-user stage was explicitly interrupted by the user before completion. Its periodic CSV contains 24 observations, zero observed failures and p95/p99 7.1s; these are partial results, not a passed complete stage.
- Higher-load stages, worker comparison and the real 30-minute soak remain unfinished. Do not mark 90% or 100% until the remaining tests run.
- Checkpoint artifact: docs/evidence/checkpoint-2026-11-15.json. Stable-profile raw files: loadtest/results/desk/cache0. Earlier failed variants are retained in root/nommap/qwen3/qwen3-shape directories.

### Resume next session

1. Open Ubuntu WSL and keep it active. Set the two demo password environment variables from INTERNAL_TOOL_DEMO.md.
2. Run scripts/start_ollama_wsl.ps1 to start the bounded server, then use scripts/compose_wsl.ps1 to start postgres/redis/api/worker and the observability profile. Never start an unbounded existing Ollama server silently.
3. Preserve the interrupted run, and rerun the remaining stages into a new directory: `.venv/Scripts/python.exe scripts/benchmark_desk.py --workers 1 --users 2 4 8 16 --output-dir loadtest/results/desk/resume-cache0`.
4. Perform the worker comparison, then use the measured sustainable rate to run `--soak-minutes 30 --soak-rps <60-percent-of-measured-rate>` in a fresh output directory.
5. Generate the load/stress and soak reports, complete the handover checks and push updated evidence to codex/internal-policy-desk.

Pre-existing script permission changes remain outside project commits.

## Resumed November 17

The user shortened the required soak to five minutes due to time constraints; optional 30-minute and two-hour profiles remain available. This is short-term stability evidence only. After the user freed host memory, the two-user three-minute stage passed with 27 observations, zero errors, no unobserved cases and p95/p99 7.1 seconds. Higher stages and worker comparison are running. Earlier RAM-guard stops remain retained. Verified completion remains 85% until the next exit checks pass.

Fixed Windows-to-WSL path translation and PowerShell argument forwarding in the deployment helpers. Added benchmark credential preflight, process-tree cleanup, actual elapsed time, GPU samples, exact case-ID capture, histogram snapshots and a soak evaluator. Corrected queue-age measurement to use Redis time because the WSL and Windows clocks differ. Targeted regressions: 71 passed before the additional five-minute profile test.

## 90% checkpoint — load, stress and worker comparison completed

One-worker stages at 2/4/8 users passed the declared latency and error checks. The 16-user stress stage completed 71 assessments without errors but exceeded the p95 target (47 seconds), establishing saturation. Recovery returned p95 to 5.1 seconds with no missing observations. Under the matched four-user workload, three workers produced 52 observations with one degraded failure (1.9%) and 0.279 assessments/second versus 0.291 with one worker; it failed the error target. This comparison is evidence of a limitation, not a scaling success. Three-worker recovery passed and the deployment was returned to one worker.

Raw evidence: loadtest/results/desk/2026-11-17-freed and 2026-11-17-workers3. Exact case-ID phase reports separate queue, retrieval and inference times. A five-minute mixed stability test is now running at 0.1859 assessments/second, approximately 60% of the passing eight-user measured rate. It includes a temporary synthetic human-approved precedent, which will be disabled after testing. Handover remains pending.

## 95% checkpoint — five-minute stability acceptance

The user-adjusted five-minute run completed 56 assessments at 0.1851 assessments/second including startup/drain. Zero errors or unobserved cases; p50 4.1s, p95 7.1s, p99 7.2s. There were 34 precedent approvals, 20 exceptional cases routed to review, and two nominal cases conservatively left for review. No exception was approved. The temporary test precedent was disabled afterwards. Mean RSS growth between the 60–120s and final-minute windows was 0.017% API and 0.102% worker; Ollama RSS decreased. Queue depth peaked at two, age at 8.19s, minimum free RAM 3.88 GiB, sampled GPU memory 3301 MiB. The monitor covered 297 seconds because of five-second sampling; actual supervisor runtime was 302.5 seconds for the 300-second Locust workload. The evaluator now distinguishes runtime from resource sampling coverage, with a regression check for that boundary.

Final review added a 64-job queue cap serialized by a shared Redis admission lock. Full queues leave desk cases visible for human review without an automated decision; the legacy endpoint returns 503. Concurrent-admission and safe-overload tests passed. Final regression count: 76 passing tests. Images are being rebuilt before final handover. The 90% checkpoint was pushed as ee1661b.

## 100% checkpoint — revised demonstration scope complete

The user-requested five-minute stability run replaces the originally planned 30-minute requirement; longer soak profiles remain optional and unverified. Final images rebuilt successfully with the bounded queue helper. All eight services run, API/worker/database/Redis health checks pass, API readiness is ready, all four Prometheus targets are up, Grafana is provisioned and Jaeger receives traces. Final real-model/PostgreSQL acceptance repeated hospital isolation, idempotency and concurrent review (exactly 200/409), automatic semantic approval/rejection, mitigating circumstances, revocation and human override. The live Redis capacity probe added no job and released its lock. Test-created precedents were disabled. No load generator remains active; the app is left running with one worker.

Final evidence: final-deployment-2026-11-17.json, queue-capacity-live.json, workflow-api.json, precedent-flow.json, monitoring-smoke.json and the five-minute soak artifacts. Performance and caveats are in INTERNAL_TOOL_PERFORMANCE.md; operation and restart instructions are in INTERNAL_TOOL_DEMO.md and RUNBOOK.md. Regression: 76 passed. GitHub checkpoints ee1661b (90%) and 4db9723 (95%) were pushed; final handover follows on the same authorized branch.

100% means the agreed synthetic internal-tool scope is implemented and verified under the revised test duration. It does not mean production or clinical readiness: five minutes does not establish long-duration stability, model prose remains imperfect, semantic fixtures are tiny with 50% positive recall, p99 samples are small, and three-worker error SLO failed. One worker is the measured local recommendation. The earlier stub scaling result is not a real-model capacity claim. Pre-existing script permission changes remain untouched and unstaged.

## Demo login shortcuts

Added one-click Hospital Staff and Claims Reviewer (Insurer) buttons using the public synthetic accounts through the existing login endpoint. Rebuilt API/worker images and verified both authenticated roles in Edge, sign-out, no JavaScript errors and 390px mobile layout. Evidence: demo-login.json and desktop/mobile screenshots.
