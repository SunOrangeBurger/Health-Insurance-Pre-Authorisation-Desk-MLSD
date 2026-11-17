# Rebuild/start the synthetic desk on the standalone Ubuntu WSL Docker Engine.
param([switch]$SkipIngest)
$ErrorActionPreference = 'Stop'
if (-not $env:DESK_HOSPITAL_PASSWORD -or -not $env:DESK_REVIEWER_PASSWORD) {
    throw 'Set DESK_HOSPITAL_PASSWORD and DESK_REVIEWER_PASSWORD before starting the demo.'
}
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot '../corpus/raw/optima_secure_policy_wording.pdf'))) {
    throw 'Place the policy PDF listed in corpus/MANIFEST.md in corpus/raw first.'
}
function Invoke-Compose {
    param([Parameter(ValueFromRemainingArguments=$true)][string[]]$CommandArguments)
    & "$PSScriptRoot/compose_wsl.ps1" @CommandArguments
    if ($LASTEXITCODE -ne 0) { throw 'Compose operation failed.' }
}
& "$PSScriptRoot/start_ollama_wsl.ps1"
if ($LASTEXITCODE -ne 0) { throw 'Bounded Ollama server did not start.' }
Invoke-Compose @('build')
Invoke-Compose @('up','-d','--wait','--wait-timeout','120','--no-deps','postgres','redis')
if (-not $SkipIngest) { Invoke-Compose @('run','--rm','--no-deps','indexer','ingest') }
Invoke-Compose @('up','-d','--wait','--wait-timeout','120','--no-deps','api','worker')
$savedExport = $env:WSLENV
try {
    $env:WSLENV = (@($savedExport,'DESK_HOSPITAL_PASSWORD','DESK_REVIEWER_PASSWORD') | Where-Object { $_ }) -join ':'
    Invoke-Compose @('exec','-T','-e','DESK_HOSPITAL_PASSWORD','-e','DESK_REVIEWER_PASSWORD','api','python','scripts/seed_accounts.py')
} finally { $env:WSLENV = $savedExport }
Invoke-Compose @('--profile','observability','up','-d','--no-deps','prometheus','grafana','jaeger','redis-exporter')
Write-Output 'Policy Desk: http://localhost:8000/ — keep Ubuntu WSL active during the demo.'
