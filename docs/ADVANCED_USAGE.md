<!-- SPDX-License-Identifier: Apache-2.0 -->

# Advanced Usage

## Production Checks

```bash
python tools/repo_audit.py
python tools/production_release_check.py --strict
python tools/package_public_release.py
python tools/production_readiness.py --run-tests
```

## Environment Flags

High-risk flags should stay disabled unless you understand the impact:

```text
SHELL_ALLOW_CODE_WRITE=0
SHELL_ALLOW_AGENT_PATCH=0
SHELL_ALLOW_AGENT_BROWSER_EXEC=0
SHELL_ALLOW_OPENCLAW_SKILL_INSTALL=0
SHELL_TELEGRAM_REMOTE_CONTROL_ENABLED=0
SHELL_TELEGRAM_ALLOW_TERMINAL=0
```

## Telegram Remote Control

Telegram remote control should use:

- A private bot token.
- Explicit allowed chat IDs.
- Clear disabled-by-default terminal execution.
- Audit logs.

## Browser Automation

Agent-browser execution is blocked by default. Use dry-run first and review the
command before enabling real execution.

## Release Packaging

Public release zip is generated under `dist/`. It excludes runtime files,
secrets, venvs, local logs, and generated screenshots.
