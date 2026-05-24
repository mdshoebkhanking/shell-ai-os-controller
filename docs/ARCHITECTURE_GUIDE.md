<!-- SPDX-License-Identifier: Apache-2.0 -->

# Architecture Guide

Shell is a desktop AI control layer. It connects UI, voice, chat, tools,
runtime state, and external integrations.

## Runtime Flow

```text
User input
  -> React Web UI in PyQt WebEngine / Voice / Telegram
  -> QWebChannel / Shell Hub / Classic Agent Runtime
  -> Natural-language Router / Tool Gateway / Agent Orchestrator
  -> Local Tool / API / Desktop Automation
  -> Structured Result
  -> UI Event Stream + Logs + User Response

Optional ShellAI Core path:

CLI / desktop feature flag
  -> shellai.api
  -> AgentRuntime
  -> Coordinator / Shell / Safety / Memory / UI / Optimizer agents
  -> ModelRouter / MemoryStore / SkillManager / ToolRegistry
  -> Structured Result + Trace + SQLite Memory
```

## Core Boundaries

| Boundary | Responsibility |
| --- | --- |
| `shell_web_ui/` | Primary React/Vite/WebGL renderer and PyQt WebEngine host |
| `shell_ui/` | Preserved legacy PyQt UI and shared rollback/boot assets |
| `agent.py` | Classic LiveKit/Gemini session wiring and legacy tool list |
| `shellai/` | Opt-in ShellAI Core CLI, agent loop, model routing, memory, skills, tools, monitor, cron, daemon |
| `core/shellai_bridge.py` | Desktop feature flag bridge into ShellAI Core |
| `shell_tool_gateway.py` | Safe tool dispatch from UI/chat |
| `shell_nl_router.py` | Natural-language mapping for chart/chat/tool commands |
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
- macOS/Linux support the Web UI, docs/dev workflows, and many Python tools.
- Windows-MCP is Windows-only and must show clear unsupported-state messaging
  outside Windows.

## Current Verified State

- GitHub Actions CI is green on Python 3.10, 3.11, 3.12, and 3.13.
- Security workflow is green for CodeQL, secret pattern guard, and Python
  dependency audit.
- Local CI-style pytest run passes with `538 passed`.
- Real Web UI probes cover Dashboard chart/chat, Settings scroll/API keys,
  Telegram controls, Control Center execution, Gallery save/render, fake
  camera/screen streams, CSS animations, and voice buttons.
