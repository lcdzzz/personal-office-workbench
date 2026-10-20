#!/bin/bash
# Restart only after the current source-workbench process has exited.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
exec bash "${DIR}/workbench.sh" restart "$@"
