# Faculty demonstration runbook

**Project:** Health Insurance Pre-Authorisation Desk

**Environment:** Windows PowerShell 5.1/7, Ubuntu WSL Docker Engine, local Ollama

**Presentation order:** startup -> usage demo -> automated load demo -> Grafana -> Prometheus -> traces -> results -> shutdown.

**Two independent stages:** Stage A is your personal claim review. Stage B starts only when you explicitly trigger the generator. Nothing automatically moves from one stage to the other; take as long as you want between them.

Follow the numbered steps in order. All claims and reviewer actions in the automated demo are synthetic. This guide assumes the existing model, policy PDF, index and Python environment on this machine are already installed.

## 1. Prepare before the faculty arrives

- Close unused applications and browser tabs. Aim for **at least 3-4 GiB free RAM after the app starts**, to leave room for model loading. The actual guard requires about **2.36 GiB available RAM** on this 16 GB laptop; total installed RAM is not the same as available RAM.
- Keep the laptop connected to power and use **one worker**.
- Use the local application and monitoring services; Docker Desktop is not required.
- Keep this runbook open. Do not run a stress benchmark at the same time as the presentation traffic.

Opening statement:

> This is an internal hospital-to-insurer pre-authorisation workspace. It combines policy retrieval, deterministic verification, a local AI recommendation and human-authorized precedent reuse. I will first show the workflow manually, then generate synthetic traffic and inspect its telemetry.

## 2. Open Ubuntu and keep it running

In **terminal tab A**, run:

```powershell
wsl -d Ubuntu
```

Leave this tab open for the entire demonstration. If Docker is not running, execute this **inside the Ubuntu tab**:

```bash
sudo systemctl start docker
```

## 3. Stage A: start each service yourself

Use **terminal tab B: PowerShell**. Run the following blocks separately, waiting for each to finish. This uses the individual commands rather than the combined demo launcher.

Set the project directory:

```powershell
Set-Location 'D:\Fedora-Recovery\Projects\mlsd-mini-project'
```

Start the bounded local model server:

```powershell
./scripts/start_ollama_wsl.ps1
```

Build the application image (needed after code changes; otherwise you can reuse the existing image):

```powershell
./scripts/compose_wsl.ps1 build api worker
```

Start the database and queue:

```powershell
./scripts/compose_wsl.ps1 up -d --no-deps --wait postgres redis
```

Start the API and one worker:

```powershell
./scripts/compose_wsl.ps1 up -d --no-deps --wait api worker
```

Start monitoring:

```powershell
./scripts/compose_wsl.ps1 --profile observability up -d --no-deps prometheus grafana jaeger redis-exporter
```

Check the containers:

```powershell
./scripts/compose_wsl.ps1 ps
```

These commands start the application only. **They do not generate claims or record reviewer decisions.** Existing accounts, policy index and database are reused on this machine.

If PowerShell blocks scripts, run `Set-ExecutionPolicy -Scope Process Bypass` in tab B and retry. For a fresh database/index rather than this existing installation, follow [the setup guide](docs/INTERNAL_TOOL_DEMO.md), including ingestion and account seeding.

**Open next:** [API readiness](http://localhost:8000/readyz). Expect `{"status":"ready"}`. Then open [Policy Desk](http://localhost:8000/).

Do not proceed if startup fails. Use the recovery section at the end; a successful image build alone does not mean the app or traffic generator is running.

## 4. Usage demo: submit a claim as hospital staff

In **tab B**, generate a unique synthetic procedure tag for this presentation:

```powershell
'FAC-' + (Get-Date -Format 'MMddHHmmss')
```

Copy the printed tag, for example `FAC-1120101530`. Reuse that exact tag in the equivalent follow-up claim below. It makes the first scenario new to this presentation instead of accidentally matching an old rehearsal precedent.

**Open:** [Policy Desk](http://localhost:8000/).

1. Click **Hospital Staff**.
2. Click **New request**, then **Fill sample claim**.
3. Replace **Procedure code** with the generated `FAC-...` tag. Leave the sample procedure description unchanged.
4. Point out the policy number, policy dates, admission, diagnosis, procedure and estimated cost. The sample policy number `SYN-POL-0001` passes the server's format validation.
5. Click **Submit for assessment** and wait for processing to finish.

Explain:

> Submission is asynchronous. The API records the claim and queues a processing run. The worker retrieves policy clauses, verifies the evidence and obtains a structured local-model assessment. A new case is presented for human review.

The initial request uses synthetic cataract details, INR 500,000 sum insured and INR 75,000 estimated cost. Autofill does not submit until the button is clicked.

## 5. Complete your personal review; then pause here

Continue at [Policy Desk](http://localhost:8000/).

1. **Sign out**, then click **Claims Reviewer (Insurer)**.
2. Open the new case at the top of the list.
3. Show the **AI case summary**, **AI suggestion**, verified policy explanation and expandable policy citations.
4. For an eligible approval/rejection, show the **Allow reuse for equivalent cases** checkbox. Leave it checked if you want to demonstrate reuse.
5. Click **Accept AI suggestion**. Alternatively, explain the manual outcome/reason controls.
6. Show the final decision and case history. The decision source is **human**, because a reviewer explicitly authorized it.
7. Sign out and choose **Hospital Staff** again. Show the final decision from the hospital side.

**Your personal review is now complete. Stop here and discuss it for as long as you want. No load generator has been started.**

Optional reuse demonstration before moving on:

1. Create another request with **Fill sample claim**. Replace **Procedure code** with the **same `FAC-...` tag**, and keep all other material fields equal to the first request.
2. Submit it. If the current assessment agrees and all guards pass, show the automatic decision with source **precedent**.

Explain:

> A previous human decision can authorize an equivalent case. Similar wording alone is insufficient: policy version, material facts, evidence and exception gates must also match. Automatic decisions do not create new precedents.

If the model asks for information or a gate fails, show that review route honestly. Do not force a reusable outcome to make the presentation appear successful. Historical cases can lack the newer summary; use a fresh request for that feature.

**Optional exception demonstration:** submit the same sample/tag with a nonempty additional-circumstances note. Show that it returns to review rather than blindly copying the precedent. The automated demo below also covers exceptions and clarification.

## 6. Stage B: trigger automated traffic only when you are ready

This is a separate action after your personal review. Keep Ubuntu tab A open and use PowerShell tab B. First check available memory:

```powershell
.venv/Scripts/python.exe scripts/traffic_demo.py --preflight
```

Expect `ready: true`. If it reports `false`, free memory before continuing. The launcher also checks this and refuses to start below the reserve.

Choose your own duration and pace. Edit these values before launching:

```powershell
$demoMinutes = 15
$pauseSeconds = 8
```

- `$demoMinutes` is the maximum run duration (1-120 minutes). You can stop it earlier whenever you want.
- `$pauseSeconds` controls the pause between scenarios (5-60 seconds). Increase it for slower activity, decrease it for more frequent requests. Model processing and simulated reviewer time are additional, so this is not an exact requests-per-second setting.

**This next command is the point where automatic claims begin:**

```powershell
./scripts/start_traffic_demo.ps1 -Minutes $demoMinutes -IntervalSeconds $pauseSeconds
```

The generator runs in the background, leaving your PowerShell prompt free. It confirms an actual first submission before reporting active traffic. The manual review does not trigger this command for you.

**Open now:** [Grafana](http://localhost:3000/d/preauth-overview?from=now-15m&to=now&refresh=5s) and [Prometheus](http://localhost:9090/graph). The detailed walkthroughs are in steps 8 and 9; move between dashboards at your own pace.

The automated sequence seeds eligible simulated reviewer approvals/rejections, replays matching cases, and exercises exceptions, clarification/resubmission, injection and unsupported procedures. It acts only on its own cases and stops at your duration limit or a safety limit. This is paced presentation traffic, not a maximum-capacity benchmark.

Stop automated submissions whenever you want, while leaving the app and dashboards running:

```powershell
./scripts/stop_traffic_demo.ps1
```

To change speed, stop the current run first, edit `$pauseSeconds`, then launch a new run with the same start command. Normal stop drains the current assessment and disables that run's temporary precedents. Restarting creates a fresh demo sequence; it does not resume the old one.

If you prefer live events in the terminal, use this **instead of** the background command:

```powershell
./scripts/start_traffic_demo.ps1 -Minutes $demoMinutes -IntervalSeconds $pauseSeconds -Foreground
```

For foreground mode, leave tab B running and use a separate PowerShell tab C for status/stop commands. Do not start foreground and background generators together.

Explain:

> First I submitted and reviewed a case myself. Now I have independently started the synthetic workload. Its duration and pace are configurable, and I can stop it without shutting down the system.

## 7. Confirm that automation is actually generating claims

Open **terminal tab C: PowerShell**:

```powershell
Set-Location 'D:\Fedora-Recovery\Projects\mlsd-mini-project'
./scripts/status_traffic_demo.ps1
```

Expect **Automated traffic: RUNNING**, with `submitted` and `assessments` increasing across checks. The output also distinguishes simulated reviewer outcomes and precedent outcomes.

**Do not infer automation from Grafana merely being open or showing a count of one.** Those can be manual decisions. If status says STOPPED, read its stop reason. A RAM-reserve stop means the runner intentionally stopped, not that requests are secretly continuing.

For the background run, optional live logs in tab B or C:

```powershell
Get-Content .runtime/traffic-demo/console.log -Wait
```

Press **Ctrl+C** to stop watching the log; this does not stop the background generator. Then tab C can accept other commands again.

## 8. Open Grafana and explain the live behavior

**Open:** [Grafana - last 15 minutes, five-second refresh](http://localhost:3000/d/preauth-overview?from=now-15m&to=now&refresh=5s).

Allow approximately one minute of traffic for useful rate curves. Present these panels in order:

| Panel | What to show / explain |
|---|---|
| Case decisions per minute - reviewer vs precedent | Separate simulated reviewer activity from precedent-based decisions; show changing rates |
| Decisions since service start | Approved, rejected and information-requested totals by decision source |
| Worker processing p50 / p95 / p99 | Median and tail processing latency; these worker measurements exclude queue and reviewer time |
| Run throughput by status | Completed versus intentionally escalated processing |
| Provider latency / retry rate | Local-model serving behavior |
| Circuit breaker / index / resource panels | Dependency protection, indexed corpus and operational context |

Important interpretation:

- `human` means a reviewer-account decision. In this automated run that reviewer is **simulated**, and the decision reason explicitly says so.
- `precedent` means an automatic decision using an eligible prior human authorization.
- Counts include manual and automated activity and **reset on service process restart**; they are not the durable database ledger.
- Escalation is not necessarily an error: guardrail or unsupported cases deliberately go to review. Degraded/failed processing is treated as a failure and stops new demo traffic.
- For counts belonging only to this generator, show the status command from step 7.

## 9. Open Prometheus and run these queries in order

**Open:** [Prometheus query page](http://localhost:9090/graph).

Paste **one expression at a time** into the query box and click **Execute**. Use **Table** for current values and **Graph** for history; choose a recent **15-minute** range. Execute again to refresh, or use auto-refresh if available in the installed UI.

### 9.1 Confirm the scrape targets are reachable

```promql
up
```

Show **Table**. `1` means the target's latest scrape succeeded; `0` means it failed. This checks scraping, not every model/database dependency. You can also open [Prometheus targets](http://localhost:9090/targets).

### 9.2 Show decision totals by outcome and source

```promql
sum by (outcome, source) (preauth_case_decisions_total)
```

Show **Table**. Point out `approved`, `rejected`, `information_requested`, `human` and `precedent`. These totals have the same process-reset/manual-activity limitations as Grafana.

### 9.3 Show decisions per minute

```promql
sum by (outcome, source) (rate(preauth_case_decisions_total[2m])) * 60
```

Switch to **Graph**. Explain that `rate` converts a counter into recent activity per second and multiplying by 60 presents it per minute. Rates can be fractional because they are estimated over a time window.

### 9.4 Show worker throughput per minute

```promql
sum by (status) (rate(preauth_worker_runs_total[2m])) * 60
```

Show **Graph** and compare completed/escalated series with the scenarios visible in the terminal.

### 9.5 Show p95 worker processing latency

```promql
histogram_quantile(0.95, sum by (le) (rate(preauth_worker_run_seconds_bucket[5m])))
```

The result is in **seconds**. Replace `0.95` with `0.50` or `0.99` to show p50 or p99. These values exclude queue wait and simulated reviewer time. Small samples make p99 weak evidence. A blank/NaN result without recent samples is not a zero-latency measurement.

Explain:

> Prometheus stores and queries the underlying time series. Grafana presents those series as dashboards. The same metric can be inspected directly with PromQL or visualized in a panel.

## 10. Show tracing and the API contract

**Open:** [Jaeger](http://localhost:16686/).

1. Select the `preauth-worker` service.
2. Search recent traces using **Find Traces**.
3. Open a recent trace and inspect its spans/timing. Use run/correlation identifiers from the application or logs when relating a specific request to its processing.

Explain that traces help diagnose where one request spent time, whereas aggregate metrics show behavior across many requests. Do not infer queue or human-review duration solely from worker spans.

**Open next:** [Interactive API documentation](http://localhost:8000/docs). Show the authentication, case, decision and precedent endpoints. The APIs enforce role/ownership and revision checks independently of which UI controls are visible. Normal account login and CSRF requirements still apply when trying mutations.

Optional supporting links:

| Link | Purpose |
|---|---|
| [OpenAPI JSON](http://localhost:8000/openapi.json) | Machine-readable endpoint/schema contract |
| [API raw metrics](http://localhost:8000/metrics) | Prometheus-format metrics exposed by the API |
| [API liveness](http://localhost:8000/healthz) | Basic API liveness |
| [API readiness](http://localhost:8000/readyz) | API dependency readiness |

## 11. Present measured results without overstating the live demo

**Open:** [Measured performance report](docs/INTERNAL_TOOL_PERFORMANCE.md), then the [full technical PDF](output/pdf/Policy_Desk_Technical_Document.pdf) if faculty request design detail.

Key reported results:

| Recorded experiment | Result to present |
|---|---|
| One worker, eight-user v1 workload | 61 assessments, zero errors; p95 23 seconds, p99 25 seconds; about 0.310 assessments/second |
| One worker, sixteen-user v1 stress workload | Saturated the p95 target: p95 47 seconds; adding demand mostly increased queueing |
| Matched three-worker comparison | One degraded result out of 52; no demonstrated throughput benefit under one inference slot |
| User-adjusted five-minute v1 stability run | 56 assessments, zero errors/missing observations; p50 4.1s, p95 7.1s, p99 7.2s |

Explain:

> The live automated sequence demonstrates the workflow and telemetry. Separate retained experiments measured capacity and saturation. More workers do not create more GPU inference capacity when all workers share one model slot.

The recorded performance matrix used the earlier **v1 prompt**. The current **v2 prompt** adds AI case summaries and has functional acceptance, but the full capacity/soak matrix has not been repeated for it. The five-minute run does not establish long-duration reliability, and this synthetic system is not clinically validated.

If asked for deeper evidence, open [load/stress results](docs/LOAD_STRESS_RESULTS.md), [progress and acceptance evidence](docs/INTERNAL_TOOL_PROGRESS.md), or [the GitHub branch](https://github.com/SunOrangeBurger/Health-Insurance-Pre-Authorisation-Desk-MLSD/tree/codex/internal-policy-desk).

## 12. Stop the generator, then shut down the application

In **PowerShell tab C**, stop the automated traffic early, or confirm it has finished:

```powershell
./scripts/stop_traffic_demo.ps1
./scripts/status_traffic_demo.ps1
```

The supported stop path drains the current assessment and disables the run's temporary precedents. App and dashboards remain available for discussion. If you chose foreground mode, its terminal returns when the generator exits. If the run has already reached its duration limit, no second generator needs to be stopped.

When the discussion is finished, shut down the full project:

```powershell
./scripts/stop_desk.ps1
```

This stops traffic before backend services, stops project containers and the verified managed Ollama server, and preserves the database, index and model downloads. Finally, close Ubuntu tab A. Do not use `down -v` unless you intend to delete project data. Shared Docker/WSL infrastructure is not forcibly terminated.

## Recovery during a presentation

| Symptom | Check / action |
|---|---|
| Grafana shows only your manual decisions | Run `./scripts/status_traffic_demo.ps1`. Confirm RUNNING and increasing submitted/assessment counts. App startup alone generates no traffic. |
| Status says RAM-reserve stop | Explain the safety guard; close unused apps, rerun preflight, and start the generator again only after it passes. Do not lower the reserve for the presentation. |
| Cannot sustain the live run | Show the retained Grafana history and measured report from step 11, clearly labeling them as earlier evidence. Do not present them as a currently running test. |
| App is unreachable | Check `./scripts/compose_wsl.ps1 ps` and `./scripts/compose_wsl.ps1 logs --tail 100 api worker`; verify Ubuntu remains open. |
| Another generator is already active | Stop it with the supported helper before launching a new one. Do not launch foreground and background modes together. |
| Ollama launcher reports an unmanaged listener | Exit that Ollama instance, then retry the bounded application launcher. |
| A case does not auto-approve/reject | Show the recommendation, eligibility and exception gates. Human review is a valid conservative result. |
| Cleanup reports a failure | Read the run summary and owned-precedents record under `.runtime/traffic-demo/`; disable the recorded synthetic precedents through the reviewer workspace. Avoid forcibly killing the runner during cleanup. |

For additional setup/operation detail: [Windows run guide](docs/HOW_TO_RUN.md), [automated demo guide](docs/AUTOMATED_DEMO.md), [demo accounts/model setup](docs/INTERNAL_TOOL_DEMO.md), and [operations runbook](docs/RUNBOOK.md).
