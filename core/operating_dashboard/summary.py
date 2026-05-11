from __future__ import annotations

from typing import Any


class OperatingDashboard:
    def snapshot(self) -> dict[str, Any]:
        from core.events import replay_events
        from core.memory import LocalMemoryStore
        from core.runtime_manager import RuntimeManager
        from core.streaming import EventStream

        events = replay_events(limit=50)
        return {
            "runtime_map": RuntimeManager().list(),
            "recent_events": events,
            "event_count": len(events),
            "memory_summary": LocalMemoryStore().summarize(limit=10),
            "timeline": [event.to_dict() for event in EventStream().current(limit=25)],
        }

