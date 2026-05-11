"""AI event bus facade.

This package provides domain event names while reusing the Phase 1
observability bus. Runtime components should publish domain events here instead
of importing UI or hub code directly.
"""

from .bus import AIEventType, publish_event, replay_events, subscribe

__all__ = ["AIEventType", "publish_event", "replay_events", "subscribe"]

