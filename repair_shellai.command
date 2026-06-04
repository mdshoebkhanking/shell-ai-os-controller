#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export SHELL_LEGACY_UI="${SHELL_LEGACY_UI:-0}"
export SHELL_V2_STREAM="${SHELL_V2_STREAM:-1}"
export SHELL_TTS_ENGINE="${SHELL_TTS_ENGINE:-fast}"
export SHELL_IMAGE_LOCAL_FALLBACK="${SHELL_IMAGE_LOCAL_FALLBACK:-1}"
python3 installer/bootstrap.py repair --yes
echo "Repair complete. Health report: .shell_runtime/install_health.json"
read -r -p "Press Enter to close..."
