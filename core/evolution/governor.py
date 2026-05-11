from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.events import publish_event
from core.governance import ExecutionContract, GovernanceEngine


TRUTHY = {"1", "true", "yes", "on"}
SAFE_TARGET_SCOPES = {"new_tool", "tool_fix", "ui_fix", "docs", "tests", "refactor"}
CORE_TARGET_SCOPES = {"agent_patch", "core_patch", "runtime_patch"}
ALL_TARGET_SCOPES = SAFE_TARGET_SCOPES | CORE_TARGET_SCOPES

BLOCKED_CODE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("eval(", "dynamic eval is not allowed in generated evolution code"),
    ("exec(", "dynamic exec is not allowed in generated evolution code"),
    ("os.system(", "direct shell execution is not allowed in generated evolution code"),
    ("subprocess.Popen", "raw subprocess launch requires a dedicated reviewed tool"),
    ("subprocess.call", "raw subprocess call requires a dedicated reviewed tool"),
    ("pickle.load", "pickle deserialization is unsafe for generated tools"),
    ("socket.socket", "network listeners require a separate security review"),
)


@dataclass(frozen=True)
class PatchValidation:
    ok: bool
    filename: str
    functions: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "filename": self.filename,
            "functions": list(self.functions),
            "imports": list(self.imports),
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class EvolutionProposal:
    proposal_id: str
    request: str
    target_scope: str
    status: str
    created_at: float = field(default_factory=time.time)
    approved_by: str = ""
    approved_at: float = 0.0
    governance: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "request": self.request,
            "target_scope": self.target_scope,
            "status": self.status,
            "created_at": self.created_at,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "governance": dict(self.governance),
            "validation": dict(self.validation),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvolutionProposal":
        return cls(
            proposal_id=str(data.get("proposal_id") or ""),
            request=str(data.get("request") or ""),
            target_scope=str(data.get("target_scope") or "new_tool"),
            status=str(data.get("status") or "pending_approval"),
            created_at=float(data.get("created_at") or time.time()),
            approved_by=str(data.get("approved_by") or ""),
            approved_at=float(data.get("approved_at") or 0.0),
            governance=dict(data.get("governance") or {}),
            validation=dict(data.get("validation") or {}),
            notes=str(data.get("notes") or ""),
        )


class EvolutionGovernor:
    """Small, deterministic control plane for Shell evolution.

    It never mutates source files. Existing write/hotpatch tools remain the
    only code mutation path, and those are still protected by shell_safety_gate.
    """

    def __init__(self, path: str | Path = ".shell_runtime/evolution/proposals.json"):
        self.path = Path(path)
        self.audit_path = self.path.with_name("audit.jsonl")

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"proposals": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"proposals": []}
        except Exception:
            return {"proposals": []}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def _audit(self, event: str, payload: dict[str, Any]) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        row = {"ts": time.time(), "event": event, "payload": payload}
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    def _replace(self, proposal: EvolutionProposal) -> None:
        data = self._load()
        rows = [EvolutionProposal.from_dict(row) for row in data.get("proposals", [])]
        found = False
        out: list[dict[str, Any]] = []
        for row in rows:
            if row.proposal_id == proposal.proposal_id:
                out.append(proposal.to_dict())
                found = True
            else:
                out.append(row.to_dict())
        if not found:
            out.append(proposal.to_dict())
        self._write({"proposals": out[-200:]})

    def proposals(self, *, status: str | None = None) -> list[EvolutionProposal]:
        rows = [EvolutionProposal.from_dict(row) for row in self._load().get("proposals", [])]
        if status:
            rows = [row for row in rows if row.status == status]
        return rows

    def status(self) -> dict[str, Any]:
        rows = self.proposals()
        counts: dict[str, int] = {}
        for row in rows:
            counts[row.status] = counts.get(row.status, 0) + 1
        code_write = str(os.environ.get("SHELL_ALLOW_CODE_WRITE") or "").strip().lower() in TRUTHY
        agent_patch = str(os.environ.get("SHELL_ALLOW_AGENT_PATCH") or "").strip().lower() in TRUTHY
        production_mode = any(str(os.environ.get(key) or "").strip().lower() in TRUTHY for key in ("SHELL_PRODUCTION_MODE", "SHELL_PUBLIC_RELEASE"))
        status = {
            "proposal_counts": counts,
            "code_write_enabled": code_write,
            "agent_patch_enabled": agent_patch,
            "production_mode": production_mode,
            "auto_apply_enabled": False,
            "write_policy": "proposal -> validation -> explicit approval -> gated write tool -> tests -> rollback if needed",
        }
        publish_event("EVOLUTION_GOVERNOR_STATUS", status, source="core.evolution")
        return status

    def propose(self, request: str, *, target_scope: str = "new_tool", notes: str = "") -> EvolutionProposal:
        clean_request = " ".join(str(request or "").split())
        if not clean_request:
            raise ValueError("Evolution request is required")
        if len(clean_request) > 4000:
            raise ValueError("Evolution request is too large; summarize it first")
        if target_scope not in ALL_TARGET_SCOPES:
            raise ValueError(f"target_scope must be one of: {', '.join(sorted(ALL_TARGET_SCOPES))}")

        permissions = ["filesystem.write"]
        zone = "standard"
        if target_scope in CORE_TARGET_SCOPES:
            permissions.append("agent.patch")
            zone = "restricted"
        contract = ExecutionContract(
            action=f"evolution:{target_scope}",
            actor="shell",
            permissions=permissions,
            zone=zone,
            reversible=True,
            metadata={"request_preview": clean_request[:200]},
        )
        decision = GovernanceEngine().evaluate(contract)
        proposal = EvolutionProposal(
            proposal_id=uuid.uuid4().hex[:12],
            request=clean_request,
            target_scope=target_scope,
            status="pending_approval",
            governance=decision.to_dict(),
            notes=notes,
        )
        self._replace(proposal)
        self._audit("proposal_created", proposal.to_dict())
        publish_event("EVOLUTION_PROPOSAL_CREATED", proposal.to_dict(), source="core.evolution")
        return proposal

    def approve(self, proposal_id: str, *, approved_by: str = "user", note: str = "") -> EvolutionProposal:
        proposal_id = str(proposal_id or "").strip()
        if not proposal_id:
            raise ValueError("proposal_id is required")
        rows = self.proposals()
        for row in rows:
            if row.proposal_id == proposal_id:
                approved = EvolutionProposal(
                    proposal_id=row.proposal_id,
                    request=row.request,
                    target_scope=row.target_scope,
                    status="approved",
                    created_at=row.created_at,
                    approved_by=approved_by,
                    approved_at=time.time(),
                    governance=row.governance,
                    validation=row.validation,
                    notes=note or row.notes,
                )
                self._replace(approved)
                self._audit("proposal_approved", approved.to_dict())
                publish_event("EVOLUTION_PROPOSAL_APPROVED", approved.to_dict(), source="core.evolution")
                return approved
        raise KeyError(f"Evolution proposal not found: {proposal_id}")

    def record_validation(self, proposal_id: str, validation: PatchValidation) -> EvolutionProposal:
        rows = self.proposals()
        for row in rows:
            if row.proposal_id == proposal_id:
                updated = EvolutionProposal(
                    proposal_id=row.proposal_id,
                    request=row.request,
                    target_scope=row.target_scope,
                    status="validated" if validation.ok else "validation_failed",
                    created_at=row.created_at,
                    approved_by=row.approved_by,
                    approved_at=row.approved_at,
                    governance=row.governance,
                    validation=validation.to_dict(),
                    notes=row.notes,
                )
                self._replace(updated)
                self._audit("proposal_validated", updated.to_dict())
                publish_event("EVOLUTION_PROPOSAL_VALIDATED", updated.to_dict(), source="core.evolution")
                return updated
        raise KeyError(f"Evolution proposal not found: {proposal_id}")

    def validate_patch(self, filename: str, python_code: str) -> PatchValidation:
        filename = str(filename or "").strip()
        code = str(python_code or "")
        blockers: list[str] = []
        warnings: list[str] = []
        functions: list[str] = []
        imports: list[str] = []

        if not re.match(r"^shell_[a-z][a-z0-9_]{1,60}\.py$", filename):
            blockers.append("filename must match shell_<name>.py with lowercase letters, numbers, and underscores")
        if len(code.encode("utf-8", errors="ignore")) > 300_000:
            blockers.append("generated module is too large; split it before review")
        for pattern, reason in BLOCKED_CODE_PATTERNS:
            if pattern in code:
                blockers.append(reason)

        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            blockers.append(f"SyntaxError line {exc.lineno}: {exc.msg}")
            return PatchValidation(False, filename, blockers=blockers, warnings=warnings)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node.name)
            elif isinstance(node, ast.Import):
                imports.extend(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".", 1)[0])

        if "shell_safe_executor" not in imports:
            warnings.append("generated tool should import god_tier_tool from shell_safe_executor")
        if not any(name.endswith("_tool") for name in functions):
            warnings.append("no *_tool function detected")

        missing = sorted({name for name in imports if name and importlib.util.find_spec(name) is None})
        if missing:
            warnings.append(f"missing optional/import dependency at validation time: {', '.join(missing[:8])}")

        return PatchValidation(not blockers, filename, sorted(set(functions)), sorted(set(imports)), blockers, warnings)
