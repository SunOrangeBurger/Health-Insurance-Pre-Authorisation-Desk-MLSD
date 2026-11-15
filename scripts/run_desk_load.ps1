param(
    [ValidateSet('smoke','load','stress','soak')][string]$Profile = 'smoke',
    [int]$Users = 1,
    [string]$HostUrl = 'http://localhost:8000',
    [int]$SoakMinutes = 30
)
$ErrorActionPreference = 'Stop'
if (-not $env:DESK_HOSPITAL_PASSWORD) { throw 'Set DESK_HOSPITAL_PASSWORD first.' }
if ($Users -lt 1 -or $Users -gt 16) { throw 'Users must be between 1 and 16 for local tests.' }
if ($SoakMinutes -lt 1 -or $SoakMinutes -gt 120) { throw 'SoakMinutes must be 1–120.' }
$duration = switch ($Profile) { smoke {'30s'} load {'3m'} stress {'3m'} soak {"${SoakMinutes}m"} }
New-Item -ItemType Directory -Force -Path loadtest/results/desk | Out-Null
$stamp = Get-Date -Format yyyyMMdd-HHmmss
& locust -f loadtest/desk.py --headless -u $Users -r 1 --run-time $duration --host $HostUrl --csv "loadtest/results/desk/$Profile-$stamp" --csv-full-history
if ($LASTEXITCODE -ne 0) { throw 'Locust reported a failed run.' }
