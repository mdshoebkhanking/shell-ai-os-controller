"""
SHELL SENTINEL (Project Apex)
-----------------------------
The Immune System of Shell AI.
- Monitors agent_error.log
- Analyzes Stack Traces
- Generates Reproduction Tests (TDR)
- Synthesizes Fixes via LLM
- Verifies Fixes before Patching
- Automatic Rollback
"""

import os
import sys
import time
import logging
import asyncio
import traceback
import subprocess
import shutil
import re
from datetime import datetime
from typing import Optional, Dict
from shell_safe_executor import god_tier_tool as function_tool

# Shell AI infrastructure
from shell_config import config
from shell_logger import get_logger

logger = get_logger("sentinel")

class Sentinel:
    def __init__(self):
        self.log_file = "agent_error.log"
        self.backup_dir = "brain/sentinel_backups"
        self.api_key = config.get_str("GOOGLE_API_KEY")

        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir, exist_ok=True)

    def scan_logs(self) -> Optional[str]:
        """Checks for new crashes in the log file."""
        if not os.path.exists(self.log_file):
            return None

        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                content = f.read()
                if "Traceback" in content or "Error:" in content:
                    return content
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)
        return None

    async def heal_file(self, target_file: str, error_trace: str) -> str:
        """
        The Core Healing Loop (Apex Tier).
        1. Analyze Error
        2. Generate Test Case
        3. Draft Fix
        4. Verify Fix (Test Pass)
        5. Patch File

        SAFETY: Writing an LLM-generated patch requires SHELL_ALLOW_AGENT_PATCH=1
        if the target is agent.py or any core file, otherwise SHELL_ALLOW_CODE_WRITE=1
        is sufficient. Disabled by default — a bad LLM patch can brick the agent.
        """
        logger.info(f"Sentinel Activated for: {target_file}")

        # 0. Safety Gate
        try:
            from shell_safety_gate import check_code_write, check_agent_patch, audit_write
        except Exception:
            return (
                "--- SENTINEL HEAL REPORT ---\n"
                f"File: {target_file}\n"
                "Status: BLOCKED — shell_safety_gate unavailable.\n"
            )

        target_basename = os.path.basename(target_file)
        is_core = target_basename in ("agent.py", "shell_config.py", "shell_prompts.py")
        gate_ok, gate_reason = (
            check_agent_patch(origin="sentinel.heal_file")
            if is_core
            else check_code_write(origin="sentinel.heal_file")
        )
        if not gate_ok:
            return (
                f"--- SENTINEL HEAL REPORT ---\n"
                f"File: {target_file}\n"
                f"Status: BLOCKED BY SAFETY GATE\n\n{gate_reason}"
            )

        # 1. Safety Backup
        backup_path = self._create_backup(target_file)

        # Capture file size before fix
        size_before = os.path.getsize(target_file) if os.path.exists(target_file) else 0

        # 1. Generate Test Case (TDR)
        test_file = f"tests/repro_{int(time.time())}.py"
        os.makedirs("tests", exist_ok=True)

        logger.info("TDR: Generating Reproduction Test...")
        test_code = await self._consult_llm_for_test(target_file, error_trace)
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(test_code)

        # 2. Draft Fix
        logger.info("TDR: Drafting Fix...")
        original_code = ""
        with open(target_file, "r", encoding="utf-8") as f:
            original_code = f.read()

        fixed_code = await self._consult_llm_for_fix(original_code, error_trace)
        if not fixed_code or "Fix Generation Failed" in fixed_code:
            return (
                f"--- SENTINEL HEAL REPORT ---\n"
                f"File: {target_file}\n"
                f"Status: FAILED - Fix Generation Failed\n"
                f"Backup: {backup_path}\n"
                f"Boss, fix generate nahi ho paya. Backup safe hai, aap manually check karo."
            )

        # 3. Verify Fix (Sandboxed)
        logger.info("Applying Experimental Patch...")
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(fixed_code)
        audit_write("sentinel.heal_file", target_file, f"size={len(fixed_code)} backup={backup_path}")

        test_passed = self._run_test(test_file)

        size_after = os.path.getsize(target_file) if os.path.exists(target_file) else 0

        if test_passed:
            logger.info("Fix Verified! System Stabilized.")
            if os.path.exists(test_file): os.remove(test_file)
            return (
                f"--- SENTINEL HEAL REPORT ---\n"
                f"File: {target_file}\n"
                f"Status: FIXED & VERIFIED\n"
                f"Size Before: {size_before} bytes\n"
                f"Size After: {size_after} bytes\n"
                f"Backup: {backup_path}\n"
                f"Boss, file heal ho gayi hai! Test bhi pass hua. Backup rakha hai agar rollback chahiye toh."
            )
        else:
            logger.warning("Fix Failed Validation. Rolling Back...")
            self._rollback(target_file)
            return (
                f"--- SENTINEL HEAL REPORT ---\n"
                f"File: {target_file}\n"
                f"Status: FAILED - Rolled Back\n"
                f"Size Before: {size_before} bytes\n"
                f"Backup: {backup_path}\n"
                f"Boss, fix kaam nahi kiya, test fail hua. Rollback kar diya hai, file safe hai."
            )

    def _create_backup(self, filepath: str) -> str:
        # ISO-8601 timestamp is collision-proof, readable, and sorts right.
        # Colons stripped so it's a valid Windows filename.
        timestamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
        filename = os.path.basename(filepath)
        backup_path = os.path.join(self.backup_dir, f"{filename}.{timestamp}.bak")
        shutil.copy(filepath, backup_path)
        logger.info(f"Backup saved to {backup_path}")
        return backup_path

    def _rollback(self, filepath: str):
        filename = os.path.basename(filepath)
        backups = sorted([f for f in os.listdir(self.backup_dir) if f.startswith(filename)])
        if backups:
            latest = os.path.join(self.backup_dir, backups[-1])
            shutil.copy(latest, filepath)
            logger.info(f"Build Restored from {latest}")

    def _run_test(self, test_file: str) -> bool:
        try:
            result = subprocess.run(
                ["python", test_file],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.error(
                    "Sentinel test failed (rc=%s) for %s\nstderr:\n%s",
                    result.returncode, test_file, (result.stderr or "")[:2000],
                )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.error("Sentinel test timed out after 30s: %s", test_file)
            return False
        except Exception as e:
            logger.error("Sentinel test runner error (%s): %s", test_file, e)
            return False

    async def _consult_llm_for_test(self, file_path: str, error: str) -> str:
        prompt = f"""Create a standalone python unittest script ensuring the file '{file_path}' works related to this error.
        Error: {error}
        Return ONLY valid python code. No markdown."""
        return await self._call_gemini(prompt)

    async def _consult_llm_for_fix(self, code: str, error: str) -> str:
        prompt = f"""Fix this python code based on the error. Return ONLY the full fixed code. NO MARKDOWN.
        Error: {error}
        Code:\n{code}"""
        return await self._call_gemini(prompt)

    async def _call_gemini(self, prompt: str) -> str:
        """Call Gemini through whichever SDK is installed.

        Prefers `google.genai` (the supported SDK) and falls back to the
        deprecated `google.generativeai` only if the new one is missing.
        """
        model_name = "gemini-2.5-flash"

        async def _run_new():
            from google import genai as _new_genai
            client = _new_genai.Client(api_key=self.api_key)

            def _call():
                return client.models.generate_content(model=model_name, contents=prompt)

            return await asyncio.to_thread(_call)

        async def _run_legacy():
            import google.generativeai as _legacy_genai
            _legacy_genai.configure(api_key=self.api_key)
            model = _legacy_genai.GenerativeModel(model_name)
            return await asyncio.to_thread(model.generate_content, prompt)

        response = None
        try:
            response = await _run_new()
        except ImportError:
            try:
                response = await _run_legacy()
            except Exception as e:
                logger.error(f"Sentinel LLM Error (legacy fallback): {e}")
                return ""
        except Exception as e:
            logger.warning("google-genai call failed, trying legacy: %s", e)
            try:
                response = await _run_legacy()
            except Exception as e2:
                logger.error(f"Sentinel LLM Error (both SDKs): {e2}")
                return ""

        if response is None:
            return ""
        text = response.text or ""
        # Strip markdown fences so downstream code can ast-parse cleanly.
        if "```python" in text:
            text = text.split("```python")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return text.strip()

sentinel = Sentinel()

@function_tool
async def self_heal_tool(filename: str) -> str:
    """
    MANUAL SENTINEL TRIGGER.
    Use this if you know a file is broken and want Sentinel to fix it.
    Shows file size before/after fix, backup path, and detailed error formatting.
    Args:
        filename: 'agent.py', 'shell_brain.py', etc.
    """
    logfile = "agent_error.log"
    if not os.path.exists(logfile):
        return (
            "--- SENTINEL HEAL REPORT ---\n"
            "Status: NO ERROR LOG\n"
            "Boss, agent_error.log file mili hi nahi. Koi error logged nahi hai abhi."
        )

    if not os.path.exists(filename):
        return (
            f"--- SENTINEL HEAL REPORT ---\n"
            f"File: {filename}\n"
            f"Status: FILE NOT FOUND\n"
            f"Boss, '{filename}' exist nahi karta. File name check karo."
        )

    with open(logfile, "r", encoding="utf-8") as f:
        error = f.read()

    if not error.strip():
        return (
            "--- SENTINEL HEAL REPORT ---\n"
            "Status: LOG EMPTY\n"
            "Boss, error log khali hai. Koi error nahi mila heal karne ke liye."
        )

    return await sentinel.heal_file(filename, error)


@function_tool
async def scan_logs_tool() -> str:
    """
    Scans agent_error.log and returns a summary report.
    Reports: total errors found, unique error types, most recent error timestamp, files affected.
    Does NOT auto-fix anything, sirf reporting karta hai.
    """
    logfile = "agent_error.log"

    if not os.path.exists(logfile):
        return (
            "--- SENTINEL LOG SCAN REPORT ---\n"
            "Status: NO LOG FILE\n"
            "Boss, agent_error.log exist nahi karta. System clean hai ya logging start nahi hui."
        )

    try:
        file_size = os.path.getsize(logfile)
        with open(logfile, "r", encoding="utf-8") as f:
            content = f.read()

        if not content.strip():
            return (
                "--- SENTINEL LOG SCAN REPORT ---\n"
                f"Log File Size: {file_size} bytes\n"
                "Total Errors: 0\n"
                "Boss, log file hai lekin khali hai. Koi error nahi mila."
            )

        lines = content.splitlines()

        # Count total errors (lines containing Error: or Traceback)
        error_lines = [l for l in lines if "Error:" in l or "Error " in l or "Exception:" in l]
        traceback_count = content.count("Traceback")
        total_errors = max(len(error_lines), traceback_count)

        # Find unique error types (SyntaxError, ImportError, etc.)
        error_type_pattern = re.compile(r'\b([A-Z][a-zA-Z]*(?:Error|Exception))\b')
        all_error_types = error_type_pattern.findall(content)
        unique_types = list(dict.fromkeys(all_error_types))

        # Find files affected (look for File "..." patterns)
        file_pattern = re.compile(r'File\s+"([^"]+)"')
        affected_files = list(dict.fromkeys(file_pattern.findall(content)))
        # Filter to local project files only
        affected_files = [f for f in affected_files if not f.startswith("<") and ("shell_" in f or "agent" in f)]

        # Most recent timestamp (try to find date patterns in log)
        timestamp_pattern = re.compile(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})')
        timestamps = timestamp_pattern.findall(content)
        most_recent = timestamps[-1] if timestamps else "Timestamp not found in log"

        # Build report
        report_lines = [
            "--- SENTINEL LOG SCAN REPORT ---",
            f"Log File Size: {file_size} bytes",
            f"Total Lines: {len(lines)}",
            f"Total Errors/Tracebacks: {total_errors}",
            f"Most Recent Timestamp: {most_recent}",
            "",
            f"Unique Error Types ({len(unique_types)}):",
        ]

        for et in unique_types:
            count = all_error_types.count(et)
            report_lines.append(f"  - {et}: {count} occurrence(s)")

        if affected_files:
            report_lines.append(f"\nFiles Affected ({len(affected_files)}):")
            for af in affected_files[:10]:
                report_lines.append(f"  - {af}")

        report_lines.append(
            "\nBoss, ye log scan report hai. Koi auto-fix nahi kiya, sirf analysis hai. "
            "Agar fix chahiye toh self_heal_tool use karo."
        )

        return "\n".join(report_lines)

    except Exception as e:
        return (
            f"--- SENTINEL LOG SCAN REPORT ---\n"
            f"Status: SCAN ERROR\n"
            f"Error: {e}\n"
            f"Boss, log scan mein error aa gaya. File corrupt ho sakti hai."
        )


@function_tool
async def sentinel_status_tool() -> str:
    """
    Shows Sentinel system status dashboard.
    Reports: backup count, total backup size, error log status, last scan info.
    Sentinel ka overall health check karta hai ye tool.
    """
    backup_dir = "brain/sentinel_backups"
    logfile = "agent_error.log"

    report_lines = ["--- SENTINEL STATUS DASHBOARD ---"]

    # Backup Info
    if os.path.exists(backup_dir):
        backup_files = [f for f in os.listdir(backup_dir) if f.endswith(".bak")]
        backup_count = len(backup_files)
        total_backup_size = sum(
            os.path.getsize(os.path.join(backup_dir, f))
            for f in backup_files
            if os.path.isfile(os.path.join(backup_dir, f))
        )

        # Find most recent backup
        if backup_files:
            backup_files_sorted = sorted(backup_files, reverse=True)
            latest_backup = backup_files_sorted[0]
            latest_backup_path = os.path.join(backup_dir, latest_backup)
            latest_mod_time = datetime.fromtimestamp(os.path.getmtime(latest_backup_path)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            latest_backup = "N/A"
            latest_mod_time = "N/A"

        report_lines.extend([
            f"\n[BACKUPS]",
            f"  Backup Directory: {backup_dir}",
            f"  Total Backups: {backup_count}",
            f"  Total Backup Size: {total_backup_size} bytes ({round(total_backup_size / 1024, 2)} KB)",
            f"  Latest Backup: {latest_backup}",
            f"  Latest Backup Time: {latest_mod_time}",
        ])
    else:
        report_lines.extend([
            f"\n[BACKUPS]",
            f"  Backup Directory: {backup_dir} (NOT FOUND)",
            f"  Total Backups: 0",
        ])

    # Error Log Info
    if os.path.exists(logfile):
        log_size = os.path.getsize(logfile)
        log_mod_time = datetime.fromtimestamp(os.path.getmtime(logfile)).strftime("%Y-%m-%d %H:%M:%S")
        report_lines.extend([
            f"\n[ERROR LOG]",
            f"  File: {logfile}",
            f"  Exists: Yes",
            f"  Size: {log_size} bytes ({round(log_size / 1024, 2)} KB)",
            f"  Last Modified: {log_mod_time}",
        ])
    else:
        report_lines.extend([
            f"\n[ERROR LOG]",
            f"  File: {logfile}",
            f"  Exists: No",
        ])

    # Sentinel readiness
    has_backups = os.path.exists(backup_dir)
    has_log = os.path.exists(logfile)

    if has_backups and has_log:
        status = "FULLY OPERATIONAL"
        status_msg = "Boss, Sentinel poori tarah active hai. Backups aur logs dono ready hain."
    elif has_backups:
        status = "PARTIAL - No Error Log"
        status_msg = "Boss, backup system ready hai lekin error log nahi mili. System clean chal raha hai."
    elif has_log:
        status = "PARTIAL - No Backups Yet"
        status_msg = "Boss, error log hai lekin abhi tak koi backup nahi bana. Pehli healing pe banega."
    else:
        status = "STANDBY"
        status_msg = "Boss, Sentinel standby pe hai. Na log hai na backup. Fresh system lag raha hai."

    report_lines.extend([
        f"\n[SYSTEM STATUS]",
        f"  Sentinel Status: {status}",
        f"  {status_msg}",
    ])

    return "\n".join(report_lines)


@function_tool
async def auto_heal_all_tool() -> str:
    """
    Poore project ki saari Python files scan karta hai aur broken files identify karta hai.
    Syntax errors wali files list karta hai with option to heal.
    Full system diagnostic report deta hai.
    """
    try:
        project_dir = os.path.dirname(os.path.abspath(__file__))
        all_py = [f for f in os.listdir(project_dir) if f.endswith(".py")]

        healthy = []
        broken = []
        warnings = []

        for filename in sorted(all_py):
            filepath = os.path.join(project_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    code = f.read()

                # Syntax check
                compile(code, filename, "exec")

                # Warning checks
                file_warnings = []
                lines = code.splitlines()
                if len(lines) > 1000:
                    file_warnings.append(f"Large file ({len(lines)} lines)")
                if "eval(" in code or "exec(" in code:
                    file_warnings.append("Contains eval/exec")

                if file_warnings:
                    warnings.append((filename, file_warnings))

                healthy.append(filename)

            except SyntaxError as e:
                broken.append((filename, f"Line {e.lineno}: {e.msg}"))
            except Exception as e:
                broken.append((filename, str(e)))

        total = len(all_py)
        report = [
            "--- SENTINEL AUTO-HEAL SCAN ---",
            f"Total Files: {total}",
            f"Healthy: {len(healthy)}",
            f"Broken: {len(broken)}",
            f"Warnings: {len(warnings)}",
            f"Health Rate: {round(len(healthy)/max(total,1)*100, 1)}%",
            f"{'=' * 45}",
        ]

        if broken:
            report.append(f"\n[BROKEN FILES] ({len(broken)})")
            for fname, error in broken:
                report.append(f"  {fname}: {error}")
            report.append("\nUse self_heal_tool to fix broken files.")

        if warnings:
            report.append(f"\n[WARNINGS] ({len(warnings)})")
            for fname, warns in warnings[:10]:
                report.append(f"  {fname}: {', '.join(warns)}")

        if not broken and not warnings:
            report.append("\nSab files healthy hain! Koi issue nahi mila.")

        report.append(
            f"\nBoss, poore project ka health scan complete. "
            f"{len(healthy)}/{total} files healthy hain."
        )

        return "\n".join(report)

    except Exception as e:
        return f"--- AUTO-HEAL SCAN ---\nStatus: ERROR\nError: {e}"


@function_tool
async def backup_module_tool(filename: str) -> str:
    """
    Kisi bhi module ka manual backup banata hai brain/sentinel_backups mein.
    Safety ke liye koi bhi file ka backup le sakte ho pehle.
    Args:
        filename: File to backup (e.g., 'agent.py', 'shell_evolution.py')
    """
    try:
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        if not os.path.exists(filepath):
            return (
                f"--- SENTINEL BACKUP REPORT ---\n"
                f"File: {filename}\n"
                f"Status: FILE NOT FOUND\n"
                f"Boss, '{filename}' exist nahi karta."
            )

        backup_dir = "brain/sentinel_backups"
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{filename}.manual_{timestamp}.bak"
        backup_path = os.path.join(backup_dir, backup_name)

        shutil.copy(filepath, backup_path)

        original_size = os.path.getsize(filepath)
        backup_size = os.path.getsize(backup_path)

        # Count existing backups for this file
        existing_backups = [f for f in os.listdir(backup_dir) if f.startswith(filename)]

        return (
            f"--- SENTINEL BACKUP REPORT ---\n"
            f"File: {filename}\n"
            f"Backup: {backup_path}\n"
            f"Original Size: {original_size} bytes ({round(original_size/1024, 1)} KB)\n"
            f"Backup Size: {backup_size} bytes\n"
            f"Total Backups for this file: {len(existing_backups)}\n"
            f"Timestamp: {timestamp}\n"
            f"Status: BACKUP SUCCESSFUL\n"
            f"Boss, '{filename}' ka backup safe hai. Sentinel protect kar raha hai."
        )

    except Exception as e:
        return f"--- SENTINEL BACKUP ---\nStatus: ERROR\nError: {e}"


@function_tool
async def restore_backup_tool(backup_filename: str) -> str:
    """
    Sentinel backup se file restore karta hai.
    Backup file ka naam do aur original file restore ho jayegi.
    Args:
        backup_filename: Backup file name from brain/sentinel_backups/ (e.g., 'agent.py.manual_20260316.bak')
    """
    try:
        backup_dir = "brain/sentinel_backups"
        backup_path = os.path.join(backup_dir, backup_filename)

        if not os.path.exists(backup_path):
            # List available backups
            if os.path.exists(backup_dir):
                available = os.listdir(backup_dir)[:20]
                available_str = "\n  ".join(available) if available else "No backups found"
            else:
                available_str = "Backup directory doesn't exist"

            return (
                f"--- SENTINEL RESTORE REPORT ---\n"
                f"Backup: {backup_filename}\n"
                f"Status: BACKUP NOT FOUND\n"
                f"\nAvailable Backups:\n  {available_str}\n"
                f"\nBoss, ye backup nahi mila. Upar available backups hain."
            )

        # Extract original filename from backup name
        # Format: originalname.py.something.bak
        parts = backup_filename.split(".")
        # Find the .py part
        py_idx = -1
        for i, part in enumerate(parts):
            if part == "py":
                py_idx = i
                break

        if py_idx == -1:
            return "--- SENTINEL RESTORE ---\nStatus: Cannot determine original filename from backup name."

        original_name = ".".join(parts[:py_idx + 1])
        original_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), original_name)

        # Backup current version before restoring
        if os.path.exists(original_path):
            pre_restore_backup = os.path.join(backup_dir, f"{original_name}.pre_restore_{int(time.time())}.bak")
            shutil.copy(original_path, pre_restore_backup)

        # Restore
        shutil.copy(backup_path, original_path)

        return (
            f"--- SENTINEL RESTORE REPORT ---\n"
            f"Backup: {backup_filename}\n"
            f"Restored To: {original_name}\n"
            f"Size: {os.path.getsize(original_path)} bytes\n"
            f"Status: RESTORE SUCCESSFUL\n"
            f"Boss, '{original_name}' restore ho gayi hai backup se. Current version ka bhi backup rakha hai."
        )

    except Exception as e:
        return f"--- SENTINEL RESTORE ---\nStatus: ERROR\nError: {e}"


@function_tool
async def list_backups_tool() -> str:
    """
    Saare Sentinel backups list karta hai — filename, size, timestamp.
    Kya kya backup hai system mein — sab dikhata hai.
    """
    try:
        backup_dir = "brain/sentinel_backups"
        if not os.path.exists(backup_dir):
            return (
                "--- SENTINEL BACKUP LIST ---\n"
                "Status: NO BACKUPS\n"
                "Boss, backup directory exist nahi karta. Abhi tak koi backup nahi bana."
            )

        files = os.listdir(backup_dir)
        if not files:
            return (
                "--- SENTINEL BACKUP LIST ---\n"
                "Status: EMPTY\n"
                "Boss, backup directory hai lekin khali hai."
            )

        backups = []
        total_size = 0
        for f in sorted(files, reverse=True):
            fp = os.path.join(backup_dir, f)
            if os.path.isfile(fp):
                size = os.path.getsize(fp)
                total_size += size
                mod_time = datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%Y-%m-%d %H:%M:%S")
                backups.append((f, size, mod_time))

        report = [
            "--- SENTINEL BACKUP LIST ---",
            f"Total Backups: {len(backups)}",
            f"Total Size: {round(total_size/1024, 1)} KB ({round(total_size/(1024*1024), 2)} MB)",
            f"{'=' * 55}",
        ]

        for name, size, mod_time in backups[:30]:
            size_str = f"{round(size/1024, 1)} KB"
            report.append(f"  [{mod_time}] {name} ({size_str})")

        if len(backups) > 30:
            report.append(f"  ... aur {len(backups) - 30} backups")

        report.append(f"\nBoss, total {len(backups)} backups hain {round(total_size/1024, 1)} KB mein.")

        return "\n".join(report)

    except Exception as e:
        return f"--- BACKUP LIST ---\nStatus: ERROR\nError: {e}"
