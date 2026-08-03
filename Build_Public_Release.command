#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo
echo "============================================================"
echo " Shell AI OS Controller - Public Release Check"
echo "============================================================"
echo

if command -v python3 >/dev/null 2>&1; then
  python3 tools/production_release_check.py
  python3 tools/package_public_release.py
  python3 tools/production_readiness.py --run-tests
else
  python tools/production_release_check.py
  python tools/package_public_release.py
  python tools/production_readiness.py --run-tests
fi

echo
echo "Public release package created in dist."
read -r -p "Press Enter to close..."
