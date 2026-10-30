# =====================================================================
# NSE Equity Research Assistant — Windows Local Startup Script
# Zero-Budget, INR-First Personal Investment Research Architecture
# =====================================================================

Write-Host "===========================================================" -ForegroundColor Green
Write-Host "  NSE Equity Research Assistant — Local Application Launcher" -ForegroundColor White
Write-Host "===========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Checking local environment..." -ForegroundColor Cyan

# 1. Check Python
$PythonCmd = ""
if (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCmd = "py"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = "python"
} else {
    Write-Host "[ERROR] Python was not found in your system PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.10+ from https://www.python.org/" -ForegroundColor Yellow
    exit 1
}

$PyVer = & $PythonCmd --version
Write-Host "[OK] Detected Python runtime: $PyVer" -ForegroundColor Green

# Install missing packages and enforce the tested API dependency range.
Write-Host "[INFO] Checking declared Python dependencies..." -ForegroundColor Cyan
& $PythonCmd -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# 2. Check Database
if (-not (Test-Path "data/nse_platform.db")) {
    Write-Host "[WARN] Local database not found. Initializing bundled NSE history..." -ForegroundColor Yellow
    & $PythonCmd -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $PythonCmd scripts/ingest_real_archives.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "[OK] SQLite database verified at data/nse_platform.db" -ForegroundColor Green
    & $PythonCmd -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

# 3. Check Search Index
if (-not (Test-Path "data/securities_search_index.json")) {
    Write-Host "[INFO] Building search index for 3,392 NSE securities..." -ForegroundColor Cyan
    & $PythonCmd scripts/build_search_index.py
}

# Refresh after-market prices. A provider outage never destroys the last verified snapshot.
Write-Host "[INFO] Checking for a newer verified NSE EOD snapshot..." -ForegroundColor Cyan
& $PythonCmd scripts/refresh_market_data.py --export-static
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] Daily refresh unavailable. Starting with the last dated local snapshot." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting FastAPI Application Server on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
Write-Host "Opening your browser in 2 seconds..." -ForegroundColor Cyan
Write-Host "Press Ctrl + C at any time to stop the server." -ForegroundColor Yellow
Write-Host ""

# Start browser in background job
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://127.0.0.1:8000"
} | Out-Null

# Run FastAPI uvicorn
& $PythonCmd -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
