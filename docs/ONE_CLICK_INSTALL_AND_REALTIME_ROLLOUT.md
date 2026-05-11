# One-Click Install + Realtime Rollout

Generated: 2026-05-11

## 1. Latency Audit

Current measured local performance:

| Area | Result |
| --- | ---: |
| Fast local intent reply | ~0.002 ms |
| Fast local intent classifier | ~0.455 ms |
| TTS engine detection | ~0.305 ms |
| Hub `/health` | ~9 ms |
| Hub `/capabilities` cold | ~0.859 s |
| Hub `/capabilities` cached | ~10 ms |
| Full UI E2E probe | passed |
| Full test suite | `141 passed, 1 warning` |

## 2. Bottleneck Analysis

Fixed in the current stabilization work:

- Shell-v2 streaming is default-on.
- Shell-v2 interactive timeout is `12s`, down from `60s`.
- Provider timeout is configurable and defaults to `18s`, down from hardcoded `45s`.
- Tiny deterministic intents bypass backend orchestration.
- TTS wakes immediately instead of waiting for a polling tick.
- Voice stream chunks now feed transcript + TTS before final response completion.
- Hub capabilities endpoint now uses an in-memory TTL cache.

Remaining bottlenecks:

- First capabilities build is still heavy because the catalog payload is about 1 MB.
- Live mic cannot start until `sounddevice` is installed.
- Realtime LiveKit voice cannot start until `livekit` is installed.
- True PCM-level streaming TTS still needs a dedicated engine such as Piper or RealtimeTTS.

## 3. TTS Optimization Strategy

Current production default:

1. Use `SHELL_TTS_ENGINE=fast`.
2. Prefer local system speech for fastest first audio:
   - macOS: `say`
   - Windows: SAPI
   - Linux: `spd-say`, `espeak-ng`, or `espeak`
3. Use neural/file TTS only as an optional quality mode.
4. Queue sentence-sized TTS segments during AI response streaming.

Next step:

- Add Piper/RealtimetTS adapter behind the existing `TTSSpeaker` interface.
- Measure first audio byte, not only playback process spawn time.

## 4. Realtime Streaming Strategy

Implemented:

- SSE text streaming is enabled by default for Shell-v2.
- Chat renders chunks incrementally.
- Voice page receives stream chunks and starts speaking sentence-sized chunks early.

Still required for full realtime voice:

- Streaming STT.
- Streaming PCM TTS.
- Barge-in cancellation.
- Audio output buffer tracing.

## 5. UI Optimization Strategy

Implemented:

- UI starts with immediate local feedback for tiny intents.
- Page prewarming remains deferred after first paint.
- System/voice timers are stopped when pages are off-screen.
- Settings now includes a Help Center with install health, repair entry, guides, and logs.

Known UI startup issue:

- Missing `"Sans Serif"` font alias costs about 50 ms during offscreen probe startup.

## 6. Installer Architecture

Created `installer/`:

- `installer/bootstrap.py`: shared install, repair, health, and launch engine.
- `installer/install_windows.bat`: Windows installer wrapper.
- `installer/install_mac.command`: macOS installer wrapper.
- `installer/install_linux.sh`: Linux installer wrapper.
- `installer/README.md`: beginner install guide.

Bootstrap commands:

```bash
python3 installer/bootstrap.py install --yes
python3 installer/bootstrap.py health
python3 installer/bootstrap.py repair --yes
python3 installer/bootstrap.py launch --repair-if-needed
```

## 7. Launcher Architecture

Top-level launchers:

- `Start_ShellAI.bat`
- `start_shellai.command`
- `start_shellai.sh`

Launch lifecycle:

1. Detect Python.
2. Use managed venv.
3. Run health.
4. Start hub.
5. Wait for `/health`.
6. Export `SHELL_HUB_URL` and `SHELL_TOKEN_URL`.
7. Start PyQt UI.
8. Write logs to `.shell_runtime/logs`.
9. Stop hub when UI exits.

## 8. Dependency Management System

Python dependencies:

- Installed from `requirements.txt`.
- Added missing runtime dependencies:
  - `websocket-client`
  - `uv`
  - `livekit`
  - `edge-tts`

System dependencies:

- macOS: `brew install ffmpeg tesseract`
- Linux: `apt`, `dnf`, or `pacman` install ffmpeg/tesseract/python venv packages
- Windows: `winget` installs Python, ffmpeg, Tesseract OCR, and uv

## 9. Health-Check Architecture

`installer/bootstrap.py health` verifies:

- OS
- Python
- venv
- core imports
- optional voice/browser/OCR imports
- ffmpeg
- tesseract
- uvx
- `.env`

Output:

- Human-readable terminal output.
- JSON report at `.shell_runtime/install_health.json`.

## 10. Auto-Repair Design

Repair entrypoints:

- `Repair_ShellAI.bat`
- `repair_shellai.command`
- `repair_shellai.sh`

Repair actions:

- Reuse/create venv.
- Upgrade pip/setuptools/wheel.
- Reinstall/upgrade Python requirements.
- Install Playwright Chromium.
- Install supported system dependencies when package manager exists.
- Re-run health check.

Errors are presented as:

> microphone capture dependency is missing. Run Repair Shell AI to install `sounddevice` automatically.

instead of raw Python tracebacks.

## 11. Startup Lifecycle

One-click launch flow:

```text
User clicks launcher
-> Python/venv detected
-> health check runs
-> repair suggestion or auto repair
-> hub starts
-> hub health is polled
-> UI starts
-> logs are captured
-> hub exits when UI exits
```

## 12. Cross-Platform Strategy

Windows:

- Batch installer and launcher.
- Uses `py -3`, `python`, then `winget` Python fallback.
- Uses `winget` for ffmpeg, Tesseract, and uv.

macOS:

- `.command` installer and launcher.
- Uses `python3`, Homebrew fallback for Python/system tools.
- Uses built-in `say` for fast TTS.

Linux:

- Shell installer and launcher.
- Supports `apt-get`, `dnf`, and `pacman`.
- Uses `spd-say` or `espeak` if available.

## 13. Performance Profiling Results

Commands used:

```bash
.codex_ui_venv/bin/python installer/bootstrap.py health
.codex_ui_venv/bin/python tools/latency_probe.py
curl -s -w 'HEALTH_TIME=%{time_total}\n' http://127.0.0.1:5000/health
curl -s -o /tmp/cap.json -w 'TIME=%{time_total}\n' http://127.0.0.1:5000/capabilities
.codex_ui_venv/bin/python tools/e2e_ui_probe.py
.codex_ui_venv/bin/python -m pytest -q
```

Measured:

- `/health`: `0.009124s`
- `/capabilities` cold: `0.858642s`
- `/capabilities` cached: `0.010468s`

## 14. Rollout Implementation Plan

Completed:

- Cross-platform installer directory.
- One-click launchers.
- One-click repair scripts.
- Bootstrap health report.
- Human-readable dependency errors.
- Runtime logs directory.
- Help Center entry inside Settings.
- Cached capabilities endpoint.
- Low-latency env defaults in launcher.

Next implementation batch:

1. Add compact `/capabilities-summary` endpoint to avoid 1 MB UI payloads.
2. Add Piper/RealtimetTS streaming adapter.
3. Add first-audio-byte metric.
4. Add first-run setup wizard modal for mic/API/voice.
5. Package app with PyInstaller/Nuitka per OS after dependency flow is stable.
6. Run clean-machine validation on Windows, Linux, and macOS.

## Test Status

Verified locally on macOS:

- Python compile checks.
- Bash wrapper syntax.
- Bootstrap health flow.
- Hub `/health`.
- Hub `/capabilities` cold and cached.
- UI E2E probe.
- Full pytest suite.

Not verified in this environment:

- Clean Windows install.
- Clean Linux install.
- Real microphone capture.
- LiveKit realtime voice.
- Fresh network dependency install.

