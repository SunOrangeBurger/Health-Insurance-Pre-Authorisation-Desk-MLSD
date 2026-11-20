$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$stateFile=Join-Path $projectRoot '.runtime/traffic-demo/state.json'
if (-not (Test-Path -LiteralPath $stateFile)) { Write-Output 'No demo run recorded.'; exit 0 }
$state=Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
$process=Get-CimInstance Win32_Process -Filter "ProcessId=$($state.pid)"
$active=$process -and $process.CommandLine -match 'traffic_demo\.py' -and (Test-Path (Join-Path $projectRoot '.runtime/traffic-demo/runner.lock'))
if ($active) { Write-Output 'Automated traffic: RUNNING' } else { Write-Output 'Automated traffic: STOPPED' }
Write-Output "Run: $($state.run_id)"
$liveFile=Join-Path $state.output 'live.json'
$summaryFile=Join-Path $state.output 'summary.json'
if ((-not $active) -and (Test-Path -LiteralPath $summaryFile)) {
    $record=Get-Content -LiteralPath $summaryFile -Raw | ConvertFrom-Json
} elseif (Test-Path -LiteralPath $liveFile) {
    $record=Get-Content -LiteralPath $liveFile -Raw | ConvertFrom-Json
    Write-Output "Last event: $($record.phase) at $($record.time)"
    Write-Output "RAM at last event: $($record.memory.available_gib) GiB free / $($record.memory.required_gib) GiB reserve"
} else { Write-Output 'Startup pending; inspect console.log and errors.log.'; exit 0 }
if ($record.stop_reason) { Write-Output "Stop reason: $($record.stop_reason)" }
if ($record.error) { Write-Output "Error: $($record.error)" }
if ($record.counts) { $record.counts.PSObject.Properties | Select-Object Name,Value | Format-Table -AutoSize }
if ($record.cleanup_failed_precedents) { Write-Warning 'Temporary precedent cleanup needs attention; inspect summary.json.' }
Write-Output "Logs and summary: $($state.output)"
