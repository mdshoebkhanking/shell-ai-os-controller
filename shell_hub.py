import sys
import traceback
import hmac
import ipaddress
import time

# CRASH LOGGER START
try:
    from aiohttp import web, WSMsgType
    import socketio
    import psutil
    import asyncio
    import socket
    import uuid
except Exception as e:
    with open("hub_error.log", "w") as f:
        f.write(f"Import Error: {str(e)}\n{traceback.format_exc()}")
    sys.exit(1)

try:
    from livekit import api
except Exception:
    api = None

# CRASH LOGGER END

from shell_config import config
from shell_logger import get_logger
logger = get_logger("shell_hub")

# Runtime coordination file for UI/agent to discover active hub port.
HUB_PORT_HINT_FILE = ".shell_hub_port"


def _truthy(value) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _hub_token() -> str:
    return (config.get_str("SHELL_HUB_TOKEN") or config.get_str("SHELL_API_TOKEN") or "").strip()


def _is_loopback_bind_host(host: str) -> bool:
    h = str(host or "").strip().lower()
    if h in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ipaddress.ip_address(h).is_loopback
    except ValueError:
        return False


def _request_authorized(request) -> bool:
    expected = _hub_token()
    if not expected:
        return True
    header = request.headers.get("Authorization", "")
    prefix = "Bearer "
    return header.startswith(prefix) and hmac.compare_digest(header[len(prefix):].strip(), expected)


def _socket_authorized(auth) -> bool:
    expected = _hub_token()
    if not expected:
        return True
    token = ""
    if isinstance(auth, dict):
        token = str(auth.get("token", "") or "")
    return hmac.compare_digest(token, expected)


def _candidate_ports():
    env_port = config.get_str("SHELL_HUB_PORT")
    if env_port and str(env_port).strip().isdigit():
        p = int(env_port)
        if 1 <= p <= 65535:
            return [p]
    return [5000, 5001, 5002, 5003]


def _write_port_hint(port: int):
    try:
        with open(HUB_PORT_HINT_FILE, "w", encoding="utf-8") as f:
            f.write(str(port))
    except Exception as _e:
        logger.debug("ignored Exception: %s", _e)


def _bind_probe_host(host: str) -> str:
    value = str(host or "").strip()
    if not value or value.lower() == "localhost":
        return "127.0.0.1"
    return value


def _pick_available_port(host: str = "127.0.0.1") -> int:
    probe_host = _bind_probe_host(host)
    family = socket.AF_INET6 if ":" in probe_host else socket.AF_INET
    for port in _candidate_ports():
        test_sock = socket.socket(family, socket.SOCK_STREAM)
        try:
            test_sock.bind((probe_host, port))
            return port
        except OSError:
            continue
        finally:
            try:
                test_sock.close()
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
    raise OSError("No free hub port found in candidate list.")


# Define the Socket.IO server with permissive CORS
ALLOWED_ORIGINS = [
    'http://localhost:5000', 'http://localhost:5001',
    'http://localhost:5002', 'http://localhost:5003',
    'http://127.0.0.1:5000', 'http://127.0.0.1:5001',
    'http://127.0.0.1:5002', 'http://127.0.0.1:5003',
    'http://localhost:3000', 'http://127.0.0.1:3000',
]

sio = socketio.AsyncServer(async_mode='aiohttp', cors_allowed_origins=ALLOWED_ORIGINS)
app = web.Application()
sio.attach(app)
_CAPABILITIES_CACHE = {"ts": 0.0, "payload": None}

# CORS setup for HTTP routes - MAX PERMISSIVE
import aiohttp_cors
cors = aiohttp_cors.setup(app, defaults={
    origin: aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            # Narrow CORS surface — Shell UI only POSTs/GETs and sends
            # Content-Type. Wildcards force the browser to preflight and
            # open a CSRF vector if the hub is ever reachable off-localhost.
            allow_headers=["Content-Type", "Authorization"],
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    )
    for origin in ALLOWED_ORIGINS
})

async def get_token(request):
    try:
        if not _request_authorized(request):
            return web.json_response({'error': 'Unauthorized'}, status=401)

        # Get API keys from Env
        lk_api_key = config.get_str("LIVEKIT_API_KEY")
        lk_api_secret = config.get_str("LIVEKIT_API_SECRET")
        lk_url = config.get_str("LIVEKIT_URL")
        
        if api is None:
            return web.json_response({'error': 'LiveKit package not installed'}, status=500)

        if not lk_api_key or not lk_api_secret or not lk_url:
            with open("token_error.log", "a") as f:
                f.write(f"Missing Keys: KEY={bool(lk_api_key)}, SECRET={bool(lk_api_secret)}, URL={bool(lk_url)}\n")
            return web.json_response({'error': 'LiveKit credentials missing in .env'}, status=500)

        # Generate Token
        # Use a random participant identity
        participant_identity = f"user_{str(uuid.uuid4())[:8]}"
        
        grant = api.VideoGrants(room_join=True, room="shell-room")
        token = api.AccessToken(lk_api_key, lk_api_secret) \
            .with_identity(participant_identity) \
            .with_name("Shell User") \
            .with_grants(grant)
        
        jwt_token = token.to_jwt()
        
        return web.json_response({'token': jwt_token, 'url': lk_url})
    except Exception as e:
        err_msg = f"Token Error: {str(e)}\n{traceback.format_exc()}"
        with open("token_error.log", "a") as f:
            f.write(err_msg + "\n")
        return web.json_response({'error': 'Internal server error. Check token_error.log for details.'}, status=500)

# Add Route and enable CORS
resource = app.router.add_resource("/token")
cors.add(resource.add_route("GET", get_token))

# ─── API-key management routes (UI Settings page) ────────────────
# The endpoint handler functions are defined later in the file — aiohttp
# resolves them lazily when a request arrives, so forward references are
# fine. CORS is applied so the PyQt WebEngine / browser UI can call them.
_api_keys_res = app.router.add_resource("/api-keys")
cors.add(_api_keys_res.add_route("GET",  lambda req: list_api_keys_endpoint(req)))
cors.add(_api_keys_res.add_route("POST", lambda req: set_api_key_endpoint(req)))
_api_keys_item = app.router.add_resource("/api-keys/{key}")
cors.add(_api_keys_item.add_route("DELETE", lambda req: delete_api_key_endpoint(req)))
_settings_res = app.router.add_resource("/settings")
cors.add(_settings_res.add_route("GET", lambda req: get_settings_endpoint(req)))
cors.add(_settings_res.add_route("POST", lambda req: set_settings_endpoint(req)))
_ready_res = app.router.add_resource("/ready")
cors.add(_ready_res.add_route("GET", lambda req: ready_endpoint(req)))
_health_res = app.router.add_resource("/health")
cors.add(_health_res.add_route("GET", lambda req: health_endpoint(req)))
_capabilities_res = app.router.add_resource("/capabilities")
cors.add(_capabilities_res.add_route("GET", lambda req: capabilities_endpoint(req)))

@sio.event
async def connect(sid, environ, auth=None):
    if not _socket_authorized(auth):
        logger.warning("Rejected unauthorized Socket.IO connection: %s", sid)
        return False
    logger.info(f"Device Connected: {sid}")
    await sio.emit('status', {'msg': 'Shell Core Connected'})

@sio.event
async def join_agent(sid):
    logger.info(f"Agent Logic Joined: {sid}")
    await sio.emit('agent_status', {'active': True})

@sio.event
async def gui_input(sid, data):
    # Message from Frontend (User Typed/Clicked)
    logger.info(f"GUI Command: {data}")
    # Broadcast to Agent
    await sio.emit('user_command', data)

@sio.event
async def agent_output(sid, data):
    # Message from Agent (Text/Speech status)
    # Broadcast to Frontend to update UI
    await sio.emit('shell_response', data)

@sio.event
async def voice_amplitude(sid, data):
    """Forward real-time voice amplitude from agent to UI."""
    await sio.emit('voice_data', data)

@sio.event
async def agent_state(sid, data):
    """Forward agent state changes (thinking/speaking/idle) to UI."""
    state = data.get("state", "").lower()
    text = data.get("text", "")
    if state == "speaking":
        await sio.emit('shell_response', {"type": "agent_speech_start", "text": text})
    elif state == "done_speaking":
        await sio.emit('shell_response', {"type": "agent_speech_stop", "text": text})
    elif state == "thinking":
        await sio.emit('shell_response', {"type": "agent_thinking", "text": ""})
    elif state == "listening":
        await sio.emit('shell_response', {"type": "user_speech", "text": text})


@sio.event
async def research_update(sid, data):
    """Forward deep research progress from agent to UI.
    Expected data: {topic, status, sources[], progress (0.0-1.0)}
    """
    await sio.emit('research_update', data)


@sio.event
async def tool_event(sid, data):
    """Relay tool-call telemetry from agent to every connected UI client.

    Payload shape:
      {phase: 'start'|'end', tool: str, category: str, duration_ms?: float,
       ok?: bool, preview?: str, args_preview?: str, error?: str}

    The UI renders these as a real-time tool-activity feed.
    """
    try:
        await sio.emit('tool_event', data)
    except Exception as _e:
        logger.debug("tool_event relay failed: %s", _e)


# ─── HTTP endpoints for UI-managed API keys ──────────────────────────

async def list_api_keys_endpoint(request):
    """GET /api-keys → list of {name, set, section, description, required}.
    Values are never returned — only a boolean 'set' flag."""
    if not _request_authorized(request):
        return web.json_response({"ok": False, "error": "Unauthorized"}, status=401)
    try:
        from shell_api_manager import list_api_keys
        return web.json_response({"ok": True, "keys": list_api_keys()})
    except Exception as e:
        logger.warning("list_api_keys failed: %s", e)
        return web.json_response({"ok": False, "error": str(e)}, status=500)


async def set_api_key_endpoint(request):
    """POST /api-keys → body {"key": "NAME", "value": "..."}.
    Writes `.env` atomically + updates this process's env."""
    if not _request_authorized(request):
        return web.json_response({"ok": False, "error": "Unauthorized"}, status=401)
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)
    key = body.get("key", "") if isinstance(body, dict) else ""
    value = body.get("value", "") if isinstance(body, dict) else ""
    try:
        from shell_api_manager import set_api_key
        ok, msg = set_api_key(key, value)
    except Exception as e:
        logger.warning("set_api_key exception: %s", e)
        return web.json_response({"ok": False, "error": str(e)}, status=500)
    # Broadcast so any open UI updates its status chips.
    try:
        await sio.emit('api_key_update', {"key": key, "set": bool(value)})
    except Exception as _e:
        logger.debug("api_key_update emit skipped: %s", _e)
    return web.json_response({"ok": ok, "message": msg}, status=200 if ok else 400)


async def delete_api_key_endpoint(request):
    """DELETE /api-keys/{key} → remove a key from .env."""
    if not _request_authorized(request):
        return web.json_response({"ok": False, "error": "Unauthorized"}, status=401)
    key = request.match_info.get("key", "")
    try:
        from shell_api_manager import delete_api_key
        ok, msg = delete_api_key(key)
    except Exception as e:
        logger.warning("delete_api_key exception: %s", e)
        return web.json_response({"ok": False, "error": str(e)}, status=500)
    try:
        await sio.emit('api_key_update', {"key": key, "set": False})
    except Exception as _e:
        logger.debug("api_key_update emit skipped: %s", _e)
    return web.json_response({"ok": ok, "message": msg}, status=200 if ok else 400)


async def get_settings_endpoint(request):
    """GET /settings → backend-visible UI settings."""
    if not _request_authorized(request):
        return web.json_response({"ok": False, "error": "Unauthorized"}, status=401)
    try:
        from shell_settings_manager import get_settings
        return web.json_response({"ok": True, "settings": get_settings()})
    except Exception as e:
        logger.warning("get_settings failed: %s", e)
        return web.json_response({"ok": False, "error": str(e)}, status=500)


async def set_settings_endpoint(request):
    """POST /settings → body {"settings": {...}}."""
    if not _request_authorized(request):
        return web.json_response({"ok": False, "error": "Unauthorized"}, status=401)
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)
    values = body.get("settings", body) if isinstance(body, dict) else {}
    try:
        from shell_settings_manager import set_settings
        ok, msg, applied = set_settings(values)
    except Exception as e:
        logger.warning("set_settings exception: %s", e)
        return web.json_response({"ok": False, "error": str(e)}, status=500)
    try:
        await sio.emit("settings_update", {"settings": applied})
    except Exception as _e:
        logger.debug("settings_update emit skipped: %s", _e)
    try:
        config.reload()
    except Exception as _e:
        logger.debug("config reload after settings update failed: %s", _e)
    return web.json_response({"ok": ok, "message": msg, "settings": applied}, status=200 if ok else 400)


async def health_endpoint(request):
    """GET /health -> startup diagnostics and recent trace/event hooks."""
    if not _request_authorized(request):
        return web.json_response({"ok": False, "error": "Unauthorized"}, status=401)
    try:
        from core.health.startup import run_startup_diagnostics
        from core.observability.events import EventBus
        from core.observability.tracing import ExecutionTracer

        diagnostics = run_startup_diagnostics()
        diagnostics["events"] = EventBus.get().recent(50)
        diagnostics["traces"] = ExecutionTracer.get().recent_traces(25)
        return web.json_response({"ok": True, "health": diagnostics})
    except Exception as e:
        logger.warning("health endpoint failed: %s", e)
        return web.json_response({"ok": False, "error": str(e)}, status=500)


async def ready_endpoint(request):
    """GET /ready -> cheap process-liveness check for launchers and probes."""
    return web.json_response({"ok": True, "status": "ready", "ts": time.time()})


async def capabilities_endpoint(request):
    """GET /capabilities -> enriched tool/agent/MCP catalog."""
    if not _request_authorized(request):
        return web.json_response({"ok": False, "error": "Unauthorized"}, status=401)
    try:
        from shell_tool_catalog import discover_capabilities
        try:
            ttl = max(1.0, float(config.get_str("SHELL_CAPABILITIES_CACHE_TTL_S") or "30"))
        except Exception:
            ttl = 30.0
        now = time.time()
        cached = _CAPABILITIES_CACHE.get("payload")
        if cached is not None and (now - float(_CAPABILITIES_CACHE.get("ts") or 0.0)) < ttl:
            return web.json_response({"ok": True, "capabilities": cached, "cached": True})

        capabilities = discover_capabilities()
        _CAPABILITIES_CACHE["ts"] = now
        _CAPABILITIES_CACHE["payload"] = capabilities
        return web.json_response({"ok": True, "capabilities": capabilities, "cached": False})
    except Exception as e:
        logger.warning("capabilities endpoint failed: %s", e)
        return web.json_response({"ok": False, "error": str(e)}, status=500)

async def system_monitor_loop():
    while True:
        try:
            cpu_val = psutil.cpu_percent(interval=None)
            ram_val = psutil.virtual_memory().percent
            gpu_val = 0
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu_val = round(gpus[0].load * 100.0, 1)
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
            stats = {
                'cpu': cpu_val,
                'ram': ram_val,
                'gpu': gpu_val,
            }
            await sio.emit('system_stats', stats)
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Monitor Error: {e}")
            await asyncio.sleep(5)

async def start_background_tasks(app):
    app['monitor_task'] = asyncio.create_task(system_monitor_loop())

async def cleanup_background_tasks(app):
    task = app.get('monitor_task')
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError as _e:
            logger.debug("ignored asyncio.CancelledError: %s", _e)

    # Close the shared aiohttp client session if shell_http opened one,
    # otherwise the connector leaks until process exit.
    try:
        from shell_http import close_async_session
        await close_async_session()
    except Exception as _e:
        logger.debug("shell_http close_async_session skipped: %s", _e)
if __name__ == '__main__':
    try:
        app.on_startup.append(start_background_tasks)
        app.on_shutdown.append(cleanup_background_tasks)
        host = config.get_str("SHELL_HUB_HOST") or "127.0.0.1"
        if not _is_loopback_bind_host(host) and not _hub_token():
            if not _truthy(config.get_str("SHELL_HUB_ALLOW_UNAUTH_REMOTE")):
                logger.warning(
                    "Refusing unauthenticated non-loopback hub bind. "
                    "Set SHELL_HUB_TOKEN or SHELL_HUB_ALLOW_UNAUTH_REMOTE=1 to override."
                )
                host = "127.0.0.1"
        port = _pick_available_port(host)
        _write_port_hint(port)
        auth_state = "token auth enabled" if _hub_token() else "no token configured"
        logger.info(f"Shell Hub starting on {host}:{port} ({auth_state}) ...")
        web.run_app(app, host=host, port=port)
    except Exception as e:
        with open("hub_error.log", "w") as f:
            f.write(f"Runtime Error: {str(e)}\n{traceback.format_exc()}")
