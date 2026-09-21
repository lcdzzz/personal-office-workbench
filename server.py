#!/usr/bin/env python3
"""Local file-backed API for Personal Office Workbench."""
from __future__ import annotations

import copy
import io
import json
import os
import shutil
import sys
import tempfile
import time
import zipfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
APP_DIR = Path.home() / "Library" / "Application Support" / "PersonalOfficeWorkbench"
CONFIG_PATH = APP_DIR / "config.json"
DATA_FILES = {"tasks": "tasks.json", "notes": "notes.json", "projects": "projects.json", "meta": "meta.json"}
DEFAULT_CONFIG = {"host": "127.0.0.1", "port": 8799}
write_lock = None


class DataError(Exception):
    pass


def now_ms() -> int:
    return int(time.time() * 1000)


def default_meta(initialized: bool = False) -> dict:
    today = time.strftime("%Y-%m-%d")
    return {"v": 1, "generation": 0, "initialized": initialized, "sample": False,
            "itemsAtExport": 0, "lastExport": None, "lastOpen": today,
            "created": now_ms()}


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise DataError(f"无法读取数据文件：{path.name}") from exc


def write_atomic(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    backup = path.with_name(path.name + ".bak")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with temp.open("r", encoding="utf-8") as fh:
            json.load(fh)
        if path.exists():
            shutil.copy2(path, backup)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def initial_state() -> dict:
    return {"tasks": [], "notes": [], "projects": [], "meta": default_meta(False), "generation": 0}


def state_from_disk() -> dict:
    paths = {key: APP_DIR / filename for key, filename in DATA_FILES.items()}
    if not any(path.exists() for path in paths.values()):
        return initial_state()
    if not all(path.exists() for path in paths.values()):
        raise DataError("本地数据文件不完整，请从备份恢复")
    tasks_doc, notes_doc, projects_doc, meta = [read_json(paths[k]) for k in ("tasks", "notes", "projects", "meta")]
    docs = (("tasks", tasks_doc), ("notes", notes_doc), ("projects", projects_doc))
    generations = [doc.get("generation") for _, doc in docs] + [meta.get("generation")]
    if len(set(generations)) != 1:
        raise DataError("本地数据正在恢复中或版本不一致，请重试或从备份恢复")
    for key, doc in docs:
        if not isinstance(doc.get("items"), list):
            raise DataError(f"{DATA_FILES[key]} 格式不正确")
    if not isinstance(meta, dict) or not isinstance(meta.get("initialized"), bool):
        raise DataError("meta.json 格式不正确")
    return {"tasks": tasks_doc["items"], "notes": notes_doc["items"],
            "projects": projects_doc["items"], "meta": meta,
            "generation": generations[0]}


def validate_state(state: dict) -> dict:
    if not isinstance(state, dict):
        raise DataError("请求数据格式不正确")
    for key in ("tasks", "notes", "projects"):
        if not isinstance(state.get(key), list):
            raise DataError(f"{key} 必须是数组")
    meta = state.get("meta")
    if not isinstance(meta, dict):
        raise DataError("meta 必须是对象")
    return state


def persist_state(state: dict) -> dict:
    global write_lock
    validate_state(state)
    generation = int(state.get("generation") or state.get("meta", {}).get("generation") or 0) + 1
    meta = copy.deepcopy(state["meta"])
    meta.update({"v": 1, "generation": generation})
    payloads = {
        "tasks": {"v": 1, "generation": generation, "items": state["tasks"]},
        "notes": {"v": 1, "generation": generation, "items": state["notes"]},
        "projects": {"v": 1, "generation": generation, "items": state["projects"]},
        "meta": meta,
    }
    APP_DIR.mkdir(parents=True, exist_ok=True)
    for key, payload in payloads.items():
        write_atomic(APP_DIR / DATA_FILES[key], payload)
    return {"tasks": state["tasks"], "notes": state["notes"], "projects": state["projects"],
            "meta": meta, "generation": generation}


def zip_bytes(state: dict) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("tasks.json", json.dumps({"v": 1, "generation": state["generation"], "items": state["tasks"]}, ensure_ascii=False, indent=2))
        archive.writestr("notes.json", json.dumps({"v": 1, "generation": state["generation"], "items": state["notes"]}, ensure_ascii=False, indent=2))
        archive.writestr("projects.json", json.dumps({"v": 1, "generation": state["generation"], "items": state["projects"]}, ensure_ascii=False, indent=2))
        archive.writestr("meta.json", json.dumps(state["meta"], ensure_ascii=False, indent=2))
    return output.getvalue()


def state_from_zip(raw: bytes) -> dict:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = set(archive.namelist())
            if not set(DATA_FILES.values()).issubset(names):
                raise DataError("备份缺少必要的数据文件")
            docs = {name: json.loads(archive.read(name).decode("utf-8")) for name in DATA_FILES.values()}
    except DataError:
        raise
    except Exception as exc:
        raise DataError("备份文件不是有效的工作台 ZIP") from exc
    state = {"tasks": docs["tasks.json"].get("items"), "notes": docs["notes.json"].get("items"),
             "projects": docs["projects.json"].get("items"), "meta": docs["meta.json"]}
    return validate_state(state)


def load_config() -> dict:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        write_atomic(CONFIG_PATH, DEFAULT_CONFIG)
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise DataError("config.json 格式不正确") from exc
    host = config.get("host", DEFAULT_CONFIG["host"])
    port = config.get("port", DEFAULT_CONFIG["port"])
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise DataError("host 只能是本机地址")
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise DataError("port 必须是 1 到 65535 之间的整数")
    return {"host": host, "port": port}


class Handler(BaseHTTPRequestHandler):
    server_version = "PersonalOfficeWorkbench/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, status, body, content_type="application/json; charset=utf-8"):
        raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length)

    def _check_origin(self):
        origin = self.headers.get("Origin")
        if origin and not origin.startswith("http://127.0.0.1:") and not origin.startswith("http://localhost:"):
            self._send(HTTPStatus.FORBIDDEN, {"error": "只允许本机工作台访问"})
            return False
        return True

    def do_GET(self):
        if self.path == "/api/workbench":
            if not self._check_origin(): return
            try: self._send(HTTPStatus.OK, state_from_disk())
            except DataError as exc: self._send(HTTPStatus.CONFLICT, {"error": str(exc)})
            return
        if self.path == "/" or self.path == "/personal-office-workbench.html":
            self.send_response(HTTPStatus.OK)
            raw = (ROOT / "personal-office-workbench.html").read_bytes()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers(); self.wfile.write(raw); return
        self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_PUT(self):
        if self.path != "/api/workbench" or not self._check_origin(): return
        try:
            saved = persist_state(json.loads(self._body().decode("utf-8")))
            self._send(HTTPStatus.OK, saved)
        except (ValueError, UnicodeDecodeError, DataError) as exc:
            self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def do_POST(self):
        if not self._check_origin(): return
        path = urlparse(self.path)
        try:
            if path.path == "/api/backup/export":
                self._send(HTTPStatus.OK, zip_bytes(state_from_disk()), "application/zip")
                return
            if path.path == "/api/backup/preview":
                state = state_from_zip(self._body())
                self._send(HTTPStatus.OK, {"count": sum(len(state[k]) for k in ("tasks", "notes", "projects"))})
                return
            if path.path == "/api/backup/import":
                mode = parse_qs(path.query).get("mode", [""])[0]
                incoming = state_from_zip(self._body())
                current = state_from_disk()
                if mode == "replace":
                    result = incoming
                elif mode == "merge":
                    result = merge_states(current, incoming)
                else:
                    raise DataError("导入模式不正确")
                result["meta"]["initialized"] = True
                result["meta"]["sample"] = False
                result["meta"]["itemsAtExport"] = 0
                self._send(HTTPStatus.OK, persist_state(result))
                return
            self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except (ValueError, UnicodeDecodeError, DataError) as exc:
            self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})


def merge_states(current: dict, incoming: dict) -> dict:
    result = copy.deepcopy(current)
    by_name = {p.get("name"): p.get("id") for p in result["projects"] if p.get("name")}
    source_names = {p.get("id"): p.get("name") for p in incoming["projects"]}
    for project in incoming["projects"]:
        if project.get("name") and project["name"] not in by_name:
            project = copy.deepcopy(project); project["id"] = f"import-{now_ms()}-{len(result['projects'])}"
            by_name[project["name"]] = project["id"]; result["projects"].append(project)
    task_titles = {x.get("title") for x in result["tasks"]}
    for task in incoming["tasks"]:
        if task.get("title") and task["title"] not in task_titles:
            task = copy.deepcopy(task); task["id"] = f"import-{now_ms()}-{len(result['tasks'])}"
            name = source_names.get(task.get("pid")); task["pid"] = by_name.get(name, "")
            result["tasks"].append(task); task_titles.add(task["title"])
    note_texts = {x.get("text") for x in result["notes"]}
    for note in incoming["notes"]:
        if note.get("text") and note["text"] not in note_texts:
            note = copy.deepcopy(note); note["id"] = f"import-{now_ms()}-{len(result['notes'])}"
            result["notes"].append(note); note_texts.add(note["text"])
    return result


def main():
    config = load_config()
    if config["host"] == "localhost": config["host"] = "127.0.0.1"
    server = ThreadingHTTPServer((config["host"], config["port"]), Handler)
    print(f"Personal Office Workbench listening on http://{config['host']}:{config['port']}", flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == "__main__":
    main()
