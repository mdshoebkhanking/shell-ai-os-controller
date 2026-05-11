#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is missing. Run ONE_CLICK_INSTALL.command first."
  read -r -p "Press Enter to close..."
  exit 1
fi

python3 installer/bootstrap.py launch --repair-if-needed
