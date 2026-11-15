# Start one host inference server, bound only to the Windows WSL adapter.
$ErrorActionPreference = 'Stop'
$gateway = (& wsl -d Ubuntu -- sh -c "ip route show default | cut -d ' ' -f 3").Trim()
if ($gateway -notmatch '^\d+\.\d+\.\d+\.\d+$') { throw 'Cannot determine WSL gateway.' }
$listeners = Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue
if ($listeners) {
    if ($listeners.LocalAddress -contains $gateway) { Write-Output "Ollama already listening on $gateway`:11434"; exit 0 }
    throw 'Ollama is listening on another interface. Exit that instance before running this launcher.'
}
$env:OLLAMA_HOST = "$gateway`:11434"
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_CONTEXT_LENGTH = '4096'
$binary = (Get-Command ollama -ErrorAction Stop).Source
Start-Process -FilePath $binary -ArgumentList 'serve' -WindowStyle Hidden -RedirectStandardOutput "$env:TEMP/policy-desk-ollama.out.log" -RedirectStandardError "$env:TEMP/policy-desk-ollama.err.log"
Write-Output "Starting Ollama on $gateway`:11434 (one inference slot)."
