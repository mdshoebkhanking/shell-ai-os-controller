#!/usr/bin/env python3
"""
Shell Scheduler Tools — Task scheduling using asyncio.
Schedule one-off delayed commands, recurring tasks, and time-based execution.
"""

import asyncio
import logging
import subprocess
import platform
import time
from datetime import datetime, timedelta
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_scheduler")

# Registry of active scheduled tasks
_scheduled_tasks: dict = {}


class ScheduledTask:
    """Represents a scheduled task with metadata."""

    def __init__(self, name: str, command: str, interval: int = 0, run_at: str = "", recurring: bool = False):
        self.name = name
        self.command = command
        self.interval = interval
        self.run_at = run_at
        self.recurring = recurring
        self.task: asyncio.Task = None
        self.created_at = datetime.now().isoformat()
        self.last_run = None
        self.run_count = 0
        self.status = "pending"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "command": self.command,
            "interval": self.interval,
            "run_at": self.run_at,
            "recurring": self.recurring,
            "created_at": self.created_at,
            "last_run": self.last_run,
            "run_count": self.run_count,
            "status": self.status,
        }


def _run_command(command: str) -> str:
    """Execute a shell command and return output."""
    try:
        if platform.system() == "Windows":
            args = ["cmd", "/c", command]
        else:
            import shlex
            args = shlex.split(command)
        result = subprocess.run(args, capture_output=True, text=True, timeout=60)
        return result.stdout.strip() or result.stderr.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "Command timed out (60s limit)"
    except Exception as e:
        return f"Command error: {e}"


async def _delayed_runner(task: ScheduledTask, delay: float):
    """Run a command after a delay."""
    try:
        task.status = "waiting"
        await asyncio.sleep(delay)
        task.status = "running"
        output = _run_command(task.command)
        task.last_run = datetime.now().isoformat()
        task.run_count += 1
        task.status = "completed"
        logger.info(f"Scheduled task '{task.name}' completed: {output[:200]}")
    except asyncio.CancelledError:
        task.status = "cancelled"
        logger.info(f"Scheduled task '{task.name}' was cancelled.")
    except Exception as e:
        task.status = f"error: {e}"
        logger.error(f"Scheduled task '{task.name}' failed: {e}")
    finally:
        if task.name in _scheduled_tasks and not task.recurring:
            del _scheduled_tasks[task.name]


async def _recurring_runner(task: ScheduledTask):
    """Run a command repeatedly at a fixed interval."""
    try:
        task.status = "active"
        while True:
            await asyncio.sleep(task.interval)
            task.status = "running"
            output = _run_command(task.command)
            task.last_run = datetime.now().isoformat()
            task.run_count += 1
            task.status = "active"
            logger.info(f"Recurring task '{task.name}' run #{task.run_count}: {output[:200]}")
    except asyncio.CancelledError:
        task.status = "cancelled"
        logger.info(f"Recurring task '{task.name}' cancelled after {task.run_count} runs.")
    except Exception as e:
        task.status = f"error: {e}"
        logger.error(f"Recurring task '{task.name}' failed: {e}")
    finally:
        if task.name in _scheduled_tasks:
            del _scheduled_tasks[task.name]


# ═══════════════════════════════════════════════════════════════
#  TOOL 1: SCHEDULE DELAYED TASK
# ═══════════════════════════════════════════════════════════════

@function_tool
async def schedule_task_tool(command: str, delay_seconds: int) -> str:
    """
    Schedule a command to run after a delay.
    Args:
        command: The shell command to execute.
        delay_seconds: Delay in seconds before execution (1-3600).
    """
    try:
        if delay_seconds < 1 or delay_seconds > 3600:
            return "Error: Delay must be between 1 and 3600 seconds."

        task_name = f"delayed_{int(time.time())}"
        task = ScheduledTask(name=task_name, command=command, interval=delay_seconds)
        task.task = asyncio.create_task(_delayed_runner(task, delay_seconds))
        _scheduled_tasks[task_name] = task

        run_time = (datetime.now() + timedelta(seconds=delay_seconds)).strftime("%H:%M:%S")
        return (
            f"Task scheduled: '{task_name}'\n"
            f"Command: {command}\n"
            f"Will run at: {run_time} (in {delay_seconds}s)"
        )
    except Exception as e:
        return f"Error scheduling task: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 2: SCHEDULE RECURRING TASK
# ═══════════════════════════════════════════════════════════════

@function_tool
async def schedule_recurring_tool(command: str, interval_seconds: int, task_name: str) -> str:
    """
    Schedule a command to run repeatedly at a fixed interval.
    Args:
        command: The shell command to execute.
        interval_seconds: Interval between runs in seconds (5-86400).
        task_name: Unique name for this recurring task.
    """
    try:
        if interval_seconds < 5 or interval_seconds > 86400:
            return "Error: Interval must be between 5 and 86400 seconds."

        if task_name in _scheduled_tasks:
            return f"Error: Task '{task_name}' already exists. Cancel it first or use a different name."

        task = ScheduledTask(name=task_name, command=command, interval=interval_seconds, recurring=True)
        task.task = asyncio.create_task(_recurring_runner(task))
        _scheduled_tasks[task_name] = task

        return (
            f"Recurring task created: '{task_name}'\n"
            f"Command: {command}\n"
            f"Interval: every {interval_seconds}s\n"
            f"First run at: {(datetime.now() + timedelta(seconds=interval_seconds)).strftime('%H:%M:%S')}"
        )
    except Exception as e:
        return f"Error creating recurring task: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 3: CANCEL SCHEDULED TASK
# ═══════════════════════════════════════════════════════════════

@function_tool
async def cancel_schedule_tool(task_name: str) -> str:
    """
    Cancel a scheduled or recurring task by name.
    Args:
        task_name: Name of the task to cancel.
    """
    try:
        if task_name not in _scheduled_tasks:
            available = list(_scheduled_tasks.keys())
            if not available:
                return "No active tasks found."
            return f"Task '{task_name}' not found. Active tasks: {', '.join(available)}"

        task = _scheduled_tasks[task_name]
        if task.task and not task.task.done():
            task.task.cancel()

        info = task.to_dict()
        del _scheduled_tasks[task_name]

        return (
            f"Task '{task_name}' cancelled.\n"
            f"Ran {info['run_count']} times. Last run: {info['last_run'] or 'never'}"
        )
    except Exception as e:
        return f"Error cancelling task: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 4: LIST SCHEDULED TASKS
# ═══════════════════════════════════════════════════════════════

@function_tool
async def list_schedules_tool() -> str:
    """
    List all active scheduled and recurring tasks.
    """
    try:
        if not _scheduled_tasks:
            return "No active scheduled tasks."

        lines = [f"Active Scheduled Tasks ({len(_scheduled_tasks)}):", "=" * 55]
        for name, task in _scheduled_tasks.items():
            info = task.to_dict()
            task_type = "Recurring" if info["recurring"] else "One-time"
            lines.append(
                f"\n  [{task_type}] {name}\n"
                f"    Command:  {info['command']}\n"
                f"    Status:   {info['status']}\n"
                f"    Interval: {info['interval']}s\n"
                f"    Runs:     {info['run_count']}\n"
                f"    Last run: {info['last_run'] or 'never'}\n"
                f"    Created:  {info['created_at']}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing tasks: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 5: SCHEDULE AT SPECIFIC TIME
# ═══════════════════════════════════════════════════════════════

@function_tool
async def schedule_at_time_tool(command: str, time_str: str) -> str:
    """
    Schedule a command to run at a specific time today (or tomorrow if time has passed).
    Args:
        command: The shell command to execute.
        time_str: Target time in HH:MM format (24-hour).
    """
    try:
        try:
            target_time = datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            return "Error: Time must be in HH:MM format (24-hour), e.g., '14:30'."

        now = datetime.now()
        target_dt = now.replace(hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0)

        if target_dt <= now:
            target_dt += timedelta(days=1)
            day_label = "tomorrow"
        else:
            day_label = "today"

        delay = (target_dt - now).total_seconds()
        task_name = f"at_{time_str.replace(':', '')}_{int(time.time())}"

        task = ScheduledTask(name=task_name, command=command, run_at=time_str)
        task.task = asyncio.create_task(_delayed_runner(task, delay))
        _scheduled_tasks[task_name] = task

        return (
            f"Task scheduled: '{task_name}'\n"
            f"Command: {command}\n"
            f"Will run at: {time_str} {day_label} (in {int(delay)}s / {int(delay / 60)} min)"
        )
    except Exception as e:
        return f"Error scheduling task: {e}"
