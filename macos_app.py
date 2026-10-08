"""GUI entry point used by the macOS application bundle."""
from __future__ import annotations

import http.client
import subprocess
import sys
import threading
import time

import webview

import server as workbench_server


def show_error(message: str) -> None:
    subprocess.run(
        ["/usr/bin/osascript", "-e", f'display alert "Personal Office Workbench" message "{message}"'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def server_is_ready(host: str, port: int) -> bool:
    try:
        connection = http.client.HTTPConnection(host, port, timeout=1)
        try:
            connection.request("GET", "/personal-office-workbench.html")
            response = connection.getresponse()
            response.read()
            return response.status == 200
        finally:
            connection.close()
    except (OSError, http.client.HTTPException):
        return False


def main() -> None:
    app_dir = workbench_server.APP_DIR
    app_dir.mkdir(parents=True, exist_ok=True)
    log_path = app_dir / "app.log"
    log = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = log
    sys.stderr = log

    config = workbench_server.load_config()
    host = "127.0.0.1" if config["host"] == "localhost" else config["host"]
    url_host = f"[{host}]" if ":" in host else host
    url = f"http://{url_host}:{config['port']}/personal-office-workbench.html"

    instance = None
    try:
        instance = workbench_server.ThreadingHTTPServer((host, config["port"]), workbench_server.Handler)
    except OSError:
        if not server_is_ready(host, config["port"]):
            show_error("The local workbench could not start. Check the configured port in Application Support/PersonalOfficeWorkbench/config.json.")
            return
    else:
        instance.daemon_threads = True
        threading.Thread(target=instance.serve_forever, name="workbench-http", daemon=True).start()
        for _ in range(50):
            if server_is_ready(host, config["port"]):
                break
            time.sleep(0.1)
        else:
            instance.shutdown()
            instance.server_close()
            show_error("The local workbench did not become ready. See app.log in Application Support/PersonalOfficeWorkbench.")
            return

    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.create_window(
            "Personal Office Workbench",
            url,
            width=1280,
            height=840,
            min_size=(880, 600),
            background_color="#f5f6fa",
        )
        webview.start()
    finally:
        if instance is not None:
            instance.shutdown()
            instance.server_close()


if __name__ == "__main__":
    main()
