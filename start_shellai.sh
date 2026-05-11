#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 is missing. Run installer/install_linux.sh or installer/install_mac.command first."
  exit 1
fi

"$PYTHON_BIN" installer/bootstrap.py launch --repair-if-needed

