from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.events import AIEventType, publish_event


class UIElementType(str, Enum):
    BUTTON = "button"
    MENU = "menu"
    DIALOG = "dialog"
    WINDOW = "window"
    NOTIFICATION = "notification"
    CHART = "chart"
    FORM = "form"
    TEXT = "text"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class UIElement:
    label: str
    element_type: UIElementType = UIElementType.UNKNOWN
    bounds: tuple[int, int, int, int] | None = None
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "element_type": self.element_type.value,
            "bounds": list(self.bounds) if self.bounds else None,
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ScreenState:
    screenshot_id: str
    elements: list[UIElement]
    ocr_text: str = ""
    active_window: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "screenshot_id": self.screenshot_id,
            "elements": [el.to_dict() for el in self.elements],
            "ocr_text": self.ocr_text,
            "active_window": self.active_window,
            "created_at": self.created_at,
        }


class VisionOperatingLayer:
    KEYWORDS = {
        UIElementType.BUTTON: ("button", "ok", "cancel", "submit", "save", "start", "stop"),
        UIElementType.MENU: ("menu", "file", "edit", "view", "settings"),
        UIElementType.DIALOG: ("dialog", "error", "warning", "confirm"),
        UIElementType.NOTIFICATION: ("notification", "notification", "toast", "alert"),
        UIElementType.CHART: ("chart", "graph", "axis", "series"),
        UIElementType.FORM: ("form", "input", "field", "password", "email"),
    }

    def parse(
        self,
        *,
        screenshot_id: str,
        ocr_text: str = "",
        elements: list[dict[str, Any]] | None = None,
        active_window: str = "",
    ) -> ScreenState:
        parsed = [self._element_from(row) for row in elements or []]
        for line in [part.strip() for part in str(ocr_text or "").splitlines() if part.strip()]:
            kind = self._infer_type(line)
            if kind != UIElementType.TEXT:
                parsed.append(UIElement(line[:80], kind, confidence=0.55, metadata={"source": "ocr"}))
        state = ScreenState(screenshot_id, parsed, str(ocr_text or ""), active_window)
        publish_event(AIEventType.VISION_SCREEN_PARSED, state.to_dict(), source="core.vision")
        return state

    def navigation_preview(self, state: ScreenState, goal: str) -> dict[str, Any]:
        goal_text = str(goal or "").lower()
        matches = [el for el in state.elements if el.label.lower() and el.label.lower() in goal_text]
        if not matches:
            matches = [el for el in state.elements if any(token in el.label.lower() for token in goal_text.split())]
        return {
            "status": "preview",
            "requires_confirmation": True,
            "reason": "visual automation is preview-only until the user approves",
            "matches": [el.to_dict() for el in matches[:5]],
        }

    def _element_from(self, row: dict[str, Any]) -> UIElement:
        kind = row.get("element_type") or row.get("type") or self._infer_type(str(row.get("label") or "")).value
        try:
            element_type = UIElementType(str(kind))
        except ValueError:
            element_type = UIElementType.UNKNOWN
        bounds = row.get("bounds")
        return UIElement(
            label=str(row.get("label") or ""),
            element_type=element_type,
            bounds=tuple(bounds) if isinstance(bounds, (list, tuple)) and len(bounds) == 4 else None,
            confidence=float(row.get("confidence", 0.5)),
            metadata=dict(row.get("metadata") or {}),
        )

    def _infer_type(self, text: str) -> UIElementType:
        lower = text.lower()
        for kind, keywords in self.KEYWORDS.items():
            if any(keyword in lower for keyword in keywords):
                return kind
        return UIElementType.TEXT

