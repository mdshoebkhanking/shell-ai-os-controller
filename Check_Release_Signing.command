#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

PY_CMD=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PY_CMD="$candidate"
    break
  fi
done

if [[ -z "$PY_CMD" ]]; then
  echo "Python 3.10+ is required for this check."
  exit 1
fi

"$PY_CMD" tools/signing_notarization_check.py --strict
echo
echo "Report: .shell_runtime/signing_notarization_report.json"
