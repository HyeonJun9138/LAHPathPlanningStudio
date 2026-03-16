#Requires -Version 5.1
<#
.SYNOPSIS
    Start the LAH Path Planning Studio React frontend dev server.
.DESCRIPTION
    Changes to the frontend directory and runs the Vite development server
    via npm. The frontend will be available at http://localhost:5173.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}

$FrontendDir = Join-Path $ProjectRoot "apps" "frontend"

if (-not (Test-Path (Join-Path $FrontendDir "package.json"))) {
    Write-Host "ERROR: package.json not found in $FrontendDir" -ForegroundColor Red
    Write-Host "Run bootstrap_windows.ps1 first to set up the project." -ForegroundColor Red
    exit 1
}

# Check for node_modules
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "node_modules not found. Running npm install..." -ForegroundColor Yellow
    Push-Location $FrontendDir
    try {
        & npm install
    } finally {
        Pop-Location
    }
}

Push-Location $FrontendDir
try {
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  Starting React Frontend (Vite)" -ForegroundColor Cyan
    Write-Host "  http://localhost:5173" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""

    & npm run dev
} finally {
    Pop-Location
}
