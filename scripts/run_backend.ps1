#Requires -Version 5.1
<#
.SYNOPSIS
    Start the LAH Path Planning Studio FastAPI backend server.
.DESCRIPTION
    Activates the virtual environment and launches uvicorn with auto-reload
    pointing at the backend application.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}

# Activate virtual environment if present
$VenvActivate = Join-Path $ProjectRoot ".venv" "Scripts" "Activate.ps1"
if (Test-Path $VenvActivate) {
    . $VenvActivate
    Write-Host "Virtual environment activated" -ForegroundColor Green
}

# Ensure we're in project root so relative paths in app.yaml resolve
Push-Location $ProjectRoot

try {
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  Starting FastAPI Backend" -ForegroundColor Cyan
    Write-Host "  http://127.0.0.1:8000" -ForegroundColor Cyan
    Write-Host "  API docs: http://127.0.0.1:8000/docs" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""

    $env:PYTHONPATH = Join-Path $ProjectRoot "src"

    & python -m uvicorn apps.backend.app.main:app `
        --host 127.0.0.1 `
        --port 8000 `
        --reload `
        --reload-dir (Join-Path $ProjectRoot "apps" "backend") `
        --reload-dir (Join-Path $ProjectRoot "src")
} finally {
    Pop-Location
}
