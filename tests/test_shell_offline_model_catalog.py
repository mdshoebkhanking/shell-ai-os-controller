from __future__ import annotations


def test_offline_model_catalog_exposes_tiered_download_options(monkeypatch, tmp_path):
    import shell_offline_model_catalog as catalog

    monkeypatch.setenv("SHELL_OFFLINE_LLM_MODEL_DIR", str(tmp_path))

    payload = catalog.catalog_payload()
    options = payload["options"]

    assert payload["runtimeDownloads"] is True
    assert payload["category"] == "chat"
    assert len(options) >= 2
    assert len(catalog.model_options(None)) >= 4
    assert all(option["id"] not in {"smollm2-135m-q4", "smollm2-360m-q4", "qwen2.5-0.5b-q4"} for option in options)
    assert any(option["id"] == "qwen2.5-3b-q4" and option["recommended"] for option in options)
    assert any(option.id == "qwen2.5-coder-3b-q4" and option.default for option in catalog.model_options("coding"))
    assert any(option.id == "qwen2.5-coder-7b-q3" and option.recommended_ram_gb >= 24 for option in catalog.model_options("coding"))
    assert all(option["min_ram_gb"] > 0 and option["recommended_ram_gb"] >= option["min_ram_gb"] for option in options)
    assert all(option["downloadUrl"].startswith("https://huggingface.co/") for option in options)
    assert all(len(option["sha256"]) == 64 for option in options)


def test_offline_model_catalog_selects_installed_model(monkeypatch, tmp_path):
    import shell_offline_model_catalog as catalog

    monkeypatch.setenv("SHELL_OFFLINE_LLM_MODEL_DIR", str(tmp_path))
    option = catalog.get_model_option("qwen2.5-3b-q4")
    assert option is not None
    model_path = catalog.model_install_dir(option.id) / option.filename
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"gguf-probe")

    catalog.write_model_metadata(option, model_path=model_path)

    assert catalog.selected_installed_model_path() == model_path
    payload = catalog.catalog_payload()
    assert payload["selectedModelId"] == option.id
    assert any(item["id"] == option.id for item in payload["installedModels"])
