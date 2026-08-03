# SuperDesign Init: Routes

## Current Shell App Routes
The existing desktop renderer is a single React app with in-component tab routing rather than URL routes.

| User Surface | URL/State | Component | Notes |
| --- | --- | --- | --- |
| Root app | `/` inside PyQt WebEngine/Vite | `shell_web_ui/src/IndexRoot.tsx` | Switches full app vs overlay and widgets |
| Full desktop shell | `isOverlay=false` | `shell_web_ui/src/UI/ShellAI.tsx` | Topbar + tabbed modules |
| Mini overlay | `isOverlay=true` | `shell_web_ui/src/components/MiniOverlay.tsx` | Small voice/control dock |
| Dashboard | `activeTab='DASHBOARD'` | `shell_web_ui/src/views/Dashboard.tsx` | Chat, telemetry, transcript, live activity |
| Apps | `activeTab='Apps'` | `shell_web_ui/src/views/APP.tsx` | Local app catalog and launch cards |
| Notes | `activeTab='NOTES'` | `shell_web_ui/src/views/Notes.tsx` | Notes/memory-style surface |
| Gallery | `activeTab='GALLERY'` | `shell_web_ui/src/views/Gallery.tsx` | Generated media/gallery |
| Control | `activeTab='CONTROL'` | `shell_web_ui/src/views/ControlCenter.tsx` | Tool catalog, tool args, execution result |
| Settings | `activeTab='SETTINGS'` | `shell_web_ui/src/views/Settings.tsx` | API keys, safety, Telegram, system controls |
| Macros | `activeTab='Macros'` | `shell_web_ui/src/views/WorkFlowEditor.tsx` | Workflow/macro editor |
| Phone | `activeTab='PHONE'` | `shell_web_ui/src/views/Phone.tsx` | Remote/mobile workflow surface |

## New Website Route Plan
Create a separate public website under `site/`:

| URL | Purpose | Required Design Notes |
| --- | --- | --- |
| `/` | Cinematic storytelling homepage | Hero + scroll-driven 3D laptop screenshot story. No video. |
| `/docs` | Beginner install and first-run docs | Clear Windows-first setup, API key setup, macOS/Linux partial source/helper flow. |
| `/architecture` | Shell architecture explanation | Scroll/pinned diagram: UI/voice/Telegram/CLI -> QWebChannel/Shell Hub -> router/tool gateway/safety -> local tools/APIs/automation -> structured result/logs/memory. |
| `/releases` | Latest download and checksum | GitHub latest release API, direct Windows EXE CTA, fallback releases link, version/date/asset/size/checksum display if available. |

## Download API Contract
- Latest release endpoint: `https://api.github.com/repos/mdshoebkhanking/shell-ai-os-controller/releases/latest`
- Windows setup asset selector: `shell-ai-os-controller-setup-*.exe`
- Fallback: `https://github.com/mdshoebkhanking/shell-ai-os-controller/releases`

## Screenshot Texture Map
Use real screenshots only. No fake screenshots, no video.

| Screen State | Source Path |
| --- | --- |
| Dashboard | `screenshots/current/dashboard.png` |
| Control | `screenshots/current/control.png` |
| Settings | `screenshots/current/settings.png` |
| Gallery | `screenshots/current/gallery.png` |
| Apps | `screenshots/current/apps.png` |
| Notes | `screenshots/current/notes.png` |
| Phone | `screenshots/current/phone.png` |
| Macros | `screenshots/current/macros.png` |

