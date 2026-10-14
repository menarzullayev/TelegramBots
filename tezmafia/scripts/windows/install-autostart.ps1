# Registers the "TezMafia Bot" scheduled task: starts run-bot.ps1 hidden at logon of the current user.
# Re-running it replaces the task. Remove with: Unregister-ScheduledTask -TaskName 'TezMafia Bot'
$ErrorActionPreference = 'Stop'
$runner = Join-Path $PSScriptRoot 'run-bot.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runner`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'TezMafia Bot' -Action $action -Trigger $trigger -Settings $settings `
    -Description 'TezMafia Telegram bot (D:\Linux\TelegramBots\tezmafia)' -Force | Out-Null
Write-Output "registered: TezMafia Bot -> $runner"
