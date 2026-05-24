import asyncio


def test_project_rag_flag_default_off(monkeypatch):
    monkeypatch.delenv("SHELL_PROJECT_RAG_ENABLED", raising=False)

    from core.project_rag import project_rag_enabled

    assert project_rag_enabled() is False


def test_project_rag_indexes_supported_files_and_gitignore(tmp_path):
    from core.project_rag import ProjectRAGConfig, ProjectRAGIndex

    root = tmp_path / "project"
    root.mkdir()
    (root / ".gitignore").write_text("ignored/\n*.secret\n", encoding="utf-8")
    (root / "app.py").write_text("def run_voice_stream():\n    return 'ok'\n", encoding="utf-8")
    (root / "README.md").write_text("# Voice project\n", encoding="utf-8")
    (root / "secret.secret").write_text("hidden", encoding="utf-8")
    (root / "ignored").mkdir()
    (root / "ignored" / "skip.py").write_text("skip", encoding="utf-8")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "skip.js").write_text("skip", encoding="utf-8")

    index = ProjectRAGIndex(root, db_path=tmp_path / "rag.sqlite3", config=ProjectRAGConfig(max_files=20))
    result = index.index_project()

    assert result["ok"] is True
    assert result["files_indexed"] == 2
    assert result["chunks_written"] == 2
    found = index.query("voice stream", limit=3)
    assert found["matches"][0]["relative_path"] == "app.py"


def test_project_rag_incremental_index_skips_unchanged_files(tmp_path):
    from core.project_rag import ProjectRAGConfig, ProjectRAGIndex

    root = tmp_path / "project"
    root.mkdir()
    source = root / "main.java"
    source.write_text("class ShellController {}\n", encoding="utf-8")
    index = ProjectRAGIndex(root, db_path=tmp_path / "rag.sqlite3", config=ProjectRAGConfig(max_files=20))

    first = index.index_project()
    second = index.index_project()
    source.write_text("class ShellController { void runCommand() {} }\n", encoding="utf-8")
    third = index.index_project()

    assert first["files_indexed"] == 1
    assert second["files_skipped"] == 1
    assert third["files_indexed"] == 1


def test_project_rag_lexical_query_supports_cpp_and_docs(tmp_path):
    from core.project_rag import ProjectRAGConfig, ProjectRAGIndex

    root = tmp_path / "project"
    root.mkdir()
    (root / "controller.cpp").write_text("class WindowAutomationDriver { void focusWindow(); };\n", encoding="utf-8")
    (root / "docs.txt").write_text("Telemetry charts render fast.\n", encoding="utf-8")
    index = ProjectRAGIndex(root, db_path=tmp_path / "rag.sqlite3", config=ProjectRAGConfig(max_files=20))
    index.index_project()

    found = index.query("window automation driver", limit=2)

    assert found["matches"][0]["relative_path"] == "controller.cpp"
    assert found["matches"][0]["lexical_score"] > 0


def test_project_rag_semantic_query_uses_injected_embedder(tmp_path):
    from core.project_rag import ProjectRAGConfig, ProjectRAGIndex

    class FakeEmbedder:
        def encode(self, texts):
            rows = []
            for text in texts:
                lowered = text.lower()
                rows.append([1.0, 0.0] if ("auth" in lowered or "login" in lowered) else [0.0, 1.0])
            return rows

    root = tmp_path / "project"
    root.mkdir()
    (root / "login.py").write_text("def guard_session():\n    return True\n", encoding="utf-8")
    index = ProjectRAGIndex(
        root,
        db_path=tmp_path / "rag.sqlite3",
        config=ProjectRAGConfig(max_files=20, embeddings_enabled=True),
        embedder=FakeEmbedder(),
    )
    index.index_project()

    found = index.query("auth", limit=1)

    assert found["matches"][0]["relative_path"] == "login.py"
    assert found["matches"][0]["semantic_score"] > 0.9


def test_project_rag_tools_respect_flag(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_PROJECT_RAG_DB", str(tmp_path / "rag.sqlite3"))
    monkeypatch.delenv("SHELL_PROJECT_RAG_ENABLED", raising=False)
    root = tmp_path / "project"
    root.mkdir()
    (root / "app.py").write_text("def open_calculator(): pass\n", encoding="utf-8")

    import shell_project_rag

    disabled = asyncio.run(shell_project_rag.project_rag_index_tool.__wrapped__(str(root), 20))
    assert disabled["ok"] is False

    monkeypatch.setenv("SHELL_PROJECT_RAG_ENABLED", "1")
    indexed = asyncio.run(shell_project_rag.project_rag_index_tool.__wrapped__(str(root), 20))
    assert indexed["files_indexed"] == 1
    found = asyncio.run(shell_project_rag.project_rag_query_tool.__wrapped__("open calculator", str(root), 5))
    assert found["matches"][0]["relative_path"] == "app.py"


def test_shell_coder_uses_project_rag_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_PROJECT_RAG_ENABLED", "1")
    monkeypatch.setenv("SHELL_PROJECT_RAG_DB", str(tmp_path / "rag.sqlite3"))
    root = tmp_path / "project"
    root.mkdir()
    (root / "auth.py").write_text("def login_guard():\n    return 'ok'\n", encoding="utf-8")

    import shell_coding_assist

    result = asyncio.run(shell_coding_assist.shell_automated_coding_assist_tool.__wrapped__(str(root), "login guard", 20))

    assert result["ok"] is True
    assert result["source"] == "project_rag_v2"
    assert result["matches"][0]["relative_path"] == "auth.py"


def test_tool_catalog_discovers_project_rag_tools():
    from shell_tool_catalog import discover_tool_catalog

    ids = {item["id"] for item in discover_tool_catalog()}
    assert "shell_project_rag:project_rag_index_tool" in ids
    assert "shell_project_rag:project_rag_query_tool" in ids
    assert "shell_project_rag:project_rag_status_tool" in ids
