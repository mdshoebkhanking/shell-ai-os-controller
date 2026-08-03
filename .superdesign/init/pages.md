# SuperDesign Init: Pages And Dependency Trees

## Current App: Root Shell Renderer
Entry: `shell_web_ui/src/main.tsx`

Dependencies:
- `shell_web_ui/src/assets/main.css`
- `shell_web_ui/src/shellBridge.ts`
- `shell_web_ui/src/IndexRoot.tsx`
  - `shell_web_ui/src/components/MiniOverlay.tsx`
  - `shell_web_ui/src/services/shell-voice-ai.ts`
  - `shell_web_ui/src/hooks/CaptureDesktop.ts`
  - `shell_web_ui/src/UI/ShellAI.tsx`
    - `shell_web_ui/src/views/Dashboard.tsx`
    - `shell_web_ui/src/views/Phone.tsx`
    - `shell_web_ui/src/views/APP.tsx`
    - `shell_web_ui/src/views/WorkFlowEditor.tsx`
    - `shell_web_ui/src/views/Notes.tsx`
    - `shell_web_ui/src/views/Settings.tsx`
    - `shell_web_ui/src/views/Gallery.tsx`
    - `shell_web_ui/src/views/ControlCenter.tsx`
    - `shell_web_ui/src/components/ViewSkelrton.tsx`
  - `shell_web_ui/src/components/TerminalOverlay.tsx`
  - `shell_web_ui/src/Widgets/MapView.tsx`
  - `shell_web_ui/src/Widgets/ImageWidget.tsx`
  - `shell_web_ui/src/Widgets/EmailWidget.tsx`
  - `shell_web_ui/src/Widgets/WeatherWidget.tsx`
  - `shell_web_ui/src/Widgets/StockWidget.tsx`
  - `shell_web_ui/src/Widgets/LiveCodingWidget.tsx`
  - `shell_web_ui/src/Widgets/WormholeWidget.tsx`
  - `shell_web_ui/src/Widgets/RagOrcaleWidget.tsx`
  - `shell_web_ui/src/Widgets/DeepResearch.tsx`
  - `shell_web_ui/src/Widgets/SematicSearch.tsx`
  - `shell_web_ui/src/Widgets/SmartZoneWidget.tsx`

## Current App: Dashboard
Entry: `shell_web_ui/src/views/Dashboard.tsx`

Dependencies:
- `shell_web_ui/src/assets/main.css`
- `shell_web_ui/src/components/Sphere.tsx`
- `shell_web_ui/src/services/system-info.ts`
- `shell_web_ui/src/services/shell-ai-brain.ts`
- `shell_web_ui/src/shellBridge.ts`

Large file note: `Dashboard.tsx` is 1139 lines. Use line ranges for SuperDesign context:
- `shell_web_ui/src/views/Dashboard.tsx:1:220` for imports/types/static data
- `shell_web_ui/src/views/Dashboard.tsx:520:1139` for major rendered UI and composer/transcript visual structure

## Current App: Settings
Entry: `shell_web_ui/src/views/Settings.tsx`

Dependencies:
- `shell_web_ui/src/assets/main.css`
- `shell_web_ui/src/services/api-key-utils.ts`
- `shell_web_ui/src/services/system-info.ts`
- `shell_web_ui/src/shellBridge.ts`

Large file note: `Settings.tsx` is 1166 lines. Use line ranges:
- `shell_web_ui/src/views/Settings.tsx:1:260`
- `shell_web_ui/src/views/Settings.tsx:760:1166`

## Current App: Control Center
Entry: `shell_web_ui/src/views/ControlCenter.tsx`

Dependencies:
- `shell_web_ui/src/assets/main.css`
- `shell_web_ui/src/shellBridge.ts`

Pass full file. It contains tool catalog, search, categories, risk pill, args textarea, execute button, and result panel.

## New Website: Homepage
Entry to create later: `site/src/pages/HomePage.tsx`

Dependencies to design:
- `site/src/components/LaptopStory.tsx`
- `site/src/components/ScreenshotStage.tsx`
- `site/src/components/ArchitecturePipeline.tsx`
- `site/src/components/SafetyGate.tsx`
- `site/src/components/ReleaseDownloadCard.tsx`
- `site/src/components/SiteNav.tsx`
- `site/src/components/SiteFooter.tsx`
- `site/src/styles/index.css`

Story sections:
1. Hero with Shell logo, CTA, badges, 3D laptop showing Dashboard.
2. Pinned/semi-sticky laptop story with screenshots changing on scroll.
3. Not an OS: AI desktop control layer over Windows/macOS/Linux.
4. Desktop problem: assistants stop at chat; Shell connects chat to tools/runtime/workflows.
5. How Shell thinks: input -> UI/voice/Telegram/CLI -> QWebChannel/Shell Hub -> router -> tool gateway -> safety -> tools/APIs/automation -> result/logs/memory.
6. What Shell can do: chat, voice, 460+ tools, desktop control, Windows control, browser wrappers, Telegram, email/media, diagnostics, telemetry, ShellAI Core, AI OS Fabric, Memory v2, RAG v2, secure sandbox, workflow checkpoints.
7. Platform story: Windows best, macOS partial, Linux partial.
8. Safety cockpit: SAFE, ASK, BLOCK, TRACE.
9. Download latest Windows EXE from GitHub release API.
10. Final CTA.

## New Website: Docs
Entry to create later: `site/src/pages/DocsPage.tsx`

Dependencies:
- `docs/INSTALL_BEGINNER.md`
- `README.md`
- `INSTALLATION.md`

Visual approach: clear install ladders, command blocks, API key safety warnings, Windows one-click path first.

## New Website: Architecture
Entry to create later: `site/src/pages/ArchitecturePage.tsx`

Dependencies:
- `docs/ARCHITECTURE_GUIDE.md`
- `docs/TRUST_AND_CREDIBILITY.md`

Visual approach: animated architecture pipeline, safety boundary, no hype claims.

## New Website: Releases
Entry to create later: `site/src/pages/ReleasesPage.tsx`

Dependencies:
- GitHub release API contract in `routes.md`
- `PUBLIC_RELEASE.md`

Visual approach: release card with version, asset, size, published date, checksum/digest if available, direct EXE CTA, fallback GitHub Releases link.

