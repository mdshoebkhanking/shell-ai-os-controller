<!-- SPDX-License-Identifier: Apache-2.0 -->

# Phase 9 Analytics And Product Insight

Analytics must be privacy-conscious, optional, and transparent. Shell should
not silently collect user data.

## Local-First Insight

Default diagnostics should remain local:

- startup time
- dependency health
- tool failure categories
- voice readiness
- UI audit findings
- release readiness reports

## Optional Telemetry

Future opt-in telemetry may include:

- anonymous install success/failure category
- crash diagnostics
- feature usage counts
- performance timings
- dependency failure categories

Never collect:

- API keys
- prompts or responses by default
- file contents
- screenshots
- personal identifiers
- Telegram chat contents

## Transparency Requirements

- clear opt-in screen
- view collected fields
- disable anytime
- delete local telemetry cache
- no telemetry required for core features

## Product Insight Metrics

- install success rate
- time to first working chat
- time to first voice output
- repair success rate
- most common missing dependency
- top docs pages
- issue categories

## Enterprise Telemetry

Enterprise telemetry should be configurable and exportable to customer-owned
systems. Do not hardwire a vendor.
