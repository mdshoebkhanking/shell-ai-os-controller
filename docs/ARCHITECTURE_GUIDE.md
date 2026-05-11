<!-- SPDX-License-Identifier: Apache-2.0 -->

# Architecture Guide

Shell is a desktop AI control layer. It connects UI, voice, chat, tools,
runtime state, and external integrations.

## Runtime Flow

```text
User input
  -> PyQt UI / Voice / Telegram
  -> Shell Hub / Agent Runtime
  -> Tool Gateway
  -> Local Tool / API / Desktop Automation
  -> Structured Result
  -> UI + Logs + User Response
```

## Core Boundaries

| Boundary | Responsibility |
| --- | --- |
| `shell_ui/` | Desktop UI, pages, themes, voice page, status displays |
| `agent.py` | AI session wiring, tool list, provider interaction |
| `shell_tool_gateway.py` | Safe tool dispatch from UI/chat |
| `shell_safe_executor.py` | Tool wrapper, timing, structured failures |
| `core/` | Future-ready modular runtime systems |
| `installer/` | Bootstrap, repair, health checks |
| `tools/` | Release, audit, packaging, acceptance probes |

## Safety Model

Dangerous actions must be blocked by default or require explicit opt-in:

- Code writing.
- Agent patching.
- Terminal execution.
- Browser automation execution.
- Telegram remote PC control.
- Workflow command execution.

## Observability

Release and runtime diagnostics are written under `.shell_runtime/` locally.
These files must not be committed or included in public release packages.

## Cross-Platform Strategy

- Windows is the primary target.
- macOS/Linux support UI and many Python tools.
- Windows-MCP is Windows-only and must show clear unsupported-state messaging
  outside Windows.
