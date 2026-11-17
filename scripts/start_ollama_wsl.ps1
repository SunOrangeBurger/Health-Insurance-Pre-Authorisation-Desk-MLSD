# Start one host inference server, bound only to the Windows WSL adapter.
param([switch]$Restart)
$ErrorActionPreference = 'Stop'
$statePath = Join-Path $env:TEMP 'policy-desk-ollama-state.json'
$gateway = (& wsl -d Ubuntu -- sh -c "ip route show default | cut -d ' ' -f 3").Trim()
if ($gateway -notmatch '^\d+\.\d+\.\d+\.\d+$') { throw 'Cannot determine WSL gateway.' }
$listeners = Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue
if ($listeners) {
    $state = if (Test-Path -LiteralPath $statePath) { Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json } else { $null }
    $owned = $state -and $state.hostCacheMiB -eq 0 -and $state.gateway -eq $gateway -and ($listeners.OwningProcess -contains $state.serverPid)
    if (-not $owned) { throw 'An unmanaged Ollama server is already listening. Exit it before launching the bounded project server.' }
    if (-not $Restart) { Write-Output "Bounded project Ollama already listening on $gateway`:11434"; exit 0 }
    Stop-Process -Id $state.serverPid
}
$env:OLLAMA_HOST = "$gateway`:11434"
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_CONTEXT_LENGTH = '4096'
$env:LLAMA_ARG_CACHE_RAM = '0'
$binary = (Get-Command ollama -ErrorAction Stop).Source
$server = Start-Process -FilePath $binary -ArgumentList 'serve' -WindowStyle Hidden -RedirectStandardOutput "$env:TEMP/policy-desk-ollama.out.log" -RedirectStandardError "$env:TEMP/policy-desk-ollama.err.log" -PassThru
@{serverPid=$server.Id; gateway=$gateway; hostCacheMiB=0} | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding utf8
Write-Output "Starting Ollama on $gateway`:11434 (one inference slot)."
