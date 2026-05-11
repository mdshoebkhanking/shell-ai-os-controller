<!-- SPDX-License-Identifier: Apache-2.0 -->

# Performance Engineering Plan

Shell must feel responsive before it becomes larger. Performance work should
focus on startup time, first response latency, voice latency, and UI smoothness.

## Current Performance Risks

- Large UI file with many widgets and effects.
- Heavy optional imports spread across tool modules.
- Provider SDK initialization can happen earlier than needed.
- Voice stack depends on API/network/audio driver readiness.
- Large tool catalog can increase routing overhead.

## Principles

- Lazy-load optional providers.
- Keep first paint light.
- Stream text as early as possible.
- Use local TTS fallback when cloud voice is slow.
- Avoid blocking the UI thread.
- Cache readiness and tool metadata.

## Measurement Targets

| Metric | Target |
| --- | --- |
| UI response to click | Under 50 ms |
| First text chunk | Under 300 ms when provider supports streaming |
| Voice playback start | Under 500 ms preferred |
| Hub `/health` | Under 50 ms locally |
| Tool route decision | Under 100 ms for common tools |

## Optimization Backlog

1. Move heavy imports behind tool execution boundaries.
2. Cache tool registry and readiness metadata.
3. Keep provider clients warm only after first paint.
4. Add first-token and first-audio-byte metrics to UI diagnostics.
5. Split UI modules further to reduce import/initialization cost.
6. Prefer subprocess isolation for heavy optional tools.
7. Add performance regression probes to CI once stable.

## Risk Controls

Do not optimize by hiding errors or removing safety checks. Performance changes
must preserve:

- Tool readiness.
- Permission checks.
- Audit logs.
- User-visible error messages.
