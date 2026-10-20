#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title shutdowngzt
# @raycast.mode compact

# Optional parameters:
# @raycast.icon 🤖

# Documentation:
# @raycast.description 关闭工作台
# @raycast.author 1473220649
# @raycast.authorURL https://raycast.com/1473220649

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
exec bash "${DIR}/workbench.sh" stop "$@"
