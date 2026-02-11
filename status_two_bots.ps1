$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$StateFile = Join-Path $ProjectRoot ".run\dual-bot-processes.json"

Write-Host "=== Dual Bot Status ==="

if (Test-Path $StateFile) {
    $state = Get-Content $StateFile -Raw | ConvertFrom-Json
    Write-Host ("Started at: " + $state.started_at)
    $rows = @()
    foreach ($item in $state.processes) {
        $proc = Get-Process -Id $item.pid -ErrorAction SilentlyContinue
        $rows += [PSCustomObject]@{
            name = $item.name
            pid = $item.pid
            running = [bool]$proc
        }
    }
    $rows | Format-Table name, pid, running -AutoSize
} else {
    Write-Host "No launcher state file found."
}

Write-Host ""
Write-Host "Listening ports (8000, 8002):"
$listeners = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -in 8000, 8002 } |
    Select-Object LocalAddress, LocalPort, OwningProcess
if ($listeners) {
    $listeners | Format-Table -AutoSize
} else {
    Write-Host "No listeners found on 8000 or 8002."
}

function Test-Health {
    param([string]$Url)
    try {
        $resp = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 3
        return "OK: $($resp.status)"
    } catch {
        return "DOWN"
    }
}

Write-Host ""
Write-Host ("http://127.0.0.1:8000/health -> " + (Test-Health -Url "http://127.0.0.1:8000/health"))
Write-Host ("http://127.0.0.1:8002/health -> " + (Test-Health -Url "http://127.0.0.1:8002/health"))
