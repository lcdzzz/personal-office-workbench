#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Build this DMG on macOS." >&2
  exit 1
fi

BUILD_ENV="${ROOT}/.build-venv"
DIST_DIR="${ROOT}/dist"
WORK_DIR="${ROOT}/build/pyinstaller"
APP_NAME="Personal Office Workbench"
APP_BUNDLE="${DIST_DIR}/${APP_NAME}.app"
DMG_PATH="${DIST_DIR}/Personal-Office-Workbench-macOS-$(uname -m).dmg"

if [[ ! -x "${BUILD_ENV}/bin/python" ]]; then
  python3 -m venv "$BUILD_ENV"
fi
"${BUILD_ENV}/bin/python" -m pip install --upgrade pip
"${BUILD_ENV}/bin/python" -m pip install -r requirements-macos-build.txt

"${BUILD_ENV}/bin/python" -m PyInstaller \
  --noconfirm --clean --windowed --onedir \
  --name "Personal Office Workbench" \
  --osx-bundle-identifier "cn.microants.personalofficeworkbench" \
  --add-data "personal-office-workbench.html:." \
  --hidden-import server \
  --hidden-import webview.platforms.cocoa \
  --distpath "$DIST_DIR" --workpath "$WORK_DIR" \
  macos_app.py

rm -rf "${DIST_DIR}/dmg-root"
mkdir -p "${DIST_DIR}/dmg-root"
ditto "$APP_BUNDLE" "${DIST_DIR}/dmg-root/${APP_NAME}.app"
ln -s /Applications "${DIST_DIR}/dmg-root/Applications"
hdiutil create -volname "$APP_NAME" -srcfolder "${DIST_DIR}/dmg-root" \
  -ov -format UDZO "$DMG_PATH"

echo "Created: $DMG_PATH"
