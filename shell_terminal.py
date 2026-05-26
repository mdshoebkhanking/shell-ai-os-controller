"""
Shell Terminal Tools - Command execution and system info
----------------------------------------------------------
Provides tools for running shell/PowerShell commands,
executing Python code, getting system info, and
managing environment variables. Includes safety checks.
"""

import os
import re
import asyncio
import platform
import subprocess
import logging
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("SHELL_TERMINAL")

SECRET_ENV_NAME_PARTS = (
    "api_key",
    "apikey",
    "auth",
    "bearer",
    "client_secret",
    "credential",
    "key",
    "password",
    "private",
    "secret",
    "session",
    "token",
    "webhook",
)

# ── Soft imports ─────────────────────────────────────
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# ── Safety: blocked dangerous commands ───────────────
DANGEROUS_PATTERNS = [
    r"\brm\s+(-\w*\s+)*-rf\s+/\s*$",         # rm -rf /
    r"\brm\s+(-\w*\s+)*-rf\s+/\*",            # rm -rf /*
    r"\bformat\s+[a-zA-Z]:",                    # format C:
    r"\bmkfs\b",                                # mkfs
    r"\bdd\s+.*of=/dev/sd",                     # dd to disk
    r"\b:(){ :\|:& };:",                        # fork bomb
    r"\bshutdown\b",                            # shutdown
    r"\breboot\b",                              # reboot
    r"\bhalt\b",                                # halt
    r"\binit\s+0\b",                            # init 0
    r"\brm\s+(-\w*\s+)*-rf\s+~",               # rm -rf ~
    r"\brd\s+/s\s+/q\s+[cC]:\\",               # rd /s /q C:\
    r"\bdel\s+/[fFsS]\s+[cC]:\\",              # del /f C:\
    r"\breg\s+delete\b.*\\\\",                  # reg delete
    r"\bnet\s+user\b.*\/delete",               # net user delete
    r"\bclear-disk\b",                          # clear-disk
    r"\bRemove-Item\s+.*-Recurse.*[cC]:\\",    # PowerShell nuke
    r"\bStop-Computer\b",                       # PowerShell shutdown
    r"\bRestart-Computer\b",                    # PowerShell restart
    r"\bshutil\.rmtree\s*\(\s*['\"](?:/|~|[a-zA-Z]:\\)",  # Python nuke
    r"\bos\.remove\s*\(\s*['\"](?:/|~|[a-zA-Z]:\\)",      # Python root removal
    r"\bos\.system\s*\([^)]*(rm\s+-rf|format\s+[a-zA-Z]:|shutdown|reboot)",
    r"\bsubprocess\.(?:run|Popen|call)\s*\([^)]*(rm\s+-rf|format\s+[a-zA-Z]:|shutdown|reboot)",
]


def _is_dangerous(command: str) -> bool:
    """Check if a command matches any dangerous pattern."""
    cmd_lower = command.strip()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd_lower, re.IGNORECASE):
            return True
    return False


def _truthy(value) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _terminal_exec_allowed() -> tuple[bool, str]:
    if not _truthy(os.environ.get("SHELL_BLOCK_TERMINAL_EXEC")):
        return True, ""
    return (
        False,
        "Terminal execution is disabled by SHELL_BLOCK_TERMINAL_EXEC=1.",
    )


def _is_secret_env_name(key: str) -> bool:
    lower = key.lower()
    return any(part in lower for part in SECRET_ENV_NAME_PARTS)


def _display_env_value(key: str, value: str) -> str:
    if _is_secret_env_name(key):
        return "<redacted:set>" if value else "<empty>"
    return value if len(value) <= 200 else value[:200] + "..."


@function_tool
async def run_command_tool(command: str) -> str:
    """
    Run a shell command and return output. Has a 30-second timeout and blocks dangerous commands.
    Args:
        command: Shell command to execute (e.g. 'dir', 'ipconfig', 'ls -la').
    """
    try:
        if not command.strip():
            return "Error: Command cannot be empty."

        allowed, reason = _terminal_exec_allowed()
        if not allowed:
            return f"BLOCKED: {reason}"

        # Safety check
        if _is_dangerous(command):
            return f"BLOCKED: This command is flagged as dangerous and was not executed.\nCommand: {command}"

        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError:
            proc.kill()
            return f"Command timed out after 30 seconds: {command}"

        output = stdout.decode("utf-8", errors="replace").strip()
        error = stderr.decode("utf-8", errors="replace").strip()

        result_parts = []
        if output:
            result_parts.append(f"Output:\n{output[:5000]}")
            if len(output) > 5000:
                result_parts.append(f"\n... (truncated, {len(output)} total chars)")
        if error:
            result_parts.append(f"Stderr:\n{error[:2000]}")
        if proc.returncode != 0:
            result_parts.append(f"Exit Code: {proc.returncode}")

        if not result_parts:
            return f"Command completed with no output. Exit code: {proc.returncode}"

        return "\n".join(result_parts)

    except Exception as e:
        logger.error(f"run_command_tool error: {e}")
        return f"Error running command: {e}"


@function_tool
async def run_powershell_tool(script: str) -> str:
    """
    Run a PowerShell script and return output.
    Args:
        script: PowerShell script or command to execute.
    """
    try:
        if not script.strip():
            return "Error: Script cannot be empty."

        allowed, reason = _terminal_exec_allowed()
        if not allowed:
            return f"BLOCKED: {reason}"

        # Safety check
        if _is_dangerous(script):
            return f"BLOCKED: This script is flagged as dangerous and was not executed.\nScript: {script}"

        proc = await asyncio.create_subprocess_exec(
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError:
            proc.kill()
            return f"PowerShell script timed out after 30 seconds."

        output = stdout.decode("utf-8", errors="replace").strip()
        error = stderr.decode("utf-8", errors="replace").strip()

        result_parts = []
        if output:
            result_parts.append(output[:5000])
            if len(output) > 5000:
                result_parts.append(f"\n... (truncated, {len(output)} total chars)")
        if error:
            result_parts.append(f"Errors:\n{error[:2000]}")
        if proc.returncode != 0:
            result_parts.append(f"Exit Code: {proc.returncode}")

        if not result_parts:
            return f"Script completed with no output. Exit code: {proc.returncode}"

        return "\n".join(result_parts)

    except Exception as e:
        logger.error(f"run_powershell_tool error: {e}")
        return f"Error running PowerShell: {e}"


@function_tool
async def run_python_tool(code: str) -> str:
    """
    Execute Python code in a separate subprocess and return output.
    Args:
        code: Python code to execute.
    """
    try:
        if not code.strip():
            return "Error: Code cannot be empty."

        try:
            from core.secure_sandbox import secure_sandbox_enabled
            if secure_sandbox_enabled():
                from shell_secure_sandbox import format_sandbox_result, run_python_in_sandbox
                return format_sandbox_result(await run_python_in_sandbox(code, timeout_s=30.0))
        except Exception as sandbox_exc:
            return f"Sandbox failed before execution: {sandbox_exc}"

        allowed, reason = _terminal_exec_allowed()
        if not allowed:
            return f"BLOCKED: {reason}"

        import sys
        python_exe = sys.executable
        if _is_dangerous(code):
            return "BLOCKED: This Python code is flagged as dangerous and was not executed."

        proc = await asyncio.create_subprocess_exec(
            python_exe, "-c", code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError:
            proc.kill()
            return "Python execution timed out after 30 seconds."

        output = stdout.decode("utf-8", errors="replace").strip()
        error = stderr.decode("utf-8", errors="replace").strip()

        result_parts = []
        if output:
            result_parts.append(f"Output:\n{output[:5000]}")
        if error:
            result_parts.append(f"Errors:\n{error[:2000]}")
        if proc.returncode != 0:
            result_parts.append(f"Exit Code: {proc.returncode}")

        if not result_parts:
            return "Code executed successfully with no output."

        return "\n".join(result_parts)

    except Exception as e:
        logger.error(f"run_python_tool error: {e}")
        return f"Error running Python code: {e}"


@function_tool
async def system_info_tool() -> str:
    """Get comprehensive system information (OS, CPU, RAM, disk, uptime)."""
    try:
        lines = ["System Information", "=" * 50]

        # Basic platform info
        lines.append(f"OS: {platform.system()} {platform.release()} ({platform.version()})")
        lines.append(f"Processor: {platform.processor()}")
        lines.append(f"Architecture: {platform.machine()}")
        lines.append(f"Hostname: {platform.node()}")
        lines.append(f"Python: {platform.python_version()}")

        if PSUTIL_AVAILABLE:
            # CPU
            cpu_count = psutil.cpu_count(logical=True)
            cpu_physical = psutil.cpu_count(logical=False)
            cpu_percent = psutil.cpu_percent(interval=0.5)
            cpu_freq = psutil.cpu_freq()
            lines.append(f"\nCPU: {cpu_physical} cores / {cpu_count} threads")
            if cpu_freq:
                lines.append(f"CPU Freq: {cpu_freq.current:.0f} MHz (max {cpu_freq.max:.0f} MHz)")
            lines.append(f"CPU Usage: {cpu_percent}%")

            # RAM
            mem = psutil.virtual_memory()
            total_gb = round(mem.total / (1024 ** 3), 2)
            used_gb = round(mem.used / (1024 ** 3), 2)
            avail_gb = round(mem.available / (1024 ** 3), 2)
            lines.append(f"\nRAM: {used_gb} GB / {total_gb} GB ({mem.percent}% used)")
            lines.append(f"RAM Available: {avail_gb} GB")

            # Disk
            lines.append("\nDisk Partitions:")
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    total = round(usage.total / (1024 ** 3), 1)
                    used = round(usage.used / (1024 ** 3), 1)
                    free = round(usage.free / (1024 ** 3), 1)
                    lines.append(f"  {part.device} ({part.fstype}): {used} GB / {total} GB ({usage.percent}% used, {free} GB free)")
                except (PermissionError, OSError):
                    lines.append(f"  {part.device}: (access denied)")

            # Network
            net = psutil.net_io_counters()
            sent_mb = round(net.bytes_sent / (1024 ** 2), 1)
            recv_mb = round(net.bytes_recv / (1024 ** 2), 1)
            lines.append(f"\nNetwork: Sent {sent_mb} MB | Received {recv_mb} MB")

            # Uptime
            import time
            boot_time = psutil.boot_time()
            uptime_secs = time.time() - boot_time
            days = int(uptime_secs // 86400)
            hours = int((uptime_secs % 86400) // 3600)
            mins = int((uptime_secs % 3600) // 60)
            lines.append(f"Uptime: {days}d {hours}h {mins}m")

            # Processes
            lines.append(f"Running Processes: {len(psutil.pids())}")

        else:
            lines.append("\n(Install psutil for detailed CPU/RAM/Disk info: pip install psutil)")
            # Fallback via PowerShell
            try:
                proc = await asyncio.create_subprocess_exec(
                    "powershell", "-Command",
                    "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                ram = stdout.decode().strip()
                if ram:
                    lines.append(f"Total RAM: {float(ram):.1f} GB")
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"system_info_tool error: {e}")
        return f"Error getting system info: {e}"


@function_tool
async def environment_vars_tool(filter_key: str = "") -> str:
    """
    List or search environment variables.
    Args:
        filter_key: Optional filter string to search variable names (case-insensitive). Leave empty to list all.
    """
    try:
        env_vars = dict(os.environ)

        if filter_key.strip():
            key_lower = filter_key.strip().lower()
            env_vars = {k: v for k, v in env_vars.items() if key_lower in k.lower()}

        if not env_vars:
            if filter_key:
                return f"No environment variables matching '{filter_key}'."
            return "No environment variables found."

        # Sort by key
        sorted_vars = sorted(env_vars.items(), key=lambda x: x[0].lower())

        lines = [f"Environment Variables ({len(sorted_vars)} {'matching' if filter_key else 'total'}):", "-" * 50]
        for key, value in sorted_vars:
            display_val = _display_env_value(key, value)
            lines.append(f"  {key} = {display_val}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"environment_vars_tool error: {e}")
        return f"Error listing environment variables: {e}"
