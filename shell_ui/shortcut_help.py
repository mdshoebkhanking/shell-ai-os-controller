"""shortcut_help — Mac-style "?" keyboard shortcut help overlay for Shell OS.

A frameless, always-on-top, modal-style overlay that lists every keyboard
shortcut the Shell UI binds, presented as a 2-column grid of Mac-style
keycaps + descriptions, grouped by category.

Wiring:
    from shell_ui.shortcut_help import ShortcutHelp
    help_overlay = ShortcutHelp(main_window)
    QShortcut(QKeySequence("?"), main_window, activated=help_overlay.toggle)

Standalone:
    python -m shell_ui.shortcut_help
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger("shell.ui.shortcut_help")
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

# Project root on sys.path so siblings import cleanly when run as a module.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from PyQt6.QtCore import (
    Qt, QSize, QEvent, QTimer, QPoint, QRect,
    QPropertyAnimation, QEasingCurve, QParallelAnimationGroup,
)
from PyQt6.QtGui import (
    QKeyEvent, QMouseEvent, QShortcut, QKeySequence, QColor, QFont,
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QScrollArea, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
    QMainWindow, QSizePolicy,
)

try:
    from shell_ui.design_tokens import C, S, T, R, M, SH, glass_card_qss
except Exception:  # pragma: no cover — design tokens are required.
    from design_tokens import C, S, T, R, M, SH, glass_card_qss  # type: ignore


# ===========================================================================
# Shortcut model
# ===========================================================================

@dataclass(frozen=True)
class Shortcut:
    """A single keyboard shortcut entry.

    `keys` is the chord rendered left-to-right as Mac-style keycaps joined
    with a "+" separator, e.g. ["Ctrl", "Alt", "S"] or ["Shift", "Enter"]
    or ["?"]. `description` is the human-readable action. `category` groups
    rows in the rendered grid.
    """
    keys: List[str]
    description: str
    category: str


# Full registry covering every key Shell binds today (and the help overlay
# itself). Keep grouped by category in display order.
SHORTCUTS: List[Shortcut] = [
    # ---- Global ---------------------------------------------------------
    Shortcut(["Ctrl", "Alt", "S"], "Open Quick Launcher",        "Global"),
    Shortcut(["Ctrl", "K"],        "Open Command Palette",       "Global"),

    # ---- Chat -----------------------------------------------------------
    Shortcut(["Enter"],            "Send message",               "Chat"),
    Shortcut(["Shift", "Enter"],   "Insert newline",             "Chat"),
    Shortcut(["↑"],           "Recall last message",        "Chat"),
    Shortcut(["Esc"],              "Clear draft",                "Chat"),
    Shortcut(["Ctrl", "L"],        "Clear chat",                 "Chat"),

    # ---- Navigation -----------------------------------------------------
    Shortcut(["Click"],            "Switch page via sidebar",    "Navigation"),
    Shortcut(["Ctrl", "1"],        "Go to Chat page",            "Navigation"),
    Shortcut(["Ctrl", "2"],        "Go to Voice page",           "Navigation"),
    Shortcut(["Ctrl", "3"],        "Go to System page",          "Navigation"),
    Shortcut(["Ctrl", "4"],        "Go to Settings page",        "Navigation"),

    # ---- Help -----------------------------------------------------------
    Shortcut(["?"],                "Toggle this shortcut help",  "Help"),
    Shortcut(["Esc"],              "Close this overlay",         "Help"),
]


# ===========================================================================
# Mac-style keycap label
# ===========================================================================

class KbdKey(QLabel):
    """Renders one key as a Mac-style keycap.

    Rounded rectangle, soft border, an extra bottom-border to give a
    subtle 3D depth (the "settle" of a physical key), monospace font
    so width-per-char stays consistent. Width auto-fits the text.
    """

    def __init__(self, text: str, parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setObjectName("kbd_key")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Maximum,
                           QSizePolicy.Policy.Fixed)
        # Slight vertical breathing room — keycaps look squat without it.
        self.setMinimumHeight(22)
        self.setStyleSheet(self._qss())

    @staticmethod
    def _qss() -> str:
        # Token-driven Mac keycap: surface_2 → surface gradient body, hairline
        # border, thicker bottom-border for that "physical key" depth, mono
        # font, generous-but-tight padding, min-width so single chars (?, ↑)
        # don't shrink to nothing.
        return (
            f"QLabel#kbd_key {{ "
            f"  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"    stop:0 {C.surface_2}, stop:1 {C.surface}); "
            f"  color:{C.text}; "
            f"  border:1px solid {C.border_strong}; "
            f"  border-bottom:2px solid {C.border_strong}; "
            f"  border-radius:{R.xs}px; "
            f"  padding:4px 8px; "
            f"  font-family:{T.family_mono}; "
            f"  font-size:{T.small_size}px; "
            f"  font-weight:600; "
            f"  min-width:22px; "
            f"}}"
        )


# ===========================================================================
# 2-column shortcut grid
# ===========================================================================

class ShortcutGrid(QWidget):
    """A 2-column grid of shortcut rows grouped by category.

    Left column = keycaps row (KbdKey widgets joined by "+"); right column =
    description. Each category is preceded by a small heading row that
    spans both columns.
    """

    def __init__(self, shortcuts: List[Shortcut],
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("shortcut_grid")
        self.setStyleSheet("QWidget#shortcut_grid { background:transparent; }")

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(S.lg)
        grid.setVerticalSpacing(S.sm)
        # Description column should soak up any extra width.
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)

        row = 0
        last_category: Optional[str] = None
        for sc in shortcuts:
            if sc.category != last_category:
                heading = QLabel(sc.category.upper())
                heading.setStyleSheet(
                    f"background:transparent; "
                    f"color:{C.text_subtle}; "
                    f"font-family:{T.family}; "
                    f"font-size:{T.small_size}px; "
                    f"font-weight:700; "
                    f"letter-spacing:1px; "
                    f"padding:{S.sm}px 0 {S.xs}px 0;"
                )
                grid.addWidget(heading, row, 0, 1, 2,
                               Qt.AlignmentFlag.AlignLeft)
                row += 1
                last_category = sc.category

            # Left: keycaps row.
            keys_widget = self._build_keys_row(sc.keys)
            grid.addWidget(keys_widget, row, 0, Qt.AlignmentFlag.AlignLeft)

            # Right: description.
            desc = QLabel(sc.description)
            desc.setStyleSheet(
                f"background:transparent; "
                f"color:{C.text}; "
                f"font-family:{T.family}; "
                f"font-size:{T.body_size}px; "
                f"font-weight:500;"
            )
            desc.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            desc.setWordWrap(True)
            grid.addWidget(desc, row, 1)

            row += 1

    @staticmethod
    def _build_keys_row(keys: List[str]) -> QWidget:
        wrap = QWidget()
        wrap.setStyleSheet("background:transparent;")
        wrap.setSizePolicy(QSizePolicy.Policy.Maximum,
                           QSizePolicy.Policy.Fixed)
        h = QHBoxLayout(wrap)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(S.xs)
        for i, k in enumerate(keys):
            if i > 0:
                plus = QLabel("+")
                plus.setStyleSheet(
                    f"background:transparent; "
                    f"color:{C.text_subtle}; "
                    f"font-family:{T.family_mono}; "
                    f"font-size:{T.small_size}px; "
                    f"font-weight:600;"
                )
                plus.setAlignment(Qt.AlignmentFlag.AlignCenter)
                h.addWidget(plus)
            h.addWidget(KbdKey(k))
        h.addStretch(1)
        return wrap


# ===========================================================================
# Modal overlay
# ===========================================================================

class ShortcutHelp(QWidget):
    """Frameless modal-style overlay with a translucent backdrop and a
    centred glass card listing every keyboard shortcut.

    Click the backdrop or press Esc to dismiss. Press ? to toggle.
    """

    CARD_W = 600
    CARD_H = 540

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._host = parent

        # Cover the whole host window — we'll paint the dim backdrop
        # ourselves on this widget, with the card as a child centred on top.
        self.setObjectName("shortcut_help_root")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"QWidget#shortcut_help_root {{ background-color:{C.scrim}; }}"
        )
        # Sit on top of all sibling widgets in the parent.
        self.setAutoFillBackground(False)

        # ----- Card -----
        self.card = QFrame(self)
        self.card.setObjectName("shortcut_help_card")
        self.card.setFixedSize(self.CARD_W, self.CARD_H)
        # Use the project's standard glass surface helper for elevated modals.
        self.card.setStyleSheet(
            f"QFrame#shortcut_help_card {{ {glass_card_qss(elevated=True, strong=True)} }}"
        )

        # Floating shadow under the card — matches CommandPalette feel.
        try:
            eff = QGraphicsDropShadowEffect(self.card)
            eff.setBlurRadius(SH.floating.blur)
            eff.setOffset(0, SH.floating.offset_y)
            eff.setColor(QColor(0, 0, 0, 200))
            self.card.setGraphicsEffect(eff)
        except Exception as _e:
            logger.debug("shortcut help shadow effect failed: %s", _e)

        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(S.xl, S.xl, S.xl, S.lg)
        cl.setSpacing(S.md)

        # ----- Title -----
        title = QLabel("Keyboard Shortcuts")
        title.setStyleSheet(
            f"background:transparent; "
            f"color:{C.text}; "
            f"font-family:{T.family}; "
            f"font-size:{T.h1_size}px; "
            f"font-weight:700;"
        )
        cl.addWidget(title)

        subtitle = QLabel("Press ? to toggle")
        subtitle.setStyleSheet(
            f"background:transparent; "
            f"color:{C.text_muted}; "
            f"font-family:{T.family}; "
            f"font-size:{T.small_size}px; "
            f"font-weight:500;"
        )
        cl.addWidget(subtitle)

        # Hairline divider under the title block.
        sep = QFrame(self.card)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color:{C.border}; border:none;")
        cl.addWidget(sep)

        # ----- Scrollable shortcut grid -----
        self.scroll = QScrollArea(self.card)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll.setStyleSheet(
            f"QScrollArea {{ background:transparent; border:none; }} "
            f"QScrollBar:vertical {{ "
            f"  background:transparent; width:8px; margin:0; "
            f"}} "
            f"QScrollBar::handle:vertical {{ "
            f"  background:{C.border_strong}; "
            f"  border-radius:4px; min-height:24px; "
            f"}} "
            f"QScrollBar::handle:vertical:hover {{ background:{C.accent}; }} "
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ "
            f"  height:0; background:transparent; "
            f"}}"
        )
        self.grid = ShortcutGrid(SHORTCUTS, self.scroll)
        self.scroll.setWidget(self.grid)
        cl.addWidget(self.scroll, 1)

        # ----- Footer hint -----
        footer = QLabel("Esc to close")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(
            f"background:transparent; "
            f"color:{C.text_subtle}; "
            f"font-family:{T.family}; "
            f"font-size:{T.small_size}px; "
            f"padding-top:{S.sm}px;"
        )
        cl.addWidget(footer)

        # Animation handles — kept on self so they aren't GC'd mid-flight.
        self._opacity_eff: Optional[QGraphicsOpacityEffect] = None
        self._anim_group: Optional[QParallelAnimationGroup] = None

        self.hide()

    # ----- Geometry -----
    def _fit_to_host(self) -> None:
        """Match the host's client area exactly, then centre the card."""
        host = self._host
        if isinstance(host, QWidget):
            try:
                self.setGeometry(host.rect())
            except Exception as _e:
                logger.debug("fit_to_host failed: %s", _e)
        self._centre_card()

    def _centre_card(self) -> None:
        x = (self.width() - self.card.width()) // 2
        y = (self.height() - self.card.height()) // 2
        self.card.move(max(0, x), max(0, y))

    def resizeEvent(self, ev) -> None:  # noqa: N802
        super().resizeEvent(ev)
        self._centre_card()

    # ----- Show / hide / animation -----
    def show_overlay(self) -> None:
        self._fit_to_host()
        self.raise_()
        self.show()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

        # Backdrop fade-in (whole overlay) + card scale-from-0.96. We can't
        # animate a QSS transform, but we *can* animate setGeometry on the
        # card to grow it into its final 600×540 footprint, which gives a
        # very similar perceived effect.
        try:
            # Opacity fade on the whole overlay.
            self._opacity_eff = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(self._opacity_eff)
            self._opacity_eff.setOpacity(0.0)

            fade = QPropertyAnimation(self._opacity_eff, b"opacity", self)
            fade.setDuration(260)
            fade.setStartValue(0.0)
            fade.setEndValue(1.0)
            fade.setEasingCurve(getattr(QEasingCurve.Type, M.ease_out_cubic))

            # Card scale via geometry: start at 96% size, centred, end at
            # 100% size, centred.
            tw, th = self.card.width(), self.card.height()
            sw, sh = int(tw * 0.96), int(th * 0.96)
            tx = (self.width() - tw) // 2
            ty = (self.height() - th) // 2
            sx = (self.width() - sw) // 2
            sy = (self.height() - sh) // 2

            scale = QPropertyAnimation(self.card, b"geometry", self)
            scale.setDuration(260)
            scale.setStartValue(QRect(sx, sy, sw, sh))
            scale.setEndValue(QRect(tx, ty, tw, th))
            scale.setEasingCurve(getattr(QEasingCurve.Type, M.ease_out_cubic))

            grp = QParallelAnimationGroup(self)
            grp.addAnimation(fade)
            grp.addAnimation(scale)
            self._anim_group = grp
            grp.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        except Exception as _e:
            logger.debug("shortcut help fade failed: %s", _e)
            try:
                if self._opacity_eff is not None:
                    self._opacity_eff.setOpacity(1.0)
            except Exception:
                pass

    def dismiss(self) -> None:
        try:
            self.hide()
            if self._host is not None:
                try:
                    self._host.activateWindow()
                except Exception as _e:
                    logger.debug("host activate failed: %s", _e)
        except Exception as _e:
            logger.debug("shortcut help dismiss failed: %s", _e)

    def toggle(self) -> None:
        if self.isVisible():
            self.dismiss()
        else:
            self.show_overlay()

    # ----- Event handling -----
    def keyPressEvent(self, ev: QKeyEvent) -> None:  # noqa: N802
        k = ev.key()
        if k == Qt.Key.Key_Escape:
            self.dismiss()
            return
        # Toggle off on '?' too, so the same key dismisses.
        if k == Qt.Key.Key_Question:
            self.dismiss()
            return
        super().keyPressEvent(ev)

    def mousePressEvent(self, ev: QMouseEvent) -> None:  # noqa: N802
        # Click on the dim backdrop (anywhere outside the card) → dismiss.
        # The card itself is a child QFrame, so its own mouse events don't
        # reach us — we only see clicks on the bare backdrop area.
        if ev.button() == Qt.MouseButton.LeftButton:
            pos = ev.position().toPoint() if hasattr(ev, "position") else ev.pos()
            if not self.card.geometry().contains(pos):
                self.dismiss()
                return
        super().mousePressEvent(ev)


# ===========================================================================
# Standalone test harness
# ===========================================================================

if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    app = QApplication(sys.argv)

    host = QMainWindow()
    host.setWindowTitle("Shortcut Help test host")
    host.resize(1200, 800)
    label = QLabel("Press ? to toggle the keyboard shortcut overlay\n(Esc closes)")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(
        f"background:{C.bg}; color:{C.text}; "
        f"font-family:{T.family}; font-size:{T.h2_size}px;"
    )
    host.setCentralWidget(label)
    host.show()

    overlay = ShortcutHelp(host)
    sc = QShortcut(QKeySequence("?"), host)
    sc.activated.connect(overlay.toggle)

    QTimer.singleShot(300, overlay.show_overlay)
    sys.exit(app.exec())
