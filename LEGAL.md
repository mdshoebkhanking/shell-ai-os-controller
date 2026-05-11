<!-- SPDX-License-Identifier: Apache-2.0 -->

# Legal And Open-Source Preparation Report

Shell AI OS Controller is prepared for public open-source release under the
Apache License, Version 2.0 (`Apache-2.0`).

This report is practical engineering guidance, not legal advice. For selling
bundled installers or accepting large outside contributions, get a lawyer to
review the final release.

## Beginner-Friendly License Comparison

| License | Simple meaning | Commercial use | Main restriction | Contributor effect | Fit for Shell |
| --- | --- | --- | --- | --- | --- |
| MIT | Very short permissive license. People can use, copy, modify, sell, and close-source forks if they keep the copyright/license notice. | Yes | Keep copyright/license notice. No warranty. | Easy for contributors, but no explicit patent grant. | Good, but weaker for AI/tooling ecosystem patents. |
| Apache-2.0 | Permissive like MIT, but more professional for larger projects. Includes explicit patent grant and requires stating changes. | Yes | Keep notices, include license, note major changes, no trademark rights. | Contributors grant copyright and patent permission for their contributions. | Best balance for Shell. |
| GPLv3 | Strong copyleft. People can use/sell it, but distributed modified versions and larger derivative works must remain GPLv3 and source-available. | Yes | Must disclose source and keep same license for derivative distribution. | Protects openness, but discourages closed-source/commercial integrations. | Too restrictive for Shell's future commercial/plugin goals. |
| MPL-2.0 | Weak copyleft. Changes to MPL files stay open, but larger apps can use other licenses. | Yes | Modified MPL-covered files must stay open. | Middle ground. | Possible, but more complex than needed. |
| AGPLv3 | Strongest copyleft for network services too. | Yes | Network-hosted modified versions must publish source. | Very open-source protective, but limits adoption. | Not recommended for this project. |

## Recommendation

Use **Apache-2.0**.

Reason:

- It allows personal and commercial use.
- It is respected in professional AI, infrastructure, cloud, and developer-tool
  projects.
- It gives clearer patent protection than MIT.
- It does not force all forks/plugins to become open source, which helps future
  ecosystem growth.
- It is compatible with a public GitHub release and commercial/personal future.
- It keeps Shell honest: users get license text, notices, no warranty, and clear
  attribution.

## Future Impact

What people can do:

- Use Shell privately.
- Use Shell commercially.
- Modify Shell.
- Distribute Shell.
- Build paid services/products around Shell.

What they must do:

- Keep the Apache-2.0 license and copyright notice.
- Keep the NOTICE file if they redistribute.
- Mark significant modifications where required.
- Not use the project name/creator branding as their own trademark.

What they are not promised:

- No warranty.
- No guarantee the software is fit for every use.
- No automatic rights to third-party APIs, models, brands, or services.

## Compliance Setup Added

- `LICENSE`: full Apache-2.0 license text.
- `NOTICE`: project copyright notice for mdshoebking.
- `THIRD_PARTY_NOTICES.md`: dependency and integration audit notes.
- `README.md`: license section updated.
- `package.json`: SPDX license metadata updated to `Apache-2.0`.

## Security And Public Release Review

Sensitive local files found and should stay private:

- `.env`
- `.shell_settings.json`
- `.telegram_log.json`
- `.telegram_state.json`
- `.telegram_users.json`
- `.shell_runtime/`
- `.shell_chat_history/`
- `*.log`
- virtual environments such as `venv/`, `.shellai_venv/`, `.codex_ui_venv/`

Current protection:

- `.gitignore` excludes `.env`, `.env.*`, logs, venvs, sessions, and build
  artifacts.
- `tools/package_public_release.py` excludes local runtime/secrets files.
- `tools/production_release_check.py --strict` passed with only a warning that
  local `.env` exists and must not be published.

## Risks To Watch Before GitHub Public Release

- Do not publish real `.env` values, API keys, Telegram tokens, email app
  passwords, Instagram credentials, or local user state.
- Review Qt/PyQt licensing before selling bundled binary installers.
- Re-run dependency license scan after a clean install because optional packages
  not installed locally could not be fully verified.
- External cloned repos keep their own licenses. Preserve their `LICENSE` files
  if publishing them.
- Generated screenshots/assets should be removed unless needed or documented.

## Next Steps

1. Keep Apache-2.0 as the project license.
2. Rotate any API keys that were ever pasted into chats, screenshots, or logs.
3. Run `tools/package_public_release.py` before sharing any zip.
4. Before pushing to GitHub, inspect `git status` and make sure no private
   runtime files are staged.
5. If accepting outside contributors, add `CONTRIBUTING.md` and consider a
   Developer Certificate of Origin (`Signed-off-by`) workflow.
