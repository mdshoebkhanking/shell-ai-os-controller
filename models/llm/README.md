# Shell Offline LLM Assets

Shell can use a packaged GGUF model as an offline chat brain. Runtime code does
not download models. Release builds stage the approved model during the Windows
installer workflow.

Default model:

- Family: `Qwen3-1.7B-GGUF`
- Source repo: `ggml-org/Qwen3-1.7B-GGUF`
- File: `Qwen3-1.7B-Q4_K_M.gguf`
- Runtime: `llama-cpp-python`
- Languages: English, Hinglish, Hindi

Expected release layout:

```text
models/llm/qwen3/
  Qwen3-1.7B-Q4_K_M.gguf
  qwen-offline-llm-assets.json
```

Build-time staging:

```bash
python tools/stage_qwen_offline_llm_assets.py --variant q4_k_m_ggml
```

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
