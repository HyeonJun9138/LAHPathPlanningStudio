#Requires -Version 5.1
<#
.SYNOPSIS
    Check CUDA availability for LAH Path Planning Studio.
.DESCRIPTION
    Activates the virtual environment and runs the CUDA detection script
    to report available GPU devices and driver information.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}

# Activate virtual environment if present
$VenvActivate = Join-Path (Join-Path (Join-Path $ProjectRoot ".venv") "Scripts") "Activate.ps1"
if (Test-Path $VenvActivate) {
    . $VenvActivate
}

$CheckScript = Join-Path (Join-Path $ProjectRoot "scripts") "check_cuda.py"

if (-not (Test-Path $CheckScript)) {
    Write-Host "ERROR: check_cuda.py not found at $CheckScript" -ForegroundColor Red
    exit 1
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  LAH Path Planning Studio - CUDA Device Check" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

& python $CheckScript
