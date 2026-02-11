$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$StateFile = Join-Path $ProjectRoot ".run\dual-bot-processes.json"

$stopped = @()

if (Test-Path $StateFile) {
    $state = Get-Content $StateFile -Raw | ConvertFrom-Json
    foreach ($item in $state.processes) {
        $proc = Get-Process -Id $item.pid -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $item.pid -Force -ErrorAction SilentlyContinue
            $stopped += [PSCustomObject]@{
                name = $item.name
                pid = $item.pid
                source = "state"
            }
        }
    }
}

$portProcesses = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -in 8000, 8002 } |
    Select-Object -ExpandProperty OwningProcess -Unique

foreach ($pid in $portProcesses) {
    $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
    if ($proc) {
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        $stopped += [PSCustomObject]@{
            name = $proc.ProcessName
            pid = $pid
            source = "port"
        }
    }
}

if (Test-Path $StateFile) {
    Remove-Item $StateFile -Force
}

if ($stopped.Count -eq 0) {
    Write-Host "No running dual-bot processes found."
    exit 0
}

Write-Host "Stopped processes:"
$stopped | Sort-Object pid -Unique | Format-Table name, pid, source -AutoSize
