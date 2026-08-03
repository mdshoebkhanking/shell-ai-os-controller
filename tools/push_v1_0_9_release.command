#!/bin/zsh
set -euo pipefail

REPO_DIR="/Users/m1/Documents/Codex/shell.v1.0-main-main/shell.v1.0-main-main/shell.v1.0-main-main/shell.v1.0-main-main"
EXPECTED_HEAD="8a4e5b90f076c509701a5a4778d3e2170d66caf4"
TAG_NAME="v1.0.9"

echo "Shell AI release tag helper"
echo "Repo: ${REPO_DIR}"
echo

cd "${REPO_DIR}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: This is not a git repository."
  exit 1
fi

current_head="$(git rev-parse HEAD)"
echo "Current HEAD: ${current_head}"

if [[ "${current_head}" != "${EXPECTED_HEAD}" ]]; then
  echo "ERROR: HEAD is not the expected v1.0.9 commit."
  echo "Expected: ${EXPECTED_HEAD}"
  echo "Actual:   ${current_head}"
  echo
  echo "Run this first, then try again:"
  echo "  git switch main"
  echo "  git pull --ff-only origin main"
  exit 1
fi

if git ls-remote --tags origin "${TAG_NAME}" | grep -q "${TAG_NAME}"; then
  echo "Remote tag ${TAG_NAME} already exists."
  exit 0
fi

if git tag --list "${TAG_NAME}" | grep -q "^${TAG_NAME}$"; then
  echo "Local tag ${TAG_NAME} already exists."
else
  echo "Creating local annotated tag ${TAG_NAME}..."
  git tag -a "${TAG_NAME}" -m "Release ${TAG_NAME}"
fi

echo "Pushing ${TAG_NAME} to origin..."
git push origin "${TAG_NAME}"

echo
echo "Done. GitHub Release workflow should start now:"
echo "https://github.com/mdshoebkhanking/shell-ai-os-controller/actions"

