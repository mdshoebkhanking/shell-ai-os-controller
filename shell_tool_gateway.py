"""
Execution gateway for decorated Shell backend tools.

The UI and MCP server use this module to run a selected tool by catalog id.
Only functions discovered by shell_tool_catalog are executable here.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import os
import time
from pathlib import Path
from typing import Any

from shell_tool_catalog import PROJECT_ROOT, discover_tool_catalog

try:
    from core.observability.events import emit_debug_event
    from core.observability.tracing import ExecutionTracer
    from core.reasoning import explain_failure, explain_tool_choice
    from core.tools.reputation import ToolReputationStore
    from core.tools.registry import CapabilityRegistry
except Exception:  # pragma: no cover - compatibility fallback
    emit_debug_event = None  # type: ignore
    ExecutionTracer = None  # type: ignore
    explain_failure = None  # type: ignore
    explain_tool_choice = None  # type: ignore
    ToolReputationStore = None  # type: ignore
    CapabilityRegistry = None  # type: ignore


def _catalog_index() -> dict[str, dict[str, Any]]:
    tools = discover_tool_catalog(PROJECT_ROOT)
    by_id = {item["id"]: item for item in tools}
    by_name: dict[str, list[dict[str, Any]]] = {}
    for item in tools:
        by_name.setdefault(item["name"], []).append(item)
    for name, items in by_name.items():
        if len(items) == 1:
            by_id[name] = items[0]
    return by_id


def _readiness_for_item(item: dict[str, Any]) -> dict[str, Any]:
    try:
        if CapabilityRegistry is None:
            return {}
        registry = CapabilityRegistry.from_catalog([item])
        enriched = registry.get(item["id"])
        return dict((enriched or {}).get("readiness") or {})
    except Exception:
        return {}


def _unavailable_result(item: dict[str, Any], readiness: dict[str, Any], trace_id: str = "") -> dict[str, Any]:
    result = {
        "status": "error",
        "tool": item.get("id"),
        "state": readiness.get("state", "UNKNOWN"),
        "message": "Tool is not ready for execution",
        "reasons": readiness.get("reasons", []),
        "requirements": readiness.get("requirements", []),
        "trace_id": trace_id,
    }
    if explain_failure is not None:
        try:
            result["explanation"] = explain_failure(result).to_dict()
        except Exception:
            pass
    return result


def _record_reputation(tool_id: str, *, ok: bool, latency_ms: float, failure_category: str = "", error: str = "") -> None:
    if ToolReputationStore is None:
        return
    try:
        ToolReputationStore().record(
            tool_id,
            ok=ok,
            latency_ms=latency_ms,
            failure_category=failure_category,
            error=error,
        )
    except Exception:
        pass


def _coerce_value(value: Any, annotation: str) -> Any:
    ann = str(annotation or "").lower()
    if value is None:
        return None
    if "bool" in ann:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    if "int" in ann and not isinstance(value, bool):
        return int(value)
    if "float" in ann:
        return float(value)
    if "dict" in ann and isinstance(value, str):
        return json.loads(value)
    if "list" in ann and isinstance(value, str):
        return json.loads(value)
    return value


def _prepare_args(item: dict[str, Any], raw_args: Any) -> dict[str, Any]:
    if raw_args is None:
        raw_args = {}
    if isinstance(raw_args, str):
        raw_args = json.loads(raw_args or "{}")
    if not isinstance(raw_args, dict):
        raise ValueError("Tool args must be a JSON object")

    params = item.get("params") or []
    prepared: dict[str, Any] = {}
    for param in params:
        name = param["name"]
        if name in raw_args:
            prepared[name] = _coerce_value(raw_args[name], param.get("annotation", ""))
        elif param.get("required"):
            raise ValueError(f"Missing required argument: {name}")
    return prepared


def _callable_from_tool_object(obj: Any) -> Any:
    if callable(obj):
        return obj
    for attr in ("raw_function", "_raw_function", "function", "_function", "func"):
        candidate = getattr(obj, attr, None)
        if callable(candidate):
            return candidate
    tool_info = getattr(obj, "_tool_info", None) or getattr(obj, "function_info", None)
    for attr in ("callable", "fn", "function"):
        candidate = getattr(tool_info, attr, None)
        if callable(candidate):
            return candidate
    raise TypeError("Selected tool object is not directly callable")


async def execute_tool(tool_id: str, args: Any = None) -> dict[str, Any]:
    started = time.perf_counter()
    tracer = ExecutionTracer.get() if ExecutionTracer is not None else None
    trace_id = tracer.start_trace("tool_gateway.execute", {"tool_id": str(tool_id)}) if tracer else ""
    span_id = tracer.start_span(trace_id, "catalog.lookup") if tracer else ""
    index = _catalog_index()
    item = index.get(str(tool_id or "").strip())
    if item is None:
        if tracer:
            tracer.finish_span(trace_id, span_id, ok=False, error=f"Unknown tool: {tool_id}")
            tracer.finish_trace(trace_id, ok=False, error=f"Unknown tool: {tool_id}")
        raise ValueError(f"Unknown tool: {tool_id}")
    if tracer:
        tracer.finish_span(trace_id, span_id, ok=True)

    readiness = _readiness_for_item(item)
    if readiness and not readiness.get("ok", True):
        result = _unavailable_result(item, readiness, trace_id)
        _record_reputation(item.get("id", ""), ok=False, latency_ms=(time.perf_counter() - started) * 1000.0, failure_category=str(readiness.get("state") or "not_ready"), error="; ".join(readiness.get("reasons") or []))
        if emit_debug_event is not None:
            emit_debug_event("tool.blocked", "shell_tool_gateway", result, trace_id=trace_id)
        if tracer:
            tracer.finish_trace(trace_id, ok=False, error=str(readiness.get("state") or "not ready"))
        return result

    root = str(PROJECT_ROOT)
    if root not in os.sys.path:
        os.sys.path.insert(0, root)

    span_id = tracer.start_span(trace_id, "tool.invoke", {"tool": item["id"]}) if tracer else ""
    try:
        module_name, function_name = item["id"].split(":", 1)
        module = importlib.import_module(module_name)
        obj = getattr(module, function_name)
        fn = _callable_from_tool_object(obj)
        kwargs = _prepare_args(item, args)

        if inspect.iscoroutinefunction(fn):
            result = await fn(**kwargs)
        else:
            result = await asyncio.to_thread(fn, **kwargs)
        if inspect.isawaitable(result):
            result = await result
        payload = {
            "status": "success",
            "tool": item["id"],
            "result": result,
            "trace_id": trace_id,
        }
        if explain_tool_choice is not None:
            try:
                payload["explanation"] = explain_tool_choice({
                    "tool": item["id"],
                    "confidence": 1.0,
                    "readiness": readiness or {"state": "READY", "ok": True},
                }).to_dict()
            except Exception:
                pass
        _record_reputation(item["id"], ok=True, latency_ms=(time.perf_counter() - started) * 1000.0)
        if emit_debug_event is not None:
            emit_debug_event("tool.success", "shell_tool_gateway", {"tool": item["id"]}, trace_id=trace_id)
        if tracer:
            tracer.finish_span(trace_id, span_id, ok=True)
            tracer.finish_trace(trace_id, ok=True)
        return payload
    except Exception as exc:
        _record_reputation(item.get("id", ""), ok=False, latency_ms=(time.perf_counter() - started) * 1000.0, failure_category="exception", error=str(exc))
        if emit_debug_event is not None:
            emit_debug_event("tool.error", "shell_tool_gateway", {"tool": item.get("id"), "error": str(exc)}, trace_id=trace_id)
        if tracer:
            tracer.finish_span(trace_id, span_id, ok=False, error=str(exc))
            tracer.finish_trace(trace_id, ok=False, error=str(exc))
        raise


def execute_tool_sync(tool_id: str, args: Any = None) -> dict[str, Any]:
    policy = asyncio.get_event_loop_policy()
    try:
        previous_loop = policy.get_event_loop()
    except RuntimeError:
        previous_loop = None
    loop = asyncio.new_event_loop()
    try:
        policy.set_event_loop(loop)
        return loop.run_until_complete(execute_tool(tool_id, args))
    finally:
        try:
            from brain.provider_transport import close_aiohttp_sessions

            loop.run_until_complete(close_aiohttp_sessions())
        except Exception:
            pass
        pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
        if pending:
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.run_until_complete(loop.shutdown_asyncgens())
        shutdown_executor = getattr(loop, "shutdown_default_executor", None)
        if shutdown_executor is not None:
            loop.run_until_complete(shutdown_executor())
        loop.close()
        if previous_loop is not None and not previous_loop.is_closed():
            policy.set_event_loop(previous_loop)
        else:
            policy.set_event_loop(asyncio.new_event_loop())
