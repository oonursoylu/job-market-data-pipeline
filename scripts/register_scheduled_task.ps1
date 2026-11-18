# Registers a Windows scheduled task that runs the pipeline on fixed weekdays.
# Run once in PowerShell from the repository root:   .\scripts\register_scheduled_task.ps1
# Other days or times:
#   .\scripts\register_scheduled_task.ps1 -DaysOfWeek Monday,Thursday -Time "08:40" -RetryTime "13:40"
#
# Why Monday, Wednesday and Friday: in the archives, collections one day apart shared about
# 93% of their adverts, while a 2-3 day gap still brought about 23% new ones (see README).
# Fixed weekdays keep the dates evenly spaced and comparable, and avoid weekend snapshots.
#
# The second run on the same day finishes anything the first run could not (for example when
# the API was down). If that day is already complete it only rebuilds dbt, so it is safe.
# If the laptop is off at both times, the task runs as soon as it is back on.
param(
    [string[]]$DaysOfWeek = @("Monday", "Wednesday", "Friday"),
    [string]$Time = "10:20",
    [string]$RetryTime = "14:20",
    [string]$TaskName = "JobMarketPipeline"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Script = Join-Path $PSScriptRoot "run_pipeline.ps1"

$Action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Script`"" `
    -WorkingDirectory $RepoRoot
$Triggers = @(
    (New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DaysOfWeek -At $Time),
    (New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DaysOfWeek -At $RetryTime)
)
# StartWhenAvailable: if the laptop was off at that time, run as soon as it is back on.
# IgnoreNew: never start a second copy while one is still running.
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Triggers -Settings $Settings `
    -Description "Adzuna extraction, PostgreSQL load and dbt build on fixed weekdays" -Force | Out-Null
Write-Host "Scheduled task '$TaskName' runs on $($DaysOfWeek -join ', ') at $Time, with a second try at $RetryTime."
Write-Host "Logs: $RepoRoot\logs\pipeline_YYYY-MM-DD.log"
