#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Sets up pindlebot-v2 inside the Hyper-V VM.
    Run this in an admin PowerShell inside the VM.
#>

$ErrorActionPreference = "Stop"
$RepoUrl = "https://github.com/craigjson/pindlebot-v2.git"
$InstallDir = "C:\pindlebot-v2"

# -- 1. Install Git -----------------------------------------------------------
Write-Host "Installing Git..." -ForegroundColor Cyan
winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# -- 2. Install Python 3.11 ---------------------------------------------------
Write-Host "Installing Python 3.11..." -ForegroundColor Cyan
winget install --id Python.Python.3.11 -e --source winget --accept-package-agreements --accept-source-agreements
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# -- 3. Install Tesseract OCR (fallback OCR engine) ---------------------------
Write-Host "Installing Tesseract OCR..." -ForegroundColor Cyan
winget install --id UB-Mannheim.TesseractOCR -e --source winget --accept-package-agreements --accept-source-agreements
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# -- 4. Clone the repo --------------------------------------------------------
if (Test-Path $InstallDir) {
    Write-Host "Directory $InstallDir already exists, pulling latest..." -ForegroundColor Yellow
    Push-Location $InstallDir
    & git pull
    Pop-Location
} else {
    Write-Host "Cloning pindlebot-v2..." -ForegroundColor Cyan
    & git clone $RepoUrl $InstallDir
}

# -- 5. Create virtualenv and install requirements ----------------------------
Write-Host "Creating virtualenv..." -ForegroundColor Cyan
Push-Location $InstallDir
& python -m venv .venv

Write-Host "Installing Python dependencies (this will take a while -- PyTorch CUDA is large)..." -ForegroundColor Cyan
& .\.venv\Scripts\pip install --upgrade pip
& .\.venv\Scripts\pip install -r requirements.txt

Pop-Location

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Install Diablo 2 Resurrected via Battle.net" -ForegroundColor White
Write-Host "  2. Launch D2R at 1280x720 windowed" -ForegroundColor White
Write-Host "  3. Edit config\custom.ini with your character/route settings" -ForegroundColor White
Write-Host "  4. cd $InstallDir && .\.venv\Scripts\activate && python src\main.py" -ForegroundColor White
