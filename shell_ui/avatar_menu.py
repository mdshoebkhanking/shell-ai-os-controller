"""avatar_menu — Mac-style profile dropdown for Shell OS topbar.

A frameless, always-on-top, glass-style popup anchored under the topbar
avatar button. Lists profile/settings/theme/voice/language/quick-launcher/
command-palette/reconnect/help/quit actions. Each row is a flat "Mac
sheet" item with hover highlight + 10 px radius.

Wiring:

    from shell_ui.avatar_menu import AvatarMenu
    menu = AvatarMenu(main_window, callbacks={
        "settings": fn_open_settings,
        "theme_cycle": fn_cycle_theme,
        ...
    })
    top_bar.avatar_clicked.connect(lambda: menu.toggle_at(top_bar.avatar))

The menu owns its own fade-in animation, focus-out handling, and Esc
closure. Each row's label is refreshed every time the popup re-opens so
"Theme: <name>", "Voice output: ON/OFF", and "Language: <code>" reflect
live state.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Callable, Dict, Optional

from PyQt6.QtCore import (
    Qt, QSize, QPoint, QPropertyAnimation, QEasingCurve, QEvent,
)
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QKeyEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QSizePolicy,
)

logger = logging.getLogger("shell.ui.avatar_menu")
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

# Project root on sys.path so siblings import cleanly when run as a module.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    from shell_ui.design_tokens import C, S, T, R, M, SH, glass_card_qss
except Exception:  # pragma: no cover — design tokens are required.
    from design_tokens import C, S, T, R, M, SH, glass_card_qss  # type: ignore


# ===========================================================================
# MenuRow — single clickable row (icon + label + optional shortcut hint)
# ===========================================================================

class MenuRow(QFrame):
    """One row in the avatar menu. 44 px tall, hover-tinted with accent."""

    ROW_HEIGHT = 44

    def __init__(self, icon: str, label: str, shortcut: str = "",
                 on_click: Optional[Callable[[], None]] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._on_click = on_click
        self.setObjectName("avatar_menu_row")
        self.setFixedHeight(self.ROW_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(S.md, 0, S.md, 0)
        lay.setSpacing(S.sm)

        self.icon_lbl = QLabel(icon)
        self.icon_lbl.setFixedWidth(22)
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_lbl.setStyleSheet(
            f"background:transparent; border:none; color:{C.accent}; "
            f"font-size:14px;"
        )
        lay.addWidget(self.icon_lbl)

        self.label_lbl = QLabel(label)
        self.label_lbl.setStyleSheet(
            f"background:transparent; border:none; color:{C.text}; "
            f"font-family:{T.family}; font-size:{T.body_size}px; "
            f"font-weight:500;"
        )
        lay.addWidget(self.label_lbl, 1)

        self.sc_lbl = QLabel(shortcut) if shortcut else None
        if self.sc_lbl is not None:
            self.sc_lbl.setStyleSheet(
                f"background:transparent; border:none; color:{C.text_subtle}; "
                f"font-family:{T.family_mono}; font-size:{T.small_size}px;"
            )
            lay.addWidget(self.sc_lbl, 0, Qt.AlignmentFlag.AlignRight)

        self._apply_style()

    def set_label(self, text: str) -> None:
        self.label_lbl.setText(text)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            f"#avatar_menu_row {{ "
            f"  background-color:transparent; "
            f"  border:none; "
            f"  border-radius:10px; "
            f"}} "
            f"#avatar_menu_row:hover {{ "
            f"  background-color:{C.accent_soft}; "
            f"}}"
        )

    def mousePressEvent(self, ev):  # noqa: N802
        if ev.button() == Qt.MouseButton.LeftButton and self._on_click:
            try:
                self._on_click()
            except Exception as _e:
                logger.debug("avatar menu row click failed: %s", _e)
            # Bubble up so the menu can close.
            p = self.parent()
            while p is not None and not isinstance(p, AvatarMenu):
                p = p.parent()
            if isinstance(p, AvatarMenu):
                p.hide()
            ev.accept()
            return
        super().mousePressEvent(ev)


# ===========================================================================
# AvatarMenu — the dropdown popup
# ===========================================================================

class AvatarMenu(QWidget):
    """Frameless, always-on-top profile dropdown. Anchored under the
    topbar avatar button via `toggle_at(button)`.

    `callbacks` keys (each a zero-arg callable, all optional):
        profile            — open profile (no-op default)
        settings           — open settings page
        theme_cycle        — cycle ThemeEngine themes
        voice_toggle       — flip voice output on/off
        language_cycle     — cycle reply language
        quick_launcher     — toggle the global quick launcher
        command_palette    — toggle the Ctrl+K palette
        reconnect          — re-establish hub connection
        help               — open help / docs
        quit               — quit application
    """

    POPUP_W = 260
    # Header (~120) + 9 menu rows × 44 + dividers (~12) + padding ≈ 540.
    # The previous 360 height clipped the lower 4 rows (Quick launcher,
    # Help, Quit, etc.) so the user couldn't reach them.
    POPUP_H = 560

    def __init__(self, parent: Optional[QWidget] = None,
                 callbacks: Optional[Dict[str, Callable[[], None]]] = None):
        super().__init__(parent)
        self._host = parent
        self._callbacks: Dict[str, Callable[[], None]] = dict(callbacks or {})
        self._fade_anim: Optional[QPropertyAnimation] = None

        self._build_ui()
        self.hide()

    # ---------- UI scaffolding ----------
    def _build_ui(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Popup  # auto-closes on outside click
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # Allow Esc + focus tracking.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(QSize(self.POPUP_W, self.POPUP_H))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(S.md, S.md, S.md, S.md)
        outer.setSpacing(0)

        # Card body — Mac-vibrancy "light" overlay (popover strength).
        # Top-level OS window so we keep the gradient + shadow approach;
        # vibrancy_layer_qss centralises the look.
        self.card = QFrame(self)
        self.card.setObjectName("avatar_menu_card")
        try:
            from shell_ui.design_tokens import vibrancy_layer_qss as _vib
            self.card.setStyleSheet(f"#avatar_menu_card {{ {_vib('light', radius=16)} }}")
        except Exception:
            self.card.setStyleSheet(
                f"#avatar_menu_card {{ "
                f"  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                f"    stop:0 {C.glass_hi}, "
                f"    stop:0.04 {C.glass_strong}, "
                f"    stop:1 {C.glass_strong}); "
                f"  border:1px solid {C.glass_border}; "
                f"  border-top:1px solid {C.glass_hi}; "
                f"  border-radius:16px; "
                f"}}"
            )
        # Soft drop shadow halo per spec.
        try:
            eff = QGraphicsDropShadowEffect(self.card)
            eff.setBlurRadius(SH.floating.blur)
            eff.setOffset(0, SH.floating.offset_y)
            eff.setColor(QColor(0, 0, 0, 170))
            self.card.setGraphicsEffect(eff)
        except Exception as _e:
            logger.debug("shadow init failed: %s", _e)

        outer.addWidget(self.card)

        card_lay = QVBoxLayout(self.card)
        card_lay.setContentsMargins(S.md, S.md, S.md, S.md)
        card_lay.setSpacing(S.xs)

        # ----- Header: avatar + name + status pill -----
        header = QVBoxLayout()
        header.setContentsMargins(0, S.xs, 0, S.xs)
        header.setSpacing(S.xs)
        header.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.big_avatar = QLabel("U")
        self.big_avatar.setFixedSize(48, 48)
        self.big_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.big_avatar.setStyleSheet(
            f"background:{C.accent}; "
            f"color:#0b0e13; "
            f"border-radius:24px; "
            f"font-family:{T.family}; "
            f"font-size:20px; font-weight:800; "
            f"border:1px solid {C.accent};"
        )
        header.addWidget(self.big_avatar, 0, Qt.AlignmentFlag.AlignHCenter)

        name_lbl = QLabel("mdshoebking")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        name_lbl.setStyleSheet(
            f"background:transparent; border:none; color:{C.text}; "
            f"font-family:{T.family}; font-size:{T.body_strong_size + 1}px; "
            f"font-weight:700;"
        )
        header.addWidget(name_lbl)

        # Status pill — small green dot + "Online" label.
        pill_row = QHBoxLayout()
        pill_row.setContentsMargins(0, 0, 0, 0)
        pill_row.setSpacing(6)
        pill_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(
            f"background:{C.success}; border-radius:4px; border:none;"
        )
        pill_row.addWidget(dot)

        status_lbl = QLabel("Online")
        status_lbl.setStyleSheet(
            f"background:transparent; border:none; color:{C.success}; "
            f"font-family:{T.family}; font-size:{T.small_size}px; "
            f"font-weight:600;"
        )
        pill_row.addWidget(status_lbl)
        header.addLayout(pill_row)

        card_lay.addLayout(header)
        card_lay.addSpacing(S.sm)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(
            f"background-color:{C.glass_border}; border:none;"
        )
        card_lay.addWidget(div)
        card_lay.addSpacing(S.xs)

        # ----- Menu rows -----
        self.row_profile = MenuRow(
            "\U0001F464", "Profile", "",
            on_click=self._cb("profile"), parent=self.card)
        card_lay.addWidget(self.row_profile)

        self.row_settings = MenuRow(
            "⚙", "Settings", "",
            on_click=self._cb("settings"), parent=self.card)
        card_lay.addWidget(self.row_settings)

        self.row_theme = MenuRow(
            "\U0001F317", "Theme: —", "",
            on_click=self._cb("theme_cycle"), parent=self.card)
        card_lay.addWidget(self.row_theme)

        self.row_voice = MenuRow(
            "\U0001F50A", "Voice output: ON", "",
            on_click=self._cb("voice_toggle"), parent=self.card)
        card_lay.addWidget(self.row_voice)

        self.row_language = MenuRow(
            "\U0001F310", "Language: hinglish", "",
            on_click=self._cb("language_cycle"), parent=self.card)
        card_lay.addWidget(self.row_language)

        self.row_ql = MenuRow(
            "\U0001F50D", "Quick launcher", "Ctrl+Alt+S",
            on_click=self._cb("quick_launcher"), parent=self.card)
        card_lay.addWidget(self.row_ql)

        self.row_cmdp = MenuRow(
            "⌨", "Command palette", "Ctrl+K",
            on_click=self._cb("command_palette"), parent=self.card)
        card_lay.addWidget(self.row_cmdp)

        self.row_reconnect = MenuRow(
            "\U0001F4E1", "Reconnect to hub", "",
            on_click=self._cb("reconnect"), parent=self.card)
        card_lay.addWidget(self.row_reconnect)

        # Divider
        div2 = QFrame()
        div2.setFixedHeight(1)
        div2.setStyleSheet(
            f"background-color:{C.glass_border}; border:none;"
        )
        card_lay.addSpacing(S.xs)
        card_lay.addWidget(div2)
        card_lay.addSpacing(S.xs)

        self.row_help = MenuRow(
            "❓", "Help", "",
            on_click=self._cb("help"), parent=self.card)
        card_lay.addWidget(self.row_help)

        self.row_quit = MenuRow(
            "\U0001F6AA", "Quit", "",
            on_click=self._cb("quit"), parent=self.card)
        card_lay.addWidget(self.row_quit)

        card_lay.addStretch(1)

    # ---------- callback helper ----------
    def _cb(self, key: str) -> Callable[[], None]:
        """Return a safe-runner that invokes the registered callback for
        `key` (or no-ops + logs if the host didn't supply one)."""
        def _run():
            fn = self._callbacks.get(key)
            if fn is None:
                logger.debug("avatar menu: no callback for %r", key)
                return
            try:
                fn()
            except Exception as _e:
                logger.debug("avatar menu cb %r failed: %s", key, _e)
        return _run

    # ---------- live-state refresh ----------
    def _refresh_live_labels(self) -> None:
        """Pull the current theme name, voice-output state and language
        from the host so the labels reflect reality each time we open."""
        # Theme — read straight from ThemeEngine if present.
        try:
            from shell_ui.shell_cinematic_full import ThemeEngine  # type: ignore
            te = ThemeEngine.get()
            self.row_theme.set_label(f"Theme: {te.active_name}")
        except Exception as _e:
            logger.debug("theme label refresh failed: %s", _e)

        # Voice output — host attribute `_voice_output_enabled`.
        try:
            host = self._host
            if host is not None and hasattr(host, "_voice_output_enabled"):
                on = bool(getattr(host, "_voice_output_enabled"))
                self.row_voice.set_label(
                    f"Voice output: {'ON' if on else 'OFF'}")
        except Exception as _e:
            logger.debug("voice label refresh failed: %s", _e)

        # Language — env var `SHELL_LANGUAGE`.
        try:
            lang = os.environ.get("SHELL_LANGUAGE", "hinglish") or "hinglish"
            self.row_language.set_label(f"Language: {lang}")
        except Exception as _e:
            logger.debug("language label refresh failed: %s", _e)

    # ---------- show / hide / position ----------
    def toggle_at(self, anchor: QWidget) -> None:
        """Show under (or close, if already open) the given anchor widget."""
        if self.isVisible():
            self.hide()
            return
        self.show_at(anchor)

    def show_at(self, anchor: QWidget) -> None:
        """Position the popup under `anchor`, right-aligned, then fade in."""
        if anchor is None:
            return
        try:
            # Anchor's bottom-right in global coords.
            br_local = QPoint(anchor.width(), anchor.height())
            br_global = anchor.mapToGlobal(br_local)
            x = br_global.x() - self.width() + S.sm  # nudge so the
            # popup right-edge sits ~S.sm past the avatar's right edge,
            # giving a Mac-style overhang.
            y = br_global.y() + S.xs
            self.move(x, y)
        except Exception as _e:
            logger.debug("avatar menu position failed: %s", _e)

        self._refresh_live_labels()

        # Fade-in 180 ms OutCubic via windowOpacity.
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.PopupFocusReason)

        try:
            anim = QPropertyAnimation(self, b"windowOpacity", self)
            anim.setDuration(M.fast_ms)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.start()
            self._fade_anim = anim
        except Exception as _e:
            logger.debug("avatar menu fade failed: %s", _e)
            self.setWindowOpacity(1.0)

    # ---------- input handling ----------
    def keyPressEvent(self, ev: QKeyEvent) -> None:  # noqa: N802
        if ev.key() == Qt.Key.Key_Escape:
            self.hide()
            ev.accept()
            return
        super().keyPressEvent(ev)

    def focusOutEvent(self, ev) -> None:  # noqa: N802
        # Click-outside dismissal. Qt.Popup handles this for us in most
        # cases (it auto-hides on outside click) — this is a safety net
        # for platforms where Popup focus semantics differ.
        try:
            self.hide()
        except Exception as _e:
            logger.debug("avatar menu focusOut hide failed: %s", _e)
        super().focusOutEvent(ev)


# ---------------------------------------------------------------------------
# Standalone smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    from PyQt6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    win = QMainWindow()
    win.resize(800, 600)
    btn = QPushButton("U", win)
    btn.setFixedSize(32, 32)
    btn.move(740, 12)
    menu = AvatarMenu(win, callbacks={
        "profile":         lambda: print("profile"),
        "settings":        lambda: print("settings"),
        "theme_cycle":     lambda: print("theme cycle"),
        "voice_toggle":    lambda: print("voice toggle"),
        "language_cycle":  lambda: print("language cycle"),
        "quick_launcher":  lambda: print("quick launcher"),
        "command_palette": lambda: print("command palette"),
        "reconnect":       lambda: print("reconnect"),
        "help":            lambda: print("help"),
        "quit":            app.quit,
    })
    btn.clicked.connect(lambda: menu.toggle_at(btn))
    win.show()
    sys.exit(app.exec())
