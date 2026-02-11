param(
    [string]$TradingApiKey = "",
    [switch]$ResetExisting
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$StateDir = Join-Path $ProjectRoot ".run"
$StateFile = Join-Path $StateDir "dual-bot-processes.json"
$EnvFile = Join-Path $ProjectRoot ".env"

function Import-EnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        return
    }
    foreach ($rawLine in Get-Content $Path) {
        $line = $rawLine.Trim()
        if (-not $line) { continue }
        if ($line.StartsWith("#")) { continue }
        $parts = $line.Split("=", 2)
        if ($parts.Count -ne 2) { continue }
        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim("'").Trim('"')
        [Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

function Start-TerminalWorker {
    param(
        [string]$Name,
        [string]$Command
    )
    $proc = Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoLogo",
        "-NoExit",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        $Command
    ) -PassThru
    return [PSCustomObject]@{
        name = $Name
        pid = $proc.Id
    }
}

if ($ResetExisting) {
    $StopScript = Join-Path $ProjectRoot "stop_two_bots.ps1"
    if (Test-Path $StopScript) {
        & $StopScript
    }
}

Import-EnvFile -Path $EnvFile
if ($TradingApiKey) {
    [Environment]::SetEnvironmentVariable("TRADING_API_KEY", $TradingApiKey, "Process")
}

if (-not $env:BOT_TOKEN_CURRENCY) {
    throw "BOT_TOKEN_CURRENCY missing. Add it to .env first."
}
if (-not $env:BOT_TOKEN_TRADING) {
    throw "BOT_TOKEN_TRADING missing. Add it to .env first."
}
if (-not $env:TRADING_API_KEY) {
    Write-Warning "TRADING_API_KEY is empty. Trading backend will run but screenshot analysis can fail."
}

if (Test-Path $StateFile) {
    $current = Get-Content $StateFile -Raw | ConvertFrom-Json
    $alive = @()
    foreach ($item in $current.processes) {
        $proc = Get-Process -Id $item.pid -ErrorAction SilentlyContinue
        if ($proc) {
            $alive += $item
        }
    }
    if ($alive.Count -gt 0) {
        Write-Host "Detected running launcher terminals. Stop first with: .\stop_two_bots.ps1"
        $alive | Format-Table name, pid -AutoSize
        exit 1
    }
}

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
$EscapedProjectRoot = $ProjectRoot.Replace("'", "''")

$commands = @(
    [PSCustomObject]@{
        name = "currency-backend"
        command = @"
Set-Location '$EscapedProjectRoot'
`$env:BOT_MODE='currency'
`$env:DATABASE_URL='bot_currency.db'
`$env:PORT='8000'
python main.py
"@
    },
    [PSCustomObject]@{
        name = "currency-bot"
        command = @"
Set-Location '$EscapedProjectRoot'
`$env:BOT_MODE='currency'
`$env:BACKEND_URL='http://127.0.0.1:8000'
python bot.py
"@
    },
    [PSCustomObject]@{
        name = "trading-backend"
        command = @"
Set-Location '$EscapedProjectRoot'
`$env:BOT_MODE='trading'
`$env:DATABASE_URL='bot_trading.db'
`$env:PORT='8002'
`$env:TRADING_API_URL='https://yoofirmtrading.xyz/api/analyze-screenshot'
python main.py
"@
    },
    [PSCustomObject]@{
        name = "trading-bot"
        command = @"
Set-Location '$EscapedProjectRoot'
`$env:BOT_MODE='trading'
`$env:BACKEND_URL='http://127.0.0.1:8002'
python bot.py
"@
    }
)

$started = @()
foreach ($item in $commands) {
    $started += Start-TerminalWorker -Name $item.name -Command $item.command
    Start-Sleep -Milliseconds 400
}

$state = [PSCustomObject]@{
    started_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    processes = $started
}
$state | ConvertTo-Json -Depth 5 | Set-Content -Path $StateFile -Encoding UTF8

Write-Host "Started 4 terminals."
$started | Format-Table name, pid -AutoSize
Write-Host "Use .\status_two_bots.ps1 to check status."
Write-Host "Use .\stop_two_bots.ps1 to stop all."
