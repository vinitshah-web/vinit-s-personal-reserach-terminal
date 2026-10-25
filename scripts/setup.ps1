# Setup Script for NSE Equity Intelligence Platform (Windows / PowerShell)
$ErrorActionPreference = "Stop"

Write-Host "=== Setting up NSE Equity Intelligence Platform ===" -ForegroundColor Cyan

# 1. Ensure data directories exist
$dataDir = Join-Path $PSScriptRoot "..\data\raw\bhavcopy"
if (-not (Test-Path $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
    Write-Host "[OK] Created raw data lake directory: $dataDir" -ForegroundColor Green
}

# 2. Check Python environment
Write-Host "Checking Python environment..."
py --version

# 3. Initialize SQLite Database Schema
Write-Host "Initializing SQLite database schema via SQLAlchemy..."
py -c "from src.db.connection import init_db; init_db(); print('[OK] Database initialized successfully.')"

# 4. Check Alembic Migrations
Write-Host "Validating Alembic migrations..."
py -m alembic upgrade head

Write-Host "=== Setup Completed Successfully ===" -ForegroundColor Green
