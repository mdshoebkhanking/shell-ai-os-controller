# Shell Offline STT Assets

Shell can use packaged sherpa-onnx assets for offline microphone
speech-to-text. Runtime code does not download STT models. Release builds stage
the approved model during the Windows installer workflow.

Default model:

- Family: `sherpa-onnx streaming Zipformer EN 20M`
- Source: `k2-fsa/sherpa-onnx` release tag `asr-models`
- Directory: `models/stt/sherpa-onnx/sherpa-onnx-streaming-zipformer-en-20M-2023-02-17/`
- Runtime: `sherpa-onnx`
- Model kind: streaming transducer
- Sample rate: 16 kHz
- Languages: English and Hinglish commands

Expected release layout:

```text
models/stt/sherpa-onnx/sherpa-onnx-streaming-zipformer-en-20M-2023-02-17/
  tokens.txt
  encoder-epoch-99-avg-1.int8.onnx
  decoder-epoch-99-avg-1.onnx
  joiner-epoch-99-avg-1.int8.onnx
  shell-stt-assets.json
```

Build-time staging:

```bash
python tools/stage_sherpa_stt_assets.py
```

Do not commit large STT binaries to normal git history. The GitHub release
workflow caches and stages them before building the Windows setup EXE. The app
itself never downloads STT assets at runtime.

For Hindi or multilingual local STT, configure a sherpa-onnx Whisper export at
runtime with `SHELL_LOCAL_STT_MODEL_KIND=whisper` and
`SHELL_LOCAL_STT_LANGUAGE=hi`.
