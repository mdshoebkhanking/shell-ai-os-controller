<!-- SPDX-License-Identifier: Apache-2.0 -->

# Release Process

Shell uses semantic versioning:

```text
MAJOR.MINOR.PATCH
```

- `PATCH`: bug fixes, docs, small safe improvements.
- `MINOR`: new features that do not break existing behavior.
- `MAJOR`: breaking changes or major architecture shifts.

## Release Branch Flow

```text
feature/* -> pull request -> main
main -> release/1.x.x -> tag -> public zip
```

## Pre-Release Checklist

Run:

```bash
python3 tools/repo_audit.py --fail-on-high
python3 tools/config_diagnostics.py --fail-on-error
python3 tools/ui_ux_audit.py --fail-on-high
python3 tools/cloud_readiness_audit.py --fail-on-high
python3 tools/agent_ecosystem_audit.py --fail-on-high
python3 tools/launch_readiness_audit.py --fail-on-high
python3 tools/public_github_launch_audit.py --fail-on-high
python3 tools/ecosystem_master_audit.py --fail-on-high
python3 -m pytest -q
python3 tools/production_release_check.py --strict
python3 tools/package_public_release.py
python3 tools/production_readiness.py --run-tests
python3 tools/enterprise_diagnostics.py --fail-on-attention
```

Check:

- `VERSION` is correct.
- `CHANGELOG.md` is updated.
- `README.md` screenshots and links work.
- `LICENSE`, `NOTICE`, `LEGAL.md`, `SECURITY.md`, and
  `THIRD_PARTY_NOTICES.md` are included.
- The zip does not contain `.env`, logs, tokens, runtime files, or venvs.

## Release Notes Template

```md
## Shell AI OS Controller vX.Y.Z

### Highlights
- ...

### Added
- ...

### Fixed
- ...

### Security
- ...

### Upgrade Notes
- ...

### Verification
- Tests:
- Production readiness:
- Package SHA256:
- Cloud/API readiness:
- Agent ecosystem readiness:
- Launch readiness:
- Public GitHub launch readiness:
- Ecosystem master audit:
```

## Public Launch Checklist

- Fresh Windows install tested.
- macOS/Linux basic launch checked.
- Non-developer user acceptance test done.
- README screenshots updated.
- Demo GIF/video links added.
- GitHub profile README published.
- Release tag created.
