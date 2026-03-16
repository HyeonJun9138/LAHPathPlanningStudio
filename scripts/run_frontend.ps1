#Requires -Version 5.1
<#
.SYNOPSIS
    Start the LAH Path Planning Studio React frontend dev server.
.DESCRIPTION
    Changes to the frontend directory and runs the Vite development server
    via npm. The frontend will be available at http://localhost:5173.
#>

param(
    [int]$Port = 5173,
    [int]$BackendPort = 8000,
    [string]$BackendHost = "127.0.0.1"
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

function Get-NpmExecutable {
    foreach ($commandName in @("npm.cmd", "npm")) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($command -and $command.Source) {
            return $command.Source
        }
    }

    foreach ($candidate in @(
        "C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Microsoft\VisualStudio\NodeJs\npm.cmd",
        "C:\Program Files\Microsoft Visual Studio\2022\Preview\MSBuild\Microsoft\VisualStudio\NodeJs\npm.cmd"
    )) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}

$FrontendDir = Join-Path (Join-Path $ProjectRoot "apps") "frontend"

if (-not (Test-Path (Join-Path $FrontendDir "package.json"))) {
    Write-Host "ERROR: package.json not found in $FrontendDir" -ForegroundColor Red
    Write-Host "Run bootstrap_windows.ps1 first to set up the project." -ForegroundColor Red
    exit 1
}

$PortOccupant = Get-PortOccupant -RequestedPort $Port
if ($PortOccupant) {
    Write-Host "ERROR: Frontend port $Port is already in use by PID $($PortOccupant.ProcessId) ($($PortOccupant.Name))" -ForegroundColor Red
    if ($PortOccupant.CommandLine) {
        Write-Host "Command: $($PortOccupant.CommandLine)" -ForegroundColor Red
    }
    exit 1
}

$NpmExecutable = Get-NpmExecutable
if (-not $NpmExecutable) {
    Write-Host "ERROR: npm was not found in PATH or known Visual Studio Node.js locations." -ForegroundColor Red
    Write-Host "Install Node.js or add npm.cmd to PATH, then rerun this script." -ForegroundColor Red
    exit 1
}
$env:PATH = "$(Split-Path -Parent $NpmExecutable);$env:PATH"

# Check for node_modules
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "node_modules not found. Running npm install..." -ForegroundColor Yellow
    Push-Location $FrontendDir
    try {
        & $NpmExecutable install
    } finally {
        Pop-Location
    }
}

Push-Location $FrontendDir
try {
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  Starting React Frontend (Vite)" -ForegroundColor Cyan
    Write-Host "  http://127.0.0.1:$Port" -ForegroundColor Cyan
    Write-Host "  Proxying /api to http://${BackendHost}:$BackendPort" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""

    $env:VITE_BACKEND_URL = "http://${BackendHost}:$BackendPort"
    $env:VITE_PORT = [string]$Port

    & $NpmExecutable run dev -- --host 127.0.0.1 --port $Port
} finally {
    Pop-Location
}
