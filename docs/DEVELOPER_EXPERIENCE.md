<!-- SPDX-License-Identifier: Apache-2.0 -->

# Developer Experience

Shell should be easy for contributors to run, test, inspect, and package.

## Fast Start

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m pytest -q
```

Windows users should prefer:

```text
ONE_CLICK_INSTALL.bat
Start_ShellAI.bat
```

## Common Developer Commands

```bash
python3 tools/config_diagnostics.py
python3 tools/enterprise_diagnostics.py
python3 tools/repo_audit.py --fail-on-high
python3 tools/production_release_check.py --strict
python3 tools/package_public_release.py
python3 tools/production_readiness.py --run-tests
python3 -m pytest -q
```

## Contribution Workflow

1. Create a focused branch.
2. Keep changes small and testable.
3. Add tests for behavior, docs, or safety gates.
4. Run repo audit.
5. Run production readiness for release-facing changes.
6. Update docs when behavior changes.

## Code Quality Standards

- No hidden autonomous execution.
- No new unsafe default flags.
- No direct secret logging.
- No new giant UI files.
- No tool execution without readiness/error handling.
- No public docs that imply unsupported capability.

## Future DX Improvements

- Add `Makefile` or `justfile` after repo is initialized.
- Add dev container for clean setup.
- Add screenshot generation script.
- Add plugin scaffold command.
- Add docs preview command for the future website.
