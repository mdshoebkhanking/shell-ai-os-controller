<!-- SPDX-License-Identifier: Apache-2.0 -->

# Phase 8 Multi-Agent Orchestration

Multi-agent orchestration should make Shell more capable without making it
opaque. Every delegation must be traceable, bounded, and reversible where
possible.

## Orchestration Flow

```text
Goal
  -> classify risk
  -> select memory scopes
  -> choose agent roles
  -> assign tasks
  -> execute under policy
  -> validate result
  -> recover or finalize
```

## Communication Model

Agents exchange structured messages:

- `delegate`
- `result`
- `handoff`
- `clarify`
- `observe`
- `validate`

Messages carry task IDs and trace IDs so UI and logs can reconstruct what
happened.

## Scheduling Rules

- Respect max agent count.
- Respect max parallel task count.
- Do not spawn recursively without a supervisor budget.
- Risky actions require validator availability.
- Background agents are disabled unless policy allows them.

## Recovery Rules

- Failed tasks return structured errors.
- Retries must have limits.
- Dangerous tasks need rollback notes.
- Cancellations must stop pending child work.
- Repeated failing agents should lose routing priority.

## Observability Hooks

- `AGENT_ORCHESTRATION_PLANNED`
- `AGENT_ECOSYSTEM_VALIDATED`
- `AGENT_MEMORY_BOUND`
- execution trace IDs
- UI-visible task timeline

## Future Work

- durable task queue
- agent supervisor watchdog
- agent trace visualizer
- distributed agent handoff
- human approval queue
