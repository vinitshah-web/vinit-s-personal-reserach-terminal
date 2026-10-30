# Register a per-user Windows task for the post-market NSE EOD refresh.
param(
    [string]$DailyTime = "19:45",
    [string]$RetryTime = "22:00"
)

$ErrorActionPreference = "Stop"
$RefreshScript = Resolve-Path (Join-Path $PSScriptRoot "refresh_daily.ps1")
$TaskName = "Vinit Research Terminal - Daily NSE Refresh"
$PowerShellExe = (Get-Command powershell.exe).Source
$ActionArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$RefreshScript`""
$Action = New-ScheduledTaskAction -Execute $PowerShellExe -Argument $ActionArgs
$Triggers = @(
    New-ScheduledTaskTrigger -Daily -At $DailyTime
    New-ScheduledTaskTrigger -Daily -At $RetryTime
)
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Triggers `
    -Settings $Settings `
    -Description "Refresh validated NSE end-of-day prices after the TejHQ 18:30 IST publication." `
    -Force | Out-Null

Write-Host "Registered '$TaskName' for $DailyTime with a $RetryTime retry each day." -ForegroundColor Green
Write-Host "The refresh is idempotent; exchange holidays retain the latest published trading date." -ForegroundColor Cyan
