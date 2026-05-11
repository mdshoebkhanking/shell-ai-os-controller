<!-- SPDX-License-Identifier: Apache-2.0 -->

# Website And Docs Plan

Shell does not need a heavy website at launch. It needs a fast landing page,
excellent install docs, and trustworthy technical documentation.

## Recommendation

Use **VitePress** first.

Why:

- Markdown-first.
- Fast static output.
- Easy to deploy anywhere.
- Good fit for docs plus a lightweight product homepage.
- Low maintenance compared with a custom app.

When to choose another stack:

| Stack | Use When |
| --- | --- |
| VitePress | Fast docs, landing page, minimal complexity |
| Docusaurus | Larger community docs, versioned docs, bigger blog strategy |
| Fumadocs | Next.js product site with MDX components and API docs |
| MkDocs | Python-only docs workflow with no Node product site |

## Future Folder Structure

```text
site/
  package.json
  index.md
  guide/
    install.md
    first-run.md
    voice.md
    telegram.md
    tools.md
  concepts/
    architecture.md
    safety.md
    tool-routing.md
  developers/
    setup.md
    testing.md
    api.md
    plugins.md
  releases/
    changelog.md
    download.md
  blog/
    2026-xx-xx-public-launch.md
  public/
    og-image.svg
    screenshots/
  .vitepress/
    config.ts
    theme/
```

## Site Navigation

Top nav:

- Overview.
- Install.
- Docs.
- Architecture.
- Security.
- Roadmap.
- GitHub.

Home page sections:

1. Hero: Shell AI OS Controller.
2. Product promise.
3. What it can do.
4. Safety and control.
5. Install in minutes.
6. Screenshots.
7. Architecture preview.
8. Roadmap.

## SEO Structure

Primary title:

```text
Shell AI OS Controller - AI Desktop Automation And Voice Assistant
```

Description:

```text
Open-source AI desktop control layer for chat, voice, tools, automation,
Telegram control, and local workflow diagnostics.
```

Suggested keywords:

- AI desktop assistant.
- Python desktop automation.
- PyQt AI assistant.
- AI tool calling desktop.
- Voice AI assistant.
- Windows automation AI.
- Open-source AI workspace.

## Deployment Options

| Platform | Best For |
| --- | --- |
| GitHub Pages | Free public docs tied to repo |
| Cloudflare Pages | Fast static hosting with simple previews |
| Vercel | Product website, previews, future Next.js/Fumadocs |
| Netlify | Static docs and form/contact integrations |

Recommended launch path:

1. Publish GitHub repository.
2. Add real screenshots.
3. Create `site/` with VitePress.
4. Deploy to GitHub Pages or Cloudflare Pages.
5. Add custom domain later.

## Content Backlog

- Install guide with screenshots.
- Voice setup guide.
- Telegram remote-control guide.
- Tool safety guide.
- Windows-MCP guide.
- Public release notes.
- "How Shell works" architecture article.
- "What Shell is not" safety article.
