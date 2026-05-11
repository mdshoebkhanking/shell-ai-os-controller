<!-- SPDX-License-Identifier: Apache-2.0 -->

# Developer Guide

## Local Setup

```bash
python -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
python -m pytest -q
```

On Windows, use:

```text
ONE_CLICK_INSTALL.bat
Start_ShellAI.bat
```

## Fast CI Setup

For repository checks without full optional desktop/media dependencies:

```bash
python -m pip install -r requirements-ci.txt
python -m pytest -q
```

## Important Commands

```bash
python tools/repo_audit.py
python tools/production_release_check.py --strict
python tools/package_public_release.py
python tools/production_readiness.py --run-tests
python -m pytest -q
```

## Development Principles

- Keep automation permission-aware.
- Do not hide tool execution.
- Return structured errors.
- Keep UI responsive.
- Keep user secrets out of logs and screenshots.
- Add tests for safety, routing, installer, and packaging changes.

## Where To Work

| Area | Files |
| --- | --- |
| UI | `shell_ui/` |
| Agent runtime | `agent.py`, `brain/`, `core/` |
| Tool execution | `shell_tool_gateway.py`, `shell_safe_executor.py` |
| Telegram | `shell_telegram.py` |
| Installer | `installer/`, `ONE_CLICK_INSTALL.*`, `Start_ShellAI.bat` |
| Release | `tools/package_public_release.py`, `tools/production_readiness.py` |

## Pull Request Flow

1. Create a feature/fix/docs branch.
2. Make small focused changes.
3. Run tests and release checks.
4. Update docs if behavior changed.
5. Open PR using the template.
