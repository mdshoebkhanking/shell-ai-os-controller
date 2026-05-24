# Shell AI Public Release Guide

This repository can now produce a guarded public release candidate. The release
process is intentionally strict: it validates installer assets, the React Shell
Web UI build, safe defaults, runtime health, and secret exclusion before
anything is marked publishable.

## Release Status

Current version: `1.0.0`

Project creator: `mdshoebking`

License: `Apache-2.0`

Current status: CI and Security are green on GitHub, including the Python
3.10-3.13 test matrix, Release integrity, CodeQL, secret-pattern guard, and
Python dependency audit. This build is intended for public testing after the
release check passes on the target OS.

## Product Launch References

Before making the repository public, review:

- `docs/PRODUCT_EXPERIENCE.md`
- `DESIGN.md`
- `docs/TRUST_AND_CREDIBILITY.md`
- `docs/PUBLIC_LAUNCH_PLAN.md`
- `docs/CURRENT_REPO_STATUS.md`
- `docs/MEDIA_KIT.md`
- `docs/WEBSITE_PLAN.md`
- `docs/ECOSYSTEM_ROADMAP.md`
- `docs/ENTERPRISE_ARCHITECTURE_REVIEW.md`
- `docs/AI_INFRASTRUCTURE_PLAN.md`
- `docs/CONFIGURATION_SYSTEM.md`
- `docs/ENTERPRISE_SECURITY_PREP.md`

These files keep product language, onboarding, launch claims, and future
roadmap expectations consistent.

Primary current media for the public repository:

- `videos/shell-current-ui-landscape-demo.mp4`
- `videos/shell-current-ui-landscape-poster.png`
- `screenshots/current/`

The landscape demo is English-only and 16:9. Older vertical/current-state and
classic cinematic videos remain available as secondary media.

## One-Click User Flow

Windows:

1. Run `ONE_CLICK_INSTALL.bat`.
2. Run `Start_ShellAI.bat`.
3. If anything breaks, run `Repair_ShellAI.bat`.

macOS:

1. Run `ONE_CLICK_INSTALL.command`.
2. Run `start_shellai.command`.
3. If anything breaks, run `repair_shellai.command`.

Linux:

1. Run `start_shellai.sh` after dependencies are installed by the bootstrapper.
2. Run `repair_shellai.sh` if dependencies need repair.

## Public Release Gate

Run:

```bash
python3 tools/production_release_check.py
```

The report is written to:

```text
.shell_runtime/production_release_report.json
```

The release gate checks:

- `.env.example` safe defaults
- installer and launcher files
- `.gitignore` secret protection
- runtime health
- Windows-MCP readiness checks
- production safety blockers

Use strict mode before uploading a package:

```bash
python3 tools/production_release_check.py --strict
```

Strict mode fails if your local `.env` enables unsafe development flags. This
is expected if you recently enabled browser automation, terminal tools, or
Telegram remote control for testing.

## Build The Public Zip

macOS/Linux:

```bash
python3 tools/package_public_release.py
```

Windows:

```bat
python tools\package_public_release.py
```

Or double-click:

```text
Build_Public_Release.command
Build_Public_Release.bat
```

The generated package is written to:

```text
dist/shell-ai-os-controller-1.0.0.zip
```

Every public source or zip release must include:

- `LICENSE`
- `NOTICE`
- `LEGAL.md`
- `SECURITY.md`
- `THIRD_PARTY_NOTICES.md`

## Production Readiness Score

After building the package, run:

```bash
python3 tools/production_readiness.py --run-tests
```

This produces an automated local score out of 100 and writes:

```text
.shell_runtime/production_readiness_report.json
```

The automated score covers code/package health, safety defaults, focused tests,
docs, and release integrity. Final public GA still requires external validation
on a clean Windows PC, installer/code-signing checks, and non-developer user
acceptance testing.

## Windows Fresh-Install Acceptance Test

On a clean Windows/RDP machine, extract the release zip and run:

```bat
Run_Windows_Acceptance_Test.bat
```

This runs the same one-click bootstrap path a normal user uses, then writes:

```text
.shell_runtime\windows_acceptance_report.json
```

The automated Windows probe validates install health, Shell Hub startup, Shell
Web UI rendering, voice dependencies, Windows audio readiness, and Windows-MCP
readiness. It does not replace the visible user test. After it finishes, start
`Start_ShellAI.bat` and manually confirm chat, voice audio, app open/close,
Gallery image rendering, Telegram status, and settings persistence through the
real UI.

## Signing And Notarization Readiness

Run:

```bash
./Check_Release_Signing.command
```

or on Windows:

```bat
Check_Release_Signing.bat
```

The report is written to:

```text
.shell_runtime/signing_notarization_report.json
```

This check is intentionally honest. It reports `BLOCKED` unless the machine has
the required Apple Developer ID/notarization credentials and Windows signing
certificate/tooling. Do not mark a final public GA build as signed/notarized
until the real signing step has completed.

## Production Safety

For a packaged release, unsafe actions must remain disabled unless the user
explicitly enables them later:

- `SHELL_ALLOW_CODE_WRITE=0`
- `SHELL_ALLOW_AGENT_PATCH=0`
- `SHELL_ALLOW_TERMINAL_EXEC=0`
- `SHELL_ALLOW_WORKFLOW_COMMANDS=0`
- `SHELL_ALLOW_WORKFLOW_FILE_WRITE=0`
- `SHELL_ALLOW_AGENT_BROWSER_EXEC=0`
- `SHELL_ALLOW_OPENCLAW_SKILL_INSTALL=0`
- `SHELL_HUB_ALLOW_UNAUTH_REMOTE=0`
- `SHELL_MCP_ALLOW_UNAUTH_REMOTE=0`
- `SHELL_TELEGRAM_ALLOW_TERMINAL=0`

If `SHELL_PRODUCTION_MODE=1` or `SHELL_PUBLIC_RELEASE=1`, Shell refuses to
launch when these production blockers are enabled.

## What Not To Ship

Do not include:

- `.env`
- `.shell_runtime/`
- `.shell_chat_history/`
- `node_modules/`
- virtual environments
- logs
- screenshots created during local testing
- user-generated files under `shell_downloads/`

## Minimum Release Checklist

- Run the production release check.
- Run installer health.
- Start hub and UI from launcher.
- Confirm chat text streams.
- Confirm voice output works on the target machine.
- Confirm Settings can add and remove API keys.
- Confirm Tools page shows unsupported tools with clear readiness states.
- Confirm Windows-MCP is blocked gracefully on non-Windows.
- Confirm Windows-MCP runs on Windows with Python 3.13+ and `uvx`.
- Confirm no secrets are present in the package.
