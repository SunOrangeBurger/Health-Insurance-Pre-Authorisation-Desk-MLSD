param([ValidateRange(1,120)][int]$WaitSeconds=115)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$control=Join-Path $projectRoot '.runtime/traffic-demo'
$lockFile=Join-Path $control 'runner.lock'
if (-not (Test-Path -LiteralPath $lockFile)) { Write-Output 'No automated demo is running.'; exit 0 }
$runnerPid=[int](Get-Content -LiteralPath $lockFile -Raw)
$runner=Get-CimInstance Win32_Process -Filter "ProcessId=$runnerPid"
if (-not $runner) { Write-Output 'Demo is not running; inspect the last summary for cleanup status.'; exit 0 }
if ($runner.CommandLine -notmatch 'traffic_demo\.py') { throw 'Recorded PID is not a verified demo runner; no process was stopped.' }
New-Item -ItemType File -Force -Path (Join-Path $control 'stop') | Out-Null
Write-Output 'Stopping new demo requests; draining the current assessment and disabling run-owned precedents...'
$deadline=(Get-Date).AddSeconds($WaitSeconds)
while ((Test-Path -LiteralPath $lockFile) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 1 }
if (Test-Path -LiteralPath $lockFile) { throw 'Shutdown is still pending. Inspect the demo log before stopping backend services.' }
$state=Get-Content -LiteralPath (Join-Path $control 'state.json') -Raw | ConvertFrom-Json
$summaryFile=Join-Path $state.output 'summary.json'
if (-not (Test-Path -LiteralPath $summaryFile)) { throw 'Runner exited without a summary. Inspect the log and owned-precedents.json before stopping the app.' }
$summary=Get-Content -LiteralPath $summaryFile -Raw | ConvertFrom-Json
if (@($summary.cleanup_failed_precedents).Count -gt 0) { throw 'Temporary precedent cleanup failed. Inspect summary.json and disable the listed IDs.' }
Write-Output 'Automated demo stopped. App and dashboards remain running.'

exit 0
