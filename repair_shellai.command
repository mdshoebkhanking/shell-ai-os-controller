#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 installer/bootstrap.py repair --yes
read -r -p "Repair complete. Press Enter to close..."

