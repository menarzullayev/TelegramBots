# Keeps the TezMafia bot running on Windows: restarts it after a crash, logs to data\logs.
# Started at logon by the "TezMafia Bot" scheduled task (see install-autostart.ps1).
$ErrorActionPreference = 'Continue'
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$python = Join-Path $root '.venv-win\Scripts\python.exe'
$logDir = Join-Path $root 'data\logs'
New-Item -ItemType Directory -Force $logDir | Out-Null
Set-Location $root
$env:PYTHONUTF8 = '1'

$alreadyRunning = 75
while ($true) {
    $stamp = Get-Date -Format 'yyyy-MM-dd'
    $log = Join-Path $logDir "bot-$stamp.log"
    Add-Content $log "=== start $(Get-Date -Format s) ==="
    # cmd's redirection keeps Python's UTF-8 bytes; PowerShell 5.1's *>> would write UTF-16.
    cmd.exe /c "`"$python`" -m tezmafia >> `"$log`" 2>&1"
    $code = $LASTEXITCODE
    Add-Content $log "=== exit $code at $(Get-Date -Format s) ==="
    if ($code -eq $alreadyRunning) { break }
    # Old logs: keep two weeks.
    Get-ChildItem $logDir -Filter 'bot-*.log' | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-14) } | Remove-Item -Force
    Start-Sleep -Seconds 10
}
