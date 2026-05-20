<!-- SPDX-License-Identifier: Apache-2.0 -->

# Architecture Guide

Shell is a desktop AI control layer. It connects UI, voice, chat, tools,
runtime state, and external integrations.

## Runtime Flow

```text
User input
  -> PyQt UI / Voice / Telegram
  -> Shell Hub / Classic Agent Runtime
  -> Tool Gateway
  -> Local Tool / API / Desktop Automation
  -> Structured Result
  -> UI + Logs + User Response

Optional ShellAI Core path:

CLI / PyQt feature flag
  -> shellai.api
  -> AgentRuntime
  -> Coordinator / Shell / Safety / Memory / UI / Optimizer agents
  -> ModelRouter / MemoryStore / SkillManager / ToolRegistry
  -> Structured Result + Trace + SQLite Memory
```

## Core Boundaries

| Boundary | Responsibility |
| --- | --- |
| `shell_ui/` | Desktop UI, pages, themes, voice page, status displays |
| `agent.py` | AI session wiring, tool list, provider interaction |
| `shellai/` | Opt-in ShellAI Core CLI, agent loop, model routing, memory, skills, tools, monitor, cron, daemon |
| `core/shellai_bridge.py` | Desktop feature flag bridge into ShellAI Core |
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
- ShellAI Core ASK/BLOCK command policy.

ShellAI Core classifies shell actions as `SAFE`, `ASK`, or `BLOCK`. SAFE
commands can execute, ASK commands require explicit approval, and BLOCK
commands never execute.

## Observability

Release and runtime diagnostics are written under `.shell_runtime/` locally.
These files must not be committed or included in public release packages.

ShellAI Core also writes compact request traces under `~/.shellai/traces` and
uses SQLite under `~/.shellai/data/memory.sqlite3` for memory, skills, and
safety audit records.

## Cross-Platform Strategy

- Windows is the primary target.
- macOS/Linux support UI and many Python tools.
- Windows-MCP is Windows-only and must show clear unsupported-state messaging
  outside Windows.
