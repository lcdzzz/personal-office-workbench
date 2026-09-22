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
  rmdir "${TEST_RUNTIME}" 2>/dev/null || true
}
trap cleanup EXIT

sleep 30 &
SLEEP_PID=$!
printf '%s\n' "${SLEEP_PID}" > "${TEST_RUNTIME}/server.pid"

TMPDIR="${TEST_RUNTIME}/" bash "${DIR}/shutdown.sh" >/dev/null

if ! kill -0 "${SLEEP_PID}" 2>/dev/null; then
  echo "shutdown.sh stopped an unrelated process" >&2
  exit 1
fi

echo "shutdown safety check passed"
