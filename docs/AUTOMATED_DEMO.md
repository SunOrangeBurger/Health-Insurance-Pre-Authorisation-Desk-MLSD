# Watch an automated Policy Desk demonstration

This creates synthetic requests and simulated reviewer decisions through the real application APIs and Ollama. It is a presentation workload, not a capacity benchmark. It never reviews unrelated inbox cases. Demo case reasons explicitly label reviewer actions as simulated.

## Start

Start the application first as described in HOW_TO_RUN.md, and keep Ubuntu WSL open. In PowerShell at the project root:

```powershell
./scripts/start_traffic_demo.ps1
```

The launcher first checks available RAM and confirms the first claim submission before reporting active traffic. If resources change afterward, the runner can pause or stop; check its status rather than assuming a launched process stayed active.

The default is **15 minutes**, one request at a time, with an **8-second pause** between scenarios plus model processing and simulated reviewer time. The runner uses the published synthetic account passwords by default; DESK_HOSPITAL_PASSWORD and DESK_REVIEWER_PASSWORD environment variables override them if needed.

For a different presentation duration:

```powershell
./scripts/start_traffic_demo.ps1 -Minutes 30 -IntervalSeconds 10
```

Intervals are limited to 5-60 seconds and duration to 1-120 minutes. This runner does not scale workers or increase Ollama concurrency. The v2 model prompt is used; earlier v1 capacity numbers are not a new benchmark for this demo.

## Watch

- Grafana: http://localhost:3000/d/preauth-overview?from=now-15m&to=now&refresh=5s
- Prometheus: http://localhost:9090/
- Cases: http://localhost:8000/ (either demo role)
- Traces: http://localhost:16686/

The two new panels at the top of Grafana show **Case decisions per minute - reviewer vs precedent** and **Decisions since service start**. Existing panels show worker latency p50/p95/p99, throughput, provider latency and resource signals. Allow roughly a minute for useful rate curves to develop. The dashboard refreshes every five seconds; select a time range containing the run.

Useful Prometheus expressions:

```promql
sum by (outcome, source) (preauth_case_decisions_total)
sum by (outcome, source) (rate(preauth_case_decisions_total[2m])) * 60
sum by (status) (rate(preauth_worker_runs_total[2m]))
histogram_quantile(0.95, sum by (le) (rate(preauth_worker_run_seconds_bucket[5m])))
```

Decision outcomes are approved, rejected and information_requested. Sources are human (reviewer-account API decisions, including this simulated reviewer), precedent (automatic reuse), and human_override. These are process counters that reset on service restart, not a durable database ledger. The counters include manual activity as well as demo activity. Case reasons and the runner's event log distinguish simulated reviewer actions. Worker processing latency excludes queue wait and simulated reviewer think time.

## What happens automatically

1. A novel cataract claim receives a simulated reviewer approval, reusable only when the normal eligibility checks permit it.
2. An unserved-waiting-period case receives a corresponding simulated reviewer rejection and eligible reusable precedent.
3. Equivalent approval and rejection cases exercise automatic precedent responses.
4. Mitigating circumstances and a changed cost require one-off review.
5. A clarification is requested; the hospital resubmits a new revision, which is assessed again.
6. Injection and unsupported-procedure cases receive requests for information instead of automatic approval.
7. The mixed cycle repeats until duration/stop/resource limits are reached.

If the AI cannot support an expected seed recommendation, the runner asks for information rather than bypassing eligibility. Consequently actual automation counts depend on the current real-model output. A degraded/failed assessment stops new demo load and is reported as an error, not disguised as a successful decision.

Each run uses a unique synthetic policy/procedure tag. It records only its own case IDs and temporary precedent IDs. Normal shutdown disables its temporary precedents while preserving case/review history. Automated outcomes cannot create further precedents. Real manual case submissions can continue separately, but the demo will not review them.

## Stop just the traffic

```powershell
./scripts/stop_traffic_demo.ps1
```

The runner stops new submissions, finishes the current assessment, disables its temporary precedents and writes a summary. The app and dashboards remain available. Allow up to about two minutes if a model request is slow. Do not forcibly kill the runner while it is cleaning up.

To stop traffic and the full application:

```powershell
./scripts/stop_desk.ps1
```

## Logs and safety limits

```powershell
Get-Content .runtime/traffic-demo/console.log -Wait
Get-Content .runtime/traffic-demo/errors.log
```

State is stored in .runtime/traffic-demo/state.json. Each run has a subdirectory containing events.jsonl, summary.json and owned-precedents.json. The summary lists submissions, assessments, simulated reviewer outcomes, automatic outcomes and cleanup failures. These transient run artifacts are Git-ignored.

New requests pause immediately below max(2 GiB, 15% physical RAM), and the run stops after 30 seconds below reserve. On this 16 GB laptop the reserve is about 2.36 GiB. The demo also stops if the existing queue exceeds eight queued/running jobs or its oldest age exceeds 90 seconds. It does not close user applications or lower the application's 64-job capacity cap.

If the runner stops early, read the stop_reason/error and cleanup_failed_precedents in summary.json. Free unused memory before retrying a RAM-guard stop. A second runner is refused while the first owns its lock. After a forced termination or machine crash, cleanup is not guaranteed: inspect owned-precedents.json and disable those synthetic entries in the reviewer workspace before restarting. Normal stop is the supported cleanup path.


## Confirm traffic and diagnose a flat dashboard

```powershell
./scripts/status_traffic_demo.ps1
```

This shows RUNNING/STOPPED, generated-claim/assessment counts, the latest event and any stop reason. The app and dashboards can be healthy while the generator is stopped. Grafana's decision totals include manual activity and reset on service restart, so a small nonzero count alone does not prove automatic traffic.

To keep progress and guard messages visible in the terminal:

```powershell
./scripts/start_traffic_demo.ps1 -Minutes 15 -IntervalSeconds 8 -Foreground
```

Use this instead of starting a second background runner. The stop helper still works from another terminal. RAM checks concern free memory after Windows, WSL, Ollama and other apps, not the machine's total 16 GB. Startup preflight returns an explicit error and generates no claims below the reserve. The first-submission check does not promise the process can never stop later; consult status/live logs if the graphs flatten.


## Using the Prometheus page

1. Open http://localhost:9090/graph.
2. Paste **one** PromQL expression into the expression box and click **Execute**.
3. Choose **Table** for current label/value pairs, or **Graph** for changes over time. Use a recent 15-minute range for a demo.
4. Execute again to refresh; enable the page's auto-refresh control if available in the installed UI.

Start with `sum by (outcome, source) (preauth_case_decisions_total)` for totals. For activity per minute, use the rate expression above. For scrape health, query `up`: 1 means the target scrape succeeded, 0 means it failed. Scrape health alone does not establish every model/database dependency is ready.

The p95 worker expression returns seconds. Change `0.95` to `0.50` or `0.99` for p50 or p99. These worker measurements exclude queue time and simulated reviewer time. Rate and histogram queries need recent samples; a blank/NaN result with no recent work is not a zero-latency measurement. Dashboard totals include manual and automated activity and reset with service processes. The run-specific status command reports only that generator's counts.
