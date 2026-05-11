#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 installer/bootstrap.py repair --yes

