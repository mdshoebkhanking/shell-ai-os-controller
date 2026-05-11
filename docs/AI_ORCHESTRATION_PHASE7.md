<!-- SPDX-License-Identifier: Apache-2.0 -->

# Phase 7 Advanced AI Orchestration

Shell's AI orchestration should stay practical: route the right request to the
right model, tool, runtime, or workflow while keeping execution observable and
permission-aware.

## Target Runtime Flow

```text
User Intent
  -> context snapshot
  -> task classification
  -> policy check
  -> model/runtime selection
  -> tool/workflow planning
  -> execution trace
  -> validation
  -> final response
```

## Multi-Model Strategy

| Task Type | Preferred Runtime |
| --- | --- |
| Simple chat | Fast low-latency provider |
| Coding/refactor | Coding-specialized model |
| Vision/OCR | Multimodal provider or local OCR |
| Voice response | Low-latency TTS path first |
| Offline command | Local model or deterministic tool |
| High-risk automation | Planner plus confirmation and audit |

## Local And Cloud Routing

Routing policy should consider:

- latency target
- model capability
- token cost
- offline availability
- user privacy level
- safety level
- historical success rate

Cloud providers should be optional accelerators, not required for launch.

## Agent Communication

Agents should exchange structured messages:

```text
TaskEnvelope
  -> role
  -> ownership
  -> allowed tools
  -> context bundle
  -> trace id
  -> timeout
  -> result schema
```

Avoid recursive spawning. A supervisor or orchestrator must own agent budgets,
timeouts, and cancellation.

## Tool Calling Rules

- Tools must be selected from registered capabilities, not hallucinated names.
- Each tool call needs a trace ID.
- Dangerous tools need explicit safety classification.
- Failed tool calls must return structured diagnostics.
- Repeated failures should reduce routing trust.

## Future Orchestration APIs

- `POST /workflows/run`
- `GET /workflows/{id}/events`
- `POST /agents/spawn`
- `POST /tools/{tool_id}/execute`
- `GET /runtime/providers`

These should remain behind local-only scopes until governance is production
ready.

## Testing Requirements

- Unit tests for route ranking and fallback.
- Integration tests for tool execution envelopes.
- Failure injection for slow providers and invalid API keys.
- UI tests for streaming response and cancellation.
- Latency tests for text and voice startup.
