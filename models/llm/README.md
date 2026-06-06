# Shell Offline LLM Assets

Shell can use a packaged GGUF model as an offline chat brain. Runtime code does
not download models. Release builds stage the approved model during the Windows
installer workflow.

Default model:

- Family: `Falcon-H1-1.5B-Deep-Instruct-GGUF`
- Source repo: `tiiuae/Falcon-H1-1.5B-Deep-Instruct-GGUF`
- File: `Falcon-H1-1.5B-Deep-Instruct-Q4_K_M.gguf`
- Runtime: `llama-cpp-python`
- Languages: English, Hinglish, Hindi
- License: Falcon-LLM License

Expected release layout:

```text
models/llm/falcon-h1-1.5b-deep/
  Falcon-H1-1.5B-Deep-Instruct-Q4_K_M.gguf
  falcon-offline-llm-assets.json
```

Build-time staging:

```bash
python tools/stage_falcon_offline_llm_assets.py --variant q4_k_m
```

Legacy Qwen3 assets under `models/llm/qwen3/` are still detected as fallback
assets for older installer trees, but new release builds stage Falcon-H1.

Runtime overrides:

```bash
SHELL_OFFLINE_LLM=1
SHELL_OFFLINE_LLM_MODEL_PATH=/path/to/model.gguf
SHELL_OFFLINE_LLM_MODEL_DIR=/path/to/model-dir
SHELL_OFFLINE_LLM_MAX_TOKENS=180
```

If the model or runtime is missing, Shell keeps chat working through provider
fallbacks and deterministic local answers, and reports `fallback` in
`offline-llm-status`.
