# Automated Test Suite Runner (Windows / PowerShell)
$ErrorActionPreference = "Stop"

Write-Host "=== Running Automated Test Suite ===" -ForegroundColor Cyan
py -m pytest tests/ -v --tb=short

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[PASS] All unit, mathematical, and integration tests passed with 100% success rate." -ForegroundColor Green
} else {
    Write-Host "`n[FAIL] One or more tests failed. Inspect output above." -ForegroundColor Red
    exit 1
}
