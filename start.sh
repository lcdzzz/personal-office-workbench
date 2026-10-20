#!/bin/bash
# Compatibility entry point; all lifecycle checks live in workbench.sh.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
exec bash "${DIR}/workbench.sh" start "$@"
