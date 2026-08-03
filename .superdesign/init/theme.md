# SuperDesign Init: Theme

## Source Tokens From Existing Shell UI
Relevant lines from `shell_web_ui/src/assets/main.css`. Full file is 1050 lines, so SuperDesign commands should pass selected ranges: `1:340`, `560:900`, `900:1050`.

```css
@import 'tailwindcss';

:root {
  --shell-bg-0: #050609;
  --shell-bg-1: #090b10;
  --shell-bg-2: #11141b;
  --shell-surface: rgba(18, 21, 29, 0.76);
  --shell-surface-soft: rgba(235, 241, 248, 0.055);
  --shell-surface-strong: rgba(28, 32, 42, 0.86);
  --shell-glass: rgba(238, 244, 252, 0.065);
  --shell-glass-strong: rgba(238, 244, 252, 0.11);
  --shell-border: rgba(215, 225, 238, 0.13);
  --shell-border-strong: rgba(230, 237, 247, 0.22);
  --shell-primary: #86a8e7;
  --shell-primary-soft: #b9c9ee;
  --shell-primary-glow: rgba(134, 168, 231, 0.20);
  --shell-ai: #d7e1ee;
  --shell-data: #9bd4ee;
  --shell-success: #22c55e;
  --shell-warning: #f59e0b;
  --shell-danger: #ef4444;
  --shell-text: #f4f7fb;
  --shell-muted: #8c98a8;
  --shell-liquid-ease: cubic-bezier(0.16, 1, 0.3, 1);
}

.shell-ui-root {
  color: var(--shell-text);
  background:
    radial-gradient(circle at 14% 8%, rgba(215, 225, 238, 0.07), transparent 33%),
    radial-gradient(circle at 86% 14%, rgba(134, 168, 231, 0.08), transparent 29%),
    linear-gradient(135deg, var(--shell-bg-0), var(--shell-bg-1) 48%, var(--shell-bg-2));
}

.shell-liquid-panel {
  position: relative;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.088), rgba(255, 255, 255, 0.036)),
    rgba(15, 18, 25, 0.66);
  border: 1px solid var(--shell-border);
  border-radius: 22px;
  box-shadow:
    0 18px 56px rgba(0, 0, 0, 0.34),
    inset 0 1px 0 rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(18px) saturate(118%);
}

.shell-primary-action {
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.17), rgba(134, 168, 231, 0.16)),
    rgba(24, 29, 39, 0.92) !important;
  border-color: rgba(185, 201, 238, 0.34) !important;
  box-shadow:
    0 14px 30px var(--shell-primary-glow),
    inset 0 1px 0 rgba(255, 255, 255, 0.22) !important;
  color: #f8fbff !important;
}

@media (prefers-reduced-motion: reduce) {
  .animate-in,
  .shell-shimmer,
  .shell-workstream-panel,
  .shell-workstream-panel::after,
  .shell-workstream-orb span,
  .shell-workstream-steps span.is-active::before {
    animation-duration: 1ms;
    animation-delay: 0ms;
  }

  .shell-tab,
  .shell-tab-indicator,
  .shell-control-button {
    transition-duration: 1ms;
  }
}
```

## Website Design Tokens
Use these as hard constraints for the new website design.

| Token | Value | Use |
| --- | --- | --- |
| `--site-bg` | `#061014` | Primary website background |
| `--site-bg-deep` | `#03070A` | Hero/deep bands |
| `--site-surface` | `rgba(13, 27, 34, 0.72)` | Liquid panels |
| `--site-surface-raised` | `rgba(19, 41, 52, 0.78)` | Active overlays |
| `--site-border` | `rgba(151, 215, 229, 0.18)` | Hairlines/glass borders |
| `--site-text` | `#EAF7FB` | Primary copy |
| `--site-muted` | `#91A8B3` | Secondary copy |
| `--site-cyan` | `#18D7F3` | Primary CTA, active screen glow |
| `--site-emerald` | `#38D996` | Ready/safe/success |
| `--site-blue` | `#4F8CFF` | Link/info |
| `--site-amber` | `#F4B860` | ASK/caution |
| `--site-red` | `#FF6673` | BLOCK/error |
| `--site-ease` | `cubic-bezier(0.16, 1, 0.3, 1)` | All transitions |

## Typography
- Hero/display: `Plus Jakarta Sans`, `Inter`, `SF Pro Display`, `Segoe UI`, system sans.
- Body: `Inter`, `SF Pro Text`, `Segoe UI`, system sans.
- Technical labels: `Geist Mono`, `JetBrains Mono`, `SFMono-Regular`, monospace.
- Avoid negative letter spacing. Uppercase technical labels may use positive tracking.

## Animation/Motion Rules
- Allowed: CSS transitions, SVG stroke animations, GSAP ScrollTrigger, Three/R3F laptop particles, framer-motion micro interactions.
- Required reduced-motion fallback: no scrubbed laptop movement; screenshots change on section enter only.
- No MP4, WebM, GIF, autoplay trailer, YouTube iframe, or animated video poster in this phase.

