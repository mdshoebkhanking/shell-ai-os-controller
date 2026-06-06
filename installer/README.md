# Shell AI One-Click Installer

Use the one-click installer for your OS:

- Windows normal-user setup: double-click `shell-ai-os-controller-setup-[version].exe`
- Windows source fallback: double-click `ONE_CLICK_INSTALL.bat`
- macOS: double-click `ONE_CLICK_INSTALL.command`
- Linux: run `bash installer/install_linux.sh`

After install:

- Windows normal-user setup: launch Shell AI from Start Menu/Desktop; the shortcut runs bundled `ShellAIApp\ShellAI.exe`.
- Windows source fallback: double-click `Start_ShellAI.bat`
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

Source bootstrap behavior:

- Creates and uses a managed `.shellai_venv` virtual environment.
- Installs `requirements.txt`.
- Installs `shell_ui/requirements_ui.txt`.
- Installs `shell_web_ui/package.json` dependencies and builds `shell_web_ui/dist/index.html`.
- Requires Node.js/npm 20.19+ or 22.12+ for Web UI builds.
- Refreshes Windows PATH after winget installs and resolves `npm.cmd` directly so npm health checks and Web UI build commands use the same executable.
- Sets the modern Web UI defaults (`SHELL_LEGACY_UI=0`, `SHELL_V2_STREAM=1`) and keeps image generation usable with `SHELL_IMAGE_LOCAL_FALLBACK=1` when cloud image keys are unavailable.
- On Windows, enables balanced performance defaults for bundled offline LLM and BLAS worker pools so low-end PCs remain responsive.
- Reports cloud image provider readiness without printing secret values. Add `OPENAI_API_KEY`, `STABILITY_API_KEY`, `REPLICATE_API_KEY`, or `HUGGINGFACE_API_KEY` for real AI images.
- Installs Playwright Chromium.
- Installs ffmpeg, Tesseract OCR, uv/uvx, Python, and Node.js when the OS package manager supports it.
- Creates `.env` automatically if missing.
- Writes readable logs to `.shell_runtime/logs/`.

Python policy:

- Core Shell runtime supports Python 3.10+.
- Windows launchers prefer 3.13, 3.12, 3.11, then 3.10 automatically.
- If no compatible Python is found on Windows, the installer attempts Python 3.13 through winget.
- CursorTouch Windows-MCP desktop automation still requires Windows, Python 3.13+, and uv/uvx.

Windows validation:

- After install or repair, run `Run_Windows_Acceptance_Test.bat` for the automated health, hub, UI, voice dependency, image-provider/fallback, and Windows-MCP readiness checks.
- The automated report is written to `.shell_runtime/windows_acceptance_report.json`.

Windows setup EXE build:

- On Windows, double-click `Build_Windows_EXE.bat`.
- The builder stages a clean public installer tree under `.shell_runtime/windows_installer_staging`.
- The builder creates the React renderer build and bundles `ShellAI.exe` with PyInstaller under `ShellAIApp\`.
- NSIS / Nullsoft compiles `tools/windows_installer/ShellAI_Setup.nsi`, matching the installer family used by IRIS-style Electron releases. The Inno script remains as a fallback.
- The setup EXE is written to `dist/shell-ai-os-controller-setup-[version].exe`.
- The installer creates Start Menu shortcuts, optional desktop shortcut, optional Windows-startup shortcut, and launches the bundled app executable.
- Normal Windows users do not need Python, Node.js, npm, or a virtual environment installed separately. `ONE_CLICK_INSTALL.bat` and `Repair_ShellAI.bat` remain explicit source-mode fallback tools only.

Updates:

- Settings > System calls the desktop updater bridge.
- `SHELL_UPDATE_REPO` defaults to the public Shell AI GitHub release feed.
- `SHELL_UPDATE_MANIFEST_URL` can override the feed with custom JSON containing `version`, `releaseNotes`, `installer_url`, and optional `sha256`.
- `UPDATE NOW` only launches downloaded `.exe` installers from `.shell_runtime/updates` on Windows.
