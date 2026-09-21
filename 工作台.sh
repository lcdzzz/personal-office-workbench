#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title 工作台
# @raycast.mode compact

# Optional parameters:
# @raycast.icon 🤖

# Documentation:
# @raycast.description 工作台
# @raycast.author 1473220649
# @raycast.authorURL https://raycast.com/1473220649


DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAGE="personal-office-workbench.html"
RUNTIME_DIR="${TMPDIR:-/tmp}/personal-office-workbench"
PIDFILE="${RUNTIME_DIR}/server.pid"
LOGFILE="${RUNTIME_DIR}/server.log"
mkdir -p "${RUNTIME_DIR}"

# ---------- 1) 找一个可用的 python3（macOS 自带 /usr/bin/python3） ----------
PY=""
for c in /usr/bin/python3 "$(command -v python3 2>/dev/null)"; do
  if [ -n "${c}" ] && [ -x "${c}" ]; then PY="${c}"; break; fi
done
if [ -z "${PY}" ]; then
  osascript -e 'display alert "个人办公工作台" message "未找到 python3，无法启动本地服务。可执行 xcode-select --install 安装命令行工具后重试。"' >/dev/null 2>&1
  exit 1
fi

# ---------- 2) 读取用户配置（实际配置位于应用数据目录） ----------
PORT="$(${PY} -c 'import json,pathlib; p=pathlib.Path.home()/"Library/Application Support/PersonalOfficeWorkbench/config.json"; print(json.loads(p.read_text()).get("port",8799) if p.exists() else 8799)' 2>/dev/null || echo 8799)"
URL="http://127.0.0.1:${PORT}/${PAGE}"

# ---------- 3) 服务已在跑？直接开页面 ----------
if curl -fsS -o /dev/null "${URL}" 2>/dev/null; then
  open "${URL}"
  exit 0
fi

# ---------- 4) 后台起服务（仅本机回环，不对外网暴露） ----------
cd "${DIR}" || exit 1
nohup "${PY}" "${DIR}/server.py" >"${LOGFILE}" 2>&1 &
echo $! > "${PIDFILE}"

# ---------- 5) 等端口就绪（最多约 6 秒） ----------
for _ in $(seq 1 60); do
  if curl -fsS -o /dev/null "${URL}" 2>/dev/null; then break; fi
  sleep 0.1
done

# ---------- 6) 开页面 ----------
open "${URL}"
