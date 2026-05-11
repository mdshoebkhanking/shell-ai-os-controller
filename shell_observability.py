"""Shell AI observability module.

Provides structured, request-id-correlated logging for the Shell AI agent.
This module replaces naive ``logging.basicConfig`` calls scattered across
the codebase with a single, idempotent ``configure_logging`` entry point
and adds helpers for tool-call logging, event emission, and timing.

Design goals:
    * stdlib-only hard dependency (``structlog`` is optional).
    * Thread-safe and async-safe: correlation IDs propagate through
      ``contextvars`` so they cross ``asyncio`` boundaries cleanly.
    * No global mutable state beyond a ``ContextVar`` and an
      ``_initialized`` guard flag.
    * Idempotent configuration: repeat calls are a no-op (unless forced).

Public API is declared in ``__all__``.
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import logging.handlers
import threading
import time
import uuid
from contextvars import ContextVar
from typing import Any, Awaitable, Callable, Optional, TypeVar

# Optional structlog import -- used only if available and requested.
try:  # pragma: no cover - optional dependency
    import structlog  # type: ignore
    _HAS_STRUCTLOG = True
except Exception:  # pragma: no cover - optional dependency
    structlog = None  # type: ignore
    _HAS_STRUCTLOG = False


__all__ = [
    "request_id",
    "configure_logging",
    "current_request_id",
    "set_request_id",
    "timed",
    "timed_async",
    "log_tool_call",
    "record_event",
]


# ---------------------------------------------------------------------------
# Correlation ID -- async/thread safe via ContextVar
# ---------------------------------------------------------------------------

request_id: ContextVar[str] = ContextVar("request_id", default="")
"""ContextVar carrying the current request correlation id.

The default value is the empty string; call :func:`set_request_id` at the
start of each logical request to populate it. ``ContextVar`` values
propagate across ``await`` boundaries automatically, so async code sees
the correct id without explicit plumbing.
"""


# ---------------------------------------------------------------------------
# Idempotent configuration guard
# ---------------------------------------------------------------------------

_initialized: bool = False
_init_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


class _RequestIdFilter(logging.Filter):
    """Inject the current ``request_id`` ContextVar onto every record."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        record.request_id = request_id.get() or "-"
        return True


class _JsonFormatter(logging.Formatter):
    """Minimal stdlib-only JSON formatter.

    Emits one JSON object per log line with fixed keys plus any ``extra``
    attributes dict-merged under the ``extra`` field.
    """

    _RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname",
        "filename", "module", "exc_info", "exc_text", "stack_info",
        "lineno", "funcName", "created", "msecs", "relativeCreated",
        "thread", "threadName", "processName", "process", "message",
        "asctime", "request_id",
    }

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in self._RESERVED and not k.startswith("_")
        }
        if extras:
            payload["extra"] = extras
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        try:
            return json.dumps(payload, default=str, ensure_ascii=False)
        except Exception:
            # Last-resort fallback so logging never raises.
            return json.dumps({"level": record.levelname, "msg": str(record.getMessage())})


# ---------------------------------------------------------------------------
# Public configuration
# ---------------------------------------------------------------------------


def configure_logging(
    level: str = "INFO",
    *,
    json_format: bool = False,
    log_file: str = "shell_ai.log",
) -> None:
    """Configure root logging for the Shell AI agent.

    Idempotent: subsequent calls are no-ops. Replaces any prior
    ``logging.basicConfig`` setup with handlers that understand the
    ``request_id`` context variable.

    Args:
        level: Log level name (e.g. ``"DEBUG"``, ``"INFO"``). Case-insensitive.
        json_format: If True, emit one JSON object per log line. Otherwise
            use a human-readable text format.
        log_file: Path to the rotating log file. Pass an empty string to
            disable file logging (stream only).

    Returns:
        None.
    """
    global _initialized
    with _init_lock:
        if _initialized:
            return

        numeric_level = getattr(logging, str(level).upper(), logging.INFO)

        root = logging.getLogger()
        # Clear any handlers installed by a prior basicConfig() call.
        for handler in list(root.handlers):
            root.removeHandler(handler)
        root.setLevel(numeric_level)

        req_filter = _RequestIdFilter()

        if json_format:
            formatter: logging.Formatter = _JsonFormatter()
        else:
            formatter = logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

        # Always have a stream handler for console/stderr visibility.
        stream = logging.StreamHandler()
        stream.setLevel(numeric_level)
        stream.setFormatter(formatter)
        stream.addFilter(req_filter)
        root.addHandler(stream)

        # Rotating file handler -- only if a path was requested.
        if log_file:
            try:
                file_handler = logging.handlers.RotatingFileHandler(
                    log_file,
                    maxBytes=5 * 1024 * 1024,
                    backupCount=3,
                    encoding="utf-8",
                    delay=True,
                )
                file_handler.setLevel(numeric_level)
                file_handler.setFormatter(formatter)
                file_handler.addFilter(req_filter)
                root.addHandler(file_handler)
            except Exception as exc:  # pragma: no cover - best-effort
                root.warning("could not attach file handler %s: %s", log_file, exc)

        # Optional structlog bridge -- only if caller has it installed.
        if _HAS_STRUCTLOG and json_format:  # pragma: no cover - optional
            try:
                structlog.configure(
                    processors=[
                        structlog.contextvars.merge_contextvars,
                        structlog.processors.add_log_level,
                        structlog.processors.TimeStamper(fmt="iso"),
                        structlog.processors.JSONRenderer(),
                    ],
                    wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
                    cache_logger_on_first_use=True,
                )
            except Exception:
                pass

        _initialized = True


# ---------------------------------------------------------------------------
# Request-id helpers
# ---------------------------------------------------------------------------


def current_request_id() -> str:
    """Return the current request id from the ``ContextVar``.

    Returns the empty string if :func:`set_request_id` has not been called
    in the current context.
    """
    return request_id.get()


def set_request_id(value: Optional[str] = None) -> str:
    """Set the current request id; generate a UUID4 if ``value`` is None.

    Args:
        value: Explicit id to set, or ``None`` to auto-generate a UUID4.

    Returns:
        The id that was stored (either ``value`` or the new UUID4).
    """
    new_id = value if value is not None else uuid.uuid4().hex
    request_id.set(new_id)
    return new_id


# ---------------------------------------------------------------------------
# Timing decorators
# ---------------------------------------------------------------------------

F = TypeVar("F", bound=Callable[..., Any])
AF = TypeVar("AF", bound=Callable[..., Awaitable[Any]])


def timed(fn: F) -> F:
    """Decorator that logs sync function name + duration at DEBUG.

    Works on any callable. Emits a single line on every call with elapsed
    milliseconds, including the current request id via the filter.

    Args:
        fn: The synchronous callable to wrap.

    Returns:
        The wrapped callable with identical signature.
    """
    log = logging.getLogger(fn.__module__)

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            log.debug(
                "timed %s took %.2fms",
                fn.__qualname__,
                elapsed_ms,
                extra={"fn": fn.__qualname__, "duration_ms": elapsed_ms},
            )

    return wrapper  # type: ignore[return-value]


def timed_async(fn: AF) -> AF:
    """Decorator that logs async function name + duration at DEBUG.

    The wrapped coroutine function preserves its signature. A single DEBUG
    log line is emitted on completion (success or failure).

    Args:
        fn: The async callable to wrap. Must be a coroutine function.

    Returns:
        The wrapped coroutine function.
    """
    if not asyncio.iscoroutinefunction(fn):
        raise TypeError("timed_async requires an async function")

    log = logging.getLogger(fn.__module__)

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            return await fn(*args, **kwargs)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            log.debug(
                "timed_async %s took %.2fms",
                fn.__qualname__,
                elapsed_ms,
                extra={"fn": fn.__qualname__, "duration_ms": elapsed_ms},
            )

    return wrapper  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Structured-line helpers
# ---------------------------------------------------------------------------


_TOOL_LOGGER = logging.getLogger("shell_ai.tool")
_EVENT_LOGGER = logging.getLogger("shell_ai.event")


def _safe_json(obj: Any) -> str:
    """Serialize ``obj`` to a compact JSON string, falling back to ``repr``."""
    try:
        return json.dumps(obj, default=str, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        try:
            return json.dumps(repr(obj), ensure_ascii=False)
        except Exception:
            return '"<unserializable>"'


def log_tool_call(
    tool_name: str,
    args: Any,
    result: Any,
    duration_ms: float,
    request_id: Optional[str] = None,  # noqa: A002 - shadow OK; explicit override
) -> None:
    """Write a single structured log line describing a tool invocation.

    Args:
        tool_name: Name of the tool that was called.
        args: Arguments passed to the tool (must be JSON-serializable, or
            will fall back to ``repr``).
        result: Tool result (serialized the same way as ``args``).
        duration_ms: Wall-clock duration of the call in milliseconds.
        request_id: Explicit correlation id. If ``None``, the current
            ContextVar value is used.
    """
    rid = request_id if request_id is not None else current_request_id()
    payload = {
        "tool": tool_name,
        "args": args,
        "result": result,
        "duration_ms": round(float(duration_ms), 3),
        "request_id": rid or "-",
    }
    _TOOL_LOGGER.info("tool_call %s", _safe_json(payload), extra=payload)


def record_event(event_name: str, **fields: Any) -> None:
    """Emit a one-line event log suitable for grep/ingest.

    The line format is ``event <name> <json>`` where ``<json>`` is a
    compact JSON object containing the supplied fields plus ``request_id``.

    Args:
        event_name: Short machine-friendly event identifier (e.g. ``"agent_start"``).
        **fields: Arbitrary structured fields. Values should be
            JSON-serializable; non-serializable values fall back to
            ``repr``.
    """
    payload: dict[str, Any] = {"event": event_name, "request_id": current_request_id() or "-"}
    payload.update(fields)
    _EVENT_LOGGER.info("event %s %s", event_name, _safe_json(payload), extra=payload)
