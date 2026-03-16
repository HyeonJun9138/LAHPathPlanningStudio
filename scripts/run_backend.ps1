#Requires -Version 5.1
<#
.SYNOPSIS
    Start the LAH Path Planning Studio FastAPI backend server.
.DESCRIPTION
    Activates the virtual environment and launches uvicorn with auto-reload
    pointing at the backend application.
#>

param(
    [int]$Port = 8000,
    [string]$ListenHost = "127.0.0.1",
    [string]$FrontendOrigin = "http://localhost:5173"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-PortOccupant {
    param([int]$RequestedPort)

    $connection = Get-NetTCPConnection -LocalPort $RequestedPort -ErrorAction SilentlyContinue |
        Where-Object { $_.OwningProcess -ne 0 } |
        Select-Object -First 1

    if (-not $connection) {
        return $null
    }

    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)" -ErrorAction SilentlyContinue

    return [pscustomobject]@{
        Port = $RequestedPort
        State = $connection.State
        ProcessId = $connection.OwningProcess
        Name = $process.Name
        CommandLine = $process.CommandLine
    }
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}

# Activate virtual environment if present
$VenvActivate = Join-Path (Join-Path (Join-Path $ProjectRoot ".venv") "Scripts") "Activate.ps1"
if (Test-Path $VenvActivate) {
    . $VenvActivate
    Write-Host "Virtual environment activated" -ForegroundColor Green
}

# Ensure we're in project root so relative paths in app.yaml resolve
Push-Location $ProjectRoot

try {
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  Starting FastAPI Backend" -ForegroundColor Cyan
    Write-Host "  http://${ListenHost}:$Port" -ForegroundColor Cyan
    Write-Host "  API docs: http://${ListenHost}:$Port/docs" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""

    $PortOccupant = Get-PortOccupant -RequestedPort $Port
    if ($PortOccupant) {
        Write-Host "ERROR: Port $Port is already in use by PID $($PortOccupant.ProcessId) ($($PortOccupant.Name))" -ForegroundColor Red
        if ($PortOccupant.CommandLine) {
            Write-Host "Command: $($PortOccupant.CommandLine)" -ForegroundColor Red
        }
        exit 1
    }

    $env:PYTHONPATH = Join-Path $ProjectRoot "src"
    $env:LAH_BACKEND_HOST = $ListenHost
    $env:LAH_BACKEND_PORT = [string]$Port
    $env:LAH_FRONTEND_ORIGIN = $FrontendOrigin

    & python -m uvicorn apps.backend.app.main:app `
        --host $ListenHost `
        --port $Port `
        --reload `
        --reload-dir (Join-Path (Join-Path $ProjectRoot "apps") "backend") `
        --reload-dir (Join-Path $ProjectRoot "src")
} finally {
    Pop-Location
}
