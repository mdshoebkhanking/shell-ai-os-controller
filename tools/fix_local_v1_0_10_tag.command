#!/bin/zsh
set -euo pipefail

REPO="/Users/m1/Documents/Codex/shell.v1.0-main-main/shell.v1.0-main-main/shell.v1.0-main-main/shell.v1.0-main-main"
TARGET_SHA="6d074c16436b3476a62dba44a9424b4a8e0f3616"

echo "Shell AI local tag fixer"
echo "Repo: $REPO"
echo

if [[ ! -d "$REPO/.git" ]]; then
  echo "ERROR: .git folder not found at repo path."
  exit 1
fi

git -C "$REPO" tag -f v1.0.10 "$TARGET_SHA"
ACTUAL="$(git -C "$REPO" rev-parse 'v1.0.10^{}')"

echo
echo "v1.0.10 now points to:"
echo "$ACTUAL"

if [[ "$ACTUAL" != "$TARGET_SHA" ]]; then
  echo "ERROR: tag verification failed."
  exit 1
fi

echo
echo "Done. Local v1.0.10 tag is synced."
echo "Press any key to close."
read -k 1
