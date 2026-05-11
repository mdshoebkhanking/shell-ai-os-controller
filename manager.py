import sys
import os
import subprocess
import time
import socket
import webbrowser
import platform
import shutil
from pathlib import Path

# Fix: Force UTF-8 encoding for Windows console
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Configuration
cprint = print  # Placeholder for colored print if needed
ROOT_DIR = Path(__file__).parent.absolute()
UI_DIR = ROOT_DIR / "shell_ui"
PORT_HUB = 5000
PORT_UI = 8000

def print_banner():
    print(r"""
   _____ __         ____  _    _     __    ___ 
  / ___// /_  ___  / / / | |  / /   /  |  /  /
  \__ \/ __ \/ _ \/ / /  | | / /   / /| | / / 
 ___/ / / / /  __/ / /   | |/ /   / / | |/ /  
/____/_/ /_/\___/_/_/    |___/   /_/  |___/   
    System Manager v1.0 | AI OS Controller
    """)

def run_command(command, cwd=None, detach=False):
    """Run a system command."""
    import shlex
    if isinstance(command, str):
        cmd_list = shlex.split(command) if platform.system() != "Windows" else command.split()
    else:
        cmd_list = command

    if detach:
        creationflags = 0
        if platform.system() == "Windows":
             creationflags = subprocess.CREATE_NEW_CONSOLE
        return subprocess.Popen(cmd_list, cwd=cwd, creationflags=creationflags)

    result = subprocess.run(cmd_list, cwd=cwd, capture_output=False)
    return result.returncode == 0

def check_requirements():
    print("🔍 System Health Check...")
    
    # Check Python
    print(f"   [OK] Python {sys.version.split()[0]}")
    
    # Check PIP requirements - Use direct import to respect venv
    required_checks = [
        ('livekit', 'livekit'),
        ('flask', 'flask'),
        ('socketio', 'socketio'),
        ('requests', 'requests'),
        ('aiohttp', 'aiohttp'),
        ('aiohttp_cors', 'aiohttp_cors')
    ]
    
    missing = []
    for display_name, import_name in required_checks:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(display_name)

    if missing:
        print(f"   [WARN] Missing dependencies: {', '.join(missing)}")
        print(f"   [ACTION] Run: pip install -r requirements.txt")
        print(f"   [INFO] Skipping auto-install to avoid redundant downloads.")
        print(f"   [INFO] If you have venv, make sure it's activated before running assistant.")
    else:
        print("   [OK] All Core Modules Found")

    # Check Node.js (for UI)
    if shutil.which("npm") is None:
        print("   [ERR] Node.js (npm) not found! Web UI requires Node.js.")
        print("         Please install from https://nodejs.org/")
    else:
        print("   [OK] Node.js Environment")

    print("✔ System Ready.\n")

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def kill_port(port):
    """Kill process running on port (Windows specific for now)"""
    if not is_port_in_use(port):
        return
    
    print(f"🧹 Cleaning port {port}...")
    try:
        if platform.system() == "Windows":
            # Find PIDs using the port, then kill them
            result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    pid = parts[-1]
                    if pid.isdigit():
                        subprocess.run(["taskkill", "/f", "/pid", pid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            result = subprocess.run(["lsof", f"-ti:{port}"], capture_output=True, text=True)
            for pid in result.stdout.strip().splitlines():
                if pid.strip().isdigit():
                    subprocess.run(["kill", "-9", pid.strip()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def start_system():
    print_banner()
    check_requirements()
    
    print("🚀 Starting Shell AI Core System...")

    # 1. Kill old processes
    kill_port(PORT_HUB)
    kill_port(PORT_UI)
    kill_port(3333) # Clear legacy HTTP MCP port if an old session left it running
    kill_port(8081) # Kill LiveKit Agent default port

    python_exec = sys.executable # Get current python path (venv)

    # 2. Start SocketIO Hub
    print("   -> Launching Neural Hub (Port 5000)...")
    hub_proc = run_command(["cmd", "/k", python_exec, "shell_hub.py"], detach=True)
    time.sleep(2) # Give it a moment

    # 3. Start Agent Brain
    print("   -> Activating LiveKit Brain...")
    agent_proc = run_command(["cmd", "/k", python_exec, "agent.py", "start"], detach=True)

    # 4. Windows-MCP is started on demand over stdio by the UI/backend runner.
    # The old proprietary HTTP MCP dispatcher is intentionally not launched.
    print("   -> Windows-MCP ready on demand (uvx windows-mcp).")

    # 5. Start Modern Cinematic UI (Python)
    print(f"   -> Launching Cinematic Interface (PID Wait)...")
    ui_script = UI_DIR / "shell_cinematic_full.py"
    if ui_script.exists():
        # run python script directly (no cmd /k wrapper for cleaner launch)
        ui_proc = run_command([python_exec, str(ui_script)], detach=True)
    else:
         print("   [ERR] UI Script not found!")

    # 6. Open Browser (Optional - Removed for Native App feel)
    # webbrowser.open(f"http://localhost:{PORT_UI}")

    print("\n✅ SHELL IS LIVE. Close this window to stop.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping System...")
        # Processes in detached consoles might stay open on Windows 
        # unless manually closed or we track PIDs better.
        # For now, we assume user closes the windows or uses 'assistant stop'
        kill_port(PORT_HUB)
        kill_port(PORT_UI)

def doctor():
    print_banner()
    print("🚑 Running System Diagnostic (Dr. Shell)...")
    check_requirements()
    # Add more detailed checks here
    print("Diagnostic Complete.")

def main():
    if len(sys.argv) < 2:
        print("Usage: assistant [start|doctor|update|repair]")
        return

    command = sys.argv[1].lower()
    
    if command == "start":
        start_system()
    elif command == "doctor":
        doctor()
    elif command == "update":
        print("Updating System...")
        run_command("git pull")
        run_command("pip install -r requirements.txt")
    elif command == "stop":
        kill_port(PORT_HUB)
        kill_port(PORT_UI)
        print("All systems halted.")
    elif command == "mcp":
        print_banner()
        check_requirements()
        print("🚀 Starting CursorTouch Windows-MCP...")
        try:
            from shell_windows_mcp import windows_mcp_command
            subprocess.run(windows_mcp_command())
        except KeyboardInterrupt:
            pass
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()
