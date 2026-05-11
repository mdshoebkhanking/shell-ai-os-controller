# Shell External Integrations

Shell can keep third-party AI/browser repositories under `integrations/external`
and expose them through safe Python wrapper tools. Public release packages do
not bundle these cloned repositories; users or maintainers should install them
through the documented setup flow after reviewing their licenses and security
posture. The cloned repositories are not imported during startup, so broken
Node/Rust/browser dependencies cannot crash the PyQt app.

## Optional Local Clones

- `external/agent-browser`: Vercel Labs browser automation CLI source.
- `external/awesome-openclaw-skills`: VoltAgent OpenClaw skills index.

## Shell Tools

- `external_integration_status_tool`: shows repo presence, licenses, versions,
  available skills, and execution state.
- `agent_browser_skill_catalog_tool`: lists locally cloned agent-browser skill
  guides.
- `agent_browser_command_tool`: runs `agent-browser` commands when
  `SHELL_ALLOW_AGENT_BROWSER_EXEC=1`. Use `dry_run=true` to preview without
  launching automation.
- `openclaw_skill_search_tool`: searches the local OpenClaw skill index.
- `openclaw_skill_install_tool`: installs an OpenClaw skill through local
  `clawhub` when `SHELL_ALLOW_OPENCLAW_SKILL_INSTALL=1`.

Agent-browser uses `SHELL_AGENT_BROWSER_SOCKET_DIR` for its daemon socket. Keep
this path short, for example `/tmp/shell-agent-browser`, to avoid Unix socket
path-length limits.

## Safety

OpenClaw skills are curated, not audited. Treat every skill as untrusted until
its source and permissions are reviewed. Browser automation can click, type,
log in, upload files, and modify web state, so Shell keeps it behind an
explicit environment flag.
