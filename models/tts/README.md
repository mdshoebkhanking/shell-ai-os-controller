# Shell Offline TTS Models

Shell does not download voice models while the app is running. Package natural
offline TTS assets here before building the Windows installer.

Recommended default for Shell v1.0.x:

- Model family: Kokoro-82M
- Runtime: `kokoro-onnx`
- Model license: Apache-2.0
- Runtime license: MIT
- Shell language modes: English, Hinglish, Hindi

Hinglish is handled by Shell routing mixed clauses before synthesis. It is not a
separate hidden model. English clauses use the English Kokoro voice; Hindi or
Hindi-heavy clauses use the Hindi Kokoro voice. Keep this transparent in release
notes and support docs.

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

- Kokoro ONNX: one `kokoro*.onnx` model file and one `voices*.bin` or
  `voices*.json` file, plus the `kokoro_onnx` Python runtime in the bundled
  environment. For broad Windows laptops, Shell stages the int8 v1.0 model by
  default: `kokoro-v1.0.int8.onnx` plus `voices-v1.0.bin`.
- Piper: one `*.onnx` model file, its JSON config, and a bundled `piper`
  executable or `PIPER_BIN` pointing to it.

Recommended Kokoro layout for the Windows installer:

```text
models/tts/kokoro/
  kokoro-v1.0.int8.onnx
  voices-v1.0.bin
```

Optional language-specific overrides can be staged under
`models/tts/kokoro/english/`, `models/tts/kokoro/hinglish/`, or
`models/tts/kokoro/hindi/`. If a language folder is missing, Shell checks the
shared `models/tts/kokoro/` folder.

Default voices:

- English: `af_heart`
- Hinglish: `af_heart` with routed Hindi clauses
- Hindi: `hf_alpha`

Environment overrides:

- `SHELL_NATURAL_TTS_VOICE_ENGLISH`
- `SHELL_NATURAL_TTS_VOICE_HINGLISH`
- `SHELL_NATURAL_TTS_VOICE_HINDI`
- `SHELL_HINGLISH_TTS_ROUTING=balanced|aggressive|english`

If these assets are missing, Shell still starts and uses the local OS TTS
fallback. The Windows acceptance probe reports this as offline TTS status, not
as a hard install failure.

Do not commit large model binaries to normal git history if they exceed GitHub's
regular file limits. Stage them in the build workspace, GitHub Release assets,
or another approved artifact flow before building the installer.

Build-time staging helper:

```bash
python tools/stage_kokoro_tts_assets.py --variant int8
```

The helper downloads assets only at build time. The app itself never downloads
voice assets at runtime.
