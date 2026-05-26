<!-- SPDX-License-Identifier: Apache-2.0 -->

# Configuration System

Shell now has an additive enterprise configuration layer in `core/config/`.
Legacy code can continue using `shell_config.py`, while new systems can use
profile-aware configuration snapshots.

## Profiles

| Profile | Purpose |
| --- | --- |
| `beginner` | Safe defaults, simple UI, high confirmations |
| `advanced` | More runtime detail, local model readiness, medium confirmations |
| `debug` | Debug logging, single concurrency, high observability |
| `enterprise` | Audit mode, signed plugins, strict remote-control posture |

Set:

```bash
SHELL_CONFIG_PROFILE=beginner
```

## Important Defaults

Only true high-risk mutation/remote flags remain disabled unless explicitly set:

- `SHELL_ALLOW_CODE_WRITE`
- `SHELL_ALLOW_AGENT_PATCH`
- `SHELL_ALLOW_AGENT_BROWSER_EXEC`
- `SHELL_ALLOW_OPENCLAW_SKILL_INSTALL`
- `SHELL_TELEGRAM_ALLOW_TERMINAL`

Normal terminal commands, managed workflow file actions, and app scaffolds are
available by default; destructive command patterns and path escapes are still
blocked at runtime.

## Diagnostics

Run:

```bash
python3 tools/config_diagnostics.py
```

Strict mode:

```bash
python3 tools/config_diagnostics.py --fail-on-error
```

Report path:

```text
.shell_runtime/config_diagnostics.json
```

The report redacts secrets and checks:

- Unknown profile.
- Risky flags.
- Invalid AI provider mode.
- Concurrency range.
- Enterprise plugin signing requirement.
- Telegram remote-control allowlist.

## Migration Plan

Short term:

- Keep `shell_config.py` as compatibility layer.
- Use `core/config` in new subsystems.
- Add config diagnostics to release/health flows.

Medium term:

- Move grouped config metadata into typed profile schema.
- Add user-editable profile UI.
- Add per-workspace config overlays.

Long term:

- Add enterprise policy templates.
- Add signed profile bundles.
- Add team-managed defaults.
