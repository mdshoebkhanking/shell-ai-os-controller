from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event
from core.user_model import UserModel


@dataclass(frozen=True)
class PersonalizationSuggestion:
    key: str
    value: Any
    reason: str
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "value": self.value, "reason": self.reason, "confidence": self.confidence}


class PersonalizationEngine:
    def __init__(self, model: UserModel | None = None):
        self.model = model or UserModel()

    def set_preference(self, key: str, value: Any) -> None:
        self.model.set_preference(key, value)
        publish_event(AIEventType.PERSONALIZATION_UPDATED, {"key": key, "value": value}, source="core.personalization")

    def suggest(self) -> list[PersonalizationSuggestion]:
        data = self.model.export()
        tool_counts = data.get("tool_counts") or {}
        suggestions: list[PersonalizationSuggestion] = []
        if tool_counts:
            favorite = max(tool_counts.items(), key=lambda item: item[1])[0]
            suggestions.append(PersonalizationSuggestion("favorite_tool", favorite, "most used tool", 0.7))
        if data.get("preferences", {}).get("voice.auto_play") is False:
            suggestions.append(PersonalizationSuggestion("chat.reply_mode", "text_first", "voice autoplay is disabled", 0.8))
        publish_event(AIEventType.PERSONALIZATION_UPDATED, {"suggestions": [s.to_dict() for s in suggestions]}, source="core.personalization")
        return suggestions

