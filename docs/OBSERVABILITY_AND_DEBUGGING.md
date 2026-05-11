<!-- SPDX-License-Identifier: Apache-2.0 -->

# Observability And Debugging

Shell needs observability that helps normal users recover and helps developers
debug without exposing secrets.

## Current System

Existing layers:

- `core/observability/events.py`: in-process event bus.
- `core/observability/tracing.py`: execution traces and spans.
- `core/health/startup.py`: dependency/API/safety diagnostics.
- `tools/repo_audit.py`: repository quality and secret-pattern scan.
- `tools/production_readiness.py`: release readiness scoring.
- `tools/config_diagnostics.py`: profile-aware config validation.
- `tools/enterprise_diagnostics.py`: redacted enterprise support report.

## Enterprise Diagnostics

Run:

```bash
python3 tools/enterprise_diagnostics.py
```

Report path:

```text
.shell_runtime/enterprise_diagnostics_report.json
```

The report includes:

- Redacted config summary.
- Startup health summary.
- Public docs presence.
- Repo audit summary.
- Production readiness summary.

It must not include raw `.env`, tokens, local chat history, or private
screenshots.

## Target Observability Model

```text
User action
  -> trace_id
  -> route decision
  -> tool/agent/provider spans
  -> result/error
  -> UI status
  -> redacted support report
```

## Event Naming

Use stable event families:

- `ui.*`
- `tool.*`
- `agent.*`
- `provider.*`
- `voice.*`
- `config.*`
- `security.*`
- `release.*`

## Log Rules

- Redact secrets before writing.
- Include trace IDs where available.
- Prefer structured JSON for debug/enterprise profiles.
- Keep normal user logs human-readable.
- Never log full API responses if they may contain private user content.

## Future OpenTelemetry Path

OpenTelemetry can be added later as an export layer. Shell should first keep
local, vendor-neutral event and trace objects, then map them to OpenTelemetry
logs/traces/metrics when external export is explicitly enabled.

## Debugging Checklist

1. Run config diagnostics.
2. Run startup health.
3. Run repo audit.
4. Run production readiness.
5. Reproduce through UI when possible.
6. Attach only redacted reports.
