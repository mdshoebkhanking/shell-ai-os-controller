<!-- SPDX-License-Identifier: Apache-2.0 -->

# Third-Party Notices

Shell AI OS Controller is licensed under Apache-2.0. This file records the
current third-party dependency and integration audit before a public release.

This is not a full legal opinion. Re-run this audit before publishing a new
release, especially after adding new SDKs, models, images, fonts, or external
repositories.

## Runtime Dependencies

The Python dependencies in `requirements.txt` are mostly permissive licenses
commonly compatible with Apache-2.0 distribution, including Apache-2.0, MIT,
BSD-style, ISC-style, and PSF-style licenses.

Examples checked from the local environment:

- `google-generativeai`: Apache-2.0
- `openai`: Apache-2.0
- `requests`: Apache-2.0
- `httpx`: BSD-3-Clause
- `aiohttp`: Apache-2.0 AND MIT
- `python-socketio`: MIT
- `websocket-client`: Apache-2.0
- `psutil`: BSD-3-Clause
- `keyboard`: MIT
- `pytest`: MIT
- `pytest-timeout`: MIT

Packages not installed in the local audit environment could not be fully
verified through package metadata. Before publishing binaries, run a dedicated
license scanner after a clean install of `requirements.txt`.

## Notable Dependency Notes

- `pynput` reports LGPLv3 in local metadata. Using it as an external Python
  dependency is usually manageable, but bundled desktop binaries should preserve
  notices and allow users to replace/update the LGPL component where required.
- `numpy` wheels can include bundled native libraries with their own notices
  such as BSD-3-Clause, MIT, Zlib, and GCC runtime library exceptions. Preserve
  wheel/binary notices if redistributing packaged binaries.
- `PyQt6` and `PyQt6-WebEngine` are Qt bindings. Qt licensing can be complex
  for commercial binary distribution. For a public source repo this is usually
  fine as a dependency, but before selling bundled installers, verify Qt/PyQt
  commercial/open-source obligations with current vendor terms.
- `opencv-python`, `pillow`, `playwright`, `selenium`, `cryptography`, and
  related packages should be rechecked in the final build environment because
  binary wheels can carry additional notices.
- The previous unused `three.js` npm wrapper dependency was removed from
  `package.json`. The WebGL orb still loads `three@0.158.0` from unpkg at
  runtime; if this becomes part of an offline/bundled build, vendor the official
  `three` package and preserve its MIT license notice.

## Optional External Repositories

Local development may clone optional external integrations under
`integrations/external`. That folder is intentionally ignored by Git and
excluded from the public release zip by the packaging script. If a future
release vendors any external repository, preserve upstream license files and
notices.

- `integrations/external/agent-browser`: Apache-2.0
- `integrations/external/awesome-openclaw-skills`: MIT

## APIs And Services

Shell integrates with hosted services such as Google Gemini, OpenAI, Groq,
LiveKit, Perplexity, Hugging Face, Telegram, Gmail/SMTP, Instagram, weather,
news, and search APIs. The Apache-2.0 project license does not override those
services' terms of use. Users must bring their own API keys and follow each
provider's terms.

## Assets

Current checked-in visual assets appear to be local screenshots, generated UI
screenshots, generated QR/smoke images, local docs SVGs, and `shell_ui/shell_logo.png`.
No separate third-party font files were found in the source audit. Before public
release, remove generated screenshots and runtime images that are not needed for
the repo, or document their origin if they remain.

## Public Release Rules

- Do not publish `.env`, `.shell_settings.json`, `.telegram_*.json`, logs, local
  chat history, runtime folders, virtual environments, or generated cache data.
- Keep `LICENSE`, `NOTICE`, and this file in every source release.
- Preserve upstream license files when vendoring third-party repositories.
- Re-run `tools/package_public_release.py` and inspect the generated zip before
  publishing.
