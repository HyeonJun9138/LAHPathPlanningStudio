#Requires -Version 5.1
<#
.SYNOPSIS
    Start both the FastAPI backend and React frontend for LAH Path Planning Studio.
.DESCRIPTION
    Launches the backend and frontend as separate background jobs, then waits
    for either to exit. Press Ctrl+C to stop both.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}

$ScriptsDir = Join-Path $ProjectRoot "scripts"
$BackendHost = "127.0.0.1"
$BackendPort = 8000
$FrontendPort = 5173
$FrontendOrigin = "http://localhost:$FrontendPort"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  LAH Path Planning Studio - Starting All Services" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Backend  : http://${BackendHost}:$BackendPort  (API docs: /docs)" -ForegroundColor White
Write-Host "  Frontend : http://localhost:$FrontendPort" -ForegroundColor White
Write-Host ""
Write-Host "  Press Ctrl+C to stop all services" -ForegroundColor Yellow
Write-Host ""

# Start backend as a job
$BackendJob = Start-Job -Name "LAH-Backend" -ScriptBlock {
    param($ScriptPath, $HostName, $PortNumber, $Origin)
    & pwsh -NoProfile -File $ScriptPath -ListenHost $HostName -Port $PortNumber -FrontendOrigin $Origin *>&1
} -ArgumentList (Join-Path $ScriptsDir "run_backend.ps1"), $BackendHost, $BackendPort, $FrontendOrigin

Write-Host "  [+] Backend started (Job ID: $($BackendJob.Id))" -ForegroundColor Green

# Brief pause to let the backend start binding
Start-Sleep -Seconds 2

# Start frontend as a job
$FrontendJob = Start-Job -Name "LAH-Frontend" -ScriptBlock {
    param($ScriptPath, $PortNumber, $BackendPortNumber, $HostName)
    & pwsh -NoProfile -File $ScriptPath -Port $PortNumber -BackendPort $BackendPortNumber -BackendHost $HostName *>&1
} -ArgumentList (Join-Path $ScriptsDir "run_frontend.ps1"), $FrontendPort, $BackendPort, $BackendHost

Write-Host "  [+] Frontend started (Job ID: $($FrontendJob.Id))" -ForegroundColor Green
Write-Host ""

# Stream output from both jobs and wait for Ctrl+C
try {
    while ($true) {
        # Receive output from both jobs
        $BackendOutput = Receive-Job -Job $BackendJob -ErrorAction SilentlyContinue
        if ($BackendOutput) {
            $BackendOutput | ForEach-Object { Write-Host "[Backend]  $_" -ForegroundColor DarkCyan }
        }

        $FrontendOutput = Receive-Job -Job $FrontendJob -ErrorAction SilentlyContinue
        if ($FrontendOutput) {
            $FrontendOutput | ForEach-Object { Write-Host "[Frontend] $_" -ForegroundColor DarkMagenta }
        }

        # Check if either job has stopped unexpectedly
        if ($BackendJob.State -in @("Completed", "Failed", "Stopped")) {
            Write-Host "  Backend job stopped unexpectedly! State: $($BackendJob.State)" -ForegroundColor Red
            Receive-Job -Job $BackendJob -ErrorAction SilentlyContinue
            break
        }
        if ($FrontendJob.State -in @("Completed", "Failed", "Stopped")) {
            Write-Host "  Frontend job stopped unexpectedly! State: $($FrontendJob.State)" -ForegroundColor Red
            Receive-Job -Job $FrontendJob -ErrorAction SilentlyContinue
            break
        }

        Start-Sleep -Milliseconds 500
    }
} finally {
    Write-Host ""
    Write-Host "Stopping services..." -ForegroundColor Yellow

    Stop-Job -Job $BackendJob -ErrorAction SilentlyContinue
    Remove-Job -Job $BackendJob -Force -ErrorAction SilentlyContinue
    Write-Host "  [-] Backend stopped" -ForegroundColor DarkYellow

    Stop-Job -Job $FrontendJob -ErrorAction SilentlyContinue
    Remove-Job -Job $FrontendJob -Force -ErrorAction SilentlyContinue
    Write-Host "  [-] Frontend stopped" -ForegroundColor DarkYellow

    Write-Host ""
    Write-Host "All services stopped." -ForegroundColor Green
}
