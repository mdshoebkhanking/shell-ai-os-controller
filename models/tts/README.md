# Shell Offline TTS Models

Shell does not download voice models while the app is running. Package natural
offline TTS assets here before building the Windows installer.

Supported lookup paths:

- `models/tts/kokoro/english/`
- `models/tts/kokoro/hinglish/`
- `models/tts/kokoro/hindi/`
- `models/tts/piper/english/`
- `models/tts/piper/hinglish/`
- `models/tts/piper/hindi/`

The runtime also checks the matching non-language folder, for example
`models/tts/piper/`, as a fallback.

Expected assets:

- Kokoro ONNX: one `*.onnx` model file and one `voices*.bin` or `voices*.json`
  file, plus the `kokoro_onnx` Python runtime in the bundled environment.
- Piper: one `*.onnx` model file, its JSON config, and a bundled `piper`
  executable or `PIPER_BIN` pointing to it.

If these assets are missing, Shell still starts and uses the local OS TTS
fallback. The Windows acceptance probe reports this as offline TTS status, not
as a hard install failure.
