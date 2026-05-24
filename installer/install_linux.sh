#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

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

python3 installer/bootstrap.py install --yes
echo "Install complete. Use ./start_shellai.sh to launch Shell AI."
