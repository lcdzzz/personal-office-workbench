$ErrorActionPreference = 'Stop'
$Dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Join-Path $env:APPDATA 'PersonalOfficeWorkbench'
$RuntimeDir = Join-Path $env:TEMP 'personal-office-workbench'
$PidFile = Join-Path $RuntimeDir 'server.pid'
$LogFile = Join-Path $RuntimeDir 'server.log'
$ErrorLog = Join-Path $RuntimeDir 'server-error.log'
$Page = 'personal-office-workbench.html'

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) { $Python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $Python) { throw '未找到 Python 3。请先安装 Python 3 并勾选 Add Python to PATH。' }
$PythonExe = $Python.Source
$Port = 8799
$Config = Join-Path $AppDir 'config.json'
if (Test-Path $Config) {
  try { $Port = [int](Get-Content -Raw -Encoding UTF8 $Config | ConvertFrom-Json).port } catch { throw "配置文件无效：$Config" }
}
$Url = "http://127.0.0.1:$Port/$Page"
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

try {
  Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 1 | Out-Null
} catch {
  $proc = Start-Process -FilePath $PythonExe -ArgumentList @('server.py') -WorkingDirectory $Dir -WindowStyle Hidden -RedirectStandardOutput $LogFile -RedirectStandardError $ErrorLog -PassThru
  Set-Content -Path $PidFile -Value $proc.Id -Encoding ASCII
  $ready = $false
  for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 100
    try { Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 1 | Out-Null; $ready = $true; break } catch { }
  }
  if (-not $ready) { throw "本地服务启动失败。请查看日志：$LogFile 和 $ErrorLog" }
}
Start-Process $Url
