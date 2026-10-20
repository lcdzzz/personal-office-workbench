"""Embed the same version, commit and core-file fingerprint in every package."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', required=True)
    parser.add_argument('--windows-version-file', type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r'v?\d+\.\d+\.\d+', args.version):
        parser.error('Version must be vX.Y.Z or X.Y.Z')
    commit = os.environ.get('WORKBENCH_SOURCE_COMMIT') or os.environ.get('GITHUB_SHA')
    if not commit:
        commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        parser.error('Source commit must be a full Git SHA')
    architecture = platform.machine().lower()
    if architecture in ('amd64','x64'): architecture = 'x86_64'
    info = {'version':args.version, 'sourceCommit':commit, 'coreSha256':server.source_fingerprint(),
            'platform':sys.platform, 'architecture':architecture}
    (ROOT/'build-info.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
    if args.windows_version_file:
        version = args.version.lstrip('v')
        numbers = tuple(int(x) for x in version.split('.')) + (0,)
        args.windows_version_file.parent.mkdir(parents=True,exist_ok=True)
        args.windows_version_file.write_text(f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers={numbers!r}, prodvers={numbers!r}, mask=0x3f,
    flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'lcdzzz'),
    StringStruct('FileDescription', 'Personal Office Workbench'),
    StringStruct('FileVersion', '{version}'),
    StringStruct('ProductName', 'Personal Office Workbench'),
    StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
''', encoding='utf-8')
    print(json.dumps(info))


if __name__ == '__main__':
    main()
