"""
Shell Startup - Startup Orchestrator v2
-----------------------------------------
Initialize all Shell AI shared services in the correct order.
Call initialize_shell() once at the start of agent.py.

Usage:
    from shell_startup import initialize_shell, shutdown_shell

    async def entrypoint():
        await initialize_shell()
        # ... rest of app
        await shutdown_shell()
"""

import time
import logging


async def initialize_shell(skip_health_check: bool = False) -> dict:
    """Initialize all Shell AI shared services.
    Returns dict with startup results. Safe to call multiple times (idempotent).
    """
    start = time.time()
    results = {}

    # 1. Config (loads .env)
    try:
        from shell_config import config
        warnings = config.validate()
        results["config_warnings"] = warnings
        active, total = config.get_active_keys_count()
        results["api_keys_configured"] = f"{active}/{total}"
    except Exception as e:
        results["config_error"] = str(e)
        warnings = []

    # 2. Logging (unified setup)
    try:
        from shell_logger import setup_logging
        log_level = "INFO"
        try:
            log_level = config.get_str("LOG_LEVEL", "INFO")
        except Exception:
            pass
        setup_logging(level=log_level)
    except Exception as e:
        results["logger_error"] = str(e)

    logger = logging.getLogger("shell_startup")

    # 3. Rate limiter registry (just instantiate to set defaults)
    try:
        from shell_rate_limiter import RateLimiterRegistry
        RateLimiterRegistry.get()
        results["rate_limiter"] = "ready"
    except ImportError:
        results["rate_limiter"] = "not available"

    # 4. Error tracker (v3 — initialize singleton)
    try:
        from shell_error_tracker import ErrorTracker
        ErrorTracker.get()
        results["error_tracker"] = "ready"
    except ImportError:
        results["error_tracker"] = "not available"

    # 5. Tool registry (v3 — initialize singleton)
    try:
        from shell_tool_registry import ToolRegistry
        ToolRegistry.get()
        results["tool_registry"] = "ready"
    except ImportError:
        results["tool_registry"] = "not available"

    # 6. Middleware chain (v3 — install defaults)
    try:
        from shell_middleware import setup_default_middleware
        setup_default_middleware()
        results["middleware"] = "ready"
    except ImportError:
        results["middleware"] = "not available"

    # 7. Health checks
    if not skip_health_check:
        try:
            from shell_health import HealthMonitor
            monitor = HealthMonitor.get()
            api_status = monitor.validate_api_keys()
            dep_status = monitor.check_dependencies()
            results["api_keys"] = api_status
            results["dependencies"] = dep_status

            active_keys = sum(1 for v in api_status.values() if v)
            total_keys = len(api_status)
            installed_deps = sum(1 for v in dep_status.values() if v)
            total_deps = len(dep_status)
            results["api_keys_summary"] = f"{active_keys}/{total_keys}"
            results["deps_summary"] = f"{installed_deps}/{total_deps}"
        except Exception as e:
            results["health_error"] = str(e)

    elapsed = time.time() - start
    results["startup_time_ms"] = round(elapsed * 1000)

    # Print startup banner
    _print_banner(results)

    return results


def _print_banner(results: dict):
    """Print a clean startup summary to console."""
    print()
    print("=" * 55)
    print("   SHELL AI 1.0.0 — SYSTEM STARTUP")
    print("   Created by mdshoebking")
    print("=" * 55)

    # Config warnings
    warnings = results.get("config_warnings", [])
    critical = [w for w in warnings if w.startswith("CRITICAL")]
    optional = [w for w in warnings if w.startswith("Optional")]
    if critical:
        for w in critical:
            print(f"  [!!] {w}")
    if optional:
        print(f"  [..] {len(optional)} optional API keys not set")

    # API Keys
    api_configured = results.get("api_keys_configured")
    if api_configured:
        print(f"  API Keys: {api_configured} configured")

    api_summary = results.get("api_keys_summary")
    if api_summary:
        print(f"  API Keys Active: {api_summary}")

    # Dependencies
    deps_summary = results.get("deps_summary")
    if deps_summary:
        print(f"  Dependencies: {deps_summary} installed")

    # Infrastructure status
    infra_items = ["rate_limiter", "error_tracker", "tool_registry", "middleware"]
    ready_count = sum(1 for i in infra_items if results.get(i) == "ready")
    print(f"  Infrastructure: {ready_count}/{len(infra_items)} modules active")

    # Errors
    for key in ["config_error", "logger_error", "health_error"]:
        if key in results:
            print(f"  [ERROR] {key}: {results[key]}")

    # Timing
    ms = results.get("startup_time_ms", 0)
    print(f"  Startup Time: {ms}ms")
    print("=" * 55)
    print()


async def shutdown_shell():
    """Graceful shutdown of all shared services."""
    logger = logging.getLogger("shell_startup")

    # Close HTTP sessions
    try:
        from shell_http import cleanup_sessions
        await cleanup_sessions()
    except Exception as e:
        logger.warning(f"HTTP session cleanup warning: {e}")

    # Cancel background tasks
    try:
        from shell_async_utils import get_bg_manager
        await get_bg_manager().cancel_all()
    except Exception as _e:
        logger.debug("ignored Exception: %s", _e)

    logger.info("Shell AI services shut down.")


# Allow running standalone for testing
if __name__ == "__main__":
    import asyncio
    asyncio.run(initialize_shell())
