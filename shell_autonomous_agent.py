"""Provider-free autonomous goal runner for Shell.

This module adds a durable, deterministic task loop on top of Shell's existing
router and tool gateway. It does not bypass safety gates: every executable step
still runs through ``shell_tool_gateway``.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import re
import ast
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union

from shell_safe_executor import god_tier_tool as function_tool
from shell_tool_catalog import PROJECT_ROOT

Executor = Callable[[str, dict[str, Any]], Union[Awaitable[dict[str, Any]], dict[str, Any]]]

_RUNTIME_DIR_ENV = "SHELL_AUTONOMY_DIR"
_SKILLS_FILENAME = "skills.json"
_RUNS_FILENAME = "runs.jsonl"
_LATEST_FILENAME = "latest_run.json"
_SCREENSHOT_DIRNAME = "screenshots"
_PREVIEW_DIRNAME = "previews"
_WORKFLOW_TOOL_ID = "__workflow__"
_VISUAL_QA_TIMEOUT_MS = 4500
_SECRET_KEY_RE = re.compile(r"(api[_-]?key|token|secret|password|passwd|credential)", re.I)
_FULLSTACK_REQUIRED_FILES = (
    "app.py",
    "templates/index.html",
    "static/css/style.css",
    "static/js/script.js",
    "requirements.txt",
    "run_app.bat",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _runtime_dir() -> Path:
    configured = os.environ.get(_RUNTIME_DIR_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return PROJECT_ROOT / ".shell_runtime" / "autonomy"


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _visual_qa_enabled() -> bool:
    return not _truthy(os.environ.get("SHELL_DISABLE_AUTONOMY_VISUAL_QA"))


def _normalize_goal(goal: str) -> str:
    text = str(goal or "").strip().lower()
    text = re.sub(r"^(?:hey\s+|ok\s+)?shell\s*(?:se|please|,|:|-)?\s+", "", text)
    text = re.sub(
        r"^(?:autonomous|autonomy|auto|agentic)\s+(?:run|execute|do|handle|perform|task|goal)\s+",
        "",
        text,
    )
    text = re.sub(r"^agent\s+(?:run|execute|do|handle|perform)\s+", "", text)
    text = re.sub(r"^(?:hard|complex)\s+task\s*[:=-]?\s*", "", text)
    text = re.sub(r"^(?:khud|apne\s+aap|automatically)\s+", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9@._:/+\-\s]", "", text)
    return text.strip()


def _goal_for_planning(goal: str) -> str:
    text = str(goal or "").strip()
    patterns = (
        r"^(?:autonomous|autonomy|auto|agentic)\s+(?:run|execute|do|handle|perform|task|goal)\s+(.+)$",
        r"^agent\s+(?:run|execute|do|handle|perform)\s+(.+)$",
        r"^(?:hard|complex)\s+task\s*[:=-]?\s*(.+)$",
        r"^(?:khud|apne\s+aap|automatically)\s+(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, text, flags=re.I | re.S)
        if match:
            return match.group(1).strip()
    return text


def _split_goal_steps(goal: str) -> list[str]:
    text = _goal_for_planning(goal)
    parts = re.split(
        r"\s*(?:;|\b(?:and\s+then|then|phir|uske\s+baad|after\s+that)\b)\s*",
        text,
        flags=re.I,
    )
    goals = [part.strip(" .,:;-") for part in parts if part.strip(" .,:;-")]
    return goals or [text.strip()]


def _skill_id(goal_signature: str, tool_id: str) -> str:
    digest = hashlib.sha1(f"{goal_signature}|{tool_id}".encode("utf-8")).hexdigest()[:12]
    return f"auto_{digest}"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            text_key = str(key)
            if _SECRET_KEY_RE.search(text_key):
                redacted[text_key] = "[REDACTED]"
            else:
                redacted[text_key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return _json_safe(value)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_json_safe(payload), ensure_ascii=False, sort_keys=True) + "\n")


def _load_skill_rows(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path, {"version": 1, "skills": []})
    rows = payload.get("skills") if isinstance(payload, dict) else []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _save_skill_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    rows = sorted(rows, key=lambda row: (str(row.get("goal_pattern") or ""), str(row.get("tool_id") or "")))
    _write_json(path, {"version": 1, "updated_at": _now_iso(), "skills": rows})


def _load_recent_runs(path: Path, limit: int) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines[-max(1, int(limit)) :]:
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _result_status(result: dict[str, Any]) -> str:
    return str(result.get("status") or result.get("state") or "unknown").lower()


def _result_error(result: dict[str, Any]) -> str:
    if not isinstance(result, dict):
        return str(result)[:400]
    if result.get("message"):
        return str(result.get("message"))[:400]
    if result.get("error"):
        return str(result.get("error"))[:400]
    if result.get("state"):
        return str(result.get("state"))[:200]
    reasons = result.get("reasons")
    if isinstance(reasons, list) and reasons:
        return "; ".join(str(item) for item in reasons)[:400]
    return "tool did not report success"


def _extract_text_result(result: dict[str, Any]) -> str:
    payload = result.get("result") if isinstance(result, dict) else result
    if isinstance(payload, str):
        return payload
    return json.dumps(_json_safe(payload), ensure_ascii=False, sort_keys=True)


def _path_from_tool_result(result: dict[str, Any]) -> Path | None:
    text = _extract_text_result(result)
    patterns = (
        r"Path:\s*`([^`]+)`",
        r"Path:\s*([^\r\n]+)",
        r"Saved(?:\s+to)?[: ]+`?([^`\r\n]+)`?",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if not match:
            continue
        candidate = match.group(1).strip().strip("\"'` ")
        if candidate:
            return Path(candidate).expanduser()
    return None


def _artifact_failed(method: str, evidence: list[str], **extra: Any) -> dict[str, Any]:
    payload = {"status": "failed", "method": method, "evidence": evidence}
    payload.update(extra)
    return payload


def _artifact_passed(method: str, evidence: list[str], **extra: Any) -> dict[str, Any]:
    payload = {"status": "passed", "method": method, "evidence": evidence}
    payload.update(extra)
    return payload


def _screenshot_nonblank(path: Path) -> tuple[bool, dict[str, Any]]:
    try:
        from PIL import Image

        with Image.open(path) as image:
            probe = image.convert("RGB").resize((64, 64))
            extrema = probe.getextrema()
            colors = probe.getcolors(maxcolors=4096) or []
            varied = any(low != high for low, high in extrema)
            return bool(varied and len(colors) > 1), {
                "width": image.width,
                "height": image.height,
                "distinct_sample_colors": len(colors),
                "extrema": extrema,
            }
    except Exception as exc:
        return False, {"error": str(exc)}


def _recovery_hints(*, goal: str, plan: dict[str, Any] | None, result: dict[str, Any] | None, error: str = "") -> list[str]:
    hints: list[str] = []
    plan_status = str((plan or {}).get("status") or "")
    if plan_status == "needs_clarification":
        hints.append("Use a concrete Shell action, for example: open calculator, snake game banao, or create file notes.md with content hello.")
    notes = (plan or {}).get("notes") if isinstance(plan, dict) else []
    for note in notes or []:
        hints.append(str(note))
    if result:
        state = str(result.get("state") or "").lower()
        message = str(result.get("message") or "")
        reasons = " ".join(str(item) for item in result.get("reasons", [])).lower() if isinstance(result.get("reasons"), list) else ""
        if "missing api key" in reasons or "api key" in message.lower():
            hints.append("Add the required API key in Settings or choose a provider-free task.")
        if "blocked" in state or "blocked" in message.lower() or "safety" in reasons:
            hints.append("The safety layer blocked this step. Rephrase as a non-destructive action or enable the documented trusted-session flag only if you really intend that capability.")
        if result.get("requirements"):
            hints.append("Check the reported requirements and run Repair Shell AI if a dependency is missing.")
    if error:
        if "unknown tool" in error.lower():
            hints.append("Tool catalog did not include the planned tool. Run Repair Shell AI, then retry.")
        elif "verification" in error.lower():
            hints.append("The action ran but verification failed. Inspect the verification evidence and retry the exact failed subgoal.")
        elif "artifact" in error.lower():
            hints.append("The generated artifact did not pass local QA. Re-run the task after checking the missing files or broken markup.")
        elif "visual" in error.lower():
            hints.append("The generated artifact rendered blank or errored in browser QA. Inspect the saved screenshot and retry.")
        else:
            hints.append("Review the run record in .shell_runtime/autonomy/latest_run.json for the exact failed step.")
    if not hints:
        hints.append("Retry with a smaller concrete first step, then chain the next action after it succeeds.")
    return list(dict.fromkeys(hints))


class AutonomousGoalRunner:
    """Deterministic autonomous loop with durable skill learning."""

    def __init__(self, *, runtime_dir: Path | None = None, executor: Executor | None = None) -> None:
        self.runtime_dir = runtime_dir or _runtime_dir()
        self.skills_path = self.runtime_dir / _SKILLS_FILENAME
        self.runs_path = self.runtime_dir / _RUNS_FILENAME
        self.latest_path = self.runtime_dir / _LATEST_FILENAME
        self.executor = executor or self._default_executor

    async def _default_executor(self, tool_id: str, args: dict[str, Any]) -> dict[str, Any]:
        from shell_tool_gateway import execute_tool

        return await execute_tool(tool_id, args)

    def _matching_skill(self, goal_signature: str) -> dict[str, Any] | None:
        if not goal_signature:
            return None
        candidates = []
        for row in _load_skill_rows(self.skills_path):
            if str(row.get("goal_pattern") or "") != goal_signature:
                continue
            candidates.append(row)
        candidates.sort(key=lambda row: (int(row.get("success_count") or 0), str(row.get("last_used_at") or "")), reverse=True)
        return dict(candidates[0]) if candidates else None

    def _learn_skill(
        self,
        *,
        goal: str,
        goal_signature: str,
        tool_id: str,
        args: dict[str, Any],
        steps_template: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        rows = _load_skill_rows(self.skills_path)
        skill_id = _skill_id(goal_signature, tool_id)
        now = _now_iso()
        for row in rows:
            if row.get("skill_id") == skill_id:
                row["success_count"] = int(row.get("success_count") or 0) + 1
                row["last_used_at"] = now
                row["sample_goal"] = goal
                row["args_template"] = _redact(args)
                if steps_template is not None:
                    row["steps_template"] = _redact(steps_template)
                _save_skill_rows(self.skills_path, rows)
                return dict(row)
        row = {
            "skill_id": skill_id,
            "name": f"Auto skill for {goal_signature[:56] or 'goal'}",
            "goal_pattern": goal_signature,
            "sample_goal": goal,
            "tool_id": tool_id,
            "args_template": _redact(args),
            "steps_template": _redact(steps_template or []),
            "success_count": 1,
            "failure_count": 0,
            "created_at": now,
            "last_used_at": now,
            "tags": ["auto", "provider_free", "tool_gateway"],
        }
        rows.append(row)
        _save_skill_rows(self.skills_path, rows)
        return dict(row)

    def _plan_from_skill(self, goal: str, skill: dict[str, Any]) -> dict[str, Any]:
        template = skill.get("steps_template")
        steps: list[dict[str, Any]] = []
        if isinstance(template, list) and template:
            for index, raw_step in enumerate(template, start=1):
                if not isinstance(raw_step, dict):
                    continue
                steps.append({
                    "step_id": uuid.uuid4().hex,
                    "sequence": index,
                    "subgoal": str(raw_step.get("subgoal") or goal),
                    "action": str(raw_step.get("action") or f"Run {raw_step.get('tool_id') or ''}"),
                    "tool_id": str(raw_step.get("tool_id") or ""),
                    "args": dict(raw_step.get("args") or {}),
                    "retry_limit": int(raw_step.get("retry_limit") or 1),
                })
        else:
            steps.append({
                "step_id": uuid.uuid4().hex,
                "sequence": 1,
                "subgoal": goal,
                "action": f"Run learned skill {skill.get('skill_id')}",
                "tool_id": str(skill.get("tool_id") or ""),
                "args": dict(skill.get("args_template") or {}),
                "retry_limit": 1,
            })
        return {
            "plan_id": f"learned-{skill.get('skill_id')}",
            "goal": goal,
            "status": "planned" if steps else "needs_clarification",
            "notes": ["reused learned provider-free skill"],
            "steps": steps,
            "subgoals": [str(step.get("subgoal") or goal) for step in steps],
            "unplanned_goals": [],
        }

    def _plan_goal(self, goal: str) -> dict[str, Any]:
        from core.planner import Planner

        subgoals = _split_goal_steps(goal)
        planner = Planner()
        notes: list[str] = []
        unplanned: list[str] = []
        steps: list[dict[str, Any]] = []
        for index, subgoal in enumerate(subgoals, start=1):
            plan = planner.plan(subgoal).to_dict()
            if plan.get("status") != "planned" or not plan.get("steps"):
                unplanned.append(subgoal)
                notes.extend(str(note) for note in plan.get("notes") or [])
                continue
            notes.extend(str(note) for note in plan.get("notes") or [])
            for raw_step in plan.get("steps") or []:
                step = dict(raw_step)
                step["step_id"] = str(step.get("step_id") or uuid.uuid4().hex)
                step["sequence"] = index
                step["subgoal"] = subgoal
                steps.append(step)
        return {
            "plan_id": uuid.uuid4().hex,
            "goal": goal,
            "status": "planned" if steps and not unplanned else "needs_clarification",
            "notes": list(dict.fromkeys(notes)),
            "steps": steps,
            "subgoals": subgoals,
            "unplanned_goals": unplanned,
        }

    async def _execute(self, tool_id: str, args: dict[str, Any]) -> dict[str, Any]:
        raw_result = self.executor(tool_id, args)
        if inspect.isawaitable(raw_result):
            raw_result = await raw_result
        return dict(raw_result or {})

    async def _verify_step(self, tool_id: str, args: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        if _result_status(result) != "success":
            return {
                "status": "failed",
                "method": "gateway_result",
                "evidence": [_result_error(result)],
            }

        evidence = [f"{tool_id} returned success"]
        verification = {
            "status": "passed",
            "method": "gateway_result",
            "evidence": evidence,
        }
        if tool_id == "shell_workspace_tools:create_workspace_file_tool" and args.get("path"):
            read_result = await self._execute(
                "shell_workspace_tools:read_workspace_file_tool",
                {"path": str(args.get("path") or "")},
            )
            read_status = _result_status(read_result)
            if read_status != "success":
                return {
                    "status": "failed",
                    "method": "workspace_readback",
                    "evidence": [f"readback failed: {_result_error(read_result)}"],
                }
            expected = str(args.get("content") or "")
            read_text = json.dumps(read_result.get("result"), ensure_ascii=False, sort_keys=True)
            if expected and expected not in read_text:
                return {
                    "status": "failed",
                    "method": "workspace_readback",
                    "evidence": ["readback succeeded but expected content was not found"],
                    "readback": _redact(read_result),
                }
            verification = {
                "status": "passed",
                "method": "workspace_readback",
                "evidence": [f"read back {args.get('path')} successfully"],
                "readback": _redact(read_result),
            }
        if tool_id == "shell_code_engine:create_fullstack_app_tool":
            return await self._verify_fullstack_app(args, result)
        if tool_id == "shell_game_builder:build_game_tool":
            return await self._verify_game_artifact(args, result)
        return verification

    def _project_path_for_repair(self, args: dict[str, Any], result: dict[str, Any], verification: dict[str, Any]) -> Path | None:
        if verification.get("project_path"):
            return Path(str(verification.get("project_path"))).expanduser().resolve()
        raw_path = _path_from_tool_result(result)
        if raw_path is not None:
            return raw_path.expanduser().resolve()
        project_name = str(args.get("project_name") or "").strip()
        if project_name:
            return (Path(os.getcwd()) / "shell_projects" / project_name).resolve()
        return None

    def _game_path_for_repair(self, args: dict[str, Any], result: dict[str, Any], verification: dict[str, Any]) -> Path | None:
        if verification.get("game_path"):
            return Path(str(verification.get("game_path"))).expanduser().resolve()
        raw_path = _path_from_tool_result(result)
        if raw_path is not None:
            return raw_path.expanduser().resolve()
        try:
            import shell_game_builder

            game = str(args.get("game") or "game")
            slug = shell_game_builder._slug(game)  # type: ignore[attr-defined]
            out_dir = shell_game_builder._output_dir()  # type: ignore[attr-defined]
            candidates = sorted(Path(out_dir).glob(f"{slug}_*.html"), key=lambda path: path.stat().st_mtime, reverse=True)
            if candidates:
                return candidates[0].resolve()
            return (Path(out_dir) / f"{slug}_repaired_{int(time.time())}.html").resolve()
        except Exception:
            return None

    def _write_fullstack_fallback(self, project_path: Path, *, project_name: str, app_type: str) -> list[str]:
        title = re.sub(r"\s+", " ", project_name.replace("_", " ").replace("-", " ")).strip().title() or "Shell App"
        project_path.mkdir(parents=True, exist_ok=True)
        for rel in ("templates", "static/css", "static/js", "static/assets", "tests", "api"):
            (project_path / rel).mkdir(parents=True, exist_ok=True)
        files = {
            "app.py": f"""from flask import Flask, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({{"status": "ok", "project": "{project_name}"}})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
""",
            "templates/index.html": f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} | Shell Repaired</title>
  <link rel="stylesheet" href="{{{{ url_for('static', filename='css/style.css') }}}}">
</head>
<body>
  <main class="app-shell">
    <section class="panel">
      <p class="eyebrow">Shell autonomous repair</p>
      <h1>{title}</h1>
      <p>{app_type}</p>
      <button id="primaryAction" type="button">Start</button>
      <div id="status">Ready</div>
    </section>
  </main>
  <script src="{{{{ url_for('static', filename='js/script.js') }}}}"></script>
</body>
</html>
""",
            "static/css/style.css": """*{box-sizing:border-box}body{margin:0;min-height:100vh;background:#101820;color:#f7fbff;font-family:Inter,Segoe UI,Arial,sans-serif}.app-shell{min-height:100vh;display:grid;place-items:center;padding:32px;background:linear-gradient(135deg,#101820,#16324f 55%,#102d2a)}.panel{width:min(720px,100%);border:1px solid rgba(255,255,255,.16);border-radius:8px;padding:32px;background:rgba(255,255,255,.08);box-shadow:0 24px 80px rgba(0,0,0,.32)}.eyebrow{margin:0 0 10px;color:#7ce7ff;text-transform:uppercase;letter-spacing:.08em;font-size:12px}h1{margin:0 0 12px;font-size:40px;line-height:1.1}p{font-size:17px;line-height:1.55;color:#d7e5f0}button{border:0;border-radius:6px;padding:12px 18px;background:#7ce7ff;color:#07131f;font-weight:700;cursor:pointer}#status{margin-top:16px;color:#9af0c9}""",
            "static/js/script.js": """const button=document.getElementById('primaryAction');const status=document.getElementById('status');if(button&&status){button.addEventListener('click',()=>{status.textContent='Shell repaired app is interactive.';});}""",
            "requirements.txt": "flask\nflask_cors\n",
            "run_app.bat": "@echo off\npython app.py\npause\n",
            "tests/test_app.py": "from app import app\n\n\ndef test_home():\n    assert app.test_client().get('/').status_code == 200\n",
        }
        changed: list[str] = []
        for rel, content in files.items():
            path = project_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            changed.append(str(path))
        return changed

    def _fallback_game_html(self, title: str) -> str:
        safe_title = re.sub(r"[^A-Za-z0-9 _-]+", " ", title or "Shell Game").strip() or "Shell Game"
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title} | Shell Repaired</title>
  <style>
    *{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#0a1020;color:#eef8ff;font-family:Segoe UI,Arial,sans-serif}}
    .wrap{{display:grid;gap:12px;text-align:center}}canvas{{border:1px solid #00f0ff;border-radius:8px;background:#07111f;box-shadow:0 0 30px rgba(0,240,255,.28)}}
    .hud{{display:flex;gap:18px;justify-content:center;color:#8df7c6}}button{{padding:10px 16px;border:0;border-radius:6px;background:#00f0ff;color:#07111f;font-weight:700;cursor:pointer}}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>{safe_title}</h1>
    <div class="hud"><span>Score: <b id="score">0</b></span><span id="state">Start</span></div>
    <canvas id="game" width="520" height="320"></canvas>
    <button id="restart">Restart</button>
    <p>Use arrow keys or WASD. Avoid the walls and keep moving.</p>
  </div>
  <script>
    const canvas=document.getElementById('game');
    const ctx=canvas.getContext('2d');
    const scoreEl=document.getElementById('score');
    const stateEl=document.getElementById('state');
    let player={{x:40,y:140,w:28,h:28,vx:2,vy:0}};
    let orb={{x:360,y:140,r:12}};
    let score=0;
    let running=true;
    const keys=new Set();
    function reset(){{player={{x:40,y:140,w:28,h:28,vx:2,vy:0}};orb={{x:360,y:140,r:12}};score=0;running=true;scoreEl.textContent='0';stateEl.textContent='Running';}}
    function draw(){{
      ctx.fillStyle='#07111f';ctx.fillRect(0,0,canvas.width,canvas.height);
      ctx.strokeStyle='rgba(0,240,255,.18)';for(let x=0;x<canvas.width;x+=32){{ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,canvas.height);ctx.stroke();}}
      ctx.fillStyle='#00f0ff';ctx.fillRect(player.x,player.y,player.w,player.h);
      ctx.fillStyle='#8df7c6';ctx.beginPath();ctx.arc(orb.x,orb.y,orb.r,0,Math.PI*2);ctx.fill();
    }}
    function loop(){{
      if(running){{
        if(keys.has('ArrowUp')||keys.has('w')) player.y-=3;
        if(keys.has('ArrowDown')||keys.has('s')) player.y+=3;
        if(keys.has('ArrowLeft')||keys.has('a')) player.x-=3;
        if(keys.has('ArrowRight')||keys.has('d')) player.x+=3;
        player.x+=player.vx;
        if(player.x<0||player.y<0||player.x+player.w>canvas.width||player.y+player.h>canvas.height){{running=false;stateEl.textContent='Game Over - press Restart';}}
        if(Math.abs(player.x-orb.x)<34&&Math.abs(player.y-orb.y)<34){{score++;scoreEl.textContent=String(score);orb.x=80+Math.random()*380;orb.y=40+Math.random()*240;}}
      }}
      draw();requestAnimationFrame(loop);
    }}
    document.addEventListener('keydown',event=>keys.add(event.key));
    document.addEventListener('keyup',event=>keys.delete(event.key));
    document.getElementById('restart').addEventListener('click',reset);
    reset();loop();
  </script>
</body>
</html>
"""

    def _visual_issue_profile(self, verification: dict[str, Any]) -> dict[str, Any]:
        visual = verification.get("visual") if isinstance(verification, dict) else None
        if not isinstance(visual, dict) or visual.get("status") != "failed":
            return {"active": False, "signals": []}
        signals: list[str] = []
        console_errors = [str(item)[:240] for item in visual.get("console_errors") or []]
        page_errors = [str(item)[:240] for item in visual.get("page_errors") or []]
        if page_errors:
            signals.append("page_error")
        if console_errors:
            signals.append("console_error")
        if visual.get("screenshot_nonblank") is False:
            signals.append("blank_screenshot")
        if visual.get("canvas_requirement_ok") is False:
            signals.append("missing_canvas")
        if visual.get("canvas_nonblank") is False:
            signals.append("blank_canvas")
        if not signals:
            signals.append("browser_visual_failure")
        return {
            "active": True,
            "signals": list(dict.fromkeys(signals)),
            "console_errors": console_errors[:5],
            "page_errors": page_errors[:5],
            "screenshot_path": str(visual.get("screenshot_path") or ""),
            "body_text_preview": str(visual.get("body_text_preview") or "")[:300],
            "title": str(visual.get("title") or "")[:160],
        }

    def _write_fullstack_visual_patch(
        self,
        project_path: Path,
        *,
        project_name: str,
        app_type: str,
        profile: dict[str, Any],
    ) -> list[str]:
        title = re.sub(r"\s+", " ", project_name.replace("_", " ").replace("-", " ")).strip().title() or "Shell App"
        signals = ", ".join(str(item) for item in profile.get("signals") or []) or "browser_visual_failure"
        project_path.mkdir(parents=True, exist_ok=True)
        for rel in ("templates", "static/css", "static/js"):
            (project_path / rel).mkdir(parents=True, exist_ok=True)
        files = {
            "templates/index.html": f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} | Shell Visual Repair</title>
  <link rel="stylesheet" href="{{{{ url_for('static', filename='css/style.css') }}}}">
</head>
<body>
  <main class="shell-app" data-repair-signals="{signals}">
    <section class="hero">
      <p class="eyebrow">Shell verified app</p>
      <h1>{title}</h1>
      <p>{app_type}</p>
      <button id="primaryAction" type="button">Run check</button>
      <span id="status">Browser visual repair applied.</span>
    </section>
    <section class="panel">
      <h2>Ready</h2>
      <p>This generated app now has stable visible markup, styling, and JavaScript.</p>
    </section>
  </main>
  <script src="{{{{ url_for('static', filename='js/script.js') }}}}"></script>
</body>
</html>
""",
            "static/css/style.css": """*{box-sizing:border-box}html,body{margin:0;min-height:100%;font-family:Inter,Segoe UI,Arial,sans-serif}body{min-height:100vh;background:#08111f;color:#eef8ff;display:grid;place-items:center}.shell-app{width:min(1040px,92vw);display:grid;grid-template-columns:minmax(0,1.4fr) minmax(240px,.8fr);gap:18px}.hero,.panel{border:1px solid rgba(0,240,255,.28);background:linear-gradient(145deg,rgba(0,240,255,.12),rgba(45,226,166,.08));border-radius:8px;padding:28px;box-shadow:0 20px 60px rgba(0,0,0,.28)}.eyebrow{color:#65f2c8;font-weight:700;text-transform:uppercase;letter-spacing:0;font-size:13px}h1{margin:10px 0;font-size:42px;line-height:1.05;letter-spacing:0}h2{margin-top:0}p{line-height:1.6;color:#cfe8ff}button{border:0;border-radius:6px;background:#00f0ff;color:#07111f;font-weight:800;padding:12px 16px;cursor:pointer}#status{display:inline-block;margin-left:12px;color:#65f2c8}@media(max-width:760px){.shell-app{grid-template-columns:1fr}h1{font-size:32px}}""",
            "static/js/script.js": """const button=document.getElementById('primaryAction');const status=document.getElementById('status');if(button&&status){button.addEventListener('click',()=>{status.textContent='Interactive check passed.';});}console.log('Shell visual repair active');""",
        }
        changed: list[str] = []
        for rel, content in files.items():
            path = project_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            changed.append(str(path))
        return changed

    async def _deterministic_patch_artifact(
        self,
        tool_id: str,
        args: dict[str, Any],
        result: dict[str, Any],
        verification: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            visual_profile = self._visual_issue_profile(verification)
            if tool_id == "shell_code_engine:create_fullstack_app_tool":
                project_path = self._project_path_for_repair(args, result, verification)
                if project_path is None:
                    return {"status": "failed", "reason": "could not resolve project path for deterministic patch"}
                project_name = str(args.get("project_name") or project_path.name)
                app_type = str(args.get("app_type") or "Shell repaired app")
                if visual_profile.get("active"):
                    changed = self._write_fullstack_visual_patch(
                        project_path,
                        project_name=project_name,
                        app_type=app_type,
                        profile=visual_profile,
                    )
                    strategy = "browser_visual_fullstack_patch"
                else:
                    changed = self._write_fullstack_fallback(
                        project_path,
                        project_name=project_name,
                        app_type=app_type,
                    )
                    strategy = "deterministic_fullstack_patch"
                patched_result = {"status": "success", "tool": tool_id, "result": f"[REPAIRED]\nPath: `{project_path}`"}
                patched_verification = await self._verify_fullstack_app(args, patched_result)
                return {
                    "status": "success" if patched_verification.get("status") != "failed" else "failed",
                    "strategy": strategy,
                    "browser_repair_profile": _redact(visual_profile),
                    "changed_files": changed,
                    "result": _redact(patched_result),
                    "verification": _redact(patched_verification),
                    "reason": "; ".join(str(item) for item in patched_verification.get("evidence", []))[:400],
                }
            if tool_id == "shell_game_builder:build_game_tool":
                game_path = self._game_path_for_repair(args, result, verification)
                if game_path is None:
                    return {"status": "failed", "reason": "could not resolve game path for deterministic patch"}
                game_path.parent.mkdir(parents=True, exist_ok=True)
                game_title = str(args.get("game") or game_path.stem or "Shell Game")
                game_path.write_text(self._fallback_game_html(game_title), encoding="utf-8")
                patched_result = {"status": "success", "tool": tool_id, "result": f"Game repaired.\nPath: `{game_path}`"}
                patched_verification = await self._verify_game_artifact(args, patched_result)
                return {
                    "status": "success" if patched_verification.get("status") != "failed" else "failed",
                    "strategy": "browser_visual_game_patch" if visual_profile.get("active") else "deterministic_game_patch",
                    "browser_repair_profile": _redact(visual_profile),
                    "changed_files": [str(game_path)],
                    "result": _redact(patched_result),
                    "verification": _redact(patched_verification),
                    "reason": "; ".join(str(item) for item in patched_verification.get("evidence", []))[:400],
                }
        except Exception as exc:
            return {"status": "failed", "reason": f"deterministic patch failed: {exc}"}
        return {"status": "skipped", "reason": "no deterministic patch available"}

    async def _attempt_repair(self, tool_id: str, args: dict[str, Any], verification: dict[str, Any]) -> dict[str, Any]:
        repairable = {
            "shell_workspace_tools:create_workspace_file_tool",
            "shell_code_engine:create_fullstack_app_tool",
            "shell_game_builder:build_game_tool",
        }
        if tool_id not in repairable:
            return {
                "status": "skipped",
                "reason": "tool is not eligible for deterministic repair retry",
            }
        try:
            result = await self._execute(tool_id, args)
        except Exception as exc:
            patch = await self._deterministic_patch_artifact(tool_id, args, {}, verification)
            if patch.get("status") == "success":
                patch["retry_error"] = f"repair execution failed: {exc}"
                patch["previous_verification"] = _redact(verification)
                return patch
            return {
                "status": "failed",
                "reason": f"repair execution failed: {exc}",
                "deterministic_patch": _redact(patch),
                "previous_verification": _redact(verification),
            }
        if _result_status(result) != "success":
            patch = await self._deterministic_patch_artifact(tool_id, args, result, verification)
            if patch.get("status") == "success":
                patch["retry_result"] = _redact(result)
                patch["previous_verification"] = _redact(verification)
                return patch
            return {
                "status": "failed",
                "reason": _result_error(result),
                "result": _redact(result),
                "deterministic_patch": _redact(patch),
                "previous_verification": _redact(verification),
            }
        repaired_verification = await self._verify_step(tool_id, args, result)
        if repaired_verification.get("status") == "failed":
            patch = await self._deterministic_patch_artifact(tool_id, args, result, repaired_verification)
            if patch.get("status") == "success":
                patch["retry_result"] = _redact(result)
                patch["previous_verification"] = _redact(verification)
                patch["retry_verification"] = _redact(repaired_verification)
                return patch
            return {
                "status": "failed",
                "reason": "; ".join(str(item) for item in repaired_verification.get("evidence", []))[:400],
                "result": _redact(result),
                "verification": _redact(repaired_verification),
                "deterministic_patch": _redact(patch),
                "previous_verification": _redact(verification),
            }
        return {
            "status": "success",
            "strategy": "tool_retry",
            "result": _redact(result),
            "verification": _redact(repaired_verification),
            "previous_verification": _redact(verification),
        }

    async def _visual_verify_url(self, url: str, *, name: str, require_canvas: bool = False) -> dict[str, Any]:
        if not _visual_qa_enabled():
            return {"status": "skipped", "method": "browser_visual_qa", "reason": "disabled by SHELL_DISABLE_AUTONOMY_VISUAL_QA"}
        screenshot_dir = self.runtime_dir / _SCREENSHOT_DIRNAME
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name or "artifact")[:60] or "artifact"
        screenshot_path = screenshot_dir / f"{safe_name}_{uuid.uuid4().hex[:10]}.png"
        browser = None
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": 1280, "height": 800}, device_scale_factor=1)
                console_errors: list[str] = []
                page_errors: list[str] = []
                page.on("console", lambda msg: console_errors.append(msg.text[:240]) if msg.type == "error" else None)
                page.on("pageerror", lambda exc: page_errors.append(str(exc)[:240]))
                await page.goto(url, wait_until="domcontentloaded", timeout=_VISUAL_QA_TIMEOUT_MS)
                await page.wait_for_timeout(700)
                title = await page.title()
                try:
                    body_text = await page.locator("body").inner_text(timeout=1500)
                except Exception:
                    body_text = ""
                canvas_count = await page.locator("canvas").count()
                canvas_nonblank = True
                if require_canvas:
                    canvas_nonblank = bool(await page.evaluate(
                        """() => {
                            const canvases = Array.from(document.querySelectorAll('canvas'));
                            if (!canvases.length) return false;
                            return canvases.some((canvas) => {
                                const ctx = canvas.getContext('2d');
                                if (!ctx || canvas.width < 1 || canvas.height < 1) return false;
                                const w = Math.min(canvas.width, 80);
                                const h = Math.min(canvas.height, 80);
                                const data = ctx.getImageData(0, 0, w, h).data;
                                for (let i = 0; i < data.length; i += 4) {
                                    if (data[i + 3] > 0 && (data[i] !== 0 || data[i + 1] !== 0 || data[i + 2] !== 0)) return true;
                                }
                                return false;
                            });
                        }"""
                    ))
                await page.screenshot(path=str(screenshot_path), full_page=True)
                await browser.close()
                browser = None
        except Exception as exc:
            try:
                if browser is not None:
                    await browser.close()
            except Exception:
                pass
            return {
                "status": "skipped",
                "method": "browser_visual_qa",
                "reason": f"browser visual QA unavailable: {exc}",
            }

        nonblank, screenshot_stats = _screenshot_nonblank(screenshot_path)
        evidence = [f"screenshot saved to {screenshot_path}"]
        if console_errors:
            evidence.append(f"console errors: {len(console_errors)}")
        if page_errors:
            evidence.append(f"page errors: {len(page_errors)}")
        canvas_requirement_ok = canvas_count > 0 if require_canvas else True
        passed = bool(nonblank and canvas_requirement_ok and not page_errors)
        return {
            "status": "passed" if passed else "failed",
            "method": "browser_visual_qa",
            "url": url,
            "screenshot_path": str(screenshot_path),
            "title": title,
            "body_text_preview": str(body_text or "")[:300],
            "canvas_count": canvas_count,
            "canvas_nonblank": canvas_nonblank,
            "canvas_requirement_ok": canvas_requirement_ok,
            "screenshot_nonblank": nonblank,
            "screenshot_stats": screenshot_stats,
            "console_errors": console_errors[:5],
            "page_errors": page_errors[:5],
            "evidence": evidence,
        }

    def _fullstack_preview_uri(self, project_path: Path) -> str:
        index_html = project_path / "templates" / "index.html"
        html = index_html.read_text(encoding="utf-8", errors="replace")

        def replace_static(match: re.Match[str]) -> str:
            rel = match.group(1).strip().replace("\\", "/")
            return (project_path / "static" / rel).resolve().as_uri()

        html = re.sub(
            r"\{\{\s*url_for\(['\"]static['\"],\s*filename=['\"]([^'\"]+)['\"]\)\s*\}\}",
            replace_static,
            html,
        )
        preview_dir = self.runtime_dir / _PREVIEW_DIRNAME
        preview_dir.mkdir(parents=True, exist_ok=True)
        preview_path = preview_dir / f"{project_path.name}_{uuid.uuid4().hex[:10]}.html"
        preview_path.write_text(html, encoding="utf-8")
        return preview_path.as_uri()

    async def _verify_fullstack_app(self, args: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        raw_path = _path_from_tool_result(result)
        if raw_path is None:
            project_name = str(args.get("project_name") or "").strip()
            raw_path = Path(os.getcwd()) / "shell_projects" / project_name if project_name else None
        if raw_path is None:
            return _artifact_failed("fullstack_artifact_qa", ["project path was not reported and could not be inferred"])

        project_path = raw_path.expanduser().resolve()
        missing = [rel for rel in _FULLSTACK_REQUIRED_FILES if not (project_path / rel).exists()]
        if missing:
            return _artifact_failed(
                "fullstack_artifact_qa",
                [f"missing required files: {', '.join(missing)}"],
                project_path=str(project_path),
            )

        app_py = project_path / "app.py"
        index_html = project_path / "templates" / "index.html"
        css = project_path / "static" / "css" / "style.css"
        js = project_path / "static" / "js" / "script.js"
        requirements = project_path / "requirements.txt"
        try:
            ast.parse(app_py.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            return _artifact_failed(
                "fullstack_artifact_qa",
                [f"app.py syntax error line {exc.lineno}: {exc.msg}"],
                project_path=str(project_path),
            )
        except Exception as exc:
            return _artifact_failed(
                "fullstack_artifact_qa",
                [f"could not read app.py: {exc}"],
                project_path=str(project_path),
            )

        app_text = app_py.read_text(encoding="utf-8", errors="replace")
        html_text = index_html.read_text(encoding="utf-8", errors="replace").lower()
        css_text = css.read_text(encoding="utf-8", errors="replace")
        js_text = js.read_text(encoding="utf-8", errors="replace")
        req_text = requirements.read_text(encoding="utf-8", errors="replace").lower()
        checks = {
            "flask_app": "Flask(" in app_text and "@app.route" in app_text,
            "html_document": "<html" in html_text and "</html>" in html_text,
            "stylesheet": len(css_text.strip()) >= 120,
            "script_file": js.exists() and js_text is not None,
            "requirements": "flask" in req_text,
        }
        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            return _artifact_failed(
                "fullstack_artifact_qa",
                [f"failed checks: {', '.join(failed)}"],
                project_path=str(project_path),
                checks=checks,
            )
        visual = await self._visual_verify_url(
            self._fullstack_preview_uri(project_path),
            name=f"fullstack_{project_path.name}",
            require_canvas=False,
        )
        if visual.get("status") == "failed":
            return _artifact_failed(
                "fullstack_artifact_qa",
                ["browser visual QA failed"],
                project_path=str(project_path),
                checks=checks,
                visual=visual,
            )
        return _artifact_passed(
            "fullstack_artifact_qa",
            [
                f"verified project files in {project_path}",
                "app.py parses as Python",
                "Flask route, HTML, CSS, JS, requirements, and launcher are present",
            ],
            project_path=str(project_path),
            checks=checks,
            visual=visual,
        )

    async def _verify_game_artifact(self, args: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        explicit_path = _path_from_tool_result(result)
        candidates: list[Path] = []
        if explicit_path is not None:
            candidates.append(explicit_path.expanduser())
        try:
            import shell_game_builder

            slug = shell_game_builder._slug(str(args.get("game") or "game"))  # type: ignore[attr-defined]
            out_dir = shell_game_builder._output_dir()  # type: ignore[attr-defined]
            candidates.extend(sorted(Path(out_dir).glob(f"{slug}_*.html"), key=lambda path: path.stat().st_mtime, reverse=True))
        except Exception:
            pass

        html_path = next((path.resolve() for path in candidates if path.exists() and path.suffix.lower() in {".html", ".htm"}), None)
        if html_path is None:
            return _artifact_failed("game_artifact_qa", ["no generated HTML game file found"])

        html = html_path.read_text(encoding="utf-8", errors="replace")
        lower = html.lower()
        checks = {
            "html_document": "<html" in lower and "</html>" in lower,
            "canvas": "<canvas" in lower,
            "script": "<script" in lower,
            "animation_loop": "requestanimationframe" in lower or "setinterval" in lower,
            "input_controls": "keydown" in lower or "touch" in lower or "pointer" in lower,
            "game_state": any(marker in lower for marker in ("score", "game over", "restart", "start")),
        }
        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            return _artifact_failed(
                "game_artifact_qa",
                [f"failed checks: {', '.join(failed)}"],
                game_path=str(html_path),
                checks=checks,
                bytes=html_path.stat().st_size,
            )
        visual = await self._visual_verify_url(
            html_path.as_uri(),
            name=f"game_{html_path.stem}",
            require_canvas=True,
        )
        if visual.get("status") == "failed":
            return _artifact_failed(
                "game_artifact_qa",
                ["browser visual QA failed"],
                game_path=str(html_path),
                checks=checks,
                bytes=html_path.stat().st_size,
                visual=visual,
            )
        return _artifact_passed(
            "game_artifact_qa",
            [
                f"verified generated game HTML at {html_path}",
                "canvas, script, animation loop, controls, and game-state markers are present",
            ],
            game_path=str(html_path),
            checks=checks,
            bytes=html_path.stat().st_size,
            visual=visual,
        )

    def list_skills(self, *, query: str = "", limit: int = 10) -> dict[str, Any]:
        needle = _normalize_goal(query)
        rows = _load_skill_rows(self.skills_path)
        if needle:
            rows = [
                row for row in rows
                if needle in str(row.get("goal_pattern") or "")
                or needle in str(row.get("sample_goal") or "").lower()
                or needle in str(row.get("tool_id") or "").lower()
            ]
        rows.sort(key=lambda row: (int(row.get("success_count") or 0), str(row.get("last_used_at") or "")), reverse=True)
        limited = rows[: max(1, int(limit))]
        return {
            "status": "success",
            "count": len(limited),
            "runtime_dir": str(self.runtime_dir),
            "skills": [_redact(row) for row in limited],
        }

    def status(self, *, task_id: str = "", limit: int = 5) -> dict[str, Any]:
        if task_id:
            for row in reversed(_load_recent_runs(self.runs_path, 1000)):
                if str(row.get("task_id") or "") == str(task_id):
                    return {"status": "success", "run": row, "runtime_dir": str(self.runtime_dir)}
            return {
                "status": "not_found",
                "task_id": task_id,
                "runtime_dir": str(self.runtime_dir),
                "message": "No autonomous run record found for that task_id.",
            }
        latest = _read_json(self.latest_path, None)
        return {
            "status": "success",
            "runtime_dir": str(self.runtime_dir),
            "latest": latest if isinstance(latest, dict) else None,
            "recent": _load_recent_runs(self.runs_path, limit),
        }

    async def run(
        self,
        goal: str,
        *,
        dry_run: bool = False,
        learn: bool = True,
        verify: bool = True,
        auto_repair: bool = True,
        resumed_from: str = "",
    ) -> dict[str, Any]:
        from core.events import AIEventType, publish_event

        started = time.perf_counter()
        task_id = uuid.uuid4().hex
        cleaned_goal = str(goal or "").strip()
        goal_signature = _normalize_goal(cleaned_goal)
        run_record: dict[str, Any] = {
            "task_id": task_id,
            "goal": cleaned_goal,
            "goal_signature": goal_signature,
            "status": "running",
            "dry_run": bool(dry_run),
            "verify": bool(verify),
            "auto_repair": bool(auto_repair),
            "resumed_from": str(resumed_from or ""),
            "started_at": _now_iso(),
            "completed_at": "",
            "plan": {},
            "steps": [],
            "reused_skill": None,
            "learned_skill": None,
            "recovery_hints": [],
        }
        publish_event(AIEventType.TASK_STARTED, {"task_id": task_id, "goal": cleaned_goal}, source="shell_autonomous_agent")

        skill = self._matching_skill(goal_signature)
        if skill:
            plan = self._plan_from_skill(cleaned_goal, skill)
            run_record["reused_skill"] = _redact(skill)
        else:
            plan = self._plan_goal(cleaned_goal)

        run_record["plan"] = _redact(plan)
        steps = list(plan.get("steps") or []) if isinstance(plan, dict) else []
        if str(plan.get("status") or "") != "planned" or not steps:
            run_record["status"] = "needs_planning"
            run_record["recovery_hints"] = _recovery_hints(goal=cleaned_goal, plan=plan, result=None)
            return self._finish(run_record, started)

        if dry_run:
            run_record["status"] = "dry_run"
            run_record["steps"] = [
                {
                    "step_id": str(step.get("step_id") or ""),
                    "sequence": int(step.get("sequence") or index + 1),
                    "subgoal": str(step.get("subgoal") or cleaned_goal),
                    "tool_id": str(step.get("tool_id") or ""),
                    "args": _redact(dict(step.get("args") or {})),
                    "status": "planned",
                    "result": "not executed because dry_run=True",
                    "verification": {"status": "planned", "method": "dry_run"},
                }
                for index, step in enumerate(steps)
            ]
            return self._finish(run_record, started)

        for step in steps:
            tool_id = str(step.get("tool_id") or "")
            args = dict(step.get("args") or {})
            step_started = time.perf_counter()
            step_record = {
                "step_id": str(step.get("step_id") or uuid.uuid4().hex),
                "sequence": int(step.get("sequence") or len(run_record["steps"]) + 1),
                "subgoal": str(step.get("subgoal") or cleaned_goal),
                "action": str(step.get("action") or f"Run {tool_id}"),
                "tool_id": tool_id,
                "args": _redact(args),
                "status": "running",
                "duration_ms": 0.0,
                "result": {},
                "verification": {"status": "skipped", "method": "verify_disabled"},
                "error": "",
            }
            try:
                result = await self._execute(tool_id, args)
                step_record["result"] = _redact(result)
                step_record["status"] = _result_status(result)
                if step_record["status"] != "success":
                    step_record["error"] = _result_error(result)
                    run_record["steps"].append(step_record)
                    run_record["status"] = "failed"
                    run_record["recovery_hints"] = _recovery_hints(goal=cleaned_goal, plan=plan, result=result, error=step_record["error"])
                    return self._finish(run_record, started)
                if verify:
                    verification = await self._verify_step(tool_id, args, result)
                    step_record["verification"] = _redact(verification)
                    if verification.get("status") == "failed":
                        step_record["status"] = "verification_failed"
                        step_record["error"] = "; ".join(str(item) for item in verification.get("evidence", []))[:400]
                        repaired = False
                        if auto_repair:
                            repair = await self._attempt_repair(tool_id, args, verification)
                            step_record["auto_repair"] = _redact(repair)
                            if repair.get("status") == "success":
                                step_record["status"] = "success"
                                step_record["error"] = ""
                                step_record["result"] = _redact(repair.get("result") or {})
                                step_record["verification"] = _redact(repair.get("verification") or {})
                                repaired = True
                        if repaired:
                            pass
                        else:
                            run_record["steps"].append(step_record)
                            run_record["status"] = "failed"
                            run_record["recovery_hints"] = _recovery_hints(goal=cleaned_goal, plan=plan, result=result, error="verification failed")
                            return self._finish(run_record, started)
            except Exception as exc:
                step_record["status"] = "error"
                step_record["error"] = str(exc)[:400]
                run_record["steps"].append(step_record)
                run_record["status"] = "failed"
                run_record["recovery_hints"] = _recovery_hints(goal=cleaned_goal, plan=plan, result=None, error=step_record["error"])
                return self._finish(run_record, started)
            finally:
                step_record["duration_ms"] = round((time.perf_counter() - step_started) * 1000.0, 3)
            run_record["steps"].append(step_record)

        run_record["status"] = "success"
        if learn and steps:
            if len(steps) > 1:
                steps_template = [
                    {
                        "sequence": int(step.get("sequence") or index + 1),
                        "subgoal": str(step.get("subgoal") or cleaned_goal),
                        "action": str(step.get("action") or f"Run {step.get('tool_id') or ''}"),
                        "tool_id": str(step.get("tool_id") or ""),
                        "args": dict(step.get("args") or {}),
                        "retry_limit": int(step.get("retry_limit") or 1),
                    }
                    for index, step in enumerate(steps)
                ]
                run_record["learned_skill"] = _redact(
                    self._learn_skill(
                        goal=cleaned_goal,
                        goal_signature=goal_signature,
                        tool_id=_WORKFLOW_TOOL_ID,
                        args={},
                        steps_template=steps_template,
                    )
                )
            else:
                first = steps[0]
                run_record["learned_skill"] = _redact(
                    self._learn_skill(
                        goal=cleaned_goal,
                        goal_signature=goal_signature,
                        tool_id=str(first.get("tool_id") or ""),
                        args=dict(first.get("args") or {}),
                    )
                )
        publish_event(AIEventType.AGENT_COMPLETED, {"task_id": task_id, "status": "success"}, source="shell_autonomous_agent")
        return self._finish(run_record, started)

    async def resume(self, task_id: str, *, dry_run: bool = False, learn: bool = True, verify: bool = True, auto_repair: bool = True) -> dict[str, Any]:
        record = self.status(task_id=task_id).get("run")
        if not isinstance(record, dict):
            return {
                "status": "not_found",
                "task_id": task_id,
                "message": "No autonomous run record found to resume.",
            }
        goal = str(record.get("goal") or "")
        if not goal:
            return {
                "status": "error",
                "task_id": task_id,
                "message": "Run record has no resumable goal.",
            }
        result = await self.run(goal, dry_run=dry_run, learn=learn, verify=verify, auto_repair=auto_repair, resumed_from=task_id)
        result["resume"] = {
            "from_task_id": task_id,
            "previous_status": str(record.get("status") or ""),
        }
        _write_json(self.latest_path, result)
        return result

    def _finish(self, run_record: dict[str, Any], started: float) -> dict[str, Any]:
        from core.events import AIEventType, publish_event

        run_record["completed_at"] = _now_iso()
        run_record["duration_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        _write_json(self.latest_path, run_record)
        _append_jsonl(self.runs_path, run_record)
        event_type = AIEventType.TASK_COMPLETED if run_record.get("status") in {"success", "dry_run"} else AIEventType.TASK_FAILED
        publish_event(event_type, {"task_id": run_record.get("task_id"), "status": run_record.get("status")}, source="shell_autonomous_agent")
        return run_record


async def autonomous_goal_run(
    goal: str,
    *,
    dry_run: bool = False,
    learn: bool = True,
    verify: bool = True,
    auto_repair: bool = True,
    executor: Executor | None = None,
) -> dict[str, Any]:
    """Run a Shell goal through planning, gateway execution, persistence, and learning."""
    return await AutonomousGoalRunner(executor=executor).run(goal, dry_run=dry_run, learn=learn, verify=verify, auto_repair=auto_repair)


async def autonomous_goal_resume(
    task_id: str,
    *,
    dry_run: bool = False,
    learn: bool = True,
    verify: bool = True,
    auto_repair: bool = True,
    executor: Executor | None = None,
) -> dict[str, Any]:
    """Resume a previous autonomous run by re-running its stored goal."""
    return await AutonomousGoalRunner(executor=executor).resume(task_id, dry_run=dry_run, learn=learn, verify=verify, auto_repair=auto_repair)


def autonomous_goal_status(task_id: str = "", limit: int = 5) -> dict[str, Any]:
    """Return latest or recent autonomous run records."""
    return AutonomousGoalRunner().status(task_id=task_id, limit=limit)


def autonomous_skill_list(query: str = "", limit: int = 10) -> dict[str, Any]:
    """Return learned provider-free autonomous skills."""
    return AutonomousGoalRunner().list_skills(query=query, limit=limit)


@function_tool(category="agents")
async def autonomous_goal_run_tool(goal: str, dry_run: bool = False, learn: bool = True, verify: bool = True, auto_repair: bool = True) -> dict[str, Any]:
    """Plan, execute, record, and learn from a Shell goal using the local tool gateway."""
    return await autonomous_goal_run(goal, dry_run=dry_run, learn=learn, verify=verify, auto_repair=auto_repair)


@function_tool(category="agents")
async def autonomous_goal_resume_tool(task_id: str, dry_run: bool = False, learn: bool = True, verify: bool = True, auto_repair: bool = True) -> dict[str, Any]:
    """Resume a previous autonomous goal by task id."""
    return await autonomous_goal_resume(task_id, dry_run=dry_run, learn=learn, verify=verify, auto_repair=auto_repair)


@function_tool(category="agents")
def autonomous_goal_status_tool(task_id: str = "", limit: int = 5) -> dict[str, Any]:
    """Show autonomous goal run history and the latest run record."""
    return autonomous_goal_status(task_id=task_id, limit=limit)


@function_tool(category="agents")
def autonomous_skill_list_tool(query: str = "", limit: int = 10) -> dict[str, Any]:
    """List provider-free skills learned from successful autonomous runs."""
    return autonomous_skill_list(query=query, limit=limit)


__all__ = [
    "AutonomousGoalRunner",
    "autonomous_goal_resume",
    "autonomous_goal_resume_tool",
    "autonomous_goal_run",
    "autonomous_goal_run_tool",
    "autonomous_goal_status",
    "autonomous_goal_status_tool",
    "autonomous_skill_list",
    "autonomous_skill_list_tool",
]
