#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_DIR}"

PORT="${SHELL_WEB_UI_DEBUG_PORT:-9352}"
OUT_DIR="${1:-${REPO_DIR}/.shell_runtime/tab_switch_stability_ui_probe}"
CHROME_BIN="${CHROME_BIN:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
PROFILE_DIR="${TMPDIR:-/tmp}/shell-tab-switch-ui-proof-${PORT}-$$"
CHROME_LOG="${OUT_DIR}/chrome.log"
RUN_LOG="${OUT_DIR}/runner.log"
APP_URL="file://${REPO_DIR}/shell_web_ui/dist/index.html?shell-ui-tab-probe=1"

mkdir -p "${OUT_DIR}"
exec > >(tee "${RUN_LOG}") 2>&1

echo "Shell AI tab switch stability UI proof"
echo "Repo: ${REPO_DIR}"
echo "Output: ${OUT_DIR}"
echo

if [[ ! -x "${CHROME_BIN}" ]]; then
  echo "ERROR: Google Chrome not found at:"
  echo "  ${CHROME_BIN}"
  echo
  echo "Set CHROME_BIN to your Chrome binary path and run again."
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "ERROR: node is required to run the CDP probe."
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is required to wait for Chrome DevTools."
  exit 1
fi

mkdir -p "${PROFILE_DIR}"

echo "Building Shell Web UI..."
npm run build --prefix shell_web_ui

cleanup() {
  if [[ -n "${CHROME_PID:-}" ]]; then
    kill "${CHROME_PID}" >/dev/null 2>&1 || true
    wait "${CHROME_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo
echo "Launching Chrome headless on DevTools port ${PORT}..."
"${CHROME_BIN}" \
  --headless=new \
  "--remote-debugging-port=${PORT}" \
  "--remote-allow-origins=*" \
  "--user-data-dir=${PROFILE_DIR}" \
  --window-size=1280,760 \
  --allow-file-access-from-files \
  --ignore-gpu-blocklist \
  --enable-webgl \
  --enable-unsafe-swiftshader \
  --disable-gpu-sandbox \
  --disable-dev-shm-usage \
  --disable-background-networking \
  --disable-component-update \
  --disable-sync \
  --disable-features=MediaRouter \
  --no-first-run \
  --no-default-browser-check \
  "${APP_URL}" >"${CHROME_LOG}" 2>&1 &
CHROME_PID=$!

ready="no"
for _ in {1..60}; do
  if curl -fsS "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1; then
    ready="yes"
    break
  fi
  if ! kill -0 "${CHROME_PID}" >/dev/null 2>&1; then
    echo "ERROR: Chrome exited before DevTools became ready."
    echo "Chrome log:"
    sed -n '1,160p' "${CHROME_LOG}" || true
    exit 1
  fi
  sleep 0.25
done

if [[ "${ready}" != "yes" ]]; then
  echo "ERROR: Chrome DevTools did not become ready on port ${PORT}."
  echo "Try another port, for example:"
  echo "  SHELL_WEB_UI_DEBUG_PORT=9362 ${0}"
  exit 1
fi

echo "Running tab switch probe..."
node tools/tab_switch_stability_cdp_probe.mjs "${PORT}" "${OUT_DIR}"

echo
echo "Done."
echo "Report: ${OUT_DIR}/report.json"
