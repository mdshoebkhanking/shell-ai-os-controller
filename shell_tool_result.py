"""Shell tool result types.

Unified, structured return types for tools invoked by the Shell agent (LiveKit
/ Gemini bridge). This module is intentionally stdlib-only so it can be
imported from any layer of the project without pulling in third-party deps.

The design goals are:

* ``ToolResult`` is the single shape every tool should return, replacing the
  ad-hoc ``str`` / ``dict`` / ``Exception`` mix currently in circulation.
* ``ToolError`` carries both a machine-readable ``code`` (for routing and
  retry logic) and a ``user_message`` (for display to the end user via
  voice / chat), keeping them cleanly separated from the internal ``message``
  used for logs.
* ``to_agent_string`` provides a backward-compatible serialization to the
  plain string shape that LiveKit / Gemini currently consume, so this type
  can be rolled out incrementally without breaking existing call sites.
"""

from __future__ import annotations

import asyncio
import errno
import socket
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "ToolError",
    "ToolResult",
    "wrap_exception",
    "to_agent_string",
]


@dataclass(frozen=True)
class ToolError:
    """Structured error information for a failed tool invocation.

    Attributes:
        code: Stable, machine-readable error identifier (e.g. ``"NOT_FOUND"``,
            ``"TIMEOUT"``). Used for routing, retry logic, and metrics.
        message: Developer-facing description of the failure. Safe to log
            verbatim; may include internal paths, stack hints, etc.
        user_message: End-user-facing description, suitable for speaking
            aloud via TTS or displaying in the chat surface. Should avoid
            internal jargon and PII.
        retryable: Whether the caller is allowed to retry the tool call
            without changing its arguments. Defaults to ``False`` because
            non-idempotent tools should opt in explicitly.
    """

    code: str
    message: str
    user_message: str
    retryable: bool = False


@dataclass(frozen=True)
class ToolResult:
    """Unified result envelope for every Shell tool invocation.

    Attributes:
        ok: ``True`` on success, ``False`` on failure. When ``False``,
            ``error`` should be populated.
        data: Arbitrary success payload. Tool-specific; callers should
            treat as opaque unless they know the concrete tool.
        error: Structured error details when ``ok`` is ``False``.
        latency_ms: Wall-clock duration of the tool call, in milliseconds.
            Used for observability and adaptive timeouts.
        side_effects: Human-readable list of side effects performed
            (e.g. ``["wrote file X", "sent email to Y"]``). Surfaced to
            the agent so it can summarize what it did.
        tool_name: Name of the tool that produced this result. Helpful
            when results flow through generic pipelines or queues.
    """

    ok: bool
    data: Any = None
    error: ToolError | None = None
    latency_ms: float = 0.0
    side_effects: list[str] = field(default_factory=list)
    tool_name: str = ""

    @staticmethod
    def success(
        data: Any = None,
        tool_name: str = "",
        latency_ms: float = 0.0,
        side_effects: list[str] | None = None,
    ) -> "ToolResult":
        """Build a successful ``ToolResult``.

        Args:
            data: Payload returned by the tool.
            tool_name: Originating tool's name. Optional but recommended.
            latency_ms: Wall-clock duration of the call.
            side_effects: Optional list of human-readable side effects.
                ``None`` is normalized to an empty list.

        Returns:
            A frozen ``ToolResult`` with ``ok=True``.
        """
        return ToolResult(
            ok=True,
            data=data,
            error=None,
            latency_ms=latency_ms,
            side_effects=list(side_effects) if side_effects else [],
            tool_name=tool_name,
        )

    @staticmethod
    def failure(
        code: str,
        message: str,
        user_message: str | None = None,
        retryable: bool = False,
        tool_name: str = "",
        latency_ms: float = 0.0,
    ) -> "ToolResult":
        """Build a failed ``ToolResult``.

        Args:
            code: Stable error identifier (see ``ToolError.code``).
            message: Developer-facing description of the failure.
            user_message: End-user-facing description. Defaults to
                ``message`` when omitted.
            retryable: Whether the caller may retry unchanged.
            tool_name: Originating tool's name.
            latency_ms: Wall-clock duration of the call.

        Returns:
            A frozen ``ToolResult`` with ``ok=False`` and ``error`` set.
        """
        err = ToolError(
            code=code,
            message=message,
            user_message=user_message if user_message is not None else message,
            retryable=retryable,
        )
        return ToolResult(
            ok=False,
            data=None,
            error=err,
            latency_ms=latency_ms,
            side_effects=[],
            tool_name=tool_name,
        )


# Mapping of common exception types to (code, user_message, retryable).
# Checked in insertion order so that more specific types should come first.
_EXCEPTION_MAP: list[tuple[type[BaseException], str, str, bool]] = [
    (FileNotFoundError, "NOT_FOUND", "I could not find that file.", False),
    (IsADirectoryError, "IS_A_DIRECTORY", "That path is a folder, not a file.", False),
    (NotADirectoryError, "NOT_A_DIRECTORY", "That path is a file, not a folder.", False),
    (FileExistsError, "ALREADY_EXISTS", "That already exists.", False),
    (PermissionError, "PERMISSION_DENIED", "I do not have permission to do that.", False),
    (InterruptedError, "INTERRUPTED", "The operation was interrupted.", True),
    (asyncio.TimeoutError, "TIMEOUT", "That took too long and timed out.", True),
    (TimeoutError, "TIMEOUT", "That took too long and timed out.", True),
    (ConnectionRefusedError, "CONNECTION_REFUSED", "I could not connect to that service.", True),
    (ConnectionResetError, "CONNECTION_RESET", "The connection was reset. Please try again.", True),
    (ConnectionAbortedError, "CONNECTION_ABORTED", "The connection was closed. Please try again.", True),
    (BrokenPipeError, "BROKEN_PIPE", "The connection closed unexpectedly.", True),
    (ConnectionError, "CONNECTION_ERROR", "I had trouble connecting. Please try again.", True),
    (socket.gaierror, "DNS_ERROR", "I could not resolve that address.", True),
    (socket.timeout, "TIMEOUT", "That took too long and timed out.", True),
    (OSError, "OS_ERROR", "The system reported an error.", False),
    (MemoryError, "OUT_OF_MEMORY", "I ran out of memory while doing that.", False),
    (NotImplementedError, "NOT_IMPLEMENTED", "That feature is not available yet.", False),
    (KeyError, "KEY_ERROR", "A required value was missing.", False),
    (IndexError, "INDEX_ERROR", "An index was out of range.", False),
    (ValueError, "INVALID_ARGUMENT", "One of the values was invalid.", False),
    (TypeError, "TYPE_ERROR", "One of the values had the wrong type.", False),
    (LookupError, "LOOKUP_ERROR", "I could not look that up.", False),
    (ArithmeticError, "ARITHMETIC_ERROR", "A math error occurred.", False),
    (asyncio.CancelledError, "CANCELLED", "The operation was cancelled.", False),
]


def wrap_exception(exc: Exception, tool_name: str) -> ToolResult:
    """Map a raised exception to a structured failed ``ToolResult``.

    Common exception types are mapped to stable error codes and friendly
    user-facing messages. Unknown types fall back to ``UNKNOWN_ERROR``.
    The internal ``message`` always includes the exception class name and
    its ``str()`` form for debuggability.

    ``OSError`` subclasses without a dedicated mapping are further inspected
    via ``errno`` to pick a better code (e.g. ``ENOSPC`` -> ``NO_SPACE``).

    Args:
        exc: The caught exception.
        tool_name: Name of the tool that raised. Recorded on the result.

    Returns:
        A ``ToolResult`` with ``ok=False`` describing the failure.
    """
    exc_type_name = type(exc).__name__
    detail = str(exc) or exc_type_name
    message = f"{exc_type_name}: {detail}"

    for exc_type, code, user_msg, retryable in _EXCEPTION_MAP:
        if isinstance(exc, exc_type):
            # Refine generic OSError by errno when possible.
            if exc_type is OSError and isinstance(exc, OSError) and exc.errno is not None:
                refined = _refine_os_error(exc.errno)
                if refined is not None:
                    r_code, r_user, r_retry = refined
                    return ToolResult.failure(
                        code=r_code,
                        message=message,
                        user_message=r_user,
                        retryable=r_retry,
                        tool_name=tool_name,
                    )
            return ToolResult.failure(
                code=code,
                message=message,
                user_message=user_msg,
                retryable=retryable,
                tool_name=tool_name,
            )

    return ToolResult.failure(
        code="UNKNOWN_ERROR",
        message=message,
        user_message="Something went wrong.",
        retryable=False,
        tool_name=tool_name,
    )


def _refine_os_error(err_no: int) -> tuple[str, str, bool] | None:
    """Return a refined ``(code, user_message, retryable)`` for an errno.

    Args:
        err_no: The ``OSError.errno`` value.

    Returns:
        A tuple describing the refined error, or ``None`` if no refinement
        is available and the caller should keep the generic mapping.
    """
    if err_no == errno.ENOSPC:
        return "NO_SPACE", "The disk is full.", False
    if err_no == errno.EACCES:
        return "PERMISSION_DENIED", "I do not have permission to do that.", False
    if err_no == errno.ENOENT:
        return "NOT_FOUND", "I could not find that.", False
    if err_no == errno.EEXIST:
        return "ALREADY_EXISTS", "That already exists.", False
    if err_no == errno.EROFS:
        return "READ_ONLY", "That location is read-only.", False
    if err_no in (errno.ETIMEDOUT,):
        return "TIMEOUT", "That took too long and timed out.", True
    if err_no in (errno.ECONNREFUSED,):
        return "CONNECTION_REFUSED", "I could not connect to that service.", True
    if err_no in (errno.EHOSTUNREACH, errno.ENETUNREACH):
        return "NETWORK_UNREACHABLE", "The network is unreachable.", True
    return None


def to_agent_string(result: ToolResult) -> str:
    """Serialize a ``ToolResult`` to the legacy agent-facing string shape.

    This preserves backward compatibility with the current LiveKit / Gemini
    integration, which consumes tool outputs as plain strings. On success,
    the payload is stringified; on failure, a concise ``"ERROR[CODE]: ..."``
    line is emitted so the model can observe the error code and the
    user-facing explanation in one place.

    Args:
        result: The ``ToolResult`` to serialize.

    Returns:
        A plain string suitable for feeding back into an LLM tool-loop.
    """
    if result.ok:
        if result.data is None:
            return ""
        if isinstance(result.data, str):
            return result.data
        return str(result.data)

    err = result.error
    if err is None:
        return "ERROR[UNKNOWN_ERROR]: Something went wrong."

    retry_hint = " (retryable)" if err.retryable else ""
    return f"ERROR[{err.code}]{retry_hint}: {err.user_message}"
