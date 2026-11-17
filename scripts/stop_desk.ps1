# Stop this project's services without deleting data or stopping shared Docker/WSL.
$ErrorActionPreference = 'Stop'
& "$PSScriptRoot/compose_wsl.ps1" --profile observability stop
if ($LASTEXITCODE -ne 0) { throw 'Could not stop project containers.' }
$statePath = Join-Path $env:TEMP 'policy-desk-ollama-state.json'
if (Test-Path -LiteralPath $statePath) {
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    $server = Get-CimInstance Win32_Process -Filter "ProcessId=$($state.serverPid)"
    $listener = Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.OwningProcess -eq $state.serverPid -and $_.LocalAddress -eq $state.gateway }
    if ($server -and $server.Name -eq 'ollama.exe' -and $server.CommandLine -match '\bserve\b' -and $listener) {
        $children = Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $server.ProcessId }
        $descendants = @($children)
        foreach ($child in $children) {
            $descendants += @(Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $child.ProcessId })
        }
        Stop-Process -Id $server.ProcessId
        $descendants | Where-Object { $_.Name -in @('llama-server.exe', 'ollama.exe', 'conhost.exe') } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
        Write-Output 'Managed project Ollama stopped.'
    } elseif ($server) {
        Write-Warning 'The recorded process could not be verified as the managed server; left it running.'
    }
}
Write-Output 'Project containers stopped. Database, index and model downloads preserved.'
