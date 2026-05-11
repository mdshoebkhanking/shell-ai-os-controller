from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class WorkflowPattern:
    pattern_id: str
    name: str
    sequence: list[str] = field(default_factory=list)
    occurrences: int = 1
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "sequence": list(self.sequence),
            "occurrences": self.occurrences,
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
        }


class WorkflowIntelligenceEngine:
    def __init__(self):
        self._patterns: dict[str, WorkflowPattern] = {}

    def record_sequence(self, name: str, sequence: list[str], *, metadata: dict[str, Any] | None = None) -> WorkflowPattern:
        key = " > ".join(sequence)
        existing = self._patterns.get(key)
        if existing:
            pattern = WorkflowPattern(existing.pattern_id, existing.name, list(existing.sequence), existing.occurrences + 1, min(1.0, existing.confidence + 0.1), {**existing.metadata, **dict(metadata or {})})
        else:
            pattern = WorkflowPattern(uuid.uuid4().hex, name, list(sequence), 1, 0.55, dict(metadata or {}))
        self._patterns[key] = pattern
        publish_event(AIEventType.WORKFLOW_INTELLIGENCE_UPDATED, pattern.to_dict(), source="core.workflow_intelligence")
        return pattern

    def predict_next(self, prefix: list[str]) -> dict[str, Any]:
        candidates = []
        for pattern in self._patterns.values():
            if pattern.sequence[:len(prefix)] == prefix and len(pattern.sequence) > len(prefix):
                candidates.append((pattern.confidence, pattern.sequence[len(prefix)], pattern))
        candidates.sort(key=lambda item: item[0], reverse=True)
        result = {"next": candidates[0][1] if candidates else "", "pattern": candidates[0][2].to_dict() if candidates else None}
        publish_event(AIEventType.WORKFLOW_INTELLIGENCE_UPDATED, {"prediction": result}, source="core.workflow_intelligence")
        return result

    def templates(self, *, min_confidence: float = 0.5) -> list[dict[str, Any]]:
        return [pattern.to_dict() for pattern in self._patterns.values() if pattern.confidence >= min_confidence]

