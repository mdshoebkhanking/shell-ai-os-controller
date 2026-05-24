# Shell Performance Benchmark

## Targets

| Path | Target |
| --- | --- |
| Voice first partial | <100 ms after audio chunk availability |
| UI frame budget | <16 ms per visible update |
| Chart/telemetry repaint | <50 ms |
| API response handling | <30 ms local dispatch overhead |
| End-to-end interaction | <100 ms for local/streaming-visible feedback |

## Implemented Optimizations

- The primary Shell dashboard now uses the React/Vite renderer inside PyQt
  WebEngine. Heavy backend work remains in Python and communicates through the
  QWebChannel bridge so UI events stay responsive.
- Transcript streaming updates reuse one mutable bubble through `_stream_label`
  rather than creating a new widget per token.
- Dashboard system telemetry updates every 500 ms and network simulation updates
  every 1700 ms to avoid UI thread saturation.
- The existing Shell stream render batching remains capped at 16 ms by default
  through `SHELL_STREAM_RENDER_BATCH_MS`.
- Shell feature tools are local and mostly stdlib-based, avoiding import-heavy
  provider initialization until needed.
- Project scanning ignores heavyweight folders such as `.git`, `node_modules`,
  `venv`, `dist`, and `build`.
- The tool catalog remains AST-based, so new Shell tools are discoverable without
  importing modules that might touch OS APIs at scan time.
- Phase 1 telemetry charts now prefer PyQtGraph (`SHELL_PYQTGRAPH_ENABLED=1`)
  with downsampling, clipped rendering, fixed 60-sample windows, and latency
  recorder sampling. The previous QPainter chart remains available by setting
  `SHELL_PYQTGRAPH_ENABLED=0` or when `pyqtgraph` is not installed.
- Phase 2 Memory v2 uses local SQLite, WAL mode, redaction-before-write,
  lexical scoring, importance weighting, time-decay ranking, tag filtering, and
  recall audit logging behind `SHELL_MEMORY_V2_ENABLED=0`.
- Phase 2 offline STT adds a lazy sherpa-onnx streaming recognizer behind
  `SHELL_LOCAL_STT_ENABLED=0`. Voice recognition keeps the existing API path by
  default and only creates the local model when fallback or primary-local mode
  is explicitly enabled.
- Phase 3 Project RAG v2 uses incremental SQLite indexing, `.gitignore`-style
  ignore rules, chunked source/doc scans, optional sentence-transformers
  embeddings, optional `rank-bm25`, and a stdlib BM25 fallback behind
  `SHELL_PROJECT_RAG_ENABLED=0`.
- Phase 3 Secure Sandbox routes Python code execution through a per-run
  temporary workspace with timeout enforcement, secret-scrubbed environment
  variables, rollback cleanup, redacted JSONL audit records, and a Python
  network-import guard behind `SHELL_SECURE_SANDBOX_ENABLED=0`.
- Phase 3 Workflow Checkpoints persist multi-step agent state with SQLite or
  JSON backends, last-action tracking, resume loading, rollback checkpoints,
  and event publication behind `SHELL_WORKFLOW_CHECKPOINTS_ENABLED=0`.

## Benchmark Commands

Run targeted validation:

```bash
python -m pytest -q tests/test_neural_shell_integration.py tests/test_low_latency_interaction.py tests/test_ui_working_smoke.py tests/test_pyqtgraph_telemetry_charts.py tests/test_memory_v2.py tests/test_local_stt.py tests/test_project_rag_v2.py tests/test_secure_sandbox.py tests/test_workflow_checkpoints.py
```

Run the existing latency probe:

```bash
python tools/latency_probe.py
```

## Latest Local Probe

Run with `.codex_ui_venv/bin/python tools/latency_probe.py`:

| Probe | Observed |
| --- | --- |
| Tool catalog discovery | 48.33 ms for 469 tools |
| Fast local chat candidate | 0.312 ms |
| Local reply generation | 0.002 ms |
| TTS system command detection | 0.95 ms |
| Streaming first token probe | 11.111 ms provider first token |
| Shell-v2 SSE client stream | 37.28 ms first text chunk, 107.32 ms stream done |
| Runtime session reuse | 1.118 ms internal reuse elapsed |
| Voice realtime session control overhead | 0.016 ms |
| PyQtGraph telemetry chart render | 0.138 ms average, 2.785 ms max over 200 offscreen updates |
| Fake wake-word detector path | 12 ms synthetic frame processing, <200 ms target |
| Silero VAD streaming frame | 0.127 ms average, 0.502 ms max over 40 silent 512-sample frames |
| pywinauto driver dispatch | Fake-driver app/window suite: 41 tests in 1.34 s |
| Memory v2 SQLite save | 1.403 ms average over 200 local inserts |
| Memory v2 SQLite recall | 4.103 ms average, 4.603 ms max over 100 local recalls against 200 memories |
| Local STT adapter overhead | 0.011 ms average, 0.030 ms max over 100 fake-recognizer transcribes |
| Project RAG v2 incremental index | 10.298 ms for 120 files / 120 chunks, no embeddings |
| Project RAG v2 lexical query | 1.304 ms average, 1.478 ms max over 100 queries against 120 chunks |
| Secure Sandbox Python run | 21.771 ms average, 23.449 ms max over 20 isolated Python executions |
| Workflow Checkpoints SQLite save/load/rollback | save 1.931 ms avg, load 0.335 ms avg, rollback 1.878 ms avg |

The local Shell-v2 socket check was blocked by sandbox networking
(`Operation not permitted`), but the mocked SSE and provider streaming probes
completed successfully.

## Current Limitations

- Browser Web Workers, Service Workers, IndexedDB, and WebAssembly are still
  future optimization tracks. The current Web UI is embedded in PyQt WebEngine
  and already keeps heavy OS/tool work outside the renderer process.
- True 0 ms latency is physically impossible. The implementation targets
  immediate streaming visibility and records first partial/first response timing
  through `shell_neural_voice.VOICE_COORDINATOR`.
- `SHELL_WAKE_WORD_ENABLED` and `SHELL_VAD_ENABLED` default to `0` for safe
  rollout. openWakeWord support is wired, but a real "Hey Shell" deployment
  requires a custom openWakeWord model path in `SHELL_WAKE_WORD_MODEL_PATHS`;
  otherwise Shell degrades to manual button mode. Silero VAD was locally smoke
  tested and loads successfully after installing `silero-vad`.
- `SHELL_PYWINAUTO_ENABLED` defaults to `0`. The pywinauto driver is fully
  wired and fake-driver tested on this macOS host; real Notepad, Calculator,
  and File Explorer success-rate validation still needs a Windows desktop/RDP
  session.
- `SHELL_MEMORY_V2_ENABLED` defaults to `0`. Memory v2 is wired and unit-tested
  locally, but it remains opt-in while existing users validate migration from
  `~/.shell_smart_memory.json`.
- `SHELL_LOCAL_STT_ENABLED` defaults to `0`. The sherpa-onnx adapter and voice
  fallback are fake-recognizer tested on this macOS host. Real `<500 ms`
  short-command latency and `>85%` accuracy require downloading a compatible
  sherpa-onnx streaming model and validating with microphone audio.
- `SHELL_PROJECT_RAG_ENABLED` defaults to `0`. Lexical indexing/query is
  validated locally; real semantic embedding quality depends on installing
  `sentence-transformers` and selecting a model that is available on the host.
- `SHELL_SECURE_SANDBOX_ENABLED` defaults to `0`. The local sandbox enforces
  timeout, environment scrubbing, rollback cleanup, and audit logging. Network
  isolation is currently a Python import guard unless a future Docker or
  bubblewrap backend is enabled on the host.
- `SHELL_WORKFLOW_CHECKPOINTS_ENABLED` defaults to `0`. SQLite and JSON
  persistence are unit-tested locally; real crash/resume UX still needs a UI
  surface that offers the latest checkpoint to the user after restart.
- Remote access is represented as safe session records and localhost checks.
  Actual public tunneling should stay behind an explicit approved provider.
