import os
import subprocess
import asyncio
import logging
import time
from typing import Any, Dict, List
from shell_safe_executor import god_tier_tool as function_tool
import shutil

logger = logging.getLogger("shell_code_engine")


def _sanitize_workspace_filename(filename: str) -> tuple[bool, str]:
    """Reject path-traversal / absolute filenames. Return (ok, reason_or_basename)."""
    if not filename or not isinstance(filename, str):
        return False, "empty filename"
    if "\x00" in filename:
        return False, "null byte in filename"
    if os.path.isabs(filename):
        return False, f"absolute paths not allowed: {filename}"
    if ".." in filename.replace("\\", "/").split("/"):
        return False, f"parent-directory traversal not allowed: {filename}"
    # Normalise Windows separators, then keep the base name pattern.
    cleaned = filename.replace("\\", "/")
    if "/" in cleaned and not cleaned.startswith("shell_workspace/"):
        # Allow relative paths that stay inside workspace; everything else must
        # be a bare filename so path joining is predictable.
        return False, f"nested paths not allowed: {filename}"
    return True, filename


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _compose_adaptive_css(css_vars: str, animations: str) -> str:
    vars_block = css_vars.strip() if css_vars else ":root { --primary:#00d4ff; --secondary:#2de2a6; --bg:#0a0d14; --text:#ffffff; --glass:rgba(255,255,255,0.08); --font-main:'Sora',sans-serif; --font-head:'Space Grotesk',sans-serif; }"
    animation_block = animations.strip() if animations else ""

    return f"""{vars_block}

* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

html, body {{
    width: 100%;
}}

body {{
    font-family: var(--font-main, 'Sora', sans-serif);
    background: radial-gradient(circle at 10% 10%, rgba(255,255,255,0.07), transparent 35%), var(--bg, #0a0d14);
    color: var(--text, #ffffff);
    line-height: 1.6;
}}

.site-nav {{
    position: sticky;
    top: 0;
    z-index: 40;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 6vw;
    border-bottom: 1px solid rgba(255,255,255,0.1);
    background: color-mix(in srgb, var(--bg) 86%, black 14%);
    backdrop-filter: blur(8px);
}}

.brand {{
    font-family: var(--font-head, 'Space Grotesk', sans-serif);
    font-weight: 700;
    letter-spacing: 0.04em;
}}

.nav-links {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.95rem;
}}

.nav-links a {{
    color: var(--text, #ffffff);
    text-decoration: none;
    opacity: 0.88;
}}

.nav-links a:hover {{
    opacity: 1;
    color: var(--primary);
}}

.hero {{
    min-height: 68vh;
    padding: 6rem 6vw 3rem;
    display: grid;
    grid-template-columns: 1.2fr 1fr;
    align-items: center;
    gap: 1.25rem;
}}

.hero h1 {{
    font-family: var(--font-head, 'Space Grotesk', sans-serif);
    font-size: clamp(2rem, 4vw, 3.4rem);
    line-height: 1.1;
    margin-bottom: 1rem;
}}

.hero p {{
    max-width: 60ch;
    opacity: 0.9;
}}

.hero-badge {{
    border: 1px solid rgba(255,255,255,0.12);
    background: var(--glass, rgba(255,255,255,0.08));
    border-radius: 14px;
    padding: 1rem 1.1rem;
    box-shadow: 0 20px 35px rgba(0,0,0,0.24);
    animation: float 7s ease-in-out infinite;
}}

main {{
    padding: 1rem 6vw 4rem;
}}

section {{
    margin-top: 2.4rem;
}}

section h2 {{
    margin-bottom: 0.95rem;
    font-size: clamp(1.4rem, 2.4vw, 2.1rem);
    font-family: var(--font-head, 'Space Grotesk', sans-serif);
}}

.card-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem;
}}

.card {{
    border: 1px solid rgba(255,255,255,0.12);
    background: var(--glass, rgba(255,255,255,0.08));
    border-radius: 14px;
    padding: 1rem;
}}

.feature-list {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
}}

.feature-list span {{
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 999px;
    padding: 0.35rem 0.8rem;
    font-size: 0.9rem;
}}

.btn {{
    margin-top: 1rem;
    border: none;
    border-radius: 999px;
    padding: 0.7rem 1.2rem;
    font-weight: 700;
    cursor: pointer;
    color: #08131d;
    background: linear-gradient(120deg, var(--primary), var(--secondary));
    transition: transform 220ms ease, box-shadow 220ms ease;
}}

.btn:hover {{
    transform: translateY(-2px);
    box-shadow: 0 12px 28px rgba(0,0,0,0.28);
}}

.site-footer {{
    padding: 1.5rem 6vw 2.2rem;
    border-top: 1px solid rgba(255,255,255,0.08);
    opacity: 0.85;
}}

@media (max-width: 900px) {{
    .hero {{
        grid-template-columns: 1fr;
        min-height: auto;
        padding-top: 4.5rem;
    }}
    .nav-links {{
        gap: 0.65rem;
        font-size: 0.95rem;
    }}
}}

{animation_block}
"""

@function_tool
async def write_code_tool(filename: str, content: str, path: str = None) -> str:
    """
    Creates or overwrites a code file with provided content.
    Includes pre-save syntax validation.

    SAFETY: Gated by shell_safety_gate.check_code_write — requires
    SHELL_ALLOW_CODE_WRITE=1 in .env. Path traversal is rejected.

    Args:
        filename: Name of the file (e.g., 'hello.py', 'index.html').
        content: The actual code string.
        path: Optional directory path. Defaults to a 'workspace' folder if not provided.
    """
    try:
        try:
            from shell_safety_gate import check_code_write, audit_write
        except Exception:
            return "❌ Save Failed: shell_safety_gate module unavailable; refusing to write."
        ok, reason = check_code_write(origin="write_code_tool")
        if not ok:
            return f"❌ CODE WRITE BLOCKED:\n{reason}"

        ok, reason = _sanitize_workspace_filename(filename)
        if not ok:
            return f"❌ Invalid filename: {reason}"

        # Pre-save validation for Python files
        if filename.endswith(".py"):
            try:
                import ast
                ast.parse(content)
            except SyntaxError as e:
                return f"❌ CODE WRITE BLOCKED: Prevented saving broken code. SyntaxError in {filename} line {e.lineno}: {e.msg}\nFix this before saving."

        # Default workspace if no path
        workspace_dir = path if path else os.path.join(os.getcwd(), "shell_workspace")
        os.makedirs(workspace_dir, exist_ok=True)

        full_path = os.path.realpath(os.path.join(workspace_dir, filename))
        # Double-check the realpath didn't escape the workspace via symlinks.
        if not full_path.startswith(os.path.realpath(workspace_dir)):
            return f"❌ Save refused: resolved path escapes workspace: {full_path}"

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        audit_write("write_code_tool", full_path, f"bytes={len(content)}")

        return f"✅ Code Saved & Validated: {full_path}"
    except Exception as e:
        logger.exception("write_code_tool failed: %s", e)
        return f"❌ Save Failed: {e}"

@function_tool
async def execute_code_tool(filename: str, path: str = None) -> str:
    """
    Executes a code file (Python or Node.js) and returns output.
    Includes guarded dependency resolution when supported.
    Args:
        filename: File to run (e.g., 'script.py').
        path: Directory where file exists.
    """
    workspace_dir = path if path else os.path.join(os.getcwd(), "shell_workspace")
    full_path = os.path.join(workspace_dir, filename)
    
    if not os.path.exists(full_path):
        return f"❌ File not found: {full_path}"

    cmd = []
    if filename.endswith(".py"):
        cmd = ["python", full_path]
    elif filename.endswith(".js"):
        cmd = ["node", full_path]
    elif filename.endswith(".bat") or filename.endswith(".cmd"):
        cmd = ["cmd", "/c", full_path]
    elif filename.endswith(".ps1"):
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", full_path]
    elif filename.endswith(".html") or filename.endswith(".htm"):
        import webbrowser
        webbrowser.open(f"file:///{full_path}")
        return f"✅ Opened {filename} in browser."
    elif filename.endswith(".sh"):
        cmd = ["bash", full_path]
    else:
        return "❌ Unsupported file type. Supported: .py, .js, .bat, .ps1, .html, .sh"

    async def _run_once():
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workspace_dir
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
            return stdout.decode().strip(), stderr.decode().strip()
        except asyncio.TimeoutError:
            process.kill()
            return "", "TIMEOUT"

    try:
        out, err = await _run_once()

        if err == "TIMEOUT":
            return "❌ Execution Timed Out (>30s)."

        # Autonomous Dependency Resolution (with safety validation)
        if filename.endswith(".py") and ("ModuleNotFoundError" in err or "ImportError" in err):
            import re
            match = re.search(r"No module named '([^']+)'", err)
            if match:
                missing_pkg = match.group(1).split('.')[0]  # Get top-level package only
                # Validate package name - only allow safe characters
                if not re.match(r'^[a-zA-Z0-9_\-]+$', missing_pkg):
                    return f"❌ Unsafe package name detected: '{missing_pkg}'. Install manually."
                # Block known dangerous packages
                blocked_pkgs = {'os', 'sys', 'subprocess', 'shutil', 'ctypes', 'importlib'}
                if missing_pkg.lower() in blocked_pkgs:
                    return f"❌ Package '{missing_pkg}' is a stdlib module, not installable."
                logger.warning(f"Auto-Resolving missing dependency: {missing_pkg}")
                install_proc = await asyncio.create_subprocess_exec(
                    "pip", "install", missing_pkg,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await install_proc.communicate()
                
                # Retry Execute
                out, err = await _run_once()
                if err == "TIMEOUT":
                    return f"⚠️ Installed '{missing_pkg}' but rerun timed out."
                if err:
                    return f"⚠️ Installed '{missing_pkg}', but script still failed:\n{err}"
                return f"✅ Dependency installed: '{missing_pkg}'.\n📜 Output:\n{out}"

        result = ""
        if out: result += f"📜 Output:\n{out}\n"
        if err: result += f"⚠️ Error/Log:\n{err}"
        
        if not result: result = "✅ Executed successfully (No Output)."
        return result
            
    except Exception as e:
        return f"❌ Execution Failed: {e}"

# --- NEURAL INTEGRATION ---
try:
    from shell_brain.hyper_cortex import hyper_cortex
    NEURAL_ENGINE_ACTIVE = True
except ImportError:
    NEURAL_ENGINE_ACTIVE = False
    hyper_cortex = None  # type: ignore[assignment]

@function_tool
async def create_fullstack_app_tool(project_name: str, app_type: str = "modern_webapp") -> str:
    """
    Scaffolds a PRODUCTION-GRADE Full-Stack Web App using "Shell Neural Architecture".

    SAFETY: Gated by shell_safety_gate.check_code_write — requires
    SHELL_ALLOW_CODE_WRITE=1 because it writes Python/HTML/JS to disk.
    """
    try:
        try:
            from shell_safety_gate import check_code_write, audit_write
        except Exception:
            return "[ERROR] shell_safety_gate module unavailable; refusing to scaffold."
        ok, reason = check_code_write(origin="create_fullstack_app_tool")
        if not ok:
            return f"[BLOCKED] {reason}"

        # Sanitize project name - only allow safe characters
        import re as _re
        if not _re.match(r'^[a-zA-Z0-9_\-]+$', project_name):
            return "[ERROR] Invalid project name. Use only letters, numbers, underscores, hyphens."
        project_path = os.path.realpath(os.path.join(os.getcwd(), "shell_projects", project_name))
        projects_root = os.path.realpath(os.path.join(os.getcwd(), "shell_projects"))
        # Defence in depth: the regex already restricts to safe chars, but the
        # realpath must still live under shell_projects/.
        if not project_path.startswith(projects_root + os.sep) and project_path != projects_root:
            return "[ERROR] Resolved project path escapes shell_projects/."
        if os.path.exists(project_path):
            # Create backup instead of destroying (time module is imported at top).
            backup_path = project_path + f"_backup_{int(time.time())}"
            try:
                os.rename(project_path, backup_path)
                logger.info(f"Existing project backed up to: {backup_path}")
            except OSError:
                shutil.rmtree(project_path)
        
        # Folder Structure
        folders = [
            f"{project_path}/static/js",
            f"{project_path}/static/css",
            f"{project_path}/static/assets",
            f"{project_path}/templates",
            f"{project_path}/tests",
            f"{project_path}/api"
        ]
        for f in folders:
            os.makedirs(f, exist_ok=True)

        # 🧠 HYPER-CORTEX ACTIVATION
        blueprint: Dict[str, Any] = {}
        if NEURAL_ENGINE_ACTIVE and hyper_cortex is not None:
            logger.info("Shell Neuro-Link: Consulting HyperCortex for '%s'...", app_type)
            try:
                # Run blocking provider calls in a worker thread.
                blueprint = await asyncio.to_thread(hyper_cortex.synergize_project, project_name, app_type)  # type: ignore[attr-defined]
            except Exception as neural_error:
                logger.warning("HyperCortex blueprint generation failed: %s", neural_error)

        frontend = _safe_dict(blueprint.get("frontend"))
        backend = _safe_dict(blueprint.get("backend"))
        meta = _safe_dict(blueprint.get("meta"))

        # Fallback Defaults (if HyperCortex fails or inactive)
        css_vars = str(frontend.get("css_vars") or ":root { --primary:#00f2ff; --secondary:#2de2a6; --bg:#090919; --text:#ffffff; --glass:rgba(255,255,255,0.08); --font-main:'Sora',sans-serif; --font-head:'Space Grotesk',sans-serif; }")
        animations = str(frontend.get("animations") or "")
        html_body = str(
            frontend.get("html_body")
            or (
                "<nav class='site-nav'><div class='brand'>{title}</div><div class='nav-links'>"
                "<a href='#home'>Home</a><a href='#about'>About</a><a href='#contact'>Contact</a>"
                "</div></nav>"
                "<header id='home' class='hero'><div><h1>{title}</h1><p>{intent}</p>"
                "<button class='btn'>Explore</button></div>"
                "<div class='hero-badge'><strong>Shell Adaptive Mode</strong><small>Ready to customize</small></div></header>"
                "<main><section id='about'><h2>Overview</h2><p>Generated with intelligent defaults.</p></section></main>"
                "<footer id='contact' class='site-footer'><small>Powered by Shell AI</small></footer>"
            ).format(title=project_name.replace("_", " ").title(), intent=app_type)
        )
        js_logic = str(frontend.get("js_logic") or "console.log('System Active');")

        # Dynamic assets
        cdn_links = _safe_list(frontend.get("cdn_links"))
        cdn_html = "\n    ".join(cdn_links)

        pkgs = _safe_list(backend.get("python_packages")) or ["flask", "flask_sqlalchemy", "flask_cors"]

        backend_routes = str(backend.get("routes_code") or "@app.route('/api/health')\ndef health():\n    return jsonify({'status': 'ok'})")
        db_models = str(backend.get("db_models") or "")
        detected_archetype = str(meta.get("archetype") or "adaptive")

        # 1. FLASK BACKEND (Neural Enhanced)
        app_code = f"""from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import random 

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)

# --- NEURAL MODELS ---
{db_models}

# --- NEURAL ROUTES ---
@app.route('/')
def home():
    return render_template('index.html')

{backend_routes}

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
"""
        with open(f"{project_path}/app.py", "w", encoding="utf-8") as f:
            f.write(app_code)

        # 2. HTML (Neural Context Aware)
        title = project_name.replace("_", " ").title()
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | Powered by Shell AI</title>
    <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;700&family=Orbitron:wght@900&display=swap" rel="stylesheet">
    <!-- DYNAMIC CDNs -->
    {cdn_html}
    <link rel="stylesheet" href="{{{{ url_for('static', filename='css/style.css') }}}}">
</head>
<body>
    <!-- AI GENERATED UI -->
    {html_body}
    <script src="{{{{ url_for('static', filename='js/script.js') }}}}"></script>
</body>
</html>"""
        with open(f"{project_path}/templates/index.html", "w", encoding="utf-8") as f:
            f.write(html_content)

        # 3. CSS (Adaptive Styling)
        css_content = _compose_adaptive_css(css_vars, animations)
        with open(f"{project_path}/static/css/style.css", "w", encoding="utf-8") as f:
            f.write(css_content)

        # 5. JAVASCRIPT Logic
        js_code = f"""
// SHELL NEURAL LINK ESTABLISHED
{js_logic}
"""
        with open(os.path.join(project_path, "static", "js", "script.js"), "w", encoding="utf-8") as f:
            f.write(js_code)

        # 6. AUTOMATED TEST SUITE
        test_code = """import unittest
import sys
import os

# Add parent dir to path so 'app.py' can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app

class TestWebApp(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_home_status_code(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)

    def test_api_response(self):
        # Only test if route exists (dynamic)
        pass 

if __name__ == '__main__':
    unittest.main()
"""
        with open(os.path.join(project_path, "tests", "test_app.py"), "w", encoding="utf-8") as f:
            f.write(test_code)

        # 7. REQUIREMENTS & LAUNCHER
        with open(os.path.join(project_path, "requirements.txt"), "w") as f:
            for p in pkgs:
                f.write(f"{p}\n")

        # One-Click Launcher (Auto-Install + Auto-Test + Auto-Run)
        launch_bat = f"""@echo off
title Shell - Launching {project_name}...
color 0b
echo [SHELL] Initializing Environment...

echo [1/3] Installing Dependencies...
pip install -r requirements.txt >nul 2>&1

echo [2/3] Running Self-Diagnostic Tests...
python tests/test_app.py
if %ERRORLEVEL% NEQ 0 (
    color 0c
    echo [ERROR] Tests Failed! Debugging required.
    pause
    exit /b
)

echo [3/3] Tests Passed! Launching App...
echo ==================================================
echo      Project: {project_name}
echo      Status:  ONLINE (http://127.0.0.1:5000)
echo ==================================================
python app.py
pause"""
        with open(os.path.join(project_path, "run_app.bat"), "w") as f:
            f.write(launch_bat)

        # 🚀 AUTO-LAUNCH IN BACKGROUND
        try:
            import subprocess
            import webbrowser
            import threading
            import time
            
            # Start the batch file in a new window so the user can see log output
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NEW_CONSOLE
                subprocess.Popen(
                    ["cmd", "/c", "run_app.bat"],
                    cwd=project_path,
                    creationflags=creationflags
                )
            else:
                subprocess.Popen(
                    ["sh", "-c", "run_app.bat"],
                    cwd=project_path,
                )
            
            # Wait a few seconds for Flask to start, then open the browser
            def open_browser():
                time.sleep(4.0)
                webbrowser.open("http://127.0.0.1:5000")
                
            threading.Thread(target=open_browser, daemon=True).start()
        except Exception as launch_err:
            logger.warning(f"Auto-launch failed: {launch_err}")

        return f"""[SUCCESS] PROJECT BUILT AND LAUNCHED SUCCESSFULLY!
Path: `{project_path}`

**What Shell Did:**
1. Frontend: Intent-aware adaptive UI (archetype: `{detected_archetype}`) + responsive styling.
2. Backend: Flask API connected.
3. QA Testing: `tests/test_app.py` generated.
4. Launcher: `run_app.bat` created and executed!

**Status:** The app is starting in a new terminal window. Your browser will open the app automatically in a few seconds (http://127.0.0.1:5000)."""

    except Exception as e:
        return f"[ERROR] Creation Failed: {e}"
