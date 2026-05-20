from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, List, Optional

from shellai.config import ShellAIConfig
from shellai.observability import RequestTrace
from shellai.safety import CommandRisk, RiskLevel, ShellRiskPolicy


POLICY_FILE_NAME = "policy.json"
AUDIT_FILE_NAME = "audit.jsonl"


DEFAULT_POLICY = {
    "version": 1,
    "mode": "default",
    "allowed_patterns": [],
    "ask_patterns": [],
    "blocked_patterns": [],
    "admin": {
        "allowed_patterns": [],
        "ask_patterns": [],
        "blocked_patterns": [],
    },
}


def policy_path(config: Optional[ShellAIConfig] = None, path: Optional[str] = None) -> Path:
    if path:
        return Path(path).expanduser()
    active_config = config or ShellAIConfig.load()
    return active_config.paths.home_dir / POLICY_FILE_NAME


def audit_log_path(config: Optional[ShellAIConfig] = None) -> Path:
    active_config = config or ShellAIConfig.load()
    return active_config.paths.data_dir / AUDIT_FILE_NAME


def load_policy(
    config: Optional[ShellAIConfig] = None,
    path: Optional[str] = None,
    create: bool = False,
) -> dict[str, Any]:
    active_config = config or ShellAIConfig.load()
    target = policy_path(active_config, path)
    if create and not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(DEFAULT_POLICY, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not target.exists():
        policy = dict(DEFAULT_POLICY)
        policy["_path"] = str(target)
        policy["_exists"] = False
        return policy
    loaded = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Policy file must contain a JSON object: {target}")
    policy = json.loads(json.dumps(DEFAULT_POLICY))
    policy.update(loaded)
    if isinstance(loaded.get("admin"), dict):
        admin = dict(DEFAULT_POLICY["admin"])
        admin.update(loaded.get("admin") or {})
        policy["admin"] = admin
    policy["_path"] = str(target)
    policy["_exists"] = True
    return policy


def _first_match(command: str, patterns: List[str]) -> str:
    for pattern in patterns:
        if re.search(str(pattern), command, re.IGNORECASE):
            return str(pattern)
    return ""


def _risk(command: str, level: RiskLevel, reason: str, pattern: str = "", metadata: Optional[dict[str, Any]] = None) -> CommandRisk:
    return CommandRisk(command, level, reason, pattern, dict(metadata or {}))


def evaluate_command(
    command: str,
    *,
    config: Optional[ShellAIConfig] = None,
    policy: Optional[dict[str, Any]] = None,
    trace: Optional[RequestTrace] = None,
) -> CommandRisk:
    active_config = config or ShellAIConfig.load()
    loaded_policy = policy or load_policy(active_config)
    clean = str(command or "").strip()
    mode = str(loaded_policy.get("mode") or "default").strip().lower()
    if mode not in {"default", "admin"}:
        mode = "default"

    base = ShellRiskPolicy(active_config.risk_policy).classify(clean)
    metadata = {"policy_mode": mode, "policy_path": loaded_policy.get("_path", "")}

    pattern = _first_match(clean, [str(item) for item in loaded_policy.get("blocked_patterns") or []])
    if pattern:
        risk = _risk(clean, RiskLevel.BLOCK, "blocked by central policy override", pattern, metadata)
        _trace_policy(trace, risk)
        return risk

    if mode == "admin":
        admin = dict(loaded_policy.get("admin") or {})
        pattern = _first_match(clean, [str(item) for item in admin.get("blocked_patterns") or []])
        if pattern:
            risk = _risk(clean, RiskLevel.BLOCK, "blocked by admin policy override", pattern, metadata)
            _trace_policy(trace, risk)
            return risk
        pattern = _first_match(clean, [str(item) for item in admin.get("allowed_patterns") or []])
        if pattern and base.level is not RiskLevel.BLOCK:
            risk = _risk(clean, RiskLevel.SAFE, "allowed by admin policy override", pattern, metadata)
            _trace_policy(trace, risk)
            return risk
        pattern = _first_match(clean, [str(item) for item in admin.get("ask_patterns") or []])
        if pattern and base.level is not RiskLevel.BLOCK:
            risk = _risk(clean, RiskLevel.ASK, "requires confirmation by admin policy override", pattern, metadata)
            _trace_policy(trace, risk)
            return risk

    pattern = _first_match(clean, [str(item) for item in loaded_policy.get("ask_patterns") or []])
    if pattern and base.level is not RiskLevel.BLOCK:
        risk = _risk(clean, RiskLevel.ASK, "requires confirmation by central policy override", pattern, metadata)
        _trace_policy(trace, risk)
        return risk

    pattern = _first_match(clean, [str(item) for item in loaded_policy.get("allowed_patterns") or []])
    if pattern and base.level is not RiskLevel.BLOCK:
        risk = _risk(clean, RiskLevel.SAFE, "allowed by central policy override", pattern, metadata)
        _trace_policy(trace, risk)
        return risk

    merged_metadata = dict(base.metadata)
    merged_metadata.update(metadata)
    risk = CommandRisk(base.command, base.level, base.reason, base.matched_pattern, merged_metadata)
    _trace_policy(trace, risk)
    return risk


def _trace_policy(trace: Optional[RequestTrace], risk: CommandRisk) -> None:
    if trace is not None:
        trace.add_step("Policy", "classified", risk.reason, risk.to_dict())


def record_audit(
    config: ShellAIConfig,
    risk: CommandRisk,
    *,
    source: str = "SafetyAgent",
    trace: Optional[RequestTrace] = None,
) -> dict[str, Any]:
    config.paths.ensure_runtime_dirs()
    payload = {
        "timestamp": time.time(),
        "source": source,
        "trace_id": trace.request_id if trace is not None else "",
        "command": risk.command,
        "level": risk.level.value,
        "reason": risk.reason,
        "matched_pattern": risk.matched_pattern,
        "metadata": dict(risk.metadata),
    }
    with audit_log_path(config).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    if trace is not None:
        trace.add_step("AuditLog", "ok", "recorded safety decision", {"level": risk.level.value})
    return payload


def read_audit_log(config: Optional[ShellAIConfig] = None, *, limit: int = 100) -> List[dict[str, Any]]:
    active_config = config or ShellAIConfig.load()
    path = audit_log_path(active_config)
    if not path.exists():
        return []
    rows: List[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    rows = rows[-max(1, int(limit)):]
    rows.reverse()
    return rows


def policy_diagnostics(config: Optional[ShellAIConfig] = None) -> dict[str, Any]:
    active_config = config or ShellAIConfig.load()
    policy = load_policy(active_config)
    return {
        "policy_file": policy.get("_path"),
        "policy_exists": bool(policy.get("_exists")),
        "mode": str(policy.get("mode") or "default"),
        "audit_log": str(audit_log_path(active_config)),
    }


__all__ = [
    "AUDIT_FILE_NAME",
    "DEFAULT_POLICY",
    "POLICY_FILE_NAME",
    "audit_log_path",
    "evaluate_command",
    "load_policy",
    "policy_diagnostics",
    "policy_path",
    "read_audit_log",
    "record_audit",
]
