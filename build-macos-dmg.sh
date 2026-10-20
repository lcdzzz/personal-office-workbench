#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$ROOT"
if [[ "$(uname -s)" != Darwin ]]; then echo 'Build this DMG on macOS.' >&2; exit 1; fi
ARCH="${1:-$(uname -m)}"
VERSION="${2:-0.0.0}"
case "$ARCH" in arm64|x86_64) ;; *) echo 'Architecture must be arm64 or x86_64.' >&2; exit 1 ;; esac
BUILD_ENV="${ROOT}/.build-venv"
PY="${WORKBENCH_BUILD_PYTHON:-${BUILD_ENV}/bin/python}"
DIST_DIR="${ROOT}/dist"
WORK_DIR="${ROOT}/build/pyinstaller"
APP_NAME='Personal Office Workbench'
APP_BUNDLE="${DIST_DIR}/${APP_NAME}.app"
DMG_PATH="${DIST_DIR}/Personal-Office-Workbench-macOS-${ARCH}-${VERSION}.dmg"
if [[ ! -x "$PY" ]]; then python3 -m venv "$BUILD_ENV"; fi
"$PY" -m pip install -r requirements-macos-build.txt
ACTUAL_ARCH="$("$PY" -c 'import platform; print(platform.machine())')"
if [[ "$ACTUAL_ARCH" != "$ARCH" ]]; then
  echo "Build ${ARCH} using a matching Python runtime; found ${ACTUAL_ARCH}." >&2; exit 1
fi
"$PY" scripts/build_metadata.py --version "$VERSION"
mkdir -p "$DIST_DIR" "$WORK_DIR" "${ROOT}/build/specs"
"$PY" -m PyInstaller \
  --noconfirm --clean --windowed --onedir \
  --name "$APP_NAME" --target-architecture "$ARCH" \
  --osx-bundle-identifier cn.microants.personalofficeworkbench \
  --add-data "$ROOT/personal-office-workbench.html:." --add-data "$ROOT/build-info.json:." \
  --collect-data webview --hidden-import server --hidden-import webview.platforms.cocoa \
  --specpath "${ROOT}/build/specs" --distpath "$DIST_DIR" --workpath "$WORK_DIR" desktop_app.py
"$PY" - "$APP_BUNDLE/Contents/Info.plist" "${VERSION#v}" <<'PYINFO'
import plistlib,sys
from pathlib import Path
path=Path(sys.argv[1]);info=plistlib.loads(path.read_bytes())
info['CFBundleShortVersionString']=sys.argv[2]
info['CFBundleVersion']=sys.argv[2]
path.write_bytes(plistlib.dumps(info))
PYINFO
codesign --force --deep --sign - "$APP_BUNDLE"
codesign --verify --deep --strict "$APP_BUNDLE"
[[ "$(lipo -archs "$APP_BUNDLE/Contents/MacOS/$APP_NAME")" = "$ARCH" ]]
# A unique staging directory preserves previous build output; no broad deletion.
STAGING="$(mktemp -d "${TMPDIR:-/tmp}/workbench-dmg.XXXXXX")"
ditto "$APP_BUNDLE" "$STAGING/$APP_NAME.app"
ln -s /Applications "$STAGING/Applications"
hdiutil create -volname "$APP_NAME" -srcfolder "$STAGING" -ov -format UDZO "$DMG_PATH"
hdiutil verify "$DMG_PATH"
echo "Created: $DMG_PATH"
