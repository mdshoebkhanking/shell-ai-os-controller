#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export SHELL_LEGACY_UI="${SHELL_LEGACY_UI:-0}"
export SHELL_V2_STREAM="${SHELL_V2_STREAM:-1}"
export SHELL_TTS_ENGINE="${SHELL_TTS_ENGINE:-fast}"
export SHELL_IMAGE_LOCAL_FALLBACK="${SHELL_IMAGE_LOCAL_FALLBACK:-1}"

if ! command -v python3 >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-venv python3-pip
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3 python3-pip python3-virtualenv
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -S --needed python python-pip python-virtualenv
  else
    echo "Python 3 is missing and no supported package manager was found."
    exit 1
  fi
fi

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
  echo "Python 3.10+ is required. Install Python 3.10+ and rerun this installer."
  exit 1
fi

python3 installer/bootstrap.py install --yes
echo "Install complete. Use ./start_shellai.sh to launch Shell AI."
echo "Health report: .shell_runtime/install_health.json"
