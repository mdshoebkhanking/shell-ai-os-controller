<!-- SPDX-License-Identifier: Apache-2.0 -->

# API And Tool Guide

Shell exposes capabilities as Python tools. Tools are called through the agent,
the UI tool gateway, or specific integrations such as Telegram.

## Tool Execution Contract

A tool should:

- Accept clear typed arguments.
- Validate risky paths and commands.
- Return a human-readable result.
- Fail gracefully.
- Avoid leaking secrets.
- Avoid claiming success unless the action actually completed.

## UI Tool Gateway

Use `shell_tool_gateway.py` for UI-triggered tool calls.

Expected result shape:

```json
{
  "status": "success",
  "result": "...",
  "tool_id": "module:tool_name"
}
```

Failures should include:

```json
{
  "status": "error",
  "error": "Clear error message",
  "tool_id": "module:tool_name"
}
```

## Adding A New Tool

1. Add the tool in the correct module.
2. Wrap with the existing tool decorator/pattern.
3. Validate inputs.
4. Add it to the agent/tool registry if required.
5. Add tests.
6. Update docs if it is user-facing.

## External APIs

Shell supports provider APIs, but users must bring their own keys. The project
license does not grant API access.

Never hardcode:

- API keys.
- SMTP passwords.
- Telegram tokens.
- Provider secrets.
