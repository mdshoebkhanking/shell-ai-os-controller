"""
Shell Safe Executor v3 — reliable tool wrapper
-------------------------------------------------
Universal wrapper for all Shell AI tools.
Provides: crash protection, profiling, retry, rate limiting,
health metrics, error tracking, middleware, circuit breaking.

Usage:
    from shell_safe_executor import god_tier_tool as function_tool

    @function_tool
    async def my_tool(query: str) -> str:
        return "result"

    @function_tool(category="web", rate_limit="google_search")
    async def search(q: str) -> str:
        ...
"""

import functools
import logging
import traceback
import asyncio
import inspect
import re
import time
import json

logger = logging.getLogger("SHELL_SENTINEL")

# ── Soft imports for infrastructure (backward compatible) ─────────
try:
    from shell_rate_limiter import RateLimiterRegistry
    _rate_limiter_available = True
except ImportError:
    _rate_limiter_available = False

try:
    from shell_health import HealthMonitor
    _health_available = True
except ImportError:
    _health_available = False

try:
    from shell_error_tracker import ErrorTracker
    _error_tracker_available = True
except ImportError:
    _error_tracker_available = False

try:
    from shell_middleware import MiddlewareChain, ToolContext
    _middleware_available = True
except ImportError:
    _middleware_available = False

try:
    from shell_tool_registry import ToolRegistry
    _registry_available = True
except ImportError:
    _registry_available = False

try:
    from core.observability.events import emit_debug_event
    _core_observability_available = True
except Exception:
    _core_observability_available = False


# ── Tool Registry for Auto-Discovery ─────────────────────────────
_registered_tools = []  # List of (tool_name, tool_object)


def get_registered_tools() -> list:
    """Return all tool objects registered via @god_tier_tool."""
    return [obj for _, obj in _registered_tools]


def get_registered_tools_info() -> list:
    """Return (name, object) pairs for all registered tools."""
    return list(_registered_tools)


# ── Tool Event Telemetry Hook (new) ───────────────────────────────
# agent.py registers a callable at startup so every tool invocation
# can broadcast a `tool_event` to the UI via Socket.IO — without this
# module having to import socketio or know about the hub.
_tool_event_hooks: list = []


def register_tool_event_hook(fn) -> None:
    """Register a callable invoked with a payload dict on tool start/end.

    The callable must be fast and non-blocking (it runs inside the tool
    call path). Any raised exception is swallowed so telemetry failures
    never break tool execution.
    """
    if callable(fn) and fn not in _tool_event_hooks:
        _tool_event_hooks.append(fn)


def unregister_tool_event_hook(fn) -> None:
    try:
        _tool_event_hooks.remove(fn)
    except ValueError:
        pass


def _emit_tool_event(payload: dict) -> None:
    """Broadcast to every registered hook. Swallow all errors."""
    if _core_observability_available:
        try:
            phase = str(payload.get("phase") or "event")
            emit_debug_event(f"tool.{phase}", "shell_safe_executor", dict(payload))
        except Exception:
            pass
    if not _tool_event_hooks:
        return
    for hook in list(_tool_event_hooks):
        try:
            hook(payload)
        except Exception:  # noqa: BLE001 — telemetry must never crash
            pass


def _safe_preview(obj, limit: int = 120) -> str:
    """Short string preview of a return value or argument, no crashes."""
    try:
        s = str(obj)
    except Exception:
        return "<unreprable>"
    return s[:limit].replace("\n", " ")


# ── safe_tool (basic wrapper) ─────────────────────────────────────

def safe_tool(func):
    """
    SENTINEL SAFETY WRAPPER
    Wraps any tool function to prevent crashes.
    1. Catches ALL exceptions.
    2. Logs full traceback for debugging.
    3. Feeds error context to Phoenix self-heal engine.
    4. Returns a friendly error string to the Agent (LLM).
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        tool_name = func.__name__
        try:
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = await asyncio.to_thread(func, *args, **kwargs)
            return result

        except Exception as e:
            error_msg = str(e)
            tb = traceback.format_exc()
            logger.error(f"CRASH PREVENTED in '{tool_name}': {error_msg}\n{tb}")

            # Error tracker integration
            if _error_tracker_available:
                try:
                    ErrorTracker.get().record(tool_name, e, tb)
                except Exception as _e:
                    logger.debug("ignored Exception: %s", _e)
            filepath = ""
            lineno = 0
            try:
                matches = re.findall(r'File "([^"]*\.py)", line (\d+)', tb)
                if matches:
                    filepath = matches[-1][0]
                    lineno = int(matches[-1][1])
                from shell_self_heal import record_error
                record_error(tool_name, error_msg, tb, filepath, lineno)
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
            return (
                f"System Error in '{tool_name}': {error_msg}. "
                f"(Error logged to Phoenix. Call `diagnose_and_fix_tool('{error_msg[:80]}')` to repair.)"
            )

    return wrapper


# ── god_tier_tool v3 (with middleware + error tracker + circuit breaker) ──

def god_tier_tool(func=None, *, category="general", rate_limit=None, **kwargs):
    """
    Universal Shell tool wrapper (v3)
    Replaces `livekit.agents.function_tool`.

    Provides:
    1. Execution Profiling (Latency measurement)
    2. Auto-Retry for transient failures (1 retry built-in)
    3. JSON Crash Formatting (Invulnerability against framework breaks)
    4. Auto-registration for tool discovery
    5. Health metrics recording
    6. Optional rate limiting
    7. [NEW v3] Error tracker integration
    8. [NEW v3] Middleware pipeline (pre/post hooks)
    9. [NEW v3] Circuit breaker awareness
    10. [NEW v3] Enhanced tool registry with categories

    Args:
        category: Tool category for organization (e.g., "browser", "social", "system")
        rate_limit: Name of rate limiter to use (e.g., "google_search", "weather_api")
        **kwargs: Passed through to LiveKit's function_tool
    """
    def decorator(f):
        @functools.wraps(f)
        async def wrapper(*args, **kw):
            tool_name = f.__name__
            start_time = time.time()
            max_retries = 1

            # ── Tool-event telemetry: start ──
            _emit_tool_event({
                "phase": "start",
                "tool": tool_name,
                "category": category,
                "args_preview": _safe_preview(kw or args, 200),
                "ts": start_time,
            })

            # ── Middleware pre-hooks ──
            ctx = None
            if _middleware_available:
                try:
                    ctx = ToolContext(tool_name, args, kw)
                    MiddlewareChain.get().run_pre(ctx)
                    if ctx.cancelled:
                        return ctx.error or f"Tool '{tool_name}' is temporarily disabled."
                    # Use potentially sanitized kwargs
                    kw = ctx.kwargs
                except Exception as _e:
                    logger.debug("ignored Exception: %s", _e)
            # ── Rate limiting ──
            if _rate_limiter_available and rate_limit:
                try:
                    limiter = RateLimiterRegistry.get().get_limiter(rate_limit)
                    await limiter.wait()
                except Exception:
                    pass  # Rate limiter failure should not block tool execution

            # ── Execution with retry ──
            for attempt in range(max_retries + 1):
                try:
                    if inspect.iscoroutinefunction(f):
                        res = await f(*args, **kw)
                    else:
                        res = await asyncio.to_thread(f, *args, **kw)

                    elapsed = time.time() - start_time

                    # Record health metrics
                    if _health_available:
                        try:
                            HealthMonitor.get().record_success(tool_name, elapsed * 1000)
                        except Exception as _e:
                            logger.debug("ignored Exception: %s", _e)
                    # ── Middleware post-hooks (success) ──
                    if _middleware_available and ctx:
                        try:
                            ctx.result = res
                            MiddlewareChain.get().run_post(ctx)
                        except Exception as _e:
                            logger.debug("ignored Exception: %s", _e)
                    latency_badge = f"\n[Tool Execution: {elapsed:.2f}s]"

                    # ── Tool-event telemetry: end (success) ──
                    _emit_tool_event({
                        "phase": "end",
                        "tool": tool_name,
                        "category": category,
                        "ok": True,
                        "duration_ms": round(elapsed * 1000, 1),
                        "preview": _safe_preview(res, 200),
                    })

                    if isinstance(res, str):
                        return res + latency_badge
                    return res

                except Exception as e:
                    if attempt < max_retries:
                        logger.warning(f"Tool '{tool_name}' failed... Auto-Retrying (Attempt {attempt+1}/{max_retries})")
                        await asyncio.sleep(1)
                        continue

                    elapsed = time.time() - start_time
                    tb = traceback.format_exc()
                    logger.error(f"CRASH PREVENTED in '{tool_name}'\n{tb}")

                    # Record failure in health monitor
                    if _health_available:
                        try:
                            HealthMonitor.get().record_failure(tool_name, str(e))
                        except Exception as _e:
                            logger.debug("ignored Exception: %s", _e)
                    # Error tracker integration (v3)
                    if _error_tracker_available:
                        try:
                            ErrorTracker.get().record(
                                tool_name, e, tb,
                                context={"elapsed_ms": elapsed * 1000, "attempt": attempt + 1}
                            )
                        except Exception as _e:
                            logger.debug("ignored Exception: %s", _e)
                    # ── Middleware post-hooks (failure) ──
                    if _middleware_available and ctx:
                        try:
                            ctx.error = str(e)
                            MiddlewareChain.get().run_post(ctx)
                        except Exception as _e:
                            logger.debug("ignored Exception: %s", _e)
                    # Phoenix self-heal (fire and forget)
                    filepath, lineno = "", 0
                    try:
                        matches = re.findall(r'File "([^"]*\.py)", line (\d+)', tb)
                        if matches:
                            filepath, lineno = matches[-1]
                        from shell_self_heal import record_error
                        record_error(tool_name, str(e), tb, filepath, int(lineno))
                    except Exception as _e:
                        logger.debug("ignored Exception: %s", _e)
                    # ── Tool-event telemetry: end (failure) ──
                    _emit_tool_event({
                        "phase": "end",
                        "tool": tool_name,
                        "category": category,
                        "ok": False,
                        "duration_ms": round(elapsed * 1000, 1),
                        "error": str(e)[:200],
                    })

                    error_payload = {
                        "status": "FATAL_ERROR",
                        "tool": tool_name,
                        "message": str(e),
                        "repair_advice": f"Phoenix engine logged the trace. Run diagnose_and_fix_tool('{str(e)[:50]}') to inspect the failure.",
                    }
                    return json.dumps(error_payload, indent=2)

        # Feed to LiveKit's function_tool (lazy import)
        try:
            from livekit.agents import function_tool as _lk_ft
        except ImportError:
            def _lk_ft(**kw):
                def d(fn): return fn
                return d

        tool_obj = _lk_ft(**kwargs)(wrapper)

        # Auto-register for discovery (legacy list)
        _registered_tools.append((f.__name__, tool_obj))

        # Register in enhanced tool registry (v3)
        if _registry_available:
            try:
                ToolRegistry.get().register(
                    f.__name__, tool_obj,
                    category=category,
                    module=getattr(f, "__module__", ""),
                )
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
        return tool_obj

    if func is None:
        return decorator
    return decorator(func)
