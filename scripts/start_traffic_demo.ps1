param([ValidateRange(1,120)][int]$Minutes=15, [ValidateRange(5,60)][int]$IntervalSeconds=8, [switch]$Foreground)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$control=Join-Path $projectRoot '.runtime/traffic-demo'
$stateFile=Join-Path $control 'state.json'
$priorRunId=$null
if (Test-Path -LiteralPath $stateFile) {
    $state=Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
    $priorRunId=$state.run_id
    $prior=Get-CimInstance Win32_Process -Filter "ProcessId=$($state.pid)"
    if ($prior -and $prior.CommandLine -match 'traffic_demo\.py') { throw 'The demo is already running. Use stop_traffic_demo.ps1 first.' }
}
$ready=Invoke-RestMethod 'http://localhost:8000/readyz'
if ($ready.status -ne 'ready') { throw 'Start the app with demo_desk.ps1 -SkipIngest first.' }
$python=Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'The project .venv Python environment is missing.' }
$preflightRaw=& $python (Join-Path $PSScriptRoot 'traffic_demo.py') --preflight
$preflightExit=$LASTEXITCODE
$preflight=($preflightRaw -join "`n") | ConvertFrom-Json
if ($preflightExit -ne 0 -or -not $preflight.ready) {
    throw "Demo NOT started: $($preflight.available_gib) GiB RAM free; $($preflight.required_gib) GiB required. Close unused apps and retry. No requests were generated."
}
Write-Output "RAM preflight: $($preflight.available_gib) GiB free / $($preflight.required_gib) GiB reserve."
if ($Foreground) {
    & $python -u (Join-Path $PSScriptRoot 'traffic_demo.py') --minutes $Minutes --interval $IntervalSeconds
    exit $LASTEXITCODE
}
New-Item -ItemType Directory -Force -Path $control | Out-Null
$outLog=Join-Path $control 'console.log'
$errorLog=Join-Path $control 'errors.log'
$process=Start-Process -FilePath $python -ArgumentList @('-u','scripts/traffic_demo.py','--minutes',"$Minutes",'--interval',"$IntervalSeconds") -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errorLog -PassThru
$confirmed=$false
$deadline=(Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline) {
    if ($process.HasExited) { Get-Content -LiteralPath $outLog -Tail 5; Get-Content -LiteralPath $errorLog; throw 'Demo exited before traffic was confirmed. See the stop reason above.' }
    if (Test-Path -LiteralPath $stateFile) {
        $current=Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
        $liveFile=Join-Path $current.output 'live.json'
        if (Test-Path -LiteralPath $liveFile) {
            $live=Get-Content -LiteralPath $liveFile -Raw | ConvertFrom-Json
            if ($current.run_id -ne $priorRunId -and $live.run_id -eq $current.run_id -and $live.counts.submitted -gt 0 -and $live.phase -ne 'finished') { $confirmed=$true; break }
        }
    }
    Start-Sleep -Milliseconds 500
}
if ($confirmed) { Write-Output "Demo traffic active: first claim submitted. Duration limit $Minutes minutes; interval $IntervalSeconds seconds plus processing/reviewer time." }
else { Write-Warning 'Runner launched but no claim submission is confirmed. Check status_traffic_demo.ps1; traffic may be paused for RAM.' }
Write-Output 'Grafana: http://localhost:3000/d/preauth-overview?from=now-15m&to=now&refresh=5s'
Write-Output 'Prometheus: http://localhost:9090/'
Write-Output 'Stop: ./scripts/stop_traffic_demo.ps1'
Write-Output 'Status: ./scripts/status_traffic_demo.ps1 (shows counts and any stop reason)'
Write-Output 'For visible live events in this terminal, restart with -Foreground.'
Write-Output "Live log: Get-Content '$outLog' -Wait"
