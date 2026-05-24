<!-- SPDX-License-Identifier: Apache-2.0 -->

# Public GitHub Release Playbook

This playbook is the final checklist before Shell AI OS Controller is pushed to
GitHub publicly.

## Visual Release Standard

- Official logo is used from `assets/brand/shell-official-logo.png`.
- README hero shows the official logo and banner.
- Current screenshots are real UI captures from `screenshots/current/`.
- Demo video media is the current 16:9 Shell UI render from `videos/shell-current-ui-landscape-demo.mp4`.
- Branding stays metallic, dark, minimal, premium, and realistic.

## Security Gate

Before pushing:

```bash
python3 tools/production_release_check.py --strict
python3 tools/repo_audit.py --fail-on-high
python3 tools/public_github_launch_audit.py --fail-on-high
python3 tools/ecosystem_master_audit.py --fail-on-high
```

Do not push if any secret, token, `.env`, log, session, cache, private config,
certificate, or machine-specific file would be staged.

## GitHub Push Flow

```bash
git init -b main
git add .
git status --short
git commit -m "chore: prepare Shell AI OS Controller public release"
git remote add origin <your-github-repo-url>
git push -u origin main
```

Only run the remote commands after the target GitHub repository URL is known.

## Public Launch Assets

- README screenshots from the current Shell UI.
- Current 16:9 UI demo video and poster.
- Future voice/workflow/architecture demos regenerated from the current UI.
- Social preview image.
- Launch post.

## Current Release Position

Recommended launch stage: public beta.

Reason: the repository is mature, but signed installers, macOS notarization,
clean-machine acceptance, and non-developer UAT are still required before a full
GA or enterprise launch claim.
