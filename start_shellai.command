#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

export PYTHONUTF8="${PYTHONUTF8:-1}"
export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"
export SHELL_TTS_ENGINE="${SHELL_TTS_ENGINE:-fast}"
export SHELL_V2_STREAM="${SHELL_V2_STREAM:-1}"
export SHELL_LEGACY_UI="${SHELL_LEGACY_UI:-0}"
export SHELL_IMAGE_LOCAL_FALLBACK="${SHELL_IMAGE_LOCAL_FALLBACK:-1}"

echo
echo "============================================================"
echo " Shell AI OS Controller - Launcher"
echo "============================================================"
echo " Starting Shell AI Web UI. Logs are written to:"
echo "   .shell_runtime/logs/hub.log"
echo "   .shell_runtime/logs/ui.log"
echo

python3 installer/bootstrap.py launch --repair-if-needed
