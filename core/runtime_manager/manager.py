from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.events import AIEventType, publish_event
from core.runtime import RuntimeMonitor, RuntimeSnapshot


class RuntimeKind(str, Enum):
    LLM = "llm"
    EMBEDDING = "embedding"
    TTS = "tts"
    STT = "stt"
    OCR = "ocr"
    BROWSER = "browser"
    AUTOMATION = "automation"


class RuntimeState(str, Enum):
    READY = "READY"
    COLD = "COLD"
    UNAVAILABLE = "UNAVAILABLE"
    DEGRADED = "DEGRADED"


@dataclass(frozen=True)
class RuntimeDescriptor:
    runtime_id: str
    kind: RuntimeKind
    provider: str
    local: bool = False
    cost_score: float = 0.5
    speed_score: float = 0.5
    memory_score: float = 0.5
    capability_tags: list[str] = field(default_factory=list)
    state: RuntimeState = RuntimeState.COLD
    last_health: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "kind": self.kind.value,
            "provider": self.provider,
            "local": self.local,
            "cost_score": self.cost_score,
            "speed_score": self.speed_score,
            "memory_score": self.memory_score,
            "capability_tags": list(self.capability_tags),
            "state": self.state.value,
            "last_health": self.last_health,
        }


class RuntimeManager:
    def __init__(self):
        self._runtimes: dict[str, RuntimeDescriptor] = {}

    def register(self, runtime: RuntimeDescriptor) -> None:
        self._runtimes[runtime.runtime_id] = runtime

    def defaults(self) -> None:
        if self._runtimes:
            return
        self.register(RuntimeDescriptor("local-light-llm", RuntimeKind.LLM, "local", True, 0.1, 0.7, 0.2, ["offline", "general"], RuntimeState.READY, time.time()))
        self.register(RuntimeDescriptor("cloud-reasoning", RuntimeKind.LLM, "cloud", False, 0.9, 0.5, 0.7, ["reasoning", "coding"], RuntimeState.READY, time.time()))
        self.register(RuntimeDescriptor("local-ocr", RuntimeKind.OCR, "tesseract", True, 0.1, 0.6, 0.2, ["ocr"], RuntimeState.COLD, 0.0))

    def select(
        self,
        kind: RuntimeKind | str,
        *,
        task_type: str = "general",
        offline: bool = False,
        snapshot: RuntimeSnapshot | None = None,
    ) -> RuntimeDescriptor | None:
        self.defaults()
        kind_enum = kind if isinstance(kind, RuntimeKind) else RuntimeKind(str(kind))
        snap = snapshot or RuntimeMonitor().snapshot()
        policy = RuntimeMonitor().policy(snap)
        candidates = [
            rt for rt in self._runtimes.values()
            if rt.kind == kind_enum and rt.state in {RuntimeState.READY, RuntimeState.COLD, RuntimeState.DEGRADED}
        ]
        if offline:
            candidates = [rt for rt in candidates if rt.local]
        if not policy.allow_heavy_tasks:
            candidates = [rt for rt in candidates if rt.memory_score <= 0.5 or rt.local]
        if task_type:
            tagged = [rt for rt in candidates if task_type in rt.capability_tags]
            if tagged:
                candidates = tagged
        if not candidates:
            publish_event(AIEventType.RUNTIME_FAILED, {"kind": kind_enum.value, "task_type": task_type}, source="core.runtime_manager")
            return None
        candidates.sort(key=lambda rt: (rt.cost_score + rt.memory_score - rt.speed_score, not rt.local))
        selected = candidates[0]
        publish_event(AIEventType.RUNTIME_SELECTED, selected.to_dict(), source="core.runtime_manager")
        return selected

    def mark_health(self, runtime_id: str, state: RuntimeState | str) -> RuntimeDescriptor | None:
        rt = self._runtimes.get(runtime_id)
        if not rt:
            return None
        new_state = state if isinstance(state, RuntimeState) else RuntimeState(str(state))
        updated = RuntimeDescriptor(
            runtime_id=rt.runtime_id,
            kind=rt.kind,
            provider=rt.provider,
            local=rt.local,
            cost_score=rt.cost_score,
            speed_score=rt.speed_score,
            memory_score=rt.memory_score,
            capability_tags=list(rt.capability_tags),
            state=new_state,
            last_health=time.time(),
        )
        self._runtimes[runtime_id] = updated
        return updated

    def list(self) -> list[dict[str, Any]]:
        self.defaults()
        return [rt.to_dict() for rt in self._runtimes.values()]

