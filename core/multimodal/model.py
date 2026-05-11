from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.events import AIEventType, publish_event


class ModalType(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    SCREENSHOT = "screenshot"
    DESKTOP_UI = "desktop_ui"
    DOCUMENT = "document"
    BROWSER = "browser"
    TERMINAL = "terminal"
    PDF = "pdf"
    OCR = "ocr"
    IMAGE = "image"
    VIDEO_FRAME = "video_frame"
    AUDIO = "audio"


@dataclass(frozen=True)
class ModalObservation:
    observation_id: str
    modal_type: ModalType
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "modal_type": self.modal_type.value,
            "content": self.content,
            "metadata": dict(self.metadata),
            "confidence": self.confidence,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class UnifiedContextModel:
    observations: list[ModalObservation]
    links: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    route_hints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "observations": [obs.to_dict() for obs in self.observations],
            "links": [dict(link) for link in self.links],
            "summary": self.summary,
            "route_hints": list(self.route_hints),
        }


class MultimodalContextEngine:
    def __init__(self):
        self._observations: list[ModalObservation] = []
        self._links: list[dict[str, Any]] = []

    def add_observation(
        self,
        modal_type: ModalType | str,
        content: str = "",
        *,
        metadata: dict[str, Any] | None = None,
        confidence: float = 0.5,
    ) -> ModalObservation:
        kind = modal_type if isinstance(modal_type, ModalType) else ModalType(str(modal_type))
        obs = ModalObservation(
            observation_id=uuid.uuid4().hex,
            modal_type=kind,
            content=str(content or ""),
            metadata=dict(metadata or {}),
            confidence=max(0.0, min(1.0, float(confidence))),
        )
        self._observations.append(obs)
        publish_event(AIEventType.MULTIMODAL_CONTEXT_UPDATED, obs.to_dict(), source="core.multimodal")
        return obs

    def link(self, source_id: str, target_id: str, relation: str, *, confidence: float = 0.5) -> dict[str, Any]:
        link = {
            "source_id": source_id,
            "target_id": target_id,
            "relation": relation,
            "confidence": max(0.0, min(1.0, float(confidence))),
        }
        self._links.append(link)
        publish_event(AIEventType.MULTIMODAL_CONTEXT_UPDATED, {"link": link}, source="core.multimodal")
        return link

    def build(self, *, limit: int = 20) -> UnifiedContextModel:
        observations = self._observations[-max(1, int(limit)):]
        route_hints: list[str] = []
        for obs in observations:
            text = f"{obs.modal_type.value} {obs.content} {obs.metadata}".lower()
            if obs.modal_type in {ModalType.SCREENSHOT, ModalType.DESKTOP_UI, ModalType.OCR}:
                route_hints.append("vision")
            if "error" in text or "traceback" in text:
                route_hints.append("debug")
            if obs.modal_type in {ModalType.TERMINAL, ModalType.BROWSER}:
                route_hints.append(obs.modal_type.value)
        seen: set[str] = set()
        route_hints = [hint for hint in route_hints if not (hint in seen or seen.add(hint))]
        summary = "; ".join(f"{obs.modal_type.value}:{obs.content[:80]}" for obs in observations if obs.content)
        model = UnifiedContextModel(observations, list(self._links), summary[:1200], route_hints)
        publish_event(AIEventType.MULTIMODAL_CONTEXT_UPDATED, {"model": model.to_dict()}, source="core.multimodal")
        return model

