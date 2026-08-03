#!/bin/zsh
set -euo pipefail

REPO_DIR="/Users/m1/Documents/Codex/shell.v1.0-main-main/shell.v1.0-main-main/shell.v1.0-main-main/shell.v1.0-main-main"
EXPECTED_HEAD="cd68852"
TAG_NAME="v1.0.10"

echo "Shell AI release tag helper"
echo "Repo: ${REPO_DIR}"
echo

cd "${REPO_DIR}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: This is not a git repository."
  exit 1
fi

current_head="$(git rev-parse --short HEAD)"
echo "Current HEAD: ${current_head}"

if [[ "${current_head}" != "${EXPECTED_HEAD}" ]]; then
  echo "ERROR: HEAD is not the expected v1.0.10 commit."
  echo "Expected: ${EXPECTED_HEAD}"
  echo "Actual:   ${current_head}"
  echo
  echo "Run this first, then try again:"
  echo "  cd \"${REPO_DIR}\""
  echo "  git switch codex/windows-exe-installer-updates"
  echo "  git pull --ff-only origin codex/windows-exe-installer-updates"
  exit 1
fi

echo "Creating/updating local annotated tag ${TAG_NAME} at ${EXPECTED_HEAD}..."
git tag -f -a "${TAG_NAME}" -m "Release ${TAG_NAME}"

echo "Force-updating remote tag ${TAG_NAME} to ${EXPECTED_HEAD}..."
git push --force origin "refs/tags/${TAG_NAME}"

echo
echo "Done. GitHub Release workflow should start now:"
echo "https://github.com/mdshoebkhanking/shell-ai-os-controller/actions"
