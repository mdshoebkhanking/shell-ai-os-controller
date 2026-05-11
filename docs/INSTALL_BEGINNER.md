<!-- SPDX-License-Identifier: Apache-2.0 -->

# Beginner Install Guide

This guide is for non-technical users. The goal is:

```text
Download -> Install -> Start Shell -> Chat/voice works
```

## Before You Start

You need:

- A Windows, macOS, or Linux computer.
- Internet connection for first install.
- A Google Gemini API key for full AI/voice features.
- Optional API keys only if you want extra integrations.

Never share your API keys publicly.

## Windows Install

1. Download the release zip.
2. Right-click the zip and choose **Extract All**.
3. Open the extracted folder.
4. Double-click:

```text
ONE_CLICK_INSTALL.bat
```

5. Wait until the installer finishes.
6. Double-click:

```text
Start_ShellAI.bat
```

If Windows asks for permission, allow the app only if you trust the folder you
downloaded.

### Windows Repair

If Shell does not start:

```text
Double-click Repair_ShellAI.bat
```

Then run:

```text
Start_ShellAI.bat
```

## macOS Install

Open Terminal in the Shell folder and run:

```bash
chmod +x ONE_CLICK_INSTALL.command start_shellai.command repair_shellai.command
./ONE_CLICK_INSTALL.command
./start_shellai.command
```

If macOS blocks the file, use:

```text
System Settings -> Privacy & Security -> Open Anyway
```

## Linux Install

Open Terminal in the Shell folder and run:

```bash
chmod +x start_shellai.sh repair_shellai.sh
./start_shellai.sh
```

If packages are missing, run:

```bash
./repair_shellai.sh
```

## API Setup

Create a local `.env` file from `.env.example`:

```bash
cp .env.example .env
```

Set at least:

```text
GOOGLE_API_KEY=your_google_key_here
LIVEKIT_API_KEY=your_livekit_key_here
LIVEKIT_API_SECRET=your_livekit_secret_here
LIVEKIT_URL=your_livekit_url_here
```

Do not upload `.env` to GitHub.

## Screenshots To Add Later

Add these images before public launch:

- `screenshots/chat.png` - Shell chat page.
- `screenshots/voice.png` - Voice page with orb.
- `screenshots/settings.png` - API/settings page with secrets hidden.
- `gifs/setup-demo.gif` - One-click install demo.

## Common Fixes

| Problem | What to do |
| --- | --- |
| Shell does not open | Run the repair script, then start again |
| Voice is silent | Check output device and volume; verify `GOOGLE_API_KEY` |
| API key invalid | Replace the key in `.env`; restart Shell |
| Windows-MCP unavailable | Use Windows with Python 3.13+ and `uv/uvx` |
| Email login fails | Use Gmail App Password, not normal Gmail password |
| Telegram does not reply | Check token, allowed chat ID, and remote-control settings |

## Public Safety Reminder

Before sharing screenshots or videos, hide:

- API keys.
- Telegram tokens.
- Email addresses/passwords.
- Private files.
- Local paths that reveal personal info.
