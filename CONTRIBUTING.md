<!-- SPDX-License-Identifier: Apache-2.0 -->

# Contributing

Thanks for helping improve Shell AI OS Controller.

This project includes AI tooling, desktop automation, browser automation,
Telegram control, email, and local file operations. Contributions should be
safe, observable, and easy to test.

## Contribution Rules

- Keep dangerous actions disabled by default.
- Do not add hidden automation.
- Do not commit secrets, `.env`, tokens, logs, or private screenshots.
- Do not claim fake AI capabilities.
- Add tests for routing, safety, installer, or UI-state changes where possible.
- Keep docs beginner-friendly.

## Local Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 -m pytest -q
```

On Windows, normal users should prefer:

```text
ONE_CLICK_INSTALL.bat
Start_ShellAI.bat
```

## Pull Request Checklist

Before opening a PR:

```bash
python3 -m pytest -q
python3 tools/config_diagnostics.py --fail-on-error
python3 tools/ui_ux_audit.py --fail-on-high
python3 tools/cloud_readiness_audit.py --fail-on-high
python3 tools/agent_ecosystem_audit.py --fail-on-high
python3 tools/launch_readiness_audit.py --fail-on-high
python3 tools/public_github_launch_audit.py --fail-on-high
python3 tools/ecosystem_master_audit.py --fail-on-high
python3 tools/repo_audit.py --fail-on-high
python3 tools/production_release_check.py --strict
python3 tools/production_readiness.py
```

Also confirm:

- No secrets in the diff.
- No generated runtime folders added.
- README/docs updated if behavior changed.
- UI screenshots updated if the UI changed.
- Enterprise docs updated if config, runtime, security, plugin, or AI provider behavior changed.
- Cloud/API docs updated if routes, scopes, sync, plugins, auth, or remote behavior changed.
- Agent ecosystem docs updated if agents, autonomy, workflows, marketplace templates, memory scopes, or tool permissions changed.
- Launch/community docs updated if distribution, support, governance, website, analytics, or public-release behavior changed.

## Branch Strategy

- `main`: stable public branch.
- `develop`: integration branch for larger work after public launch.
- `feature/<short-name>`: new features.
- `fix/<short-name>`: bug fixes.
- `docs/<short-name>`: documentation-only changes.
- `release/<version>`: release preparation.

## Commit Style

Use clear commits:

```text
feat: add telegram status diagnostics
fix: prevent unsafe shell command execution
docs: improve Windows install guide
test: cover provider key errors
```

## Security Reports

Do not open public issues for secrets, remote-control bypasses, arbitrary code
execution, or unsafe automation bugs. Follow `SECURITY.md`.
