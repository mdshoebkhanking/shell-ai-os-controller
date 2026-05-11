"""Structured observability primitives for Shell runtime."""

from .events import DebugEvent, EventBus, emit_debug_event
from .tracing import ExecutionTrace, ExecutionTracer, TraceSpan

__all__ = [
    "DebugEvent",
    "EventBus",
    "ExecutionTrace",
    "ExecutionTracer",
    "TraceSpan",
    "emit_debug_event",
]

