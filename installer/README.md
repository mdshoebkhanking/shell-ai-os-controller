# Shell AI One-Click Installer

Use the one-click installer for your OS:

- Windows: double-click `ONE_CLICK_INSTALL.bat`
- macOS: double-click `ONE_CLICK_INSTALL.command`
- Linux: run `bash installer/install_linux.sh`

After install:

- Windows: double-click `Start_ShellAI.bat`
- macOS: double-click `start_shellai.command`
- Linux: run `./start_shellai.sh`

Repair tools:

- Windows: `Repair_ShellAI.bat`
- macOS: `repair_shellai.command`
- Linux: `./repair_shellai.sh`

The shared engine is `installer/bootstrap.py`:

```bash
python3 installer/bootstrap.py install --yes
python3 installer/bootstrap.py health
python3 installer/bootstrap.py repair --yes
python3 installer/bootstrap.py launch --repair-if-needed
```

Health output is saved to `.shell_runtime/install_health.json`.

Installer behavior:

- Creates and uses a managed `.shellai_venv` virtual environment.
- Installs `requirements.txt`.
- Installs `shell_ui/requirements_ui.txt`.
- Installs `shell_web_ui/package.json` dependencies and builds `shell_web_ui/dist/index.html`.
- Requires Node.js/npm 20.19+ or 22.12+ for Web UI builds.
- Refreshes Windows PATH after winget installs and resolves `npm.cmd` directly so npm health checks and Web UI build commands use the same executable.
- Installs Playwright Chromium.
- Installs ffmpeg, Tesseract OCR, uv/uvx, Python, and Node.js when the OS package manager supports it.
- Creates `.env` automatically if missing.
- Writes readable logs to `.shell_runtime/logs/`.

Python policy:

- Core Shell runtime supports Python 3.10+.
- Windows launchers prefer 3.13, 3.12, 3.11, then 3.10 automatically.
- If no compatible Python is found on Windows, the installer attempts Python 3.13 through winget.
- CursorTouch Windows-MCP desktop automation still requires Windows, Python 3.13+, and uv/uvx.
