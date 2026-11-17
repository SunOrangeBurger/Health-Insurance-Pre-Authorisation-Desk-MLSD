# Run Policy Desk on this Windows machine

The verified setup uses Docker Engine inside Ubuntu WSL and Ollama on Windows. Docker Desktop is not required. The existing database, policy index and downloaded model are preserved between runs.

## 1. Keep Ubuntu open

Open a terminal tab and run:

```powershell
wsl -d Ubuntu
```

Leave that tab open while using the app. It keeps the WSL environment active. If Docker is not running inside Ubuntu, run `sudo systemctl start docker` there.

## 2. Start from a separate PowerShell tab

```powershell
Set-Location 'D:\Fedora-Recovery\Projects\mlsd-mini-project'
$env:DESK_HOSPITAL_PASSWORD = 'Hospital-demo-2026'
$env:DESK_REVIEWER_PASSWORD = 'Reviewer-demo-2026'
./scripts/demo_desk.ps1 -SkipIngest
```

This starts bounded Ollama, builds the app, starts its database/queue/API/worker, seeds the demo accounts and starts monitoring. Allow the command to finish. Use `-SkipIngest` on this machine because its policy index is already populated. Omit that option if you intentionally need to build a missing index from the policy PDF.

If PowerShell blocks local scripts, run `Set-ExecutionPolicy -Scope Process Bypass` in that tab and retry. This lasts only for the current PowerShell process. If an unmanaged Ollama server is already listening, exit that Ollama instance, then retry the launcher so the project's bounded settings apply.

## 3. Open and demonstrate the app

Open **http://localhost:8000/**.

1. Click **Hospital Staff** to log in.
2. Click **New request**, then **Fill sample claim**.
3. Review the synthetic details and click **Submit for assessment**.
4. Wait for the assessment, then sign out.
5. Click **Claims Reviewer (Insurer)** and open the submitted case.
6. Read the AI summary, suggestion and cited policy evidence.
7. Click **Accept AI suggestion** to record the suggested approval/rejection, or enter a different manual decision. The reuse checkbox controls whether an eligible human decision can authorize future equivalent cases.
8. Sign back in as Hospital Staff to see the decision. Equivalent future cases may be answered automatically after a reusable human decision; exceptions still go to review.

Historical cases may not have an AI summary. Submit a fresh sample to demonstrate the new summary prompt. Keep one worker on this laptop; three workers did not improve the measured local throughput.

Manual accounts, if needed:

| Role | Email | Demo password |
|---|---|---|
| Hospital Staff | hospital@desk.local | Hospital-demo-2026 |
| Claims Reviewer | reviewer@desk.local | Reviewer-demo-2026 |
| Second hospital | hospital2@desk.local | Hospital-demo-2026 |

## 4. Check services or inspect monitoring

```powershell
./scripts/compose_wsl.ps1 ps
./scripts/compose_wsl.ps1 logs --tail 100 api worker
```

- Readiness: http://localhost:8000/readyz
- Grafana: http://localhost:3000/d/preauth-overview
- Prometheus: http://localhost:9090/
- Jaeger: http://localhost:16686/

If the app is unreachable, check the startup output and API/worker health first. If the machine is low on RAM, close unused applications before running model workloads. The launcher intentionally limits Ollama memory/concurrency; do not replace it with an unbounded server for the demo.

## 5. Stop when finished

From project PowerShell, run:

```powershell
./scripts/stop_desk.ps1
```

This stops project containers and the verified launcher-owned Ollama server, preserving data. Then close the Ubuntu tab. Shared Docker/WSL infrastructure is not forcibly shut down. Do not use `down -v` unless you intend to delete the demo database/index volumes.

The full technical reference is in `output/pdf/Policy_Desk_Technical_Document.pdf`.
