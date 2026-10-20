#!/bin/bash
# Source-workbench lifecycle entry point. Safe to call from any directory.
set -u

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
RUNTIME_DIR="${TMPDIR:-/tmp}/personal-office-workbench"
PIDFILE="${RUNTIME_DIR}/server.pid"
LOGFILE="${RUNTIME_DIR}/server.log"
ACTION="${1:-}"
OPEN_BROWSER=1
if [ "$#" -gt 0 ]; then shift; fi
for option in "$@"; do
  case "${option}" in
    --no-open) OPEN_BROWSER=0 ;;
    '') ;;
    *) echo "未知参数：${option}" >&2; exit 1 ;;
  esac
done

usage() {
  echo "用法：${BASH_SOURCE[0]} {start|stop|restart|status} [--no-open]"
  echo "start 启动 · stop 停止 · restart 重启 · status 查看状态"
}

if [ -z "${ACTION}" ]; then
  printf '个人办公工作台\n1) 启动\n2) 停止\n3) 重启\n4) 查看状态\n0) 退出\n'
  read -r -p '请选择：' ACTION || { usage; exit 1; }
fi
case "${ACTION}" in
  1|启动) ACTION=start ;;
  2|停止) ACTION=stop ;;
  3|重启) ACTION=restart ;;
  4|状态) ACTION=status ;;
  0|退出) exit 0 ;;
  -h|--help|help) usage; exit 0 ;;
  start|stop|restart|status) ;;
  *) usage; exit 1 ;;
esac

PY="$(command -v python3 2>/dev/null || true)"
if [ -z "${PY}" ]; then echo '未找到 Python 3，无法管理工作台。' >&2; exit 1; fi
for dependency in curl lsof ps; do
  if ! command -v "${dependency}" >/dev/null 2>&1; then
    echo "缺少命令：${dependency}" >&2; exit 1
  fi
done

# Import only configuration constants; do not create or change user data here.
CONFIG="$("${PY}" - "${DIR}" <<'PY'
import json
import sys
sys.path.insert(0, sys.argv[1])
import server
try:
    config = json.loads(server.CONFIG_PATH.read_text(encoding='utf-8')) if server.CONFIG_PATH.exists() else server.DEFAULT_CONFIG
    host = config.get('host', '127.0.0.1')
    port = config.get('port', 8799)
    if host not in ('127.0.0.1', 'localhost', '::1'):
        raise ValueError('host 只能是本机地址')
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('port 必须是 1 到 65535 之间的整数')
    print('127.0.0.1' if host == 'localhost' else host)
    print(port)
except (OSError, ValueError, AttributeError) as error:
    print('读取工作台配置失败：' + str(error), file=sys.stderr)
    sys.exit(1)
PY
)" || exit 1
HOST="${CONFIG%%$'\n'*}"
PORT="${CONFIG#*$'\n'}"
URL_HOST="${HOST}"
if [ "${HOST}" = '::1' ]; then URL_HOST='[::1]'; fi
URL="http://${URL_HOST}:${PORT}/personal-office-workbench.html"
PROC_PID=""

alive() {
  kill -0 "$1" 2>/dev/null || return 1
  # A terminated child may remain as a zombie until its parent reaps it.
  case "$(ps -p "$1" -o stat= 2>/dev/null)" in *Z*) return 1 ;; esac
  return 0
}

owned_pid() {
  local command suffix executable
  command="$(ps -p "$1" -o command= 2>/dev/null)" || return 1
  suffix=" ${DIR}/server.py"
  [[ "${command}" == *"${suffix}" ]] || return 1
  executable="${command%"${suffix}"}"
  [[ "${executable##*/}" =~ ^[Pp]ython([0-9]+([.][0-9]+)*)?$ ]]
}

# A port is used only to discover candidates. Every candidate must also be
# a Python process running this checkout's exact server.py before any signal.
find_server() {
  local recorded listeners candidate
  PROC_PID=""
  recorded=""
  if [ -r "${PIDFILE}" ]; then recorded="$(tr -d '[:space:]' < "${PIDFILE}")"; fi
  if [ -n "${recorded}" ]; then
    if ! [[ "${recorded}" =~ ^[1-9][0-9]*$ ]]; then
      echo "PID 文件内容无效，拒绝操作：${PIDFILE}" >&2; return 2
    fi
    if alive "${recorded}"; then
      if ! owned_pid "${recorded}"; then
        echo "PID ${recorded} 不属于当前工作台，拒绝操作。" >&2; return 2
      fi
      PROC_PID="${recorded}"
    fi
  fi
  listeners="$(lsof -nP -t -iTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null | sort -u)"
  for candidate in ${listeners}; do
    if ! owned_pid "${candidate}"; then
      echo "端口 ${PORT} 被其他程序占用（PID ${candidate}），拒绝操作。" >&2; return 2
    fi
    if [ -n "${PROC_PID}" ] && [ "${PROC_PID}" != "${candidate}" ]; then
      echo '发现多个工作台进程，拒绝自动操作，请先检查。' >&2; return 2
    fi
    PROC_PID="${candidate}"
  done
  [ -n "${PROC_PID}" ]
}

ready() { curl --noproxy '*' --connect-timeout 1 --max-time 2 -fsS -o /dev/null "${URL}" 2>/dev/null; }

open_page() {
  [ "${OPEN_BROWSER}" -eq 1 ] || return 0
  if command -v open >/dev/null 2>&1; then
    open "${URL}" || echo "服务已运行，浏览器未能自动打开，请访问：${URL}" >&2
  else
    echo "请在浏览器打开：${URL}"
  fi
}

start_workbench() {
  local result pid count
  find_server; result=$?
  if [ "${result}" -eq 2 ]; then return 1; fi
  if [ "${result}" -eq 0 ]; then
    if ! ready; then echo "工作台进程存在但页面未就绪（PID ${PROC_PID}），请检查日志：${LOGFILE}" >&2; return 1; fi
    echo "工作台已在运行（PID ${PROC_PID}）：${URL}"
    open_page; return 0
  fi
  mkdir -p "${RUNTIME_DIR}" || return 1
  (
    cd "${DIR}" || exit 1
    exec nohup "${PY}" "${DIR}/server.py"
  ) >"${LOGFILE}" 2>&1 </dev/null &
  pid=$!
  printf '%s\n' "${pid}" > "${PIDFILE}"
  count=0
  while [ "${count}" -lt 60 ]; do
    if ! alive "${pid}"; then break; fi
    if ready && owned_pid "${pid}"; then
      echo "工作台已启动（PID ${pid}）：${URL}"
      open_page; return 0
    fi
    sleep 0.1
    count=$((count + 1))
  done
  echo "工作台启动失败或未就绪，请查看日志：${LOGFILE}" >&2
  return 1
}

stop_workbench() {
  local result pid count
  find_server; result=$?
  if [ "${result}" -eq 2 ]; then return 1; fi
  if [ "${result}" -eq 1 ]; then echo '工作台未运行。'; return 0; fi
  pid="${PROC_PID}"
  if ! kill -TERM "${pid}"; then echo "无法停止工作台（PID ${pid}）。" >&2; return 1; fi
  count=0
  while [ "${count}" -lt 50 ]; do
    if ! alive "${pid}"; then
      if [ -r "${PIDFILE}" ] && [ "$(tr -d '[:space:]' < "${PIDFILE}")" = "${pid}" ]; then : > "${PIDFILE}"; fi
      echo "工作台已停止（PID ${pid}）。"
      return 0
    fi
    sleep 0.1
    count=$((count + 1))
  done
  echo "工作台尚未退出（PID ${pid}），已取消后续启动。" >&2
  return 1
}

case "${ACTION}" in
  start) start_workbench ;;
  stop) stop_workbench ;;
  restart)
    echo '正在重启工作台……'
    stop_workbench && start_workbench
    ;;
  status)
    find_server; result=$?
    if [ "${result}" -eq 2 ]; then exit 1; fi
    if [ "${result}" -eq 0 ]; then echo "工作台运行中（PID ${PROC_PID}）：${URL}"; else echo '工作台未运行。'; fi
    ;;
esac
