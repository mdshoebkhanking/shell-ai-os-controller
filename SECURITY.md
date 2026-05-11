<!-- SPDX-License-Identifier: Apache-2.0 -->

# Security Policy

## Supported Version

| Version | Supported |
| --- | --- |
| 1.0.0 | Yes |

## Reporting Security Issues

Do not publish security issues publicly until they are understood and fixed.
For now, report issues privately to the project owner before opening a public
GitHub issue.

## Secrets Policy

Never commit:

- `.env`
- API keys or provider tokens
- Telegram bot tokens
- SMTP/Gmail app passwords
- Instagram credentials
- `.shell_settings.json`
- `.telegram_*.json`
- runtime logs, chat history, screenshots with private data, or local caches

Use `.env.example` and `.env.template` for placeholder configuration only.

## High-Risk Features

Shell includes desktop automation, browser automation, Telegram remote control,
email sending, and code-writing tools. Dangerous execution paths must remain
disabled by default and require explicit user configuration, audit logs, and
clear UI/backend status.

Before a public release, run:

```bash
python3 tools/production_release_check.py --strict
python3 tools/package_public_release.py
python3 tools/production_readiness.py --run-tests
```
