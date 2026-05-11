import json
import os
import re
import logging
import asyncio
import subprocess
import time
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger("shell_workflow")
WORKFLOW_DIR = "brain/automation/workflows"


def _truthy(value) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _workflow_command_allowed() -> bool:
    return _truthy(os.environ.get("SHELL_ALLOW_WORKFLOW_COMMANDS"))


def _workflow_file_write_allowed() -> bool:
    return _truthy(os.environ.get("SHELL_ALLOW_WORKFLOW_FILE_WRITE"))


def _workflow_file_read_allowed() -> bool:
    return _truthy(os.environ.get("SHELL_ALLOW_WORKFLOW_FILE_READ"))


def _blocked(message: str, state: Dict, report: List[str], step_id: str) -> None:
    state[f"{step_id}.output"] = message
    report.append(f"  Step {step_id}: {message[:200]}")


def _validate_workflow_url(url: str) -> tuple:
    try:
        from shell_downloader import _validate_url
        return _validate_url(url)
    except Exception:
        if str(url or "").strip().lower().startswith(("http://", "https://")):
            return True, ""
        return False, "only http/https URLs are allowed"


def _workflow_filename(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name or "").strip()).strip("._-")
    if not slug:
        raise ValueError("workflow name must contain at least one letter or number")
    return f"{slug.lower()}.json"

class WorkflowEngine:
    """
    No-Code Automation Engine V2 — 15+ action types.
    Executes JSON-defined pipelines with real tool integration.
    """

    def __init__(self):
        self._ensure_dir()
        self.workflows = {}
        self._execution_log = []
        self.load_workflows()

    def _ensure_dir(self):
        os.makedirs(WORKFLOW_DIR, exist_ok=True)

    def load_workflows(self):
        if not os.path.exists(WORKFLOW_DIR): return
        count = 0
        for f in os.listdir(WORKFLOW_DIR):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(WORKFLOW_DIR, f), 'r') as file:
                        wf = json.load(file)
                        self.workflows[wf['name']] = wf
                        count += 1
                except Exception as e:
                    logger.error(f"Failed to load workflow {f}: {e}")
        logger.info(f"Loaded {count} workflows.")

    def create_workflow(self, name: str, description: str, steps: List[Dict]) -> str:
        """Create a new workflow definition."""
        if not _workflow_file_write_allowed():
            return (
                "BLOCKED: workflow creation writes files. "
                "Set SHELL_ALLOW_WORKFLOW_FILE_WRITE=1 only for trusted workflows."
            )
        wf = {
            "name": name,
            "description": description,
            "created": datetime.now().isoformat(),
            "steps": steps
        }
        filepath = os.path.join(WORKFLOW_DIR, _workflow_filename(name))
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(wf, f, indent=2)
        self.workflows[name] = wf
        return f"Workflow '{name}' created with {len(steps)} steps."

    async def execute_workflow(self, workflow_name: str, context: Dict = None) -> str:
        if context is None:
            context = {}
        wf = self.workflows.get(workflow_name)
        if not wf:
            return f"Workflow '{workflow_name}' not found. Available: {', '.join(self.workflows.keys())}"

        report = [f"**Workflow: {workflow_name}**"]
        steps = wf.get("steps", [])
        state = context.copy()
        start_time = time.time()

        for step in steps:
            step_id = step.get("id", "unknown")
            action_type = step.get("action")
            params = dict(step.get("params", {}) or {})

            # Template substitution
            try:
                for k, v in params.items():
                    if isinstance(v, str) and "{{" in v:
                        for sk, sv in state.items():
                            v = v.replace(f"{{{{{sk}}}}}", str(sv))
                        params[k] = v
            except Exception:
                pass

            result = "Skipped"

            try:
                # === 15+ ACTION TYPES ===

                if action_type == "run_command":
                    if not _workflow_command_allowed():
                        _blocked(
                            "BLOCKED: workflow shell commands are disabled. "
                            "Set SHELL_ALLOW_WORKFLOW_COMMANDS=1 only for trusted workflows.",
                            state, report, step_id,
                        )
                        continue

                    # Run shell command
                    proc = await asyncio.create_subprocess_shell(
                        params.get("command", "echo hello"),
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
                    result = stdout.decode()[:500] if stdout else stderr.decode()[:500]

                elif action_type == "write_file":
                    if not _workflow_file_write_allowed():
                        _blocked(
                            "BLOCKED: workflow file writes are disabled. "
                            "Set SHELL_ALLOW_WORKFLOW_FILE_WRITE=1 only for trusted workflows.",
                            state, report, step_id,
                        )
                        continue

                    content = params.get("content", "")
                    filename = params.get("filename", "output.txt")
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(content)
                    result = f"File written: {filename} ({len(content)} chars)"

                elif action_type == "read_file":
                    if not _workflow_file_read_allowed():
                        _blocked(
                            "BLOCKED: workflow file reads are disabled. "
                            "Set SHELL_ALLOW_WORKFLOW_FILE_READ=1 only for trusted workflows.",
                            state, report, step_id,
                        )
                        continue

                    filename = params.get("filename", "")
                    if os.path.exists(filename):
                        with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                            result = f.read()[:2000]
                    else:
                        result = f"File not found: {filename}"

                elif action_type == "wait":
                    seconds = int(params.get("seconds", 1))
                    await asyncio.sleep(min(seconds, 30))
                    result = f"Waited {seconds}s"

                elif action_type == "speak":
                    if not _workflow_command_allowed():
                        _blocked(
                            "BLOCKED: workflow TTS shell command is disabled. "
                            "Set SHELL_ALLOW_WORKFLOW_COMMANDS=1 only for trusted workflows.",
                            state, report, step_id,
                        )
                        continue

                    text = params.get("text", "")
                    try:
                        proc = await asyncio.create_subprocess_shell(
                            f'powershell -Command "Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Speak(\'{text[:200]}\')"',
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                        )
                        await asyncio.wait_for(proc.communicate(), timeout=15)
                        result = f"Spoke: {text[:100]}"
                    except Exception:
                        result = f"TTS unavailable. Text: {text[:100]}"

                elif action_type == "ai_generate":
                    from brain.core import MultiAIBrain
                    brain = MultiAIBrain()
                    prompt = params.get("prompt", "")
                    mode = params.get("mode", "FAST")
                    result = await asyncio.wait_for(
                        brain.generate_response(prompt, mode=mode), timeout=30
                    )

                elif action_type == "open_url":
                    import webbrowser
                    url = params.get("url", "")
                    ok, reason = _validate_workflow_url(url)
                    if not ok:
                        result = f"BLOCKED: URL rejected: {reason}"
                        state[f"{step_id}.output"] = result
                        report.append(f"  Step {step_id}: {result[:200]}")
                        continue
                    webbrowser.open(url)
                    result = f"Opened: {url}"

                elif action_type == "http_request":
                    url = params.get("url", "")
                    ok, reason = _validate_workflow_url(url)
                    if not ok:
                        result = f"BLOCKED: URL rejected: {reason}"
                        state[f"{step_id}.output"] = result
                        report.append(f"  Step {step_id}: {result[:200]}")
                        continue
                    from shell_downloader import _urllib_open_with_safe_redirects
                    with _urllib_open_with_safe_redirects("GET", url, 15)[0] as resp:
                        result = resp.read().decode('utf-8', errors='ignore')[:2000]

                elif action_type == "set_variable":
                    var_name = params.get("name", "var")
                    var_value = params.get("value", "")
                    state[var_name] = var_value
                    result = f"Variable '{var_name}' = '{var_value}'"

                elif action_type == "condition":
                    check_var = params.get("variable", "")
                    expected = params.get("equals", "")
                    actual = state.get(check_var, "")
                    if str(actual) != str(expected):
                        result = f"Condition failed: {check_var}={actual} (expected {expected}). Skipping."
                        report.append(f"  Step {step_id}: {result}")
                        continue
                    result = f"Condition passed: {check_var}={actual}"

                elif action_type == "loop":
                    items = params.get("items", "").split(",")
                    var_name = params.get("variable", "item")
                    sub_steps = step.get("sub_steps", [])
                    loop_results = []
                    for item in items[:10]:
                        state[var_name] = item.strip()
                        for sub in sub_steps:
                            # Recursive execution would go here
                            loop_results.append(f"{var_name}={item.strip()}")
                    result = f"Loop completed: {len(items)} iterations"

                elif action_type == "log":
                    message = params.get("message", "")
                    logger.info(f"Workflow Log: {message}")
                    result = f"Logged: {message}"

                elif action_type == "notification":
                    if not _workflow_command_allowed():
                        _blocked(
                            "BLOCKED: workflow notification shell command is disabled. "
                            "Set SHELL_ALLOW_WORKFLOW_COMMANDS=1 only for trusted workflows.",
                            state, report, step_id,
                        )
                        continue

                    title = params.get("title", "Shell AI")
                    message = params.get("message", "")
                    try:
                        proc = await asyncio.create_subprocess_shell(
                            f'powershell -Command "[System.Reflection.Assembly]::LoadWithPartialName(\'System.Windows.Forms\'); [System.Windows.Forms.MessageBox]::Show(\'{message[:200]}\', \'{title}\')"',
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                        )
                        await asyncio.wait_for(proc.communicate(), timeout=10)
                        result = f"Notification: {title}"
                    except Exception:
                        result = f"Notification failed: {message[:100]}"

                elif action_type == "clipboard_copy":
                    if not _workflow_command_allowed():
                        _blocked(
                            "BLOCKED: workflow clipboard shell command is disabled. "
                            "Set SHELL_ALLOW_WORKFLOW_COMMANDS=1 only for trusted workflows.",
                            state, report, step_id,
                        )
                        continue

                    text = params.get("text", "")
                    try:
                        proc = await asyncio.create_subprocess_shell(
                            f'echo {text[:500]} | clip',
                            stdout=asyncio.subprocess.PIPE
                        )
                        await proc.communicate()
                        result = f"Copied to clipboard: {text[:50]}"
                    except Exception:
                        result = "Clipboard copy failed"

                elif action_type == "append_file":
                    if not _workflow_file_write_allowed():
                        _blocked(
                            "BLOCKED: workflow file writes are disabled. "
                            "Set SHELL_ALLOW_WORKFLOW_FILE_WRITE=1 only for trusted workflows.",
                            state, report, step_id,
                        )
                        continue

                    filename = params.get("filename", "output.txt")
                    content = params.get("content", "")
                    with open(filename, 'a', encoding='utf-8') as f:
                        f.write(content + "\n")
                    result = f"Appended to {filename}"

                else:
                    result = f"Unknown action: {action_type}"

                state[f"{step_id}.output"] = result
                report.append(f"  Step {step_id}: {result[:200]}")

            except Exception as e:
                error = f"Step {step_id} Failed: {e}"
                report.append(f"  {error}")
                if step.get("stop_on_error", True):
                    break

        elapsed = round(time.time() - start_time, 2)
        report.append(f"\n**Completed in {elapsed}s**")

        self._execution_log.append({
            "workflow": workflow_name,
            "time": datetime.now().isoformat(),
            "elapsed": elapsed,
            "steps": len(steps)
        })

        return "\n".join(report)

    def list_workflows(self) -> List[str]:
        return list(self.workflows.keys())

    def get_workflow_info(self, name: str) -> str:
        wf = self.workflows.get(name)
        if not wf:
            return f"Workflow '{name}' not found."
        steps = wf.get("steps", [])
        lines = [f"Workflow: {name}", f"Description: {wf.get('description', 'N/A')}", f"Steps: {len(steps)}"]
        for s in steps:
            lines.append(f"  {s.get('id', '?')}: {s.get('action', '?')} — {json.dumps(s.get('params', {}))[:100]}")
        return "\n".join(lines)

    def get_execution_log(self) -> str:
        if not self._execution_log:
            return "No workflow executions yet."
        lines = ["Workflow Execution Log", "=" * 40]
        for entry in self._execution_log[-10:]:
            lines.append(f"  {entry['workflow']} | {entry['time']} | {entry['elapsed']}s | {entry['steps']} steps")
        return "\n".join(lines)

workflow_engine = WorkflowEngine()
