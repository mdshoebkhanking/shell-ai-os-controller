"""
Shell MCP Server (Strict Production Mode)
-----------------------------------------
- Threaded
- Image Gen (SDXL 1.0)
- Browser Control
"""

import sys
# Fix Windows Unicode Output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass  # Non-critical: encoding reconfigure not supported

import webbrowser
import json
import urllib.parse
import sys
import logging
import os
import hmac
import ipaddress
try:
    import requests
except Exception:
    requests = None
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from datetime import datetime
try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(*args, **kwargs):
        return False

load_dotenv()

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MCP_SERVER")
MAX_BODY_BYTES = int(os.getenv("SHELL_MCP_MAX_BODY_BYTES", "1048576"))

_brain_instance = None
_autopilot_instance = None
_workflow_engine_instance = None
_memory_core_instance = None


def _get_brain():
    global _brain_instance
    if _brain_instance is None:
        from brain.core import MultiAIBrain
        _brain_instance = MultiAIBrain()
    return _brain_instance


def _get_autopilot():
    global _autopilot_instance
    if _autopilot_instance is None:
        from brain.autonomous.engine import autopilot
        _autopilot_instance = autopilot
    return _autopilot_instance


def _get_workflow_engine():
    global _workflow_engine_instance
    if _workflow_engine_instance is None:
        from brain.automation.engine import workflow_engine
        _workflow_engine_instance = workflow_engine
    return _workflow_engine_instance


def _get_memory_core():
    global _memory_core_instance
    if _memory_core_instance is None:
        from brain.memory_core import memory_core
        _memory_core_instance = memory_core
    return _memory_core_instance

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

ALLOWED_ORIGINS = {"http://localhost", "http://127.0.0.1"}

def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

def _is_loopback_bind_host(host):
    h = str(host or "").strip().lower()
    if h in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ipaddress.ip_address(h).is_loopback
    except ValueError:
        return False

def _is_allowed_origin(origin):
    """Check if the origin is a localhost origin."""
    if not origin:
        return False
    # Allow any localhost origin with any port
    for allowed in ALLOWED_ORIGINS:
        if origin == allowed or origin.startswith(allowed + ":"):
            return True
    return False

class MCPHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        origin = self.headers.get("Origin", "")
        self.send_response(204)
        if _is_allowed_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_POST(self):
        try:
            if not self._authorized():
                self.send_error(401, "Unauthorized")
                return

            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self.send_error(400, "Empty Body")
                return
            if content_length > MAX_BODY_BYTES:
                self.send_error(413, "Body too large")
                return

            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return
            action = data.get("action", "")
            
            logger.info(f"⚡ ACTION: {action}")
            
            response = {"status": "error", "message": "Unknown action"}

            if action == "open_youtube":
                response = self.handle_youtube(data)
            elif action == "open_google":
                response = self.handle_google(data)
            elif action == "open_url":
                response = self.handle_open_url(data)
            elif action == "generate_image":
                response = self.handle_generate_image(data)
            elif action == "ask_brain":
                response = self.handle_ask_brain(data)
            
            # --- NEW CAPABILITIES ---
            elif action == "autopilot":
                response = self.handle_autopilot(data)
            elif action == "run_workflow":
                response = self.handle_workflow(data)
            elif action == "remember":
                response = self.handle_memory_add(data)
            elif action == "recall":
                response = self.handle_memory_search(data)
                
            elif action == "ingest_knowledge":
                response = self.handle_ingest_knowledge(data)
            elif action == "rag_ask":
                response = self.handle_rag_ask(data)
            elif action == "list_capabilities":
                response = self.handle_list_capabilities(data)
            elif action == "run_tool":
                response = self.handle_run_tool(data)
                
            elif action == "test":
                response = {"status": "success", "message": "MCP OK - Shell v2.0 Ready"}
                
            self.send_json(response)
            
        except Exception as e:
            logger.error(f"Server Error: {e}")
            self.send_error(500, str(e))

    def send_json(self, data):
        origin = self.headers.get("Origin", "")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        if _is_allowed_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _authorized(self):
        """Require a bearer token when SHELL_MCP_TOKEN is configured."""
        expected = os.getenv("SHELL_MCP_TOKEN", "").strip()
        if not expected:
            return True
        header = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not header.startswith(prefix):
            return False
        return hmac.compare_digest(header[len(prefix):].strip(), expected)

    def handle_youtube(self, data):
        search = data.get("search", "").strip()
        if search:
            url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(search)}"
            msg = f"Searching YouTube: {search}"
        else:
            url = "https://www.youtube.com"
            msg = "Opened YouTube Home"
        
        webbrowser.open(url)
        return {"status": "success", "message": msg}

    def handle_google(self, data):
        search = data.get("search", "").strip()
        if search:
            url = f"https://www.google.com/search?q={urllib.parse.quote(search)}"
            msg = f"Searching Google: {search}"
        else:
            url = "https://www.google.com"
            msg = "Opened Google Home"
            
        webbrowser.open(url)
        return {"status": "success", "message": msg}

    def handle_open_url(self, data):
        url = data.get("url", "").strip()
        if not url: return {"status": "error", "message": "No URL provided"}
        
        if not url.startswith("http"):
            url = "https://" + url
        try:
            from shell_downloader import _validate_url
            ok, reason = _validate_url(url)
            if not ok:
                return {"status": "error", "message": f"URL rejected: {reason}"}
        except Exception as e:
            return {"status": "error", "message": f"URL validation failed: {e}"}
            
        webbrowser.open(url)
        return {"status": "success", "message": f"Opened {url}"}

    def handle_generate_image(self, data):
        prompt = data.get("prompt", "")
        if not prompt: return {"status": "error", "message": "No prompt"}
        
        logger.info(f"🎨 Generating: {prompt}")
        
        API_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
        api_key = os.getenv("HUGGINGFACE_API_KEY") or os.getenv("HF_API_KEY")
        
        if not api_key:
            return {"status": "error", "message": "Missing HUGGINGFACE_API_KEY or HF_API_KEY"}
        if requests is None:
            return {"status": "error", "message": "Missing Python dependency: requests"}
            
        headers = {"Authorization": f"Bearer {api_key}"}
        
        try:
            r = requests.post(API_URL, headers=headers, json={"inputs": prompt}, timeout=45)
            if r.status_code != 200:
                return {"status": "error", "message": f"HF Error: {r.text}"}
                
            filename = f"gen_{int(datetime.now().timestamp())}.png"
            with open(filename, "wb") as f:
                f.write(r.content)
            
            if os.name == 'nt':
                # Validate filename before opening
                if '..' in filename or not os.path.exists(filename):
                    return {"status": "error", "message": "Invalid or non-existent file"}
                os.startfile(filename)
                
            return {"status": "success", "message": f"Image generated: {filename}"}
        except Exception as e:
            return {"status": "error", "message": f"Gen Error: {e}"}

    def handle_ask_brain(self, data):
        prompt = data.get("prompt", "")
        mode = data.get("mode", "SMART") # Default to SMART
        
        if not prompt: 
            return {"status": "error", "message": "No prompt provided"}
            
        logger.info(f"🧠 Asking Brain ({mode}): {prompt[:50]}...")
        
        try:
            # Sync wrapper for now
            response_text = _get_brain().generate_response_sync(prompt, mode=mode)
            return {"status": "success", "response": response_text, "mode": mode}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # --- NEW HANDLERS ---
    def handle_ingest_knowledge(self, data):
        """Ingests a file or folder into the RAG brain."""
        path = data.get("path")
        recursive = data.get("recursive", True)
        
        if not path: return {"status": "error", "message": "No path provided"}
        
        memory_core = _get_memory_core()
        if os.path.isfile(path):
            res = memory_core.ingest_file(path)
        elif os.path.isdir(path):
            res = memory_core.ingest_folder(path, recursive=recursive)
        else:
            return {"status": "error", "message": "Invalid path"}
            
        return {"status": "success", "message": res}

    def handle_rag_ask(self, data):
        """RAG Query: Search Memory -> Generate Answer."""
        prompt = data.get("prompt", "")
        if not prompt: return {"status": "error", "message": "No prompt"}
        
        # 1. Retrieve
        memory_core = _get_memory_core()
        context_docs = memory_core.search_memory(prompt, top_k=3)
        context_text = "\n\n".join([d['text'] for d in context_docs])
        
        if not context_text:
            context_text = "No relevant documents found."
            
        # 2. Augment Prompt
        rag_prompt = f"""
        CONTEXT FROM KNOWLEDGE BASE:
        {context_text}
        
        USER QUESTION:
        {prompt}
        
        INSTRUCTIONS:
        Answer the user's question based ONLY on the context provided above. 
        If the answer is not in the context, say so, but try to be helpful.
        """
        
        # 3. Generate
        logger.info(f"🧠 RAG Asking: {prompt[:50]}...")
        try:
             response_text = _get_brain().generate_response_sync(rag_prompt)
             return {"status": "success", "response": response_text, "context_used": len(context_docs)}
        except Exception as e:
             return {"status": "error", "message": str(e)}

    def handle_autopilot(self, data):
        """Triggers AutoPilot for a goal."""
        goal = data.get("goal")
        if not goal: return {"status": "error", "message": "No goal provided"}
        
        # Note: AutoPilot is async. In this sync server, we might block or need loop management.
        # For simplicity in this 'No-Install' environment, we try to run it.
        # Ideally, this should offload to a background thread.
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(_get_autopilot().engage(goal))
            finally:
                loop.close()
            return {"status": "success", "report": result}
        except Exception as e:
             return {"status": "error", "message": str(e)}

    def handle_workflow(self, data):
        """Triggers a Workflow."""
        name = data.get("name")
        if not name: return {"status": "error", "message": "No workflow name provided"}
        
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(_get_workflow_engine().execute_workflow(name))
            finally:
                loop.close()
            return {"status": "success", "report": result}
        except Exception as e:
             return {"status": "error", "message": str(e)}

    def handle_memory_add(self, data):
        text = data.get("text")
        if not text: return {"status": "error", "message": "No text"}
        memory_core = _get_memory_core()
        memory_core.add_memory(text, meta={"source": "mcp_api"})
        return {"status": "success", "message": "Memory Saved"}

    def handle_memory_search(self, data):
        query = data.get("query")
        if not query: return {"status": "error", "message": "No query"}
        memory_core = _get_memory_core()
        results = memory_core.search_memory(query)
        return {"status": "success", "results": results}

    def handle_list_capabilities(self, data):
        """Return MCP actions plus statically discovered backend tools."""
        try:
            from shell_tool_catalog import discover_capabilities
            return discover_capabilities()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def handle_run_tool(self, data):
        """Run a decorated backend tool by catalog id via the safe gateway."""
        tool_id = data.get("tool") or data.get("tool_id") or data.get("name")
        args = data.get("args", {})
        if not tool_id:
            return {"status": "error", "message": "No tool id provided"}
        try:
            from shell_tool_gateway import execute_tool_sync
            return execute_tool_sync(str(tool_id), args)
        except Exception as e:
            return {"status": "error", "message": str(e), "tool": tool_id}

    def log_message(self, format, *args):
        return

def run(port=3333):
    host = os.getenv("SHELL_MCP_HOST", "127.0.0.1").strip() or "127.0.0.1"
    if not _is_loopback_bind_host(host) and not os.getenv("SHELL_MCP_TOKEN", "").strip():
        if not _truthy(os.getenv("SHELL_MCP_ALLOW_UNAUTH_REMOTE")):
            logger.warning(
                "Refusing unauthenticated non-loopback MCP bind. Set SHELL_MCP_TOKEN "
                "or SHELL_MCP_ALLOW_UNAUTH_REMOTE=1 to override."
            )
            host = "127.0.0.1"

    server = ThreadingHTTPServer((host, port), MCPHandler)
    auth_state = "token auth enabled" if os.getenv("SHELL_MCP_TOKEN", "").strip() else "no token configured"
    logger.info(f"🚀 MCP Server running on {host}:{port} ({auth_state})")
    try:
        server.serve_forever()
    except Exception as _e:
        logger.debug("ignored Exception: %s", _e)

if __name__ == "__main__":
    run()
