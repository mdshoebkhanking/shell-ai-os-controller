from __future__ import annotations

from typing import Any

from shellai.agent_loop import create_user_request, run_agent_task
from shellai.config import ShellAIConfig
from shellai.observability import TRACE_STORE, RequestTrace, get_logger


def _error_response(
    *,
    error_type: str,
    message: str,
    trace: RequestTrace,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trace.add_step(
        "ShellAIAPI",
        "error",
        message,
        {"error_type": error_type, **dict(details or {})},
    )
    return {
        "ok": False,
        "status": "error",
        "summary": message,
        "error": {
            "type": error_type,
            "message": message,
            "details": dict(details or {}),
        },
        "steps": [],
        "trace_id": trace.request_id,
        "trace": trace.to_dict(),
    }


def run_shellai_task(
    text: str,
    *,
    context: dict[str, Any] | None = None,
    auto_approve_ask: bool = False,
) -> dict[str, Any]:
    """Run one ShellAI core task for desktop/daemon callers.

    This is the stable Python API for non-CLI integrations. It deliberately
    returns structured errors instead of raising raw tracebacks so a UI can
    display a useful message and keep the classic desktop path alive.
    """
    logger = get_logger("shellai.api")
    trace = TRACE_STORE.start_trace(text)
    trace.add_step("ShellAIAPI", "start", "desktop/api request received", {
        "context_keys": sorted((context or {}).keys()),
        "auto_approve_ask": bool(auto_approve_ask),
    })

    try:
        config = ShellAIConfig.load()
    except Exception as exc:
        logger.exception("shellai config load failed")
        return _error_response(
            error_type=exc.__class__.__name__,
            message=f"ShellAI configuration could not be loaded: {exc}",
            trace=trace,
            details={"stage": "config_load"},
        )

    try:
        config.paths.ensure_runtime_dirs()
        trace.add_step("ShellAIAPI", "runtime_ready", "runtime paths initialized", {
            "home_dir": str(config.paths.home_dir),
            "memory_db": str(config.paths.memory_db),
        })
    except Exception as exc:
        logger.exception("shellai runtime initialization failed")
        return _error_response(
            error_type=exc.__class__.__name__,
            message=f"ShellAI runtime paths are not writable or could not be initialized: {exc}",
            trace=trace,
            details={
                "stage": "runtime_init",
                "home_dir": str(config.paths.home_dir),
                "memory_db": str(config.paths.memory_db),
            },
        )

    try:
        request = create_user_request(
            text,
            context=dict(context or {}),
            auto_approve_ask=auto_approve_ask,
        )
        result = run_agent_task(request, trace=trace, config=config)
        if isinstance(result, dict):
            trace.add_step("ShellAIAPI", "ok", "agent loop returned", {
                "status": result.get("status"),
                "steps": len(result.get("steps", []) or []),
            })
            result.setdefault("ok", result.get("status") not in {"error", "blocked"})
            result["trace_id"] = trace.request_id
            result["trace"] = trace.to_dict()
            return result
        return _error_response(
            error_type="InvalidAgentLoopResult",
            message="ShellAI agent loop returned a non-dict result.",
            trace=trace,
            details={"stage": "agent_loop", "result_type": type(result).__name__},
        )
    except Exception as exc:
        logger.exception("shellai task failed")
        return _error_response(
            error_type=exc.__class__.__name__,
            message=f"ShellAI task failed: {exc}",
            trace=trace,
            details={"stage": "agent_loop"},
        )


__all__ = ["run_shellai_task"]
