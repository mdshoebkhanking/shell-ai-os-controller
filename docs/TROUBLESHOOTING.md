<!-- SPDX-License-Identifier: Apache-2.0 -->

# Troubleshooting

## Shell Does Not Start

Run repair:

```text
Windows: Repair_ShellAI.bat
macOS:   ./repair_shellai.command
Linux:   ./repair_shellai.sh
```

Then run the start launcher again.

## Voice Is Silent

Check:

- System volume.
- Output device.
- `GOOGLE_API_KEY`.
- `DISABLE_TTS`.
- Voice provider readiness in Settings.
- Windows audio permissions/preflight.

## Gemini API Key Invalid

Replace `GOOGLE_API_KEY` in `.env`, then restart Shell.

## Email Login Rejected

For Gmail, use a Google App Password. Normal account passwords are rejected.

## Windows-MCP Is Unavailable

Windows-MCP requires:

- Windows.
- Python 3.13+.
- `uv` / `uvx`.

On macOS/Linux, Shell should show a clear unsupported message.

## Telegram Bot Not Working

Check:

- Token format.
- Bot started.
- Allowed chat IDs.
- Remote-control enabled only if intended.
- Terminal execution remains disabled unless explicitly needed.

## Public Release Fails

Run:

```bash
python tools/repo_audit.py
python tools/production_release_check.py --strict
python tools/package_public_release.py
python tools/production_readiness.py
```
