# Registers the "TezMafia Bot" scheduled task: at logon of the current user it starts
# supervisor.py with pythonw.exe (no console window), which keeps the bot running.
# Re-running it replaces the task. Remove with: Unregister-ScheduledTask -TaskName 'TezMafia Bot'
$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$pythonw = Join-Path $root '.venv-win\Scripts\pythonw.exe'
$supervisor = Join-Path $PSScriptRoot 'supervisor.py'
$action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$supervisor`"" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'TezMafia Bot' -Action $action -Trigger $trigger -Settings $settings `
    -Description 'TezMafia Telegram bot (D:\Linux\TelegramBots\tezmafia)' -Force | Out-Null
Write-Output "registered: TezMafia Bot -> $pythonw $supervisor"
