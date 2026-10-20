param([Parameter(Mandatory=$true)][string]$Version)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$BuildEnv = Join-Path $PSScriptRoot '.build-venv-windows'
$Python = Join-Path $BuildEnv 'Scripts\python.exe'
if (-not (Test-Path $Python)) {
    python -m venv $BuildEnv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the build environment' }
}
& $Python -m pip install -r requirements-desktop-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Could not install build dependencies' }
& $Python -c "import platform,sys; assert sys.platform == 'win32' and platform.machine().lower() in ('amd64','x86_64'), 'Build the x64 EXE on 64-bit Windows'"
if ($LASTEXITCODE -ne 0) { throw 'Windows x64 is required' }
& $Python scripts/build_metadata.py --version $Version --windows-version-file build/windows-version.txt
if ($LASTEXITCODE -ne 0) { throw 'Could not generate version metadata' }
& $Python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name 'Personal Office Workbench' `
    --add-data "${PSScriptRoot}/personal-office-workbench.html:." --add-data "${PSScriptRoot}/build-info.json:." `
    --hidden-import server --hidden-import webview.platforms.winforms `
    --hidden-import webview.platforms.edgechromium --collect-data webview `
    --version-file (Join-Path $PSScriptRoot 'build/windows-version.txt') --specpath build/specs `
    --distpath dist --workpath build/pyinstaller-windows (Join-Path $PSScriptRoot 'desktop_app.py')
if ($LASTEXITCODE -ne 0) { throw 'EXE build failed' }
$Target = Join-Path $PSScriptRoot "dist/Personal-Office-Workbench-Windows-x64-$Version.exe"
Move-Item -Force (Join-Path $PSScriptRoot 'dist/Personal Office Workbench.exe') $Target
Write-Output "Created: $Target"
