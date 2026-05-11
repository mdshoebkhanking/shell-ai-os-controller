<!-- SPDX-License-Identifier: Apache-2.0 -->

# Phase 8 AI Agent Ecosystem

Shell's agent ecosystem is designed to coordinate specialized AI workers while
keeping the human user in control. This is not unrestricted autonomy. Agents
are capability-scoped, policy-gated, observable, and cancellable.

## Architecture Purpose

```text
UI / Voice / Telegram
  -> intent and context capture
  -> agent ecosystem registry
  -> orchestrator plan
  -> memory binding
  -> tool/workflow execution
  -> validation
  -> user-visible trace
```

## Agent Types

- Planner agents break goals into tasks.
- Executor agents run approved tools or workflows.
- Validator agents check outputs and risky actions.
- Researcher agents gather context.
- Debugger agents inspect errors and logs.
- Observer agents monitor state without mutating systems.
- Recovery agents suggest rollback or repair steps.
- Voice agents handle speech pipelines.
- Workflow agents coordinate reusable automations.

## Layer Boundaries

| Layer | Responsibility |
| --- | --- |
| UI | Display state, approvals, traces, cancellation |
| Orchestration | Plan, assign, retry, recover |
| Execution | Run tools/workflows under policy |
| Memory | Retrieve approved context scopes |
| Tool | Expose typed, permissioned capabilities |
| Governance | Decide what needs approval |

## Autonomy Levels

- `manual`: user explicitly starts every action.
- `assisted`: agent can plan and recommend.
- `approved_automation`: agent can run a pre-approved workflow.
- `background_safe`: safe observer/background actions only.
- `blocked`: disabled by policy or safety state.

Dangerous and critical actions must never run only because a model suggested
them.

## Implementation Boundary

The current Phase 8 implementation adds the contracts and audit gates for this
ecosystem. Production background workers, remote agent execution, marketplace
signing, and persistent agent queues are future work.
