# Refresh verified NSE EOD data for the local terminal.
$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

if (Test-Path ".venv\Scripts\python.exe") {
    $PythonCmd = ".venv\Scripts\python.exe"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCmd = "py"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = "python"
} else {
    throw "Python 3.10+ was not found."
}

& $PythonCmd -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $PythonCmd scripts/refresh_market_data.py --export-static
exit $LASTEXITCODE
