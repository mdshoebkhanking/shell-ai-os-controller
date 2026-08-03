# SuperDesign Init: Extractable Components

## ShellTopNav
- Source: `shell_web_ui/src/UI/ShellAI.tsx`
- Category: layout
- Description: Main Shell topbar with logo, module tabs, more menu, and ready status.
- Extractable props: `activeItem` string default `DASHBOARD`, `showMore` boolean default `false`.
- Hardcoded: logo path, module labels, react-icons, all glass classes.

## MiniControlDock
- Source: `shell_web_ui/src/components/MiniOverlay.tsx`
- Category: layout
- Description: Compact liquid-glass voice/control dock with mic, power, camera, screen, expand controls.
- Extractable props: `isActive` boolean default `true`, `isMuted` boolean default `false`, `visionMode` string default `none`.
- Hardcoded: icon set, circular control layout, Shell glass styling.

## ShellLiquidPanel
- Source: `shell_web_ui/src/assets/main.css`
- Category: basic
- Description: Reusable glass panel pattern with dark surface, blurred backdrop, border, inset highlight, and large shadow.
- Extractable props: none.
- Hardcoded: `shell-liquid-panel` styling.

## ShellControlButton
- Source: `shell_web_ui/src/assets/main.css`
- Category: basic
- Description: Pressable control button with small scale/translate hover and active states.
- Extractable props: `active` boolean default `false`.
- Hardcoded: hover transform, Shell primary-action styling.

## ShellParticleOrb
- Source: `shell_web_ui/src/components/Sphere.tsx`
- Category: basic
- Description: Three.js/R3F particle orb with CSS fallback.
- Extractable props: `active` boolean default `true`.
- Hardcoded: particle colors and audio-reactive behavior.

## ReleaseDownloadCard
- Source: to create under `site/src/components/ReleaseDownloadCard.tsx`
- Category: basic
- Description: Website card that fetches latest release metadata and exposes direct Windows EXE download.
- Extractable props: `version`, `assetName`, `assetSize`, `publishedAt`, `downloadHref`, `fallbackHref`.
- Hardcoded: GitHub owner/repo, Windows EXE selection rule.

## LaptopStoryStage
- Source: to create under `site/src/components/LaptopStory.tsx`
- Category: layout
- Description: Main website hero/story object: 3D laptop mockup with real screenshot textures and scroll-linked transforms.
- Extractable props: `screenState` string default `dashboard`, `reducedMotion` boolean default `false`.
- Hardcoded: screenshot map, laptop body geometry, Shell cyan/emerald glow.

