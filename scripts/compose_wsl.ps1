# Use the Ubuntu Docker Engine, independently of Docker Desktop.
# Example: ./scripts/compose_wsl.ps1 up -d --build
$projectRoot = Split-Path -Parent $PSScriptRoot
$translatedRoot = & wsl -d Ubuntu -- wslpath -a ($projectRoot.Replace('\','/'))
if ($LASTEXITCODE -ne 0 -or -not $translatedRoot) { throw 'Cannot resolve project path in Ubuntu WSL.' }
$linuxRoot = $translatedRoot.Trim()
$wslGateway = (& wsl -d Ubuntu -- sh -c "ip route show default | cut -d ' ' -f 3").Trim()
if ($wslGateway -notmatch '^\d+\.\d+\.\d+\.\d+$') { throw 'Cannot determine the Windows WSL adapter address.' }
& wsl -d Ubuntu --cd $linuxRoot -- env "OLLAMA_HOST_IP=$wslGateway" /usr/bin/docker compose -f docker-compose.yml -f docker-compose.desk.yml @args
exit $LASTEXITCODE
