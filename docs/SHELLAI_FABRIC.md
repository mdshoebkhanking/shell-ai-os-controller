<!-- SPDX-License-Identifier: Apache-2.0 -->

# ShellAI Core and AI OS Fabric

ShellAI Core is the current opt-in backend brain for Shell AI OS Controller.
It is focused on shell and desktop OS automation while keeping the classic
PyQt desktop experience stable by default.

## What It Provides Today

- `python -m shellai` CLI with `doctor`, `run`, `skills`, `monitor`,
  `optimize`, `cron`, and `daemon` commands.
- A single-request agent loop: user request -> planning JSON -> safety/tool
  execution -> summary -> memory and trace update.
- In-process agent wrappers: Coordinator, Shell, Safety, Memory, UI, and
  Optimizer.
- Model routing for planning, command generation, and summarization roles.
- OpenAI-compatible HTTP providers, OpenRouter-compatible config, and local
  Ollama support.
- SQLite memory for conversations, user profile, skill metadata, usage stats,
  traces, and safety audit records.
- JSON skills under `~/.shellai/skills`, including deterministic auto-skill
  drafts for reusable successful workflows.
- Safety policy with `SAFE`, `ASK`, and `BLOCK` command classes.
- A feature-flagged desktop bridge through `SHELLAI_BACKEND_MODE=shellai_core`.

## Runtime Layout

```text
~/.shellai/
├── config.json              # provider, model role, tools, profile defaults
├── data/memory.sqlite3      # conversation, profile, skill, audit metadata
├── logs/                    # local logs
├── skills/
│   ├── manual/              # user-curated JSON skills
│   └── auto/                # agent-created drafts
└── traces/                  # compact persisted request traces
```

Set `SHELLAI_CONFIG=/path/to/config.json` to use a different runtime root.

## CLI Quickstart

```bash
python -m shellai doctor
python -m shellai config get
python -m shellai model show
python -m shellai run "!pwd" --json
python -m shellai skills list
python -m shellai monitor --limit 10
python -m shellai optimize
python -m shellai cron list
python -m shellai daemon status
```

Explicit shell commands can be prefixed with `!`, `$`, or `shell:`. Risky
commands are classified by policy before execution.

## Desktop Bridge

Classic desktop mode is the default:

```bash
SHELLAI_BACKEND_MODE=classic python launch.py
```

Opt in to ShellAI Core for chat requests:

```bash
SHELLAI_BACKEND_MODE=shellai_core python launch.py
```

When enabled, normal chat text can route through ShellAI Core. Existing slash
commands such as `/tool`, `/agent`, and `/mcp` continue to use the classic
backend-command path.

## Model Configuration

ShellAI Core resolves models by role:

- `planning`: intent, plan JSON, agent coordination.
- `command`: command/tool-oriented generation.
- `summarization`: user-facing and memory summaries.

Supported provider backends in the current implementation:

- `openai`: OpenAI-compatible HTTP API at `https://api.openai.com/v1`.
- `openrouter`: OpenAI-compatible HTTP API at OpenRouter.
- `ollama`: local HTTP API at `http://127.0.0.1:11434`.

Useful environment variables:

```bash
SHELLAI_PROVIDER=openai
SHELLAI_MODEL_PLANNING=gpt-4o-mini
SHELLAI_MODEL_COMMAND=gpt-4o-mini
SHELLAI_MODEL_SUMMARIZATION=gpt-4o-mini
OPENAI_API_KEY=
OPENROUTER_API_KEY=
SHELLAI_OLLAMA_BASE_URL=http://127.0.0.1:11434
```

If a provider needs a key and the key is missing, real model calls are refused
with structured diagnostics so `shellai doctor` and the desktop UI can explain
the problem instead of crashing.

## Safety Policy

Default behavior:

- `SAFE`: read-only commands like `pwd`, `ls`, `git status`, version checks.
- `ASK`: commands that modify state or install/push/delete, such as `rm`,
  `pip install`, `npm install`, `git push`, and `sudo`.
- `BLOCK`: obviously destructive commands such as `rm -rf /`, disk format,
  shutdown/reboot, fork bombs, and raw disk writes.

Policy can be extended through the ShellAI policy file under the runtime config
root. BLOCK commands never execute. ASK commands require explicit approval; the
current desktop bridge reports that approval is required rather than running
them automatically.

## Current Limitations

- The daemon is a minimal opt-in local queue, not an autonomous background
  operator.
- Optimizer suggestions are read-only; they do not rewrite skills or policy.
- Cron jobs are manually invoked and disabled by default.
- Desktop approval UI for ASK-level commands is still pending.
- ADB, browser, git, and VS Code tools are represented in config priorities,
  but richer first-class adapters are future work.

## Validation Snapshot

The current pushed state was validated with:

```bash
python -m pytest -q
```

Result in this workspace: `466 passed, 1 warning`. The warning is local
Python/LibreSSL compatibility from `urllib3`, not a ShellAI Core failure.
