#Requires -Version 5.1
<#
.SYNOPSIS
    Bootstrap the LAH Path Planning Studio development environment on Windows.
.DESCRIPTION
    Checks Python version, creates a virtual environment, installs all
    dependencies, initializes the workspace, and prints a success summary.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  LAH Path Planning Studio - Windows Bootstrap" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# -----------------------------------------------------------------------
# 1. Check Python
# -----------------------------------------------------------------------
Write-Host "[1/5] Checking Python installation..." -ForegroundColor Yellow

$PythonCmd = $null
foreach ($candidate in @("python", "python3", "py")) {
    try {
        $version = & $candidate --version 2>&1
        if ($version -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 10) {
                $PythonCmd = $candidate
                Write-Host "  Found $version ($candidate)" -ForegroundColor Green
                break
            } else {
                Write-Host "  $candidate is $version (need >= 3.10, skipping)" -ForegroundColor DarkYellow
            }
        }
    } catch {
        # candidate not found, continue
    }
}

if (-not $PythonCmd) {
    Write-Host "  ERROR: Python >= 3.10 is required but not found." -ForegroundColor Red
    Write-Host "  Please install Python 3.10+ from https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}

# -----------------------------------------------------------------------
# 2. Create virtual environment
# -----------------------------------------------------------------------
Write-Host ""
Write-Host "[2/5] Creating virtual environment..." -ForegroundColor Yellow

$VenvDir = Join-Path $ProjectRoot ".venv"

if (Test-Path $VenvDir) {
    Write-Host "  Virtual environment already exists at $VenvDir" -ForegroundColor DarkYellow
    Write-Host "  Skipping creation (delete .venv/ to recreate)" -ForegroundColor DarkYellow
} else {
    & $PythonCmd -m venv $VenvDir
    Write-Host "  Created virtual environment at $VenvDir" -ForegroundColor Green
}

# Activate
$ActivateScript = Join-Path (Join-Path $VenvDir "Scripts") "Activate.ps1"
if (-not (Test-Path $ActivateScript)) {
    Write-Host "  ERROR: Cannot find activation script at $ActivateScript" -ForegroundColor Red
    exit 1
}
. $ActivateScript
Write-Host "  Virtual environment activated" -ForegroundColor Green

# -----------------------------------------------------------------------
# 3. Upgrade pip and install dependencies
# -----------------------------------------------------------------------
Write-Host ""
Write-Host "[3/5] Installing dependencies..." -ForegroundColor Yellow

Write-Host "  Upgrading pip..."
& python -m pip install --upgrade pip --quiet

    Write-Host "  Installing project (editable + dev extras)..."
& pip install -e "$ProjectRoot[dev]" --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "  WARNING: editable install failed, falling back to requirements.txt" -ForegroundColor DarkYellow
    $ReqFile = Join-Path (Join-Path (Join-Path $ProjectRoot "apps") "backend") "requirements.txt"
    & pip install -r $ReqFile --quiet
}

$ReqFile = Join-Path (Join-Path (Join-Path $ProjectRoot "apps") "backend") "requirements.txt"
Write-Host "  Installing backend requirements..."
& pip install -r $ReqFile --quiet

Write-Host "  Dependencies installed" -ForegroundColor Green

# -----------------------------------------------------------------------
# 4. Install frontend dependencies
# -----------------------------------------------------------------------
Write-Host ""
Write-Host "[4/5] Installing frontend dependencies..." -ForegroundColor Yellow

$FrontendDir = Join-Path (Join-Path $ProjectRoot "apps") "frontend"
$NpmExecutable = Get-NpmExecutable
if (Test-Path (Join-Path $FrontendDir "package.json")) {
    Push-Location $FrontendDir
    try {
        if ($NpmExecutable) {
            $env:PATH = "$(Split-Path -Parent $NpmExecutable);$env:PATH"
            & $NpmExecutable install --silent 2>&1 | Out-Null
            Write-Host "  Frontend dependencies installed" -ForegroundColor Green
        } else {
            Write-Host "  WARNING: npm not found, skipping frontend install" -ForegroundColor DarkYellow
            Write-Host "  Install Node.js from https://nodejs.org/" -ForegroundColor DarkYellow
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Host "  No package.json found, skipping frontend install" -ForegroundColor DarkYellow
}

# -----------------------------------------------------------------------
# 5. Initialize workspace
# -----------------------------------------------------------------------
Write-Host ""
Write-Host "[5/5] Initializing workspace..." -ForegroundColor Yellow

$InitScript = Join-Path (Join-Path $ProjectRoot "scripts") "init_workspace.py"
& python $InitScript

# -----------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Bootstrap complete!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  To activate the environment in a new terminal:" -ForegroundColor White
Write-Host "    .\.venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""
Write-Host "  To start the application:" -ForegroundColor White
Write-Host "    .\scripts\run_all.ps1" -ForegroundColor White
Write-Host ""
Write-Host "  Or start components individually:" -ForegroundColor White
Write-Host "    .\scripts\run_backend.ps1   # FastAPI backend on :8000" -ForegroundColor White
Write-Host "    .\scripts\run_frontend.ps1  # React frontend on :5173" -ForegroundColor White
Write-Host ""
Write-Host "  Check CUDA availability:" -ForegroundColor White
Write-Host "    .\scripts\check_cuda.ps1" -ForegroundColor White
Write-Host ""
