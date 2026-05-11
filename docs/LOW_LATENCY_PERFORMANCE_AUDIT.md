# Shell AI OS Controller Low-Latency Audit

Generated: 2026-05-11

## 1. Latency Audit

Measured hot paths before/after this pass:

| Path | Before | After | Notes |
| --- | ---: | ---: | --- |
| Local canned reply | 0.348 ms | 0.002 ms | Direct local path is effectively instant. |
| Fast local intent classifier | N/A | 0.455 ms | New conservative bypass for greetings/time/help/thanks. |
| Tool/catalog discovery | 924.94 ms | 915.63 ms | Still the largest local CPU/backend payload path. |
| TTS engine detection | N/A | 0.305 ms | macOS resolves to built-in `say`. |
| Hub `/health` while running | N/A | 8.281 ms | Healthy backend diagnostic path. |
| Hub `/capabilities` while running | ~0.763 s | 0.766 s | 1,062,645 byte payload; still heavy. |
| Shell-v2 default timeout | 60 s | 12 s | Worst-case interactive stall reduced. |
| AI provider timeout | 45 s | 18 s | Worst-case provider stall reduced. |

## 2. Bottleneck Analysis

- Shell-v2 streaming existed but was opt-in. Text could wait for full non-streaming responses unless `SHELL_V2_STREAM=1` was manually set.
- Shell-v2 timeout was 60 seconds, which is unacceptable for interactive chat fallback behavior.
- Brain provider timeout was hardcoded to 45 seconds in multiple paths.
- TTS queue used 100 ms polling, adding avoidable delay before speech even starts.
- TTS default path preferred `edge-tts` file generation and Windows PowerShell playback. On this macOS host, `edge_tts` is not installed and PowerShell playback is not a valid low-latency fallback.
- Voice worker streaming signals were not connected in the voice path, so successful streaming could fail to finalize the voice UI.
- Capabilities payload remains large at about 1.06 MB and takes about 0.77 s over the local hub.

## 3. Voice Latency Analysis

Current host blockers:

- `sounddevice` is missing, so live microphone capture cannot start.
- `livekit` is missing, so the realtime cloud voice path is unavailable.
- `edge_tts` is missing, so neural file-based speech is unavailable.
- Built-in macOS `say` is available and now used as the fast default TTS fallback.

Implemented improvements:

- TTS thread now wakes by event instead of polling every 100 ms.
- TTS now defaults to `SHELL_TTS_ENGINE=fast`.
- Fast system TTS support added:
  - macOS: `say`
  - Windows: SAPI through PowerShell
  - Linux: `spd-say`, `espeak-ng`, or `espeak`
- Voice streaming now queues sentence-sized TTS chunks before the full AI response is complete.

## 4. Orchestration Overhead Analysis

- Remote Shell-v2 is still the primary non-local chat path.
- Streaming is enabled by default to reduce perceived first-token latency.
- Provider fallback timeout is now governed by `SHELL_AI_PROVIDER_TIMEOUT_S`, defaulting to 18 seconds.
- The local fast-intent bypass avoids tool routing, Socket.IO, Shell-v2 HTTP, and provider routing for tiny deterministic intents.

## 5. UI Performance Analysis

Verified through `tools/e2e_ui_probe.py`:

- Chat page renders and accepts real input.
- Voice page visual toggle preserves geometry.
- Tools page can execute calculator tool from UI.
- Windows MCP path shows unsupported-OS fallback on macOS.
- Settings page can update and commit settings.
- Text chat does not auto-trigger TTS.

Known UI/perf warnings:

- Offscreen Qt cannot render WebGL, so the probe uses the legacy visualizer.
- macOS reports missing accessibility trust for global hotkeys.
- Missing font family `"Sans Serif"` costs about 50 ms on startup.

## 6. Async Architecture Improvements

- Shell-v2 worker now emits structured latency events for request preparation, stream connection, first chunk, stream completion, non-stream completion, and failures.
- TTS thread now uses event wakeup and tracks queue/playback timing.
- Voice streaming now uses chunk callbacks instead of waiting only for a final reply.
- Low-latency warmup runs after first paint without blocking UI startup.

## 7. TTS Optimization Strategy

Current implementation prioritizes fast local playback:

1. Use local system TTS first for low startup latency.
2. Use `edge-tts` only when explicitly requested or when fast/system mode fails.
3. Keep TTS on a background thread.
4. Queue sentence-sized chunks during voice streaming.
5. Record TTS latency events into the in-process latency recorder.

Recommended next step:

- Install a real streaming local TTS engine such as Piper or RealtimeTTS and wrap it behind the same `TTSSpeaker` interface.

## 8. Streaming Implementation Strategy

Implemented:

- Text chat Shell-v2 SSE streaming is default-on.
- Voice AI worker stream chunks now update voice state and queue TTS chunks.

Still needed:

- Add true audio chunk streaming for a TTS engine that supports progressive PCM output.
- Add barge-in cancellation that stops current speech when the user starts talking.
- Add first-audio-byte metrics from the audio backend itself, not only process spawn time.

## 9. Caching Strategy

Implemented:

- Local deterministic intent bypass for repeated tiny intents.
- Existing MultiBrain cache remains active for provider responses.
- Latency recorder keeps recent in-memory hot-path samples.

Recommended:

- Cache `/capabilities` response in the hub and only recompute on plugin/tool file changes.
- Add a compact capabilities endpoint for UI list views.
- Keep full metadata lazy-loaded only when a tool row is opened.

## 10. Preload/Warmup Strategy

Implemented:

- UI schedules low-latency warmup 250 ms after startup.
- Warmup touches the fast local reply path and wakes the TTS thread.
- TTS detects the available system speech command during warmup without speaking.

Recommended:

- Precompute compact tool index at hub startup.
- Warm provider clients only after the UI is responsive.
- Avoid loading heavyweight memory/vector systems on first paint.

## 11. Fallback Strategy

Current fallback order:

1. Tiny deterministic chat intent -> local reply immediately.
2. Normal text -> Shell-v2 SSE stream.
3. Broken stream -> Shell-v2 non-streaming request.
4. Unreachable backend -> local fallback reply.
5. Voice TTS -> fast system TTS, then optional `edge-tts`.

Safety preserved:

- Text chat still does not auto-speak replies.
- Dangerous shell/code execution remains gated by existing safety flags.

## 12. Profiling Metrics

Commands used:

- `.codex_ui_venv/bin/python tools/latency_probe.py --json-out /private/tmp/shell_latency_probe_after.json`
- `.codex_ui_venv/bin/python tools/e2e_ui_probe.py --json-out /private/tmp/shell_ui_probe_latency_report2.json --screens-dir /private/tmp/shell_ui_probe_latency2`
- `curl -s -w '\nTIME_TOTAL=%{time_total}\n' http://127.0.0.1:5000/health`
- `curl -s -o /private/tmp/shell_capabilities.json -w 'TIME_TOTAL=%{time_total}\nSIZE=%{size_download}\n' http://127.0.0.1:5000/capabilities`
- `.codex_ui_venv/bin/python -m pytest -q`

Verification:

- UI E2E probe: passed.
- Targeted low-latency/UI/TTS tests: passed.
- Full test suite: `141 passed, 1 warning in 3.12s`.

## 13. Realtime Architecture Plan

Next high-impact changes:

1. Add compact cached `/capabilities-summary` endpoint.
2. Add true streaming local TTS provider with PCM chunk playback.
3. Add first-token and first-audio-byte metrics to the UI dashboard.
4. Add provider warm pools for configured API providers.
5. Add cancellation/barge-in from voice input to TTS playback.
6. Move heavy catalog discovery and memory indexing to explicit background readiness states.

## 14. Optimization Rollout Plan

Done in this pass:

- Default Shell-v2 streaming enabled.
- Interactive Shell-v2 timeout reduced from 60 s to 12 s.
- Provider timeout reduced from 45 s to configurable 18 s.
- Conservative local fast intents added.
- TTS event wakeup added.
- Fast portable system TTS fallback added.
- Voice streaming signal path fixed.
- Runtime latency recorder added.
- Latency probe tool added.
- Full UI probe and full tests validated.

Remaining production risks:

- Live mic cannot be validated until `sounddevice` is installed and microphone permission is granted.
- LiveKit realtime voice cannot be validated until `livekit` is installed.
- Shell-v2 service on port `8765` is not started by the current launcher.
- Capabilities payload remains too large for a realtime control surface.

