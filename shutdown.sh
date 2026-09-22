#!/bin/bash
#
# 个人办公工作台 · 本地停止器
# 仅停止由同目录 start.sh 启动的 server.py；不会按端口猜测或强制结束进程。

set -u

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="${TMPDIR:-/tmp}/personal-office-workbench"
PIDFILE="${RUNTIME_DIR}/server.pid"

if [ ! -r "${PIDFILE}" ]; then
  echo "工作台服务未运行。"
  exit 0
fi

PID="$(tr -d '[:space:]' < "${PIDFILE}")"
if ! [[ "${PID}" =~ ^[0-9]+$ ]]; then
  echo "PID 文件内容无效，未停止任何进程：${PIDFILE}" >&2
  exit 1
fi

if ! kill -0 "${PID}" 2>/dev/null; then
  rm -f "${PIDFILE}"
  echo "工作台服务未运行，已清理失效的 PID 文件。"
  exit 0
fi

COMMAND="$(ps -p "${PID}" -o command= 2>/dev/null || true)"
if [[ "${COMMAND}" != *"${DIR}/server.py"* ]]; then
  echo "PID 文件未指向当前工作台服务，未停止任何进程。" >&2
  exit 1
fi

kill -TERM "${PID}"

for _ in $(seq 1 50); do
  if ! kill -0 "${PID}" 2>/dev/null; then
    rm -f "${PIDFILE}"
    echo "工作台服务已停止。"
    exit 0
  fi
  sleep 0.1
done

echo "已请求停止工作台服务，但进程仍在退出中：${PID}" >&2
exit 1
