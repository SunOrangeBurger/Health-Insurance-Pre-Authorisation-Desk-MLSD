param([ValidateRange(1,120)][int]$Minutes=15, [ValidateRange(5,60)][int]$IntervalSeconds=8)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$control=Join-Path $projectRoot '.runtime/traffic-demo'
$stateFile=Join-Path $control 'state.json'
if (Test-Path -LiteralPath $stateFile) {
    $state=Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
    $prior=Get-CimInstance Win32_Process -Filter "ProcessId=$($state.pid)"
    if ($prior -and $prior.CommandLine -match 'traffic_demo\.py') { throw 'The demo is already running. Use stop_traffic_demo.ps1 first.' }
}
$ready=Invoke-RestMethod 'http://localhost:8000/readyz'
if ($ready.status -ne 'ready') { throw 'Start the app with demo_desk.ps1 -SkipIngest first.' }
$python=Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'The project .venv Python environment is missing.' }
New-Item -ItemType Directory -Force -Path $control | Out-Null
$outLog=Join-Path $control 'console.log'
$errorLog=Join-Path $control 'errors.log'
$process=Start-Process -FilePath $python -ArgumentList @('-u','scripts/traffic_demo.py','--minutes',"$Minutes",'--interval',"$IntervalSeconds") -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errorLog -PassThru
Start-Sleep -Seconds 3
if ($process.HasExited) { Get-Content -LiteralPath $errorLog; throw 'Demo runner exited during startup; inspect .runtime/traffic-demo logs.' }
Write-Output "Synthetic demo started for $Minutes minutes; interval $IntervalSeconds seconds plus processing/reviewer time."
Write-Output 'Grafana: http://localhost:3000/d/preauth-overview?from=now-15m&to=now&refresh=5s'
Write-Output 'Prometheus: http://localhost:9090/'
Write-Output 'Stop: ./scripts/stop_traffic_demo.ps1'
Write-Output "Live log: Get-Content '$outLog' -Wait"
