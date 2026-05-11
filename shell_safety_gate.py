"""
shell_safety_gate.py — explicit permission checks for dangerous operations
===========================================================================

The Evolution, Sentinel, and Self-Heal modules can write LLM-generated
Python source to disk and even mutate agent.py. When the Gemini response
is wrong or adversarially manipulated, this becomes a full arbitrary-code-
execution path into the running Shell instance.

These operations are now disabled by default and require an explicit
opt-in through environment variables. Every write is logged to
`.shell_safety_audit.log` next to agent.py.

Env flags
---------
SHELL_ALLOW_CODE_WRITE=1   Permit creating/overwriting `shell_*.py` files
                           from tools like `create_capability_tool`.
SHELL_ALLOW_AGENT_PATCH=1  Additionally permit mutating `agent.py` or other
                           core files (sentinel auto-heal, hotpatch).
                           Implies SHELL_ALLOW_CODE_WRITE.

Helpers
-------
check_code_write(origin)   -> (ok: bool, reason: str)
check_agent_patch(origin)  -> (ok: bool, reason: str)
audit_write(origin, path)  -> appends an entry to the audit log
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("shell_safety_gate")

AUDIT_LOG = Path(__file__).parent / ".shell_safety_audit.log"

_DENY_MESSAGE_CODE_WRITE = (
    "BLOCKED: Writing LLM-generated Python to disk is disabled by default.\n"
    "Reason: Gemini output is not guaranteed safe; accidental or adversarial\n"
    "prompts could install a backdoor. To enable this for a trusted session,\n"
    "set SHELL_ALLOW_CODE_WRITE=1 in .env and restart. Review the generated\n"
    "code manually before opting in."
)

_DENY_MESSAGE_AGENT_PATCH = (
    "BLOCKED: Modifying agent.py or other core files is disabled by default.\n"
    "Reason: A bad LLM patch can brick the whole agent. Set\n"
    "SHELL_ALLOW_AGENT_PATCH=1 (implies SHELL_ALLOW_CODE_WRITE=1) only for\n"
    "an isolated dev session, ideally after you have committed your current\n"
    "working tree so rollback is easy."
)


def _truthy(value: str | None) -> bool:
    return bool(value) and str(value).strip().lower() in ("1", "true", "yes", "on")


def code_write_allowed() -> bool:
    return _truthy(os.environ.get("SHELL_ALLOW_CODE_WRITE")) or agent_patch_allowed()


def agent_patch_allowed() -> bool:
    return _truthy(os.environ.get("SHELL_ALLOW_AGENT_PATCH"))


def check_code_write(origin: str = "unknown") -> tuple[bool, str]:
    """Gate for creating or overwriting `shell_*.py` files from LLM output."""
    if code_write_allowed():
        logger.info("Code-write permitted for %s.", origin)
        return True, "permitted"
    logger.warning("Code-write blocked for %s (SHELL_ALLOW_CODE_WRITE not set).", origin)
    return False, _DENY_MESSAGE_CODE_WRITE


def check_agent_patch(origin: str = "unknown") -> tuple[bool, str]:
    """Stricter gate for patching agent.py or other core modules."""
    if agent_patch_allowed():
        logger.info("Agent-patch permitted for %s.", origin)
        return True, "permitted"
    logger.warning("Agent-patch blocked for %s (SHELL_ALLOW_AGENT_PATCH not set).", origin)
    return False, _DENY_MESSAGE_AGENT_PATCH


def audit_write(origin: str, path: str, note: str = "") -> None:
    """Append a single audit record for any permitted write. Non-blocking."""
    try:
        stamp = datetime.now().isoformat(timespec="seconds")
        line = f"[{stamp}] origin={origin} path={path} note={note}\n"
        with AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        logger.debug("Audit write failed for %s: %s", path, e)


__all__ = [
    "code_write_allowed",
    "agent_patch_allowed",
    "check_code_write",
    "check_agent_patch",
    "audit_write",
]
