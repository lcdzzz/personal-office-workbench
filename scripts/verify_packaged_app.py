"""Mount a DMG or launch an EXE; verify real webview flows twice, then cleanup."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import platform
import socket
import subprocess
import tempfile
import time


def verify(executable, directory, version, architecture):
    reports = []
    for attempt in range(2):
        result_file = directory/'result.json'
        if result_file.exists(): result_file.unlink()
        with (directory.parent/f'launcher-{attempt}.log').open('ab') as log:
            process = subprocess.Popen([str(executable),'--verify-package',str(directory)],stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+120
                while time.monotonic()<deadline and process.poll() is None and not result_file.exists():
                    time.sleep(.2)
                if not result_file.exists():
                    app_log = directory/'data/app.log'
                    detail=app_log.read_text(encoding='utf-8',errors='replace')[-4000:] if app_log.exists() else ''
                    raise AssertionError(f'Application verification produced no result (exit={process.poll()}): {detail}')
                report=json.loads(result_file.read_text(encoding='utf-8'))
                assert report['ok'],report
                assert report['runtime']['version']==version,report
                actual=report['architecture'].lower()
                if actual in ('amd64','x64'): actual='x86_64'
                assert actual==architecture,(actual,architecture)
                assert report['runtime']['architecture']==architecture,report
                if attempt: assert report['restoredTask'],report
                assert process.wait(timeout=30)==0,report
                with socket.socket() as probe:
                    assert probe.connect_ex(('127.0.0.1',report['port']))!=0,'App left its server running after closing'
                reports.append(report)
            finally:
                if process.poll() is None:
                    # A PyInstaller one-file EXE has a bootloader parent and an
                    # application child. End only this launched process tree.
                    if platform.system() == 'Windows':
                        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],
                                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
                    else:
                        process.terminate()
                    process.wait(timeout=15)
    return reports


def main():
    parser=argparse.ArgumentParser()
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--dmg',type=Path)
    source.add_argument('--executable',type=Path)
    parser.add_argument('--version',required=True)
    parser.add_argument('--architecture',choices=['arm64','x86_64'],required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='workbench-package-acceptance-') as temp:
        directory=Path(temp)
        mount=directory/'mounted';mount.mkdir()
        mounted=False
        try:
            if args.dmg:
                subprocess.run(['hdiutil','verify',str(args.dmg.resolve())],check=True)
                subprocess.run(['hdiutil','attach','-readonly','-nobrowse','-mountpoint',str(mount),str(args.dmg.resolve())],check=True)
                mounted=True
                bundle=mount/'Personal Office Workbench.app'
                subprocess.run(['codesign','--verify','--deep','--strict',str(bundle)],check=True)
                executable=bundle/'Contents/MacOS/Personal Office Workbench'
                binary_arch=subprocess.check_output(['lipo','-archs',str(executable)],text=True).strip()
                assert binary_arch==args.architecture,binary_arch
                manifest=json.loads((bundle/'Contents/Resources/build-info.json').read_text())
                assert manifest['version']==args.version,manifest
                assert manifest['architecture']==args.architecture,manifest
            else:
                executable=args.executable.resolve()
            checks=directory/'checks';checks.mkdir()
            reports=verify(executable,checks,args.version,args.architecture)
            artifact=args.dmg or args.executable
            output={'ok':True,'artifact':artifact.name,'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),
                    'runs':reports,'host':platform.platform()}
            args.report.parent.mkdir(parents=True,exist_ok=True)
            args.report.write_text(json.dumps(output,indent=2),encoding='utf-8')
            print(json.dumps(output,indent=2))
        finally:
            if mounted: subprocess.run(['hdiutil','detach',str(mount)],check=True)


if __name__=='__main__':
    main()
