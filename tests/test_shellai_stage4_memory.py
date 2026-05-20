from __future__ import annotations


def test_memory_store_initializes_sqlite_tables(tmp_path) -> None:
    from shellai.memory import MemoryStore

    db_path = tmp_path / "memory.sqlite3"
    store = MemoryStore(db_path)

    assert db_path.exists()
    assert store.get_user_profile()["preferences"]["primary_user"] == "power-user developer in India"


def test_conversation_memory_save_and_search_with_trace(tmp_path) -> None:
    from shellai.memory import MemoryStore
    from shellai.observability import TRACE_STORE
    from shellai.protocol import AgentRole

    TRACE_STORE.clear()
    trace = TRACE_STORE.start_trace("remember this")
    store = MemoryStore(tmp_path / "memory.sqlite3")
    result = store.save_memory(
        "conversation",
        {
            "conversation_id": "conv-1",
            "agent_role": AgentRole.COORDINATOR,
            "user_input": "setup python project",
            "agent_output": "created venv plan",
            "summary": "Python project setup workflow",
            "metadata": {"project": "demo"},
        },
        trace=trace,
    )
    rows = store.search_memory("conversation", "python", trace=trace)

    assert result["conversation_id"] == "conv-1"
    assert len(rows) == 1
    assert rows[0]["summary"] == "Python project setup workflow"
    assert [step.name for step in trace.steps] == ["MemoryStore", "MemoryStore"]
    assert trace.steps[0].metadata["memory_type"] == "conversation"
    assert trace.steps[1].metadata["operation"] == "search"


def test_user_profile_upsert_merges_preferences_and_workflows(tmp_path) -> None:
    from shellai.memory import MemoryStore

    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.save_memory(
        "user_profile",
        {
            "preferences": {"default_editor": "VS Code", "language_style": "Hinglish"},
            "dev_workflows": {"tools": ["git", "adb"]},
        },
    )
    store.save_memory(
        "user_profile",
        {
            "preferences": {"risk_tolerance": "ask-before-write"},
            "dev_workflows": {"os_priority": ["linux", "windows"]},
        },
    )
    profile = store.get_user_profile()

    assert profile["preferences"]["default_editor"] == "VS Code"
    assert profile["preferences"]["risk_tolerance"] == "ask-before-write"
    assert profile["dev_workflows"]["tools"] == ["git", "adb"]
    assert profile["dev_workflows"]["os_priority"] == ["linux", "windows"]


def test_skill_memory_save_get_list_and_usage(tmp_path) -> None:
    from shellai.memory import MemoryStore

    store = MemoryStore(tmp_path / "memory.sqlite3")
    saved = store.save_memory(
        "skill",
        {
            "name": "git_status_review",
            "description": "Check git status and summarize changed files.",
            "metadata": {"tools": ["git"], "inputs": ["repo_path"]},
        },
    )

    skill = store.get_skill(saved["skill_id"])
    assert skill is not None
    assert skill["name"] == "git_status_review"
    assert skill["metadata"]["tools"] == ["git"]

    listed = store.list_skills({"query": "git"})
    assert [item["name"] for item in listed] == ["git_status_review"]

    used = store.record_skill_usage(saved["skill_id"], success=True, duration_ms=120)
    assert used["success_count"] == 1
    assert used["failure_count"] == 0
    assert used["avg_duration_ms"] == 120.0

    failed = store.record_skill_usage(saved["skill_id"], success=False, duration_ms=180)
    assert failed["success_count"] == 1
    assert failed["failure_count"] == 1
    assert failed["avg_duration_ms"] == 150.0
