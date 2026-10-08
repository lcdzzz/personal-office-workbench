$ErrorActionPreference = 'Stop'
$Dir = (Resolve-Path (Split-Path -Parent $MyInvocation.MyCommand.Path)).Path
$PidFile = Join-Path $env:TEMP 'personal-office-workbench\server.pid'
if (-not (Test-Path $PidFile)) { Write-Output '工作台服务未运行。'; exit 0 }
$rawPid = (Get-Content -Raw $PidFile).Trim()
$procId = 0
if (-not [int]::TryParse($rawPid, [ref]$procId)) { throw "PID 文件内容无效，未停止任何进程：$PidFile" }
$proc = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
if (-not $proc) { Remove-Item $PidFile; Write-Output '工作台服务未运行，已清理失效的 PID 文件。'; exit 0 }
$expected = Join-Path $Dir 'server.py'
if (-not $proc.CommandLine -or $proc.CommandLine.IndexOf($expected, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
  throw 'PID 文件未指向当前工作台服务，未停止任何进程。'
}
Stop-Process -Id $procId
Remove-Item $PidFile
Write-Output '工作台服务已停止。'
