#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo
echo "============================================================"
echo " Shell AI OS Controller - One-Click Installer"
echo "============================================================"
echo " This will automatically:"
echo "  - find or install Python 3.10+ where possible"
echo "  - create the managed .shellai_venv virtual environment"
echo "  - install Python requirements"
echo "  - install all UI requirements from shell_ui/requirements_ui.txt"
echo "  - install and build the React Shell Web UI in shell_web_ui"
echo "  - install Playwright Chromium"
echo "  - install ffmpeg, OCR, and Node.js when Homebrew is available"
echo "  - create .env and runtime folders"
echo "  - run health checks"
echo

export SHELL_LEGACY_UI="${SHELL_LEGACY_UI:-0}"

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "Python 3.10+ missing. Installing Python 3.13 with Homebrew..."
    brew install python@3.13
  else
    echo "Python 3.10+ is missing and Homebrew is not installed."
    echo "Install Python 3.10+ from https://www.python.org/downloads/macos/ and run this again."
    read -r -p "Press Enter to close..."
    exit 1
  fi
fi

python3 installer/bootstrap.py install --yes

echo
echo "============================================================"
echo " Install complete."
echo " Now double-click start_shellai.command to open Shell AI."
echo "============================================================"
read -r -p "Press Enter to close..."
