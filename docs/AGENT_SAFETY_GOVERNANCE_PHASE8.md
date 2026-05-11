<!-- SPDX-License-Identifier: Apache-2.0 -->

# Phase 8 Agent Safety And Governance

Autonomous behavior is useful only when boundaries are clear. Shell agents must
remain governable, observable, and interruptible.

## Risk Levels

- `safe`: read-only or reversible guidance.
- `caution`: low-impact local action.
- `dangerous`: file writes, desktop control, external sends, shell execution.
- `critical`: destructive, credential, payment, security, or irreversible work.

## Governance Rules

- Dangerous and critical tasks require explicit approval.
- Background agents cannot run risky actions.
- Agents cannot expand their own permissions.
- Tool calls must come from registered capabilities.
- Sensitive memory scopes require permission.
- Every risky action needs an audit event.

## User Override

The user must always be able to:

- pause agents
- cancel workflows
- deny approvals
- disable a plugin
- reset memory
- repair dependencies
- inspect traces

## Prompt Injection And Agentic Risk

LLM output is treated as untrusted planning input, not authority. The system
must validate every tool call, output, and handoff through policy before acting.

## Audit Logs

Audit records should include:

- actor
- requested action
- risk level
- approval state
- tool/workflow IDs
- trace ID
- result
- rollback status

## Release Blockers For Real Autonomy

Do not enable background autonomous execution until durable queues, approvals,
watchdogs, rollback, and UI-visible traces are implemented and tested.
