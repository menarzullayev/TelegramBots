# Keeps the TezMafia bot running on Windows: restarts it after a crash or a kill (that is how a
# deploy restarts it). Started at logon by the "TezMafia Bot" scheduled task (install-autostart.ps1).
#
# The bot runs as its own hidden process and writes data\logs\bot.log itself (UTF-8, rotating).
# No cmd.exe or output redirection here: under Task Scheduler's hidden console those ended the
# whole runner with STATUS_CONTROL_C_EXIT whenever the bot process was killed.
param(
    # Overridable only to test the restart loop itself.
    [string]$Python = '',
    [string[]]$BotArgs = @('-m', 'tezmafia'),
    [string]$LogDir = ''
)
$ErrorActionPreference = 'Continue'
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$python = if ($Python) { $Python } else { Join-Path $root '.venv-win\Scripts\python.exe' }
$logDir = if ($LogDir) { $LogDir } else { Join-Path $root 'data\logs' }
New-Item -ItemType Directory -Force $logDir | Out-Null
$runnerLog = Join-Path $logDir 'runner.log'
$env:PYTHONUTF8 = '1'
$env:LOG_FILE = Join-Path $logDir 'bot.log'

$alreadyRunning = 75
while ($true) {
    Add-Content $runnerLog "start $(Get-Date -Format s)"
    try {
        $proc = Start-Process -FilePath $python -ArgumentList $BotArgs -WorkingDirectory $root `
            -WindowStyle Hidden -PassThru -Wait
        $code = $proc.ExitCode
    } catch {
        $code = -1
        Add-Content $runnerLog "launch failed: $($_.Exception.Message)"
    }
    Add-Content $runnerLog "exit $code at $(Get-Date -Format s)"
    if ($code -eq $alreadyRunning) { break }
    Start-Sleep -Seconds 10
}
