"""Shared native-window entry point for macOS and Windows packages."""
from __future__ import annotations

import argparse
import http.client
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

import server as workbench_server


def show_error(message: str) -> None:
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, 'Personal Office Workbench', 0x10)
    else:
        script = 'on run argv\ndisplay alert "Personal Office Workbench" message (item 1 of argv)\nend run'
        subprocess.run(['/usr/bin/osascript', '-e', script, '--', message],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def server_is_ready(host: str, port: int) -> bool:
    try:
        connection = http.client.HTTPConnection(host, port, timeout=1)
        try:
            connection.request('GET', '/api/runtime')
            response = connection.getresponse()
            raw = response.read()
            return response.status == 200 and json.loads(raw).get('coreSha256') == workbench_server.runtime_info()['coreSha256']
        finally:
            connection.close()
    except (OSError, ValueError, AttributeError, http.client.HTTPException):
        return False


def prepare_verification(directory: Path) -> None:
    directory = directory.resolve()
    marker = directory / '.workbench-package-check'
    if directory.exists() and any(directory.iterdir()) and not marker.is_file():
        raise ValueError('Package verification requires an empty directory.')
    directory.mkdir(parents=True, exist_ok=True)
    marker.write_text('Personal Office Workbench package verification\n', encoding='utf-8')
    workbench_server.APP_DIR = directory / 'data'
    workbench_server.CONFIG_PATH = workbench_server.APP_DIR / 'config.json'
    workbench_server.APP_DIR.mkdir(parents=True, exist_ok=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    workbench_server.CONFIG_PATH.write_text(json.dumps({'host':'127.0.0.1', 'port':port}), encoding='utf-8')
    if not (workbench_server.APP_DIR / 'meta.json').exists():
        state = workbench_server.initial_state()
        state['meta']['initialized'] = True
        workbench_server.persist_state(state)


def main() -> int:
    parser = argparse.ArgumentParser(description='Personal Office Workbench')
    parser.add_argument('--verify-package', type=Path, help='Run isolated native-package checks and exit')
    args, _ = parser.parse_known_args()
    if args.verify_package:
        prepare_verification(args.verify_package)
    app_dir = workbench_server.APP_DIR
    app_dir.mkdir(parents=True, exist_ok=True)
    log = open(app_dir / 'app.log', 'a', encoding='utf-8', buffering=1)
    sys.stdout = log
    sys.stderr = log
    config = workbench_server.load_config()
    host = '127.0.0.1' if config['host'] == 'localhost' else config['host']
    url_host = f'[{host}]' if ':' in host else host
    url = f'http://{url_host}:{config["port"]}/personal-office-workbench.html'
    instance = None
    try:
        instance = workbench_server.ThreadingHTTPServer((host, config['port']), workbench_server.Handler)
    except OSError:
        if not server_is_ready(host, config['port']):
            show_error('工作台端口已被其他程序或旧版本占用，请先停止旧工作台，再打开此应用。\nThe port is in use by another program or version. Stop it and reopen this app.')
            return 1
    else:
        instance.daemon_threads = True
        threading.Thread(target=instance.serve_forever, name='workbench-http', daemon=True).start()
    try:
        for _ in range(50):
            if server_is_ready(host, config['port']):
                break
            time.sleep(0.1)
        else:
            show_error('工作台未能启动，请检查应用数据目录中的 app.log。')
            return 1
        import webview
        webview.settings['ALLOW_DOWNLOADS'] = True
        window = webview.create_window('Personal Office Workbench', url, width=1280, height=840,
                                       min_size=(880,600), background_color='#f5f6fa')
        options = {'gui':'edgechromium'} if sys.platform == 'win32' else {}
        if args.verify_package:
            from package_check import run_check
            webview.start(run_check, (window, args.verify_package.resolve(), url), **options)
            report = json.loads((args.verify_package / 'result.json').read_text())
            return 0 if report.get('ok') else 1
        webview.start(**options)
        return 0
    except Exception as error:
        print(repr(error), flush=True)
        if args.verify_package:
            (args.verify_package / 'result.json').write_text(json.dumps({'ok':False, 'error':str(error)}), encoding='utf-8')
        else:
            message = '无法打开工作台窗口，请查看 app.log。'
            if sys.platform == 'win32':
                message += '\n请确认已安装 Microsoft Edge WebView2 Runtime。'
            show_error(message)
        return 1
    finally:
        if instance is not None:
            instance.shutdown()
            instance.server_close()


if __name__ == '__main__':
    raise SystemExit(main())
