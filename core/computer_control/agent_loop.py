from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.automation import TrustedAutomationLayer
from core.events import publish_event
from core.vision import VisionOperatingLayer


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _strip_quotes(text: str) -> str:
    return str(text or "").strip().strip("\"'` ")


def _json_to_elements(value: str | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, dict)]
    raw = str(value or "").strip()
    if not raw:
        return []
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("elements must be a JSON array")
    return [dict(row) for row in parsed if isinstance(row, dict)]


@dataclass(frozen=True)
class DesktopObservation:
    observation_id: str
    screenshot_id: str
    active_window: str = ""
    ocr_text: str = ""
    elements: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "screenshot_id": self.screenshot_id,
            "active_window": self.active_window,
            "ocr_text": self.ocr_text[:600],
            "elements": [dict(row) for row in self.elements],
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class DesktopAgentStep:
    step_id: str
    action: str
    target: str
    tool_id: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    risk: str = "ELEVATED"
    requires_confirmation: bool = True
    reversible: bool = False
    status: str = "proposed"
    verification: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "target": self.target,
            "tool_id": self.tool_id,
            "args": dict(self.args),
            "risk": self.risk,
            "requires_confirmation": self.requires_confirmation,
            "reversible": self.reversible,
            "status": self.status,
            "verification": dict(self.verification),
        }


@dataclass(frozen=True)
class DesktopAgentPlan:
    plan_id: str
    goal: str
    status: str
    observation: DesktopObservation
    steps: list[DesktopAgentStep]
    requires_confirmation: bool
    one_step_at_a_time: bool = True
    reasons: list[str] = field(default_factory=list)
    automation_preview: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "status": self.status,
            "observation": self.observation.to_dict(),
            "steps": [step.to_dict() for step in self.steps],
            "requires_confirmation": self.requires_confirmation,
            "one_step_at_a_time": self.one_step_at_a_time,
            "reasons": list(self.reasons),
            "automation_preview": dict(self.automation_preview),
            "created_at": self.created_at,
        }


class DesktopAgentLoop:
    """Observe-preview-confirm-execute-verify loop for desktop control.

    This class is intentionally not a free-running agent. It produces a bounded
    plan and can execute only one approved step at a time. The caller must
    provide fresh observations between steps for real visual verification.
    """

    def __init__(self, audit_path: str | Path = ".shell_runtime/automation_audit.jsonl"):
        self.automation = TrustedAutomationLayer(audit_path)
        self.vision = VisionOperatingLayer()

    def observe(
        self,
        *,
        screenshot_id: str = "",
        ocr_text: str = "",
        elements: str | list[dict[str, Any]] | None = None,
        active_window: str = "",
    ) -> DesktopObservation:
        parsed_elements = _json_to_elements(elements)
        state = self.vision.parse(
            screenshot_id=screenshot_id or f"manual-{uuid.uuid4().hex[:8]}",
            ocr_text=ocr_text,
            elements=parsed_elements,
            active_window=active_window,
        )
        return DesktopObservation(
            observation_id=uuid.uuid4().hex,
            screenshot_id=state.screenshot_id,
            active_window=state.active_window,
            ocr_text=state.ocr_text,
            elements=[element.to_dict() for element in state.elements],
        )

    def plan(
        self,
        goal: str,
        *,
        screenshot_id: str = "",
        ocr_text: str = "",
        elements: str | list[dict[str, Any]] | None = None,
        active_window: str = "",
    ) -> DesktopAgentPlan:
        cleaned_goal = _clean(goal)
        observation = self.observe(
            screenshot_id=screenshot_id,
            ocr_text=ocr_text,
            elements=elements,
            active_window=active_window,
        )
        steps, reasons = self._infer_steps(cleaned_goal, observation)
        preview_actions = [
            {
                "kind": "desktop.control" if step.action != "observe_screen" else "desktop.observe",
                "target": step.target,
                "params": {"tool_id": step.tool_id, **step.args},
                "reversible": step.reversible,
            }
            for step in steps
        ]
        automation_preview = self.automation.preview(
            f"Desktop Agent: {cleaned_goal or 'unlabeled goal'}",
            preview_actions,
        ).to_dict() if preview_actions else {}
        requires_confirmation = bool(automation_preview.get("requires_confirmation", bool(steps)))
        status = "ready_for_confirmation" if steps and all(step.tool_id for step in steps) else "needs_observation"
        if not cleaned_goal:
            status = "needs_goal"
            reasons.append("desktop goal is empty")
        plan = DesktopAgentPlan(
            plan_id=uuid.uuid4().hex,
            goal=cleaned_goal,
            status=status,
            observation=observation,
            steps=steps,
            requires_confirmation=requires_confirmation,
            reasons=reasons,
            automation_preview=automation_preview,
        )
        publish_event("DESKTOP_AGENT_PLAN_CREATED", plan.to_dict(), source="core.computer_control")
        return plan

    def execute_step(
        self,
        plan: DesktopAgentPlan | dict[str, Any] | str,
        *,
        step_id: str = "",
        approved: bool = False,
        dry_run: bool = True,
        verify_after: bool = False,
    ) -> dict[str, Any]:
        plan_dict = self._coerce_plan(plan)
        steps = [dict(row) for row in plan_dict.get("steps", []) if isinstance(row, dict)]
        selected = self._select_step(steps, step_id)
        if selected is None:
            return {"status": "blocked", "reason": "step not found", "plan_id": plan_dict.get("plan_id")}
        result = {
            "plan_id": plan_dict.get("plan_id"),
            "step": selected,
            "approved": bool(approved),
            "dry_run": bool(dry_run),
            "one_step_at_a_time": True,
        }
        if selected.get("requires_confirmation", True) and not approved:
            result.update({"status": "blocked", "reason": "explicit user approval required before desktop control"})
            publish_event("DESKTOP_AGENT_STEP_BLOCKED", result, source="core.computer_control")
            return result
        if dry_run:
            result.update({"status": "dry_run", "would_execute": self._tool_call_for_step(selected)})
            publish_event("DESKTOP_AGENT_STEP_DRY_RUN", result, source="core.computer_control")
            return result
        tool_id = str(selected.get("tool_id") or "")
        if not tool_id:
            result.update({"status": "blocked", "reason": "step has no executable tool; provide a fresh screen observation"})
            publish_event("DESKTOP_AGENT_STEP_BLOCKED", result, source="core.computer_control")
            return result
        from shell_tool_gateway import execute_tool_sync

        tool_result = execute_tool_sync(tool_id, selected.get("args") or {})
        result.update({"status": tool_result.get("status", "unknown"), "tool_result": tool_result})
        if verify_after:
            result["verification"] = {
                "status": "pending_observation",
                "required": True,
                "instruction": "Capture a fresh screenshot/OCR observation and compare it with the step verification target.",
                "expected": selected.get("verification", {}),
            }
        publish_event("DESKTOP_AGENT_STEP_EXECUTED", result, source="core.computer_control")
        return result

    def _infer_steps(self, goal: str, observation: DesktopObservation) -> tuple[list[DesktopAgentStep], list[str]]:
        lower = goal.lower()
        reasons: list[str] = []
        if not goal:
            return [], reasons
        if re.search(r"\b(take|capture|show)\s+(a\s+)?screenshot\b|\bscreenshot\b", lower):
            return [self._step("observe_screen", "current screen", "shell_screenshot:take_screenshot_tool", {"filename": "desktop_agent_observation"}, reversible=True)], reasons
        match = re.match(r"^(?:open|launch|start)\s+(?:app\s+)?(.+)$", goal, flags=re.I)
        if match and "url" not in lower and "http" not in lower:
            app = _strip_quotes(match.group(1))
            return [self._step("open_app", app, "shell_window_CTRL:open_app", {"app_title": app}, reversible=True)], reasons
        match = re.match(r"^(?:close|quit|stop|band)\s+(?:app\s+)?(.+)$", goal, flags=re.I)
        if match:
            app = _strip_quotes(match.group(1))
            return [self._step("close_app", app, "shell_window_CTRL:close_app", {"window_title": app})], reasons
        match = re.match(r"^(?:click|tap)\s+(?:at\s+)?(-?\d+)\s*,?\s+(-?\d+)$", goal, flags=re.I)
        if match:
            x, y = int(match.group(1)), int(match.group(2))
            return [self._step("click", f"{x},{y}", "shell_desktop_tools:desktop_click_tool", {"x": x, "y": y, "button": "left"})], reasons
        if re.match(r"^(?:click|tap)\s+.+$", goal, flags=re.I):
            target = re.sub(r"^(?:click|tap)\s+", "", goal, flags=re.I).strip()
            found = self._find_element(target, observation.elements)
            if found and found.get("bounds"):
                x, y = self._center(found["bounds"])
                return [self._step("click", str(found.get("label") or target), "shell_desktop_tools:desktop_click_tool", {"x": x, "y": y, "button": "left"})], reasons
            reasons.append("target element needs a fresh screen observation with bounds before clicking")
            return [self._step("click", target, "", {}, status="needs_target")], reasons
        match = re.match(r"^(?:type|write)\s+(.+)$", goal, flags=re.I | re.S)
        if match:
            text = _strip_quotes(match.group(1))
            return [self._step("type_text", "active focused field", "shell_desktop_tools:desktop_type_tool", {"text": text, "clear": False})], reasons
        match = re.match(r"^(?:press|hotkey|shortcut)\s+(.+)$", goal, flags=re.I | re.S)
        if match:
            keys = _strip_quotes(match.group(1))
            return [self._step("shortcut", keys, "shell_desktop_tools:desktop_shortcut_tool", {"keys": keys})], reasons
        reasons.append("desktop goal is not yet mapped to a safe deterministic action")
        return [self._step("observe_screen", "current screen", "shell_screenshot:take_screenshot_tool", {"filename": "desktop_agent_observation"}, reversible=True)], reasons

    def _step(
        self,
        action: str,
        target: str,
        tool_id: str,
        args: dict[str, Any],
        *,
        reversible: bool = False,
        status: str = "proposed",
    ) -> DesktopAgentStep:
        verification = {
            "required": True,
            "method": "fresh_screenshot_after_step",
            "expected_target": target,
            "instruction": "Compare the post-step screen state with the intended target before continuing.",
        }
        return DesktopAgentStep(
            step_id=uuid.uuid4().hex,
            action=action,
            target=target,
            tool_id=tool_id,
            args=dict(args),
            requires_confirmation=True,
            reversible=reversible,
            status=status,
            verification=verification,
        )

    @staticmethod
    def _find_element(target: str, elements: list[dict[str, Any]]) -> dict[str, Any] | None:
        target_lower = target.lower()
        for row in elements:
            label = str(row.get("label") or "").lower()
            if label and (label == target_lower or label in target_lower or target_lower in label):
                return row
        target_tokens = {token for token in re.findall(r"[a-z0-9]+", target_lower) if len(token) > 2}
        if not target_tokens:
            return None
        best: dict[str, Any] | None = None
        best_score = 0
        for row in elements:
            label_tokens = set(re.findall(r"[a-z0-9]+", str(row.get("label") or "").lower()))
            score = len(target_tokens & label_tokens)
            if score > best_score:
                best = row
                best_score = score
        return best if best_score else None

    @staticmethod
    def _center(bounds: Any) -> tuple[int, int]:
        if not isinstance(bounds, (list, tuple)) or len(bounds) != 4:
            return 0, 0
        x, y, width, height = [int(float(value)) for value in bounds]
        return int(x + width / 2), int(y + height / 2)

    @staticmethod
    def _coerce_plan(plan: DesktopAgentPlan | dict[str, Any] | str) -> dict[str, Any]:
        if isinstance(plan, DesktopAgentPlan):
            return plan.to_dict()
        if isinstance(plan, dict):
            return dict(plan)
        parsed = json.loads(str(plan or "{}"))
        if not isinstance(parsed, dict):
            raise ValueError("plan must be a JSON object")
        return parsed

    @staticmethod
    def _select_step(steps: list[dict[str, Any]], step_id: str) -> dict[str, Any] | None:
        if step_id:
            return next((step for step in steps if str(step.get("step_id") or "") == str(step_id)), None)
        return steps[0] if steps else None

    @staticmethod
    def _tool_call_for_step(step: dict[str, Any]) -> dict[str, Any]:
        return {"tool_id": step.get("tool_id"), "args": dict(step.get("args") or {})}
