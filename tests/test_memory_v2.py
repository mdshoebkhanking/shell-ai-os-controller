import asyncio
import importlib
import json
import sqlite3
import time


def test_memory_v2_flag_default_off(monkeypatch):
    monkeypatch.delenv("SHELL_MEMORY_V2_ENABLED", raising=False)

    from core.memory.v2 import memory_v2_enabled

    assert memory_v2_enabled() is False


def test_memory_v2_save_recall_redacts_and_audits(tmp_path):
    from core.memory.v2 import MemoryV2Store

    store = MemoryV2Store(tmp_path / "memory.sqlite3")
    record = store.save_memory(
        "User email is alice@example.com and api_key=sk-testsecret12345",
        tags=["preference", "contact"],
        importance=80,
    )

    assert "alice@example.com" not in record.text
    assert "sk-testsecret" not in record.text
    assert "<redacted:email>" in record.redacted_text

    found = store.recall_memory("email", limit=3)
    assert len(found) == 1
    assert found[0].record.memory_id == record.memory_id

    audit = store.audit_log(limit=5)
    assert len(audit) == 1
    assert audit[0]["query"] == "email"
    assert audit[0]["memory_id"] == record.memory_id


def test_memory_v2_importance_and_decay_affect_ranking(tmp_path):
    from core.memory.v2 import MemoryV2Store

    store = MemoryV2Store(tmp_path / "memory.sqlite3", decay_half_life_days=30)
    old = store.save_memory("editor preference is nano", tags=["preference"], importance=10)
    recent = store.save_memory("editor preference is vscode", tags=["preference"], importance=95)

    old_time = time.time() - (90 * 86400)
    with sqlite3.connect(tmp_path / "memory.sqlite3") as conn:
        conn.execute("UPDATE memories SET updated_at = ? WHERE id = ?", (old_time, old.memory_id))
        conn.commit()

    found = store.recall_memory("editor preference", limit=2)
    assert [item.record.memory_id for item in found] == [recent.memory_id, old.memory_id]


def test_memory_v2_tags_and_forget_are_filtered(tmp_path):
    from core.memory.v2 import MemoryV2Store

    store = MemoryV2Store(tmp_path / "memory.sqlite3")
    ui = store.save_memory("theme should be emerald", tags=["ui", "preference"])
    store.save_memory("default shell is zsh", tags=["terminal", "preference"])

    tagged = store.recall_memory("", tags="ui", limit=5)
    assert [item.record.memory_id for item in tagged] == [ui.memory_id]

    assert store.forget_memory(tag="ui") == 1
    assert store.recall_memory("emerald", limit=5) == []


def test_memory_v2_migrates_legacy_json(tmp_path):
    from core.memory.v2 import MemoryV2Store

    legacy = tmp_path / "legacy.json"
    legacy.write_text(
        json.dumps(
            {
                "personal_info": {"nickname": "Boss"},
                "preferences": {"theme": "emerald"},
            }
        ),
        encoding="utf-8",
    )

    store = MemoryV2Store(tmp_path / "memory.sqlite3")
    result = store.migrate_legacy(legacy)

    assert result == {"migrated": 2, "skipped": 0}
    found = store.recall_memory("emerald", limit=3)
    assert found[0].record.metadata["legacy_category"] == "preferences"


def test_memory_v2_tools_respect_env_flag(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_MEMORY_V2_PATH", str(tmp_path / "memory.sqlite3"))
    monkeypatch.delenv("SHELL_MEMORY_V2_ENABLED", raising=False)

    import shell_memory_v2

    shell_memory_v2 = importlib.reload(shell_memory_v2)
    disabled = asyncio.run(shell_memory_v2.memory_v2_save_tool.__wrapped__("remember disabled", "test", 50))
    assert disabled["ok"] is False

    monkeypatch.setenv("SHELL_MEMORY_V2_ENABLED", "1")
    enabled = asyncio.run(shell_memory_v2.memory_v2_save_tool.__wrapped__("remember enabled", "test", 50))
    assert enabled["ok"] is True
    recalled = asyncio.run(shell_memory_v2.memory_v2_recall_tool.__wrapped__("enabled", 5, "test"))
    assert recalled["count"] == 1


def test_legacy_shell_memory_routes_to_v2_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_MEMORY_V2_ENABLED", "1")
    monkeypatch.setenv("SHELL_MEMORY_V2_PATH", str(tmp_path / "memory.sqlite3"))

    import shell_memory

    shell_memory = importlib.reload(shell_memory)
    saved = asyncio.run(shell_memory.update_memory_tool.__wrapped__("preferences", "editor", "vscode"))
    assert "Memory v2" in saved

    found = asyncio.run(shell_memory.search_memory_tool.__wrapped__("vscode"))
    assert "editor: vscode" in found


def test_tool_catalog_discovers_memory_v2_tools():
    from shell_tool_catalog import discover_tool_catalog

    ids = {item["id"] for item in discover_tool_catalog()}
    assert "shell_memory_v2:memory_v2_save_tool" in ids
    assert "shell_memory_v2:memory_v2_recall_tool" in ids
    assert "shell_memory_v2:memory_v2_forget_tool" in ids
