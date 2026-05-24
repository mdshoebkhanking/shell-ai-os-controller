"""design_tokens — central design system for Shell OS UI.

One source of truth for colours, type, spacing, motion and shadows.
The current palettes are tuned as a coherent four-theme set: cyber,
graphite, light, and midnight. They replace the old mix of ad-hoc colour
constants and inline `setStyleSheet` blobs scattered across the UI.

Usage:

    from shell_ui.design_tokens import C, S, T, R, M, SH

    label.setStyleSheet(f"color:{C.text}; font-size:{T.body_size}px;")
    layout.setContentsMargins(S.lg, S.md, S.lg, S.md)
    QPropertyAnimation(eff, b"opacity", self).setDuration(M.base_ms)
"""
from __future__ import annotations

import sys
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Colour — canonical Shell themes.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Palette:
    # Surfaces — warm off-black, never pure black. Cards lift over bg.
    bg: str
    surface: str       # cards, sidebar
    surface_2: str     # hovered card / active nav
    surface_3: str     # double-elevated (modal content)

    # Hairlines
    border: str        # 1px on cards
    border_strong: str # 1px on inputs / dividers

    # Text
    text: str          # body
    text_muted: str    # metadata, placeholders
    text_subtle: str   # timestamps, hints

    # Brand accent (Anthropic warm coral)
    accent: str          # CTA fills, focus ring
    accent_hover: str    # primary button :hover
    accent_soft: str     # backgrounds, user bubble fill

    # Semantic
    success: str
    warning: str
    error: str

    # Semitransparent overlays
    scrim: str           # dim behind modals
    backdrop: str        # ambient bg wash

    # Glassmorphism — translucent surfaces with subtle top-edge highlight.
    # `glass` is the body, `glass_hi` is a 1-px gradient line at the top
    # of the card to simulate the way light catches frosted edges.
    glass: str           # rgba — main glass body
    glass_strong: str    # rgba — more opaque variant for elevated panels
    glass_hi: str        # rgba — top edge highlight
    glass_border: str    # rgba — border for glass cards (warmer than `border`)

    # Soft brand glow used in radial gradients on the bg.
    accent_glow: str     # rgba — wide-radius warm wash

    # ---- Apple-glassy additions (Phase 0) -----------------------------
    # Vibrancy — translucent overlay layer that pairs with a real
    # backdrop blur (see `shell_ui.glass_backdrop.GlassBackdrop`).
    # `vibrancy_dark` is for chrome (sidebar, top bar).
    # `vibrancy_light` is for popovers (palette, menus, toasts).
    vibrancy_dark: str
    vibrancy_light: str

    # One hover-overlay color used everywhere. Replaces the 14 ad-hoc
    # rgba(143,245,255,0.06)/0.08/0.10/0.12 scattered across the app.
    hover_overlay: str

    # Selection fill — translucent accent (never opaque, like macOS).
    selection: str


WARM_DARK = _Palette(
    # Shell Neural OS — near-black glass with emerald as the operating
    # accent and cyan/purple/orange telemetry notes.
    bg            = "#030303",
    surface       = "#09090b",
    surface_2     = "#18181b",
    surface_3     = "#27272a",

    border         = "rgba(255,255,255,0.07)",
    border_strong  = "rgba(16,185,129,0.30)",

    text          = "#f4f4f5",
    text_muted    = "#a1a1aa",
    text_subtle   = "#71717a",

    accent        = "#10b981",
    accent_hover  = "#34d399",
    accent_soft   = "rgba(16,185,129,0.18)",

    success       = "#34d399",
    warning       = "#f97316",
    error         = "#ef4444",

    scrim         = "rgba(0,0,0,0.72)",
    backdrop      = "rgba(16,185,129,0.07)",

    # Glass — translucent zinc-black panel with emerald light catch.
    glass         = "rgba(9,9,11,0.58)",
    glass_strong  = "rgba(12,12,14,0.78)",
    glass_hi      = "rgba(52,211,153,0.18)",
    glass_border  = "rgba(255,255,255,0.08)",

    accent_glow   = "rgba(16,185,129,0.28)",

    # Apple-glassy additions
    vibrancy_dark  = "rgba(9,9,11,0.72)",
    vibrancy_light = "rgba(24,24,27,0.78)",
    hover_overlay  = "rgba(16,185,129,0.12)",
    selection      = "rgba(16,185,129,0.24)",
)

WARM_LIGHT = _Palette(
    bg            = "#f6f8fb",
    surface       = "#ffffff",
    surface_2     = "#eef3f8",
    surface_3     = "#e4ebf3",

    border         = "rgba(22,42,64,0.10)",
    border_strong  = "rgba(22,42,64,0.18)",

    text          = "#162234",
    text_muted    = "#536275",
    text_subtle   = "#7c8796",

    accent        = "#2563eb",
    accent_hover  = "#1d4ed8",
    accent_soft   = "rgba(37,99,235,0.11)",

    success       = "#15803d",
    warning       = "#b45309",
    error         = "#dc2626",

    scrim         = "rgba(4,10,20,0.28)",
    backdrop      = "rgba(37,99,235,0.035)",

    glass         = "rgba(255,255,255,0.72)",
    glass_strong  = "rgba(255,255,255,0.92)",
    glass_hi      = "rgba(255,255,255,0.92)",
    glass_border  = "rgba(22,42,64,0.12)",
    accent_glow   = "rgba(37,99,235,0.16)",

    # Apple-glassy additions
    vibrancy_dark  = "rgba(255,255,255,0.78)",
    vibrancy_light = "rgba(255,255,255,0.94)",
    hover_overlay  = "rgba(37,99,235,0.08)",
    selection      = "rgba(37,99,235,0.18)",
)

# ---------------------------------------------------------------------------
# Two more palettes — completing the 4-theme set the UI exposes.
# ---------------------------------------------------------------------------

# Graphite dark — quiet high-contrast base for repeated daily work.
DARK = _Palette(
    bg            = "#080b10",
    surface       = "#111720",
    surface_2     = "#1a2230",
    surface_3     = "#242d3c",

    border         = "rgba(202,213,226,0.09)",
    border_strong  = "rgba(202,213,226,0.18)",

    text          = "#edf2f8",
    text_muted    = "#a4b0c0",
    text_subtle   = "#697587",

    accent        = "#60a5fa",
    accent_hover  = "#93c5fd",
    accent_soft   = "rgba(96,165,250,0.13)",

    success       = "#34d399",
    warning       = "#fbbf24",
    error         = "#f87171",

    scrim         = "rgba(3,6,12,0.68)",
    backdrop      = "rgba(96,165,250,0.04)",

    glass         = "rgba(22,30,42,0.58)",
    glass_strong  = "rgba(28,38,52,0.76)",
    glass_hi      = "rgba(226,235,247,0.13)",
    glass_border  = "rgba(202,213,226,0.13)",

    accent_glow   = "rgba(96,165,250,0.20)",

    # Apple-glassy additions
    vibrancy_dark  = "rgba(17,23,32,0.64)",
    vibrancy_light = "rgba(35,45,60,0.76)",
    hover_overlay  = "rgba(202,213,226,0.08)",
    selection      = "rgba(96,165,250,0.22)",
)

# Midnight purple — moody violet glass, soft pink accent.
MIDNIGHT = _Palette(
    bg            = "#0b0714",
    surface       = "#141027",
    surface_2     = "#1e1838",
    surface_3     = "#2a2250",

    border         = "rgba(211,190,255,0.10)",
    border_strong  = "rgba(211,190,255,0.20)",

    text          = "#f0eaff",
    text_muted    = "#aaa0cf",
    text_subtle   = "#746992",

    accent        = "#a78bfa",
    accent_hover  = "#c4b5fd",
    accent_soft   = "rgba(167,139,250,0.15)",

    success       = "#5fd3a3",
    warning       = "#ffb547",
    error         = "#ff6b8a",

    scrim         = "rgba(5,2,15,0.65)",
    backdrop      = "rgba(167,139,250,0.05)",

    glass         = "rgba(30,23,54,0.58)",
    glass_strong  = "rgba(40,31,70,0.76)",
    glass_hi      = "rgba(230,218,255,0.17)",
    glass_border  = "rgba(211,190,255,0.18)",

    accent_glow   = "rgba(167,139,250,0.25)",

    # Apple-glassy additions
    vibrancy_dark  = "rgba(20,15,39,0.64)",
    vibrancy_light = "rgba(40,31,70,0.78)",
    hover_overlay  = "rgba(211,190,255,0.10)",
    selection      = "rgba(167,139,250,0.24)",
)

# Map theme NAME (from ThemeEngine) → palette. Names match the keys in
# ThemeEngine.THEMES so a single `set_palette_by_name(name)` call is enough.
PALETTES: dict[str, _Palette] = {
    "DARK":             DARK,            # Mac-warm dark
    "LIGHT":            WARM_LIGHT,      # Mac-warm light
    "CYBER_NEON":       WARM_DARK,       # current cyan-cyber (was DEFAULT)
    "MIDNIGHT_PURPLE":  MIDNIGHT,        # violet
}


@dataclass(frozen=True)
class ThemeMetadata:
    display_name: str
    mode: str
    intent: str
    best_for: str


THEME_METADATA: dict[str, ThemeMetadata] = {
    "CYBER_NEON": ThemeMetadata(
        display_name="Cyber Neon",
        mode="dark",
        intent="Signature Shell cockpit with cyan operational accents.",
        best_for="voice, tools, and live automation demos",
    ),
    "DARK": ThemeMetadata(
        display_name="Graphite Dark",
        mode="dark",
        intent="Quiet daily-work theme with restrained blue accents.",
        best_for="long coding, chat, and repeat usage",
    ),
    "LIGHT": ThemeMetadata(
        display_name="Clean Light",
        mode="light",
        intent="Bright accessible mode for documentation, setup, and daytime work.",
        best_for="beginner setup, screenshots, and support flows",
    ),
    "MIDNIGHT_PURPLE": ThemeMetadata(
        display_name="Midnight",
        mode="dark",
        intent="Soft violet mode for low-light voice and focus sessions.",
        best_for="voice, ambient operation, and presentations",
    ),
}


@dataclass(frozen=True)
class PaletteAuditIssue:
    theme: str
    token: str
    background: str
    ratio: float
    required: float
    severity: str

# Default — `CYBER_NEON` keeps backward compat with current visual.
C: _Palette = PALETTES["CYBER_NEON"]
_active_name: str = "CYBER_NEON"

# Listeners get called on every palette swap so widgets can re-polish.
_listeners: list = []


def palette_names() -> list[str]:
    return list(PALETTES.keys())


def theme_metadata(name: str | None = None) -> ThemeMetadata:
    """Return human-facing theme details for UI settings and docs."""
    theme_name = name or _active_name
    return THEME_METADATA.get(
        theme_name,
        ThemeMetadata(
            display_name=theme_name.replace("_", " ").title(),
            mode="unknown",
            intent="Custom Shell theme.",
            best_for="general use",
        ),
    )


def active_palette_name() -> str:
    return _active_name


def set_palette(p: _Palette) -> None:
    """Swap the active palette by reference (legacy helper)."""
    global C
    C = p
    for fn in list(_listeners):
        try: fn()
        except Exception: pass


def set_palette_by_name(name: str) -> bool:
    """Swap the active palette by ThemeEngine name. Returns True if found.

    On success, fires every registered listener so widgets can re-polish.
    Names supported: DARK, LIGHT, CYBER_NEON, MIDNIGHT_PURPLE.
    """
    global C, _active_name
    p = PALETTES.get(name)
    if p is None:
        return False
    C = p
    _active_name = name
    for fn in list(_listeners):
        try: fn()
        except Exception: pass
    return True


def audit_palette_contrast(
    *,
    text_min: float = 4.5,
    muted_min: float = 3.0,
) -> list[PaletteAuditIssue]:
    """Check theme contrast for the core surfaces.

    This intentionally audits solid hex tokens only. Translucent glass
    overlays depend on the parent surface, so they are validated visually
    by screenshot review instead of pretending a single ratio is exact.
    """
    issues: list[PaletteAuditIssue] = []
    for name, p in PALETTES.items():
        checks = [
            ("text", p.text, p.bg, text_min),
            ("text", p.text, p.surface, text_min),
            ("text", p.text, p.surface_2, text_min),
            ("text", p.text, p.surface_3, text_min),
            ("muted", p.text_muted, p.bg, muted_min),
            ("muted", p.text_muted, p.surface, muted_min),
            ("subtle", p.text_subtle, p.bg, muted_min),
            ("accent_text", text_for_fill(p.accent), p.accent, text_min),
        ]
        for token, fg, bg, required in checks:
            ratio = contrast_ratio(fg, bg)
            if ratio < required:
                issues.append(
                    PaletteAuditIssue(
                        theme=name,
                        token=token,
                        background=bg,
                        ratio=round(ratio, 2),
                        required=required,
                        severity="high" if required >= 4.5 else "medium",
                    )
                )
    return issues


def on_palette_change(fn) -> None:
    """Register a callback fired after the active palette changes."""
    if fn not in _listeners:
        _listeners.append(fn)


def off_palette_change(fn) -> None:
    try: _listeners.remove(fn)
    except ValueError: pass


# ---------------------------------------------------------------------------
# Type scale — sizes in px, weights match Qt's int convention (1–99 or
# Qt.QFont.Weight.* enums in widgets.py).
# ---------------------------------------------------------------------------

_DEFAULT_UI_FONT = "Segoe UI" if sys.platform == "win32" else "Arial" if sys.platform == "darwin" else "DejaVu Sans"
_DEFAULT_MONO_FONT = "Consolas" if sys.platform == "win32" else "Menlo" if sys.platform == "darwin" else "DejaVu Sans Mono"

@dataclass(frozen=True)
class _Type:
    # Keep these concrete for Qt stylesheets. Generic CSS families like
    # `sans-serif` can trigger slow missing-font alias resolution in Qt.
    family: str = _DEFAULT_UI_FONT
    family_mono: str = _DEFAULT_MONO_FONT

    # Mac-style scale — slightly larger body, looser line-heights for
    # the breathing-room feel of macOS apps.
    display_size: int = 32
    h1_size: int = 24
    h2_size: int = 19
    body_size: int = 14
    body_strong_size: int = 14
    small_size: int = 12
    mono_size: int = 13

    display_lh: float = 1.18
    h1_lh: float = 1.25
    h2_lh: float = 1.32
    body_lh: float = 1.55
    small_lh: float = 1.45


T = _Type()


# ---------------------------------------------------------------------------
# Spacing scale — pixel values. Use these instead of magic 4/12/14/etc.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Space:
    xs:   int = 4
    sm:   int = 8
    md:   int = 12
    lg:   int = 16
    xl:   int = 24
    xxl:  int = 32
    xxxl: int = 48


S = _Space()


# ---------------------------------------------------------------------------
# Border radius
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Radius:
    # Mac-style: larger, softer corners. macOS Sonoma uses ~10 for
    # buttons, 12-16 for cards, 20+ for modals/sheets.
    xs:  int = 6    # tags, dots
    sm:  int = 8    # small buttons
    md:  int = 12   # buttons, inputs
    lg:  int = 16   # cards
    xl:  int = 20   # modals, big cards
    pill: int = 999


R = _Radius()


# ---------------------------------------------------------------------------
# Motion — durations + canonical easing curve names (Qt enum names).
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Motion:
    # Mac-style timing — slightly longer than typical web, with springy
    # easings that give the "soft landing" feel of macOS sheets.
    fast_ms:  int = 180   # hover fades, dot pulses
    base_ms:  int = 280   # page transitions, bubble entry
    slow_ms:  int = 380   # modal/overlay, sheet slide
    extra_ms: int = 500   # very slow, ambient

    # Apple-glassy: spring-settle for sheets and popovers.
    spring_settle_ms: int = 320
    spring_overshoot: float = 1.05

    # macOS spring curve approximation. QEasingCurve doesn't ship a
    # named "macSpring" but `OutCubic` and `OutQuint` are visually close.
    # Use `OutCubic` for hover/press, `OutQuint` for sheet/page.
    ease_out_cubic:  str = "OutCubic"
    ease_out_quint:  str = "OutQuint"
    ease_in_out_quart: str = "InOutQuart"
    ease_linear:     str = "Linear"


M = _Motion()


# ---------------------------------------------------------------------------
# Shadows — applied via QGraphicsDropShadowEffect (blur, offset_y, color).
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _ShadowSpec:
    blur: int
    offset_y: int
    color: str  # rgba string


@dataclass(frozen=True)
class _Shadow:
    # Mac-style shadows — softer, more spread, gentler offset.
    # macOS uses a layered shadow approach: tiny crisp 1px + bigger soft.
    # We approximate with a single QGraphicsDropShadowEffect per layer.
    soft:     _ShadowSpec = _ShadowSpec(blur=20, offset_y=6,  color="rgba(0,0,0,0.22)")
    elevated: _ShadowSpec = _ShadowSpec(blur=36, offset_y=12, color="rgba(0,0,0,0.28)")
    floating: _ShadowSpec = _ShadowSpec(blur=56, offset_y=20, color="rgba(0,0,0,0.34)")
    # Very subtle ambient — used on rest-state buttons / chips.
    whisper:  _ShadowSpec = _ShadowSpec(blur=10, offset_y=2,  color="rgba(0,0,0,0.14)")


SH = _Shadow()


# ---------------------------------------------------------------------------
# Convenience helpers — produce common QSS snippets so widgets stay terse.
# ---------------------------------------------------------------------------

def card_qss(elevated: bool = False) -> str:
    """Standard card surface: `surface` bg, hairline border, radius lg."""
    rad = R.xl if elevated else R.lg
    return (
        f"background-color:{C.surface}; "
        f"border:1px solid {C.border}; "
        f"border-radius:{rad}px;"
    )


def glass_card_qss(elevated: bool = False, strong: bool = False) -> str:
    """Glassmorphism surface — translucent warm panel with a top-edge
    highlight gradient simulating refracted light. Sits over the ambient
    bg wash so the warmth bleeds through."""
    rad = R.xl if elevated else R.lg
    body = C.glass_strong if strong else C.glass
    # Gradient: top 1-2px = `glass_hi` (highlight), then settles into
    # the body colour. Creates a subtle frosted-edge feel.
    return (
        f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        f"  stop:0 {C.glass_hi}, "
        f"  stop:0.04 {body}, "
        f"  stop:1 {body}); "
        f"border:1px solid {C.glass_border}; "
        f"border-top:1px solid {C.glass_hi}; "
        f"border-radius:{rad}px;"
    )


def _hex_to_rgb(value: str) -> tuple[int, int, int] | None:
    value = (value or "").strip()
    if not value.startswith("#"):
        return None
    raw = value[1:]
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6:
        return None
    try:
        return tuple(int(raw[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel(v: int) -> float:
        c = v / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str) -> float:
    """Return WCAG contrast ratio for two hex colors, or 1.0 if unknown."""
    fg_rgb = _hex_to_rgb(fg)
    bg_rgb = _hex_to_rgb(bg)
    if fg_rgb is None or bg_rgb is None:
        return 1.0
    l1 = _relative_luminance(fg_rgb)
    l2 = _relative_luminance(bg_rgb)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def text_for_fill(fill: str, *, dark: str = "#041018", light: str = "#ffffff") -> str:
    """Choose the higher-contrast readable text color for a solid fill."""
    return dark if contrast_ratio(dark, fill) >= contrast_ratio(light, fill) else light


def accent_text_color() -> str:
    """Readable text color for the active accent fill."""
    return text_for_fill(C.accent)


def _accessible_button_text() -> str:
    return accent_text_color()


def primary_button_qss() -> str:
    # Mac-style: solid accent, slight inner gradient for depth, generous
    # padding, larger radius. `:pressed` gives a 1-px settle (scale-down
    # is not available in QSS so we shift padding instead).
    # A11y: text color is chosen to clear WCAG AA on the chosen accent
    # (the old hard-coded white failed badly on cyan).
    txt = _accessible_button_text()
    return (
        f"QPushButton {{ "
        f"  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, "
        f"    stop:0 {C.accent_hover}, stop:0.5 {C.accent}, stop:1 {C.accent}); "
        f"  color:{txt}; "
        f"  border:1px solid {C.accent_hover}; "
        f"  border-radius:{R.md}px; "
        f"  padding:8px 18px; "
        f"  font-family:'{T.family}'; font-size:{T.body_size}px; font-weight:600; "
        f"}} "
        f"QPushButton:hover  {{ "
        f"  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, "
        f"    stop:0 {C.accent_hover}, stop:1 {C.accent_hover}); "
        f"}} "
        f"QPushButton:pressed {{ padding-top:9px; padding-bottom:7px; }} "
        f"QPushButton:disabled {{ background:{C.surface_2}; color:{C.text_subtle}; "
        f"  border:1px solid {C.border}; }}"
    )


def secondary_button_qss() -> str:
    # Mac toolbar / inspector button — translucent fill, hairline border.
    return (
        f"QPushButton {{ "
        f"  background-color:{C.surface_2}; color:{C.text}; "
        f"  border:1px solid {C.border_strong}; border-radius:{R.md}px; "
        f"  padding:8px 18px; "
        f"  font-family:'{T.family}'; font-size:{T.body_size}px; font-weight:600; "
        f"}} "
        f"QPushButton:hover   {{ background-color:{C.surface_3}; "
        f"  border:1px solid {C.accent}; }} "
        f"QPushButton:pressed {{ padding-top:9px; padding-bottom:7px; }} "
        f"QPushButton:disabled {{ color:{C.text_subtle}; }}"
    )


def ghost_button_qss() -> str:
    return (
        f"QPushButton {{ "
        f"  background-color:transparent; color:{C.text_muted}; "
        f"  border:none; border-radius:{R.md}px; "
        f"  padding:6px 12px; "
        f"  font-family:'{T.family}'; font-size:{T.body_size}px; "
        f"}} "
        f"QPushButton:hover  {{ background-color:{C.accent_soft}; color:{C.text}; }} "
        f"QPushButton:pressed {{ padding-top:7px; padding-bottom:5px; }}"
    )


def input_qss(focused: bool = False) -> str:
    # Mac inputs: rounded, taller, soft accent ring on focus (approximated
    # by a 2px accent border).
    border = C.accent if focused else C.border_strong
    border_width = 2 if focused else 1
    return (
        f"background-color:{C.surface}; "
        f"color:{C.text}; "
        f"border:{border_width}px solid {border}; "
        f"border-radius:{R.md}px; "
        f"padding:9px 14px; "
        f"font-family:'{T.family}'; font-size:{T.body_size}px; "
        f"selection-background-color:{C.accent_soft}; "
        f"selection-color:{C.text};"
    )


def pill_qss(tone: str = "neutral") -> str:
    """Small inline status pill. Tone: neutral / success / warning / error / accent."""
    fg = {
        "neutral": C.text_muted,
        "success": C.success,
        "warning": C.warning,
        "error":   C.error,
        "accent":  C.accent,
    }.get(tone, C.text_muted)
    return (
        f"background-color:transparent; "
        f"color:{fg}; "
        f"border:1px solid {fg}40; "  # 40 ≈ 25% alpha when appended to hex (Qt accepts)
        f"border-radius:{R.pill}px; "
        f"padding:3px 10px; "
        f"font-size:{T.small_size}px; "
        f"font-weight:600;"
    )


def status_color(state: str) -> str:
    """Canonical color for capability/runtime status labels."""
    key = (state or "").strip().lower()
    if key in {"ready", "online", "success", "connected", "listening", "speaking"}:
        return C.success
    if key in {"warning", "needs_setup", "needs_api_key", "missing_dependency", "offline_only"}:
        return C.warning
    if key in {"error", "failed", "blocked", "blocked_by_safety", "critical"}:
        return C.error
    if key in {"active", "running", "info", "experimental"}:
        return C.accent
    return C.text_muted


def status_pill_qss(state: str = "neutral") -> str:
    """Readable status pill used by health, tools, voice, and settings."""
    col = status_color(state)
    return (
        f"background-color:transparent; "
        f"color:{col}; "
        f"border:1px solid {col}55; "
        f"border-radius:{R.pill}px; "
        f"padding:4px 11px; "
        f"font-family:'{T.family}'; "
        f"font-size:{T.small_size}px; "
        f"font-weight:700;"
    )


def scrollbar_qss(axis: str = "vertical") -> str:
    """Thin, low-noise scrollbar for dense operation panels."""
    if axis == "horizontal":
        return (
            "QScrollBar:horizontal { height:8px; background:transparent; margin:0; }"
            f"QScrollBar::handle:horizontal {{ background:{C.border_strong}; "
            "border-radius:4px; min-width:28px; }}"
            f"QScrollBar::handle:horizontal:hover {{ background:{C.accent}; }}"
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }"
            "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background:transparent; }"
        )
    return (
        "QScrollBar:vertical { width:8px; background:transparent; margin:0; }"
        f"QScrollBar::handle:vertical {{ background:{C.border_strong}; "
        "border-radius:4px; min-height:28px; }}"
        f"QScrollBar::handle:vertical:hover {{ background:{C.accent}; }}"
        "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }"
        "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background:transparent; }"
    )


def app_shell_qss() -> str:
    """Base app surface for top-level PyQt widgets."""
    return (
        f"background-color:{C.bg}; "
        f"color:{C.text}; "
        f"font-family:'{T.family}';"
    )


def vibrancy_layer_qss(strength: str = "dark", *, bordered: bool = True,
                       radius: int | None = None) -> str:
    """Translucent overlay that pairs with `GlassBackdrop` for true Apple
    Sonoma vibrancy. Use on chrome surfaces (sidebar, top bar, popovers).

    Pass strength="dark" for sidebars / top bars over content,
    "light" for popovers / menus that float above everything.

    Pair this with a `GlassBackdrop` placed BEHIND the widget so the
    blurred parent pixmap shows through the translucency.
    """
    body = C.vibrancy_dark if strength == "dark" else C.vibrancy_light
    rad = radius if radius is not None else R.lg
    border_line = f"border:1px solid {C.glass_border}; " if bordered else "border:none; "
    return (
        f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        f"  stop:0 {C.glass_hi}, "
        f"  stop:0.04 {body}, "
        f"  stop:1 {body}); "
        f"{border_line}"
        f"border-top:1px solid {C.glass_hi}; "
        f"border-radius:{rad}px;"
    )
