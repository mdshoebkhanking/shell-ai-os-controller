# Shell AI Storytelling Website Design System

## Product Context
Shell AI OS Controller is an open-source, local-first AI desktop control layer for chat, voice, tools, automation, memory, agents, diagnostics, and safe local workflows.

Public copy must say:
- "AI desktop control layer"
- "AI workspace assistant"
- "Guarded tool execution"
- "Human-controlled automation"
- "Readiness state"

Public copy must not say:
- "AGI"
- "Self-aware"
- "Unlimited autonomous OS"
- "Can do anything"
- "Unrestricted automation"

## Website Goal
Create a premium, video-free, storytelling website that explains Shell as an AI control layer running on top of Windows/macOS/Linux. The first viewport must immediately show Shell through a 3D laptop mockup with real Shell UI screenshots.

## Phase Constraint: No Video
Strictly forbidden in this design phase:
- MP4
- WebM
- GIF
- autoplay demo
- YouTube/iframe embeds
- animated video posters
- trailer/reel sections

Allowed:
- static screenshots
- CSS/SVG/canvas/Three animations
- 3D laptop mockup
- screenshot texture changes inside laptop screen
- scroll-driven diagrams

## Required Visual Direction
Base style selected from SuperDesign prompt library: `neon-velocity-countdown`.

Adapt it to Shell:
- Keep dark futuristic product-launch energy, glass, bento, technical labels, scroll reveals.
- Replace laser-lime dominance with Shell cyan/emerald.
- Avoid purple gradients, beige/cream, orange/brown-dominant palettes, and generic SaaS card stacks.
- The page should feel like an OS launch/story, not a marketing template.

## Tokens

```css
:root {
  --site-bg: #061014;
  --site-bg-deep: #03070A;
  --site-bg-raised: #0D1B22;
  --site-surface: rgba(13, 27, 34, 0.72);
  --site-surface-strong: rgba(19, 41, 52, 0.82);
  --site-glass: rgba(234, 247, 251, 0.07);
  --site-border: rgba(151, 215, 229, 0.18);
  --site-border-strong: rgba(151, 215, 229, 0.30);
  --site-text: #EAF7FB;
  --site-muted: #91A8B3;
  --site-cyan: #18D7F3;
  --site-cyan-soft: rgba(24, 215, 243, 0.16);
  --site-emerald: #38D996;
  --site-emerald-soft: rgba(56, 217, 150, 0.16);
  --site-blue: #4F8CFF;
  --site-amber: #F4B860;
  --site-red: #FF6673;
  --site-shadow: 0 28px 80px rgba(0, 0, 0, 0.46);
  --site-glow-cyan: 0 0 42px rgba(24, 215, 243, 0.20);
  --site-glow-emerald: 0 0 42px rgba(56, 217, 150, 0.18);
  --site-ease: cubic-bezier(0.16, 1, 0.3, 1);
}
```

## Typography
- Display: `Plus Jakarta Sans`, `Inter`, `SF Pro Display`, `Segoe UI`, system sans.
- Body: `Inter`, `SF Pro Text`, `Segoe UI`, system sans.
- Technical/meta: `Geist Mono`, `JetBrains Mono`, `SFMono-Regular`, monospace.
- Hero H1: large and confident, but not unreadably cropped. H1 text: `Shell AI OS Controller`.
- Body copy: professional English. Internal planning can be Hinglish; public UI copy should be English.
- Letter spacing: no negative tracking. Technical labels may use positive tracking.

## Shape And Surface Rules
- Navigation and control overlays may use iOS/liquid-glass panels.
- Cards only for repeated feature items, release cards, and bounded tools.
- Do not put cards inside cards.
- Page sections should be full-width bands or unframed layouts.
- Claymorphism is allowed only as subtle 3D feature objects, not playful blobs.
- Cards radius: 8px or less unless the element is a pill, dock, or glass nav.

## Required Routes
- `/`: cinematic storytelling homepage.
- `/docs`: install and beginner docs.
- `/architecture`: detailed Shell architecture story.
- `/releases`: latest download and checksum/release metadata.

## Required Homepage Story
1. Hero: Shell AI OS Controller, open source badges, Windows CTA, GitHub/docs links, 3D laptop with Dashboard screenshot.
2. Scroll laptop story: laptop moves down, rotates subtly, screen states change through Dashboard, Control, Settings, Gallery, Apps, Notes, Phone, Macros.
3. "Not an OS. A control layer over your OS."
4. Desktop problem: apps/files/terminal/browser/APIs/logs become organized through Shell overlay.
5. How Shell thinks: user input -> Shell UI/voice/Telegram/CLI -> QWebChannel/Shell Hub -> natural-language router -> tool gateway -> safety policy -> local tools/APIs/automation -> structured result/logs/memory.
6. What Shell can do: chat, voice, 460+ guarded tools, desktop control, Windows control, browser wrappers, Telegram, email/media, runtime diagnostics, telemetry, ShellAI Core, AI OS Fabric, Memory v2, Project RAG v2, secure sandbox, workflow checkpoints.
7. Platform story: Windows best experience, macOS partial support, Linux partial support.
8. Safety cockpit: SAFE, ASK, BLOCK, TRACE.
9. Download/release: direct latest Windows EXE using GitHub latest release API.
10. Final CTA: download, audit source, read install guide.

## 3D Laptop Requirements
- Mandatory hero/story object.
- Body: dark graphite metal, thin screen bezel, glass screen layer, cyan edge glow, realistic shadow under base.
- Screen aspect: 16:10 or 16:9; screenshot must not stretch.
- Use real screenshots from `screenshots/current/*.png`.
- Scroll animation: translateY, rotateX, rotateY, scale, screen crossfade, glow intensity.
- Reduced motion: laptop static, no scrubbed rotation; screenshots change only on section enter.

## Screenshot State Map
- Dashboard: `screenshots/current/dashboard.png`
- Control: `screenshots/current/control.png`
- Settings: `screenshots/current/settings.png`
- Gallery: `screenshots/current/gallery.png`
- Apps: `screenshots/current/apps.png`
- Notes: `screenshots/current/notes.png`
- Phone: `screenshots/current/phone.png`
- Macros: `screenshots/current/macros.png`

## Platform Copy Rules
Windows:
- Label: `Best experience`
- One-click setup EXE
- Bundled `ShellAI.exe`
- Start Menu shortcut
- Optional desktop/startup shortcuts
- pywinauto support
- Windows-MCP support
- PyAutoGUI/pywin32 fallback
- Best PC-control path

macOS:
- Label: `Partial support`
- Source/helper launch
- Web UI/chat/docs/dev workflows
- Many Python tools
- Camera/mic permissions may be needed
- Windows control unavailable

Linux:
- Label: `Partial support`
- Source/helper launch
- ShellAI Core CLI
- Web UI/chat/diagnostics/dev workflows
- Desktop automation depends on local environment
- Windows-MCP/pywinauto unavailable

## Release Download Contract
- Fetch: `https://api.github.com/repos/mdshoebkhanking/shell-ai-os-controller/releases/latest`
- Select asset: `shell-ai-os-controller-setup-*.exe`
- Show version tag, asset name, file size, published date, SHA256/digest if provided.
- CTA should direct to asset `browser_download_url`.
- Fallback to `https://github.com/mdshoebkhanking/shell-ai-os-controller/releases`.

## Accessibility
- Provide visible keyboard focus.
- Meaningful text contrast must meet WCAG AA.
- Use reduced-motion media query.
- Text must not overflow buttons/cards at 375px mobile.
- First viewport must not be blank while 3D loads; use CSS laptop fallback or static screenshot fallback.

## SuperDesign Fidelity Constraint
Use ONLY the fonts, colors, spacing, and component styles defined in this design system. Do not introduce any fonts, colors, or visual styles not in this design system.

