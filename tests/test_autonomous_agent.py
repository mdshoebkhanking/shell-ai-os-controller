from __future__ import annotations

import asyncio
import json


def test_autonomous_goal_dry_run_records_plan_without_execution(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL_AUTONOMY_DIR", str(tmp_path / "autonomy"))

    from shell_autonomous_agent import autonomous_goal_run

    result = asyncio.run(autonomous_goal_run("what is 2 + 3 * 4", dry_run=True))

    assert result["status"] == "dry_run"
    assert result["steps"][0]["tool_id"] == "shell_calculator:calculate_tool"
    assert result["steps"][0]["status"] == "planned"
    assert "not executed" in result["steps"][0]["result"]
    assert (tmp_path / "autonomy" / "latest_run.json").exists()


def test_autonomous_goal_executes_records_and_learns_skill(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL_AUTONOMY_DIR", str(tmp_path / "autonomy"))

    from shell_autonomous_agent import autonomous_goal_run, autonomous_skill_list

    calls = []

    async def executor(tool_id, args):
        calls.append((tool_id, args))
        return {"status": "success", "tool": tool_id, "result": {"answer": 14}}

    result = asyncio.run(autonomous_goal_run("what is 2 + 3 * 4", executor=executor))

    assert result["status"] == "success"
    assert calls == [("shell_calculator:calculate_tool", {"expression": "2 + 3 * 4"})]
    assert result["learned_skill"]["tool_id"] == "shell_calculator:calculate_tool"

    skills = autonomous_skill_list("2 + 3", limit=5)
    assert skills["count"] == 1
    assert skills["skills"][0]["success_count"] == 1


def test_autonomous_goal_reuses_exact_learned_skill(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL_AUTONOMY_DIR", str(tmp_path / "autonomy"))

    from shell_autonomous_agent import autonomous_goal_run

    async def executor(tool_id, args):
        return {"status": "success", "tool": tool_id, "result": {"args": args}}

    first = asyncio.run(autonomous_goal_run("count words in hello shell world", executor=executor))
    second = asyncio.run(autonomous_goal_run("count words in hello shell world", executor=executor))

    assert first["learned_skill"]["skill_id"] == second["reused_skill"]["skill_id"]
    assert second["status"] == "success"
    assert second["plan"]["notes"] == ["reused learned provider-free skill"]

    skills_payload = json.loads((tmp_path / "autonomy" / "skills.json").read_text(encoding="utf-8"))
    assert skills_payload["skills"][0]["success_count"] == 2


def test_autonomous_multistep_goal_executes_and_reuses_workflow_skill(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL_AUTONOMY_DIR", str(tmp_path / "autonomy"))

    from shell_autonomous_agent import autonomous_goal_run

    calls = []

    async def executor(tool_id, args):
        calls.append((tool_id, args))
        return {"status": "success", "tool": tool_id, "result": {"ok": True}}

    goal = "count words in hello shell world then what is 2 + 3 * 4"
    first = asyncio.run(autonomous_goal_run(goal, executor=executor))
    second = asyncio.run(autonomous_goal_run(goal, executor=executor))

    assert first["status"] == "success"
    assert [step["subgoal"] for step in first["steps"]] == [
        "count words in hello shell world",
        "what is 2 + 3 * 4",
    ]
    assert [call[0] for call in calls[:2]] == [
        "shell_text_tools:text_count_tool",
        "shell_calculator:calculate_tool",
    ]
    assert first["learned_skill"]["tool_id"] == "__workflow__"
    assert second["reused_skill"]["skill_id"] == first["learned_skill"]["skill_id"]
    assert len(second["steps"]) == 2


def test_autonomous_workspace_create_verifies_with_readback(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL_AUTONOMY_DIR", str(tmp_path / "autonomy"))

    from shell_autonomous_agent import autonomous_goal_run

    calls = []

    async def executor(tool_id, args):
        calls.append((tool_id, args))
        if tool_id == "shell_workspace_tools:read_workspace_file_tool":
            return {"status": "success", "tool": tool_id, "result": {"content": "namaste"}}
        return {"status": "success", "tool": tool_id, "result": {"created": args["path"]}}

    result = asyncio.run(autonomous_goal_run("create file verify.md with content namaste", executor=executor))

    assert result["status"] == "success"
    assert [call[0] for call in calls] == [
        "shell_workspace_tools:create_workspace_file_tool",
        "shell_workspace_tools:read_workspace_file_tool",
    ]
    assert result["steps"][0]["verification"]["status"] == "passed"
    assert result["steps"][0]["verification"]["method"] == "workspace_readback"


def test_autonomous_workspace_verification_failure_fails_run(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL_AUTONOMY_DIR", str(tmp_path / "autonomy"))

    from shell_autonomous_agent import autonomous_goal_run

    async def executor(tool_id, args):
        if tool_id == "shell_workspace_tools:read_workspace_file_tool":
            return {"status": "success", "tool": tool_id, "result": {"content": "wrong"}}
        return {"status": "success", "tool": tool_id, "result": {"created": args["path"]}}

    result = asyncio.run(autonomous_goal_run("create file verify.md with content namaste", executor=executor))

    assert result["status"] == "failed"
    assert result["steps"][0]["status"] == "verification_failed"
    assert any("verification failed" in hint.lower() for hint in result["recovery_hints"])


def test_autonomous_fullstack_app_artifact_qa_passes(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL_AUTONOMY_DIR", str(tmp_path / "autonomy"))
    monkeypatch.chdir(tmp_path)

    from shell_autonomous_agent import AutonomousGoalRunner, autonomous_goal_run

    async def fake_visual(self, url, *, name, require_canvas=False):
        return {
            "status": "passed",
            "method": "browser_visual_qa",
            "url": url,
            "screenshot_path": str(tmp_path / "shot.png"),
            "canvas_count": 0,
            "canvas_nonblank": True,
            "screenshot_nonblank": True,
        }

    monkeypatch.setattr(AutonomousGoalRunner, "_visual_verify_url", fake_visual)

    async def executor(tool_id, args):
        project = tmp_path / "shell_projects" / args["project_name"]
        (project / "templates").mkdir(parents=True)
        (project / "static" / "css").mkdir(parents=True)
        (project / "static" / "js").mkdir(parents=True)
        (project / "app.py").write_text(
            "from flask import Flask\napp = Flask(__name__)\n@app.route('/')\ndef home():\n    return 'ok'\n",
            encoding="utf-8",
        )
        (project / "templates" / "index.html").write_text("<html><body><h1>OK</h1></body></html>", encoding="utf-8")
        (project / "static" / "css" / "style.css").write_text("body{color:#fff;}" * 12, encoding="utf-8")
        (project / "static" / "js" / "script.js").write_text("console.log('ok')", encoding="utf-8")
        (project / "requirements.txt").write_text("flask\n", encoding="utf-8")
        (project / "run_app.bat").write_text("@echo off\npython app.py\n", encoding="utf-8")
        return {"status": "success", "tool": tool_id, "result": f"[SUCCESS]\nPath: `{project}`"}

    result = asyncio.run(autonomous_goal_run("todo app banao with login", executor=executor))

    assert result["status"] == "success"
    assert result["steps"][0]["verification"]["method"] == "fullstack_artifact_qa"
    assert result["steps"][0]["verification"]["checks"]["flask_app"] is True
    assert result["steps"][0]["verification"]["visual"]["method"] == "browser_visual_qa"


def test_autonomous_fullstack_app_artifact_qa_fails_missing_files(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL_AUTONOMY_DIR", str(tmp_path / "autonomy"))
    monkeypatch.setenv("SHELL_DISABLE_AUTONOMY_VISUAL_QA", "1")
    monkeypatch.chdir(tmp_path)

    from shell_autonomous_agent import autonomous_goal_run

    async def executor(tool_id, args):
        project = tmp_path / "shell_projects" / args["project_name"]
        project.mkdir(parents=True)
        (project / "app.py").write_text("from flask import Flask\n", encoding="utf-8")
        return {"status": "success", "tool": tool_id, "result": f"[SUCCESS]\nPath: `{project}`"}

    result = asyncio.run(autonomous_goal_run("todo app banao", executor=executor, auto_repair=False))

    assert result["status"] == "failed"
    assert result["steps"][0]["status"] == "verification_failed"
    assert "missing required files" in result["steps"][0]["verification"]["evidence"][0]


def test_autonomous_game_artifact_qa_passes(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL_AUTONOMY_DIR", str(tmp_path / "autonomy"))

    import shell_game_builder
    from shell_autonomous_agent import AutonomousGoalRunner, autonomous_goal_run

    games_dir = tmp_path / "games"
    monkeypatch.setattr(shell_game_builder, "_output_dir", lambda: games_dir)

    async def fake_visual(self, url, *, name, require_canvas=False):
        return {
            "status": "passed",
            "method": "browser_visual_qa",
            "url": url,
            "screenshot_path": str(tmp_path / "game.png"),
            "canvas_count": 1,
            "canvas_nonblank": True,
            "screenshot_nonblank": True,
        }

    monkeypatch.setattr(AutonomousGoalRunner, "_visual_verify_url", fake_visual)

    async def executor(tool_id, args):
        games_dir.mkdir(parents=True)
        path = games_dir / "snake_123.html"
        path.write_text(
            "<html><body><canvas></canvas><script>function loop(){requestAnimationFrame(loop)};"
            "document.addEventListener('keydown',()=>{}); let score=0; let gameOver=false;</script></body></html>",
            encoding="utf-8",
        )
        return {"status": "success", "tool": tool_id, "result": "Game ready!"}

    result = asyncio.run(autonomous_goal_run("snake game banao", executor=executor, auto_repair=False))

    assert result["status"] == "success"
    assert result["steps"][0]["verification"]["method"] == "game_artifact_qa"
    assert result["steps"][0]["verification"]["checks"]["canvas"] is True
    assert result["steps"][0]["verification"]["visual"]["canvas_nonblank"] is True


def test_autonomous_game_artifact_qa_fails_unplayable_html(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL_AUTONOMY_DIR", str(tmp_path / "autonomy"))
    monkeypatch.setenv("SHELL_DISABLE_AUTONOMY_VISUAL_QA", "1")

    import shell_game_builder
    from shell_autonomous_agent import autonomous_goal_run

    games_dir = tmp_path / "games"
    monkeypatch.setattr(shell_game_builder, "_output_dir", lambda: games_dir)

    async def executor(tool_id, args):
        games_dir.mkdir(parents=True)
        (games_dir / "snake_123.html").write_text("<html><body>No game</body></html>", encoding="utf-8")
        return {"status": "success", "tool": tool_id, "result": "Game ready!"}

    result = asyncio.run(autonomous_goal_run("snake game banao", executor=executor, auto_repair=False))

    assert result["status"] == "failed"
    assert result["steps"][0]["status"] == "verification_failed"
    assert "failed checks" in result["steps"][0]["verification"]["evidence"][0]


def test_autonomous_auto_repair_retries_after_artifact_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL_AUTONOMY_DIR", str(tmp_path / "autonomy"))
    monkeypatch.setenv("SHELL_DISABLE_AUTONOMY_VISUAL_QA", "1")

    import shell_game_builder
    from shell_autonomous_agent import autonomous_goal_run

    games_dir = tmp_path / "games"
    monkeypatch.setattr(shell_game_builder, "_output_dir", lambda: games_dir)
    attempts = {"count": 0}

    async def executor(tool_id, args):
        attempts["count"] += 1
        games_dir.mkdir(parents=True, exist_ok=True)
        path = games_dir / "snake_123.html"
        if attempts["count"] == 1:
            path.write_text("<html><body>No game</body></html>", encoding="utf-8")
        else:
            path.write_text(
                "<html><body><canvas></canvas><script>function loop(){requestAnimationFrame(loop)};"
                "document.addEventListener('keydown',()=>{}); let score=0; let gameOver=false;</script></body></html>",
                encoding="utf-8",
            )
        return {"status": "success", "tool": tool_id, "result": "Game ready!"}

    result = asyncio.run(autonomous_goal_run("snake game banao", executor=executor))

    assert result["status"] == "success"
    assert attempts["count"] == 2
    assert result["steps"][0]["auto_repair"]["status"] == "success"
    assert result["steps"][0]["verification"]["status"] == "passed"


def test_autonomous_auto_repair_patches_game_when_retry_still_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL_AUTONOMY_DIR", str(tmp_path / "autonomy"))
    monkeypatch.setenv("SHELL_DISABLE_AUTONOMY_VISUAL_QA", "1")

    import shell_game_builder
    from shell_autonomous_agent import autonomous_goal_run

    games_dir = tmp_path / "games"
    monkeypatch.setattr(shell_game_builder, "_output_dir", lambda: games_dir)

    async def executor(tool_id, args):
        games_dir.mkdir(parents=True, exist_ok=True)
        (games_dir / "snake_123.html").write_text("<html><body>still broken</body></html>", encoding="utf-8")
        return {"status": "success", "tool": tool_id, "result": "Game ready!"}

    result = asyncio.run(autonomous_goal_run("snake game banao", executor=executor))

    assert result["status"] == "success"
    repair = result["steps"][0]["auto_repair"]
    assert repair["status"] == "success"
    assert repair["strategy"] == "deterministic_game_patch"
    assert result["steps"][0]["verification"]["method"] == "game_artifact_qa"
    assert result["steps"][0]["verification"]["checks"]["canvas"] is True
    assert "<canvas" in (games_dir / "snake_123.html").read_text(encoding="utf-8")


def test_autonomous_auto_repair_uses_browser_profile_for_game_visual_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL_AUTONOMY_DIR", str(tmp_path / "autonomy"))

    import shell_game_builder
    from shell_autonomous_agent import AutonomousGoalRunner, autonomous_goal_run

    games_dir = tmp_path / "games"
    monkeypatch.setattr(shell_game_builder, "_output_dir", lambda: games_dir)
    visual_calls = {"count": 0}

    async def fake_visual(self, url, *, name, require_canvas=False):
        visual_calls["count"] += 1
        if visual_calls["count"] < 3:
            return {
                "status": "failed",
                "method": "browser_visual_qa",
                "url": url,
                "screenshot_path": str(tmp_path / f"bad-game-{visual_calls['count']}.png"),
                "canvas_count": 1,
                "canvas_nonblank": False,
                "canvas_requirement_ok": True,
                "screenshot_nonblank": False,
                "console_errors": ["ReferenceError: missingLoop is not defined"],
                "page_errors": ["missingLoop is not defined"],
                "body_text_preview": "",
            }
        return {
            "status": "passed",
            "method": "browser_visual_qa",
            "url": url,
            "screenshot_path": str(tmp_path / "fixed-game.png"),
            "canvas_count": 1,
            "canvas_nonblank": True,
            "canvas_requirement_ok": True,
            "screenshot_nonblank": True,
        }

    monkeypatch.setattr(AutonomousGoalRunner, "_visual_verify_url", fake_visual)

    async def executor(tool_id, args):
        games_dir.mkdir(parents=True, exist_ok=True)
        (games_dir / "snake_123.html").write_text(
            "<html><body><canvas></canvas><script>requestAnimationFrame(()=>missingLoop());"
            "document.addEventListener('keydown',()=>{}); let score=0; let gameOver=false;</script></body></html>",
            encoding="utf-8",
        )
        return {"status": "success", "tool": tool_id, "result": "Game ready!"}

    result = asyncio.run(autonomous_goal_run("snake game banao", executor=executor))

    assert result["status"] == "success"
    repair = result["steps"][0]["auto_repair"]
    assert repair["strategy"] == "browser_visual_game_patch"
    assert "page_error" in repair["browser_repair_profile"]["signals"]
    assert "blank_screenshot" in repair["browser_repair_profile"]["signals"]
    assert result["steps"][0]["verification"]["visual"]["screenshot_nonblank"] is True
    assert visual_calls["count"] == 3


def test_autonomous_auto_repair_patches_fullstack_when_retry_still_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL_AUTONOMY_DIR", str(tmp_path / "autonomy"))
    monkeypatch.setenv("SHELL_DISABLE_AUTONOMY_VISUAL_QA", "1")
    monkeypatch.chdir(tmp_path)

    from shell_autonomous_agent import autonomous_goal_run

    async def executor(tool_id, args):
        project = tmp_path / "shell_projects" / args["project_name"]
        project.mkdir(parents=True, exist_ok=True)
        (project / "app.py").write_text("broken python !", encoding="utf-8")
        return {"status": "success", "tool": tool_id, "result": f"[SUCCESS]\nPath: `{project}`"}

    result = asyncio.run(autonomous_goal_run("todo app banao", executor=executor))
    project = tmp_path / "shell_projects" / "todo"

    assert result["status"] == "success"
    repair = result["steps"][0]["auto_repair"]
    assert repair["status"] == "success"
    assert repair["strategy"] == "deterministic_fullstack_patch"
    assert result["steps"][0]["verification"]["checks"]["flask_app"] is True
    assert (project / "templates" / "index.html").exists()
    assert "Flask(" in (project / "app.py").read_text(encoding="utf-8")


def test_autonomous_auto_repair_uses_browser_profile_for_fullstack_visual_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL_AUTONOMY_DIR", str(tmp_path / "autonomy"))
    monkeypatch.chdir(tmp_path)

    from shell_autonomous_agent import AutonomousGoalRunner, autonomous_goal_run

    visual_calls = {"count": 0}

    async def fake_visual(self, url, *, name, require_canvas=False):
        visual_calls["count"] += 1
        if visual_calls["count"] < 3:
            return {
                "status": "failed",
                "method": "browser_visual_qa",
                "url": url,
                "screenshot_path": str(tmp_path / f"bad-app-{visual_calls['count']}.png"),
                "canvas_count": 0,
                "canvas_nonblank": True,
                "canvas_requirement_ok": True,
                "screenshot_nonblank": False,
                "console_errors": ["TypeError: Cannot read properties of null"],
                "page_errors": [],
                "body_text_preview": "",
            }
        return {
            "status": "passed",
            "method": "browser_visual_qa",
            "url": url,
            "screenshot_path": str(tmp_path / "fixed-app.png"),
            "canvas_count": 0,
            "canvas_nonblank": True,
            "canvas_requirement_ok": True,
            "screenshot_nonblank": True,
        }

    monkeypatch.setattr(AutonomousGoalRunner, "_visual_verify_url", fake_visual)

    async def executor(tool_id, args):
        project = tmp_path / "shell_projects" / args["project_name"]
        (project / "templates").mkdir(parents=True, exist_ok=True)
        (project / "static" / "css").mkdir(parents=True, exist_ok=True)
        (project / "static" / "js").mkdir(parents=True, exist_ok=True)
        (project / "app.py").write_text(
            "from flask import Flask\napp = Flask(__name__)\n@app.route('/')\ndef home():\n    return 'ok'\n",
            encoding="utf-8",
        )
        (project / "templates" / "index.html").write_text("<html><body><h1>Broken Visual</h1></body></html>", encoding="utf-8")
        (project / "static" / "css" / "style.css").write_text("body{color:#fff;}" * 12, encoding="utf-8")
        (project / "static" / "js" / "script.js").write_text("document.getElementById('missing').x=1", encoding="utf-8")
        (project / "requirements.txt").write_text("flask\n", encoding="utf-8")
        (project / "run_app.bat").write_text("@echo off\npython app.py\n", encoding="utf-8")
        return {"status": "success", "tool": tool_id, "result": f"[SUCCESS]\nPath: `{project}`"}

    result = asyncio.run(autonomous_goal_run("todo app banao", executor=executor))
    project = tmp_path / "shell_projects" / "todo"

    assert result["status"] == "success"
    repair = result["steps"][0]["auto_repair"]
    assert repair["strategy"] == "browser_visual_fullstack_patch"
    assert "console_error" in repair["browser_repair_profile"]["signals"]
    assert "blank_screenshot" in repair["browser_repair_profile"]["signals"]
    assert result["steps"][0]["verification"]["visual"]["screenshot_nonblank"] is True
    assert "Shell Visual Repair" in (project / "templates" / "index.html").read_text(encoding="utf-8")
    assert visual_calls["count"] == 3


def test_autonomous_goal_failure_records_recovery_hints(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL_AUTONOMY_DIR", str(tmp_path / "autonomy"))

    from shell_autonomous_agent import autonomous_goal_run, autonomous_goal_status

    async def executor(tool_id, args):
        return {
            "status": "error",
            "tool": tool_id,
            "state": "BLOCKED_BY_SAFETY",
            "message": "blocked by safety flag",
            "reasons": ["blocked by safety flag: SHELL_ALLOW_AGENT_PATCH"],
        }

    result = asyncio.run(autonomous_goal_run("what is 2 + 3 * 4", executor=executor))

    assert result["status"] == "failed"
    assert result["steps"][0]["status"] == "error"
    assert any("safety layer blocked" in hint.lower() for hint in result["recovery_hints"])

    status = autonomous_goal_status(result["task_id"])
    assert status["status"] == "success"
    assert status["run"]["task_id"] == result["task_id"]


def test_autonomous_goal_without_route_is_honest_needs_planning(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL_AUTONOMY_DIR", str(tmp_path / "autonomy"))

    from shell_autonomous_agent import autonomous_goal_run

    result = asyncio.run(autonomous_goal_run("make Shell more emotionally intelligent"))

    assert result["status"] == "needs_planning"
    assert result["steps"] == []
    assert any("concrete Shell action" in hint for hint in result["recovery_hints"])


def test_autonomous_goal_resume_reruns_stored_goal(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL_AUTONOMY_DIR", str(tmp_path / "autonomy"))

    from shell_autonomous_agent import autonomous_goal_resume, autonomous_goal_run

    async def fail_executor(tool_id, args):
        return {"status": "error", "tool": tool_id, "message": "temporary failure"}

    async def success_executor(tool_id, args):
        return {"status": "success", "tool": tool_id, "result": {"ok": True}}

    failed = asyncio.run(autonomous_goal_run("what is 2 + 2", executor=fail_executor, verify=False))
    resumed = asyncio.run(autonomous_goal_resume(failed["task_id"], executor=success_executor, verify=False))

    assert failed["status"] == "failed"
    assert resumed["status"] == "success"
    assert resumed["resumed_from"] == failed["task_id"]
    assert resumed["resume"]["previous_status"] == "failed"


def test_autonomous_tools_are_cataloged_without_provider_key_requirement(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from core.tools.registry import enrich_catalog
    from shell_tool_catalog import discover_tool_catalog

    rows = [
        row for row in discover_tool_catalog()
        if row["id"] in {
            "shell_autonomous_agent:autonomous_goal_run_tool",
            "shell_autonomous_agent:autonomous_goal_resume_tool",
            "shell_autonomous_agent:autonomous_goal_status_tool",
            "shell_autonomous_agent:autonomous_skill_list_tool",
        }
    ]
    enriched = enrich_catalog(rows)

    assert {row["id"] for row in enriched} == {
        "shell_autonomous_agent:autonomous_goal_run_tool",
        "shell_autonomous_agent:autonomous_goal_resume_tool",
        "shell_autonomous_agent:autonomous_goal_status_tool",
        "shell_autonomous_agent:autonomous_skill_list_tool",
    }
    assert all(row["kind"] == "tool" for row in enriched)
    assert all(row["readiness"]["ok"] is True for row in enriched)
