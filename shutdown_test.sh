#!/bin/bash
# Verifies that shutdown.sh never stops an unrelated process recorded in a stale PID file.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_RUNTIME="$(mktemp -d)"
SLEEP_PID=""

cleanup() {
  if [ -n "${SLEEP_PID}" ] && kill -0 "${SLEEP_PID}" 2>/dev/null; then
    kill "${SLEEP_PID}" 2>/dev/null || true
    wait "${SLEEP_PID}" 2>/dev/null || true
  fi
  if [ -f "${TEST_RUNTIME}/personal-office-workbench/server.pid" ]; then
    rm "${TEST_RUNTIME}/personal-office-workbench/server.pid"
  fi
  rmdir "${TEST_RUNTIME}/personal-office-workbench" "${TEST_RUNTIME}" 2>/dev/null || true
}
trap cleanup EXIT

sleep 30 &
SLEEP_PID=$!
mkdir "${TEST_RUNTIME}/personal-office-workbench"
printf '%s\n' "${SLEEP_PID}" > "${TEST_RUNTIME}/personal-office-workbench/server.pid"

if OUTPUT="$(TMPDIR="${TEST_RUNTIME}/" bash "${DIR}/shutdown.sh" 2>&1)"; then
  echo "shutdown.sh should reject an unrelated PID" >&2
  exit 1
fi
if [[ "${OUTPUT}" != *"不属于当前工作台，拒绝操作"* ]]; then
  echo "shutdown.sh failed before checking the unrelated PID: ${OUTPUT}" >&2
  exit 1
fi

if ! kill -0 "${SLEEP_PID}" 2>/dev/null; then
  echo "shutdown.sh stopped an unrelated process" >&2
  exit 1
fi

echo "shutdown safety check passed"
