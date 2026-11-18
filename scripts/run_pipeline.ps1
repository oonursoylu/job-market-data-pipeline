# Runs the pipeline once with the project's virtual environment.
# The pipeline writes its own log: logs\pipeline_YYYY-MM-DD.log
# Used by the scheduled task (see register_scheduled_task.ps1); it can also be run by hand.
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "Virtual environment not found: $Python"
    exit 1
}

$env:PYTHONIOENCODING = "utf-8"
& $Python -m src.run_pipeline @args
exit $LASTEXITCODE
