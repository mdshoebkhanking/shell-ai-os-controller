"""widgets — token-driven reusable UI components for Shell OS.

Every widget reads from `design_tokens.C/T/S/R/M/SH`. State changes go
through `setProperty("state", ...)` + `style().polish()` so Qt repaints
without us re-issuing whole `setStyleSheet` strings (the main cause of
hover-flash and theme-switch breakage in the legacy code).
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy,
    QTextEdit, QVBoxLayout, QWidget, QGraphicsDropShadowEffect, QGridLayout,
)

from shell_ui import design_tokens as DT


# ---------------------------------------------------------------------------
# Typography helpers — saves boilerplate per label.
# ---------------------------------------------------------------------------

def _font(size: int, weight: int = 400) -> QFont:
    f = QFont(DT.T.family, size)
    f.setWeight(weight)
    return f


class Display(QLabel):
    """Largest heading — only for hero / empty-state titles."""
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setFont(_font(DT.T.display_size, QFont.Weight.Bold))
        self.setStyleSheet(f"color:{DT.C.text}; background:transparent; border:none;")
        self.setWordWrap(True)


class H1(QLabel):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setFont(_font(DT.T.h1_size, QFont.Weight.Bold))
        self.setStyleSheet(f"color:{DT.C.text}; background:transparent; border:none;")
        self.setWordWrap(True)


class H2(QLabel):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setFont(_font(DT.T.h2_size, QFont.Weight.DemiBold))
        self.setStyleSheet(f"color:{DT.C.text}; background:transparent; border:none;")
        self.setWordWrap(True)


class Body(QLabel):
    def __init__(self, text: str = "", parent=None, *, strong: bool = False, muted: bool = False):
        super().__init__(text, parent)
        weight = QFont.Weight.DemiBold if strong else QFont.Weight.Normal
        self.setFont(_font(DT.T.body_size, weight))
        col = DT.C.text_muted if muted else DT.C.text
        self.setStyleSheet(f"color:{col}; background:transparent; border:none;")
        self.setWordWrap(True)


class Muted(QLabel):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setFont(_font(DT.T.small_size, QFont.Weight.Normal))
        self.setStyleSheet(f"color:{DT.C.text_muted}; background:transparent; border:none;")
        self.setWordWrap(True)


class Subtle(QLabel):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setFont(_font(DT.T.small_size, QFont.Weight.Normal))
        self.setStyleSheet(f"color:{DT.C.text_subtle}; background:transparent; border:none;")
        self.setWordWrap(True)


# ---------------------------------------------------------------------------
# Card — primary container surface.
# ---------------------------------------------------------------------------

class Card(QFrame):
    """A surface card. Two visual styles:

    * `glass=True` (default) — translucent warm glassmorphism panel
      with top-edge highlight, sitting over the ambient bg wash.
    * `glass=False` — solid `surface` with hairline border.

    `elevated=True` increases radius and shadow. `interactive=True`
    enables a subtle hover-lift animation.
    """

    def __init__(self, parent=None, *, elevated: bool = False,
                 padded: bool = True, glass: bool = True,
                 interactive: bool = False):
        super().__init__(parent)
        self.setObjectName("dsCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._glass = glass
        self._elevated = elevated
        self._interactive = interactive
        self._apply_qss()
        if padded:
            lay = QVBoxLayout(self)
            lay.setContentsMargins(DT.S.lg, DT.S.lg, DT.S.lg, DT.S.lg)
            lay.setSpacing(DT.S.md)
        self._apply_shadow(elevated)

    def _apply_qss(self):
        if self._glass:
            qss = DT.glass_card_qss(elevated=self._elevated)
        else:
            qss = DT.card_qss(elevated=self._elevated)
        self.setStyleSheet(f"#dsCard {{ {qss} }}")

    def _apply_shadow(self, elevated: bool):
        sh = DT.SH.elevated if elevated else DT.SH.soft
        eff = QGraphicsDropShadowEffect(self)
        eff.setBlurRadius(sh.blur)
        eff.setOffset(0, sh.offset_y)
        try:
            inner = sh.color[sh.color.find("(") + 1: sh.color.rfind(")")]
            r, g, b, a = [float(x) for x in inner.split(",")]
            eff.setColor(QColor(int(r), int(g), int(b), int(a * 255)))
        except Exception:
            eff.setColor(QColor(0, 0, 0, 50))
        self.setGraphicsEffect(eff)
        self._shadow_eff = eff

    # -- Mac-style smooth hover lift (used when interactive=True) ------
    # Uses QPropertyAnimation on `blurRadius` + `yOffset` of the
    # QGraphicsDropShadowEffect so the lift is *animated* rather than
    # snapping. 220 ms OutCubic feels like macOS hover.
    def enterEvent(self, e):
        if self._interactive and getattr(self, "_shadow_eff", None):
            self._animate_shadow(DT.SH.elevated)
        super().enterEvent(e)

    def leaveEvent(self, e):
        if self._interactive and getattr(self, "_shadow_eff", None):
            sh = DT.SH.elevated if self._elevated else DT.SH.soft
            self._animate_shadow(sh)
        super().leaveEvent(e)

    def _animate_shadow(self, target_spec):
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        try:
            ah = QPropertyAnimation(self._shadow_eff, b"blurRadius", self)
            ah.setDuration(DT.M.fast_ms)
            ah.setEasingCurve(QEasingCurve.Type.OutCubic)
            ah.setEndValue(target_spec.blur)
            ah.start()
            self._shadow_anim_blur = ah
            # Y offset can't animate via Qt property directly (it's a
            # QPointF); set instantly. The blur change carries the lift.
            self._shadow_eff.setOffset(0, target_spec.offset_y)
        except Exception:
            self._shadow_eff.setBlurRadius(target_spec.blur)
            self._shadow_eff.setOffset(0, target_spec.offset_y)


# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------

class PrimaryButton(QPushButton):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(DT.primary_button_qss())
        # Mac control height — 32-36 is the SwiftUI default.
        self.setFixedHeight(34)
        # Subtle whisper shadow on rest, lifts to 'soft' on hover.
        self._sh = QGraphicsDropShadowEffect(self)
        self._sh.setBlurRadius(DT.SH.whisper.blur)
        self._sh.setOffset(0, DT.SH.whisper.offset_y)
        self._sh.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(self._sh)

    def enterEvent(self, e):
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        a = QPropertyAnimation(self._sh, b"blurRadius", self)
        a.setDuration(DT.M.fast_ms); a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.setEndValue(DT.SH.soft.blur); a.start()
        self._a = a
        super().enterEvent(e)

    def leaveEvent(self, e):
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        a = QPropertyAnimation(self._sh, b"blurRadius", self)
        a.setDuration(DT.M.fast_ms); a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.setEndValue(DT.SH.whisper.blur); a.start()
        self._a = a
        super().leaveEvent(e)


class SecondaryButton(QPushButton):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(DT.secondary_button_qss())
        self.setFixedHeight(34)


class GhostButton(QPushButton):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(DT.ghost_button_qss())
        self.setFixedHeight(32)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)


class IconButton(QPushButton):
    """Square icon-only button. Pass either `text` (single glyph/emoji)
    or set an icon via `setIcon(...)` afterwards.
    """
    def __init__(self, glyph: str = "", parent=None, *, size: int = 36, tone: str = "ghost"):
        super().__init__(glyph, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(size, size)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if tone == "primary":
            self.setStyleSheet(
                f"QPushButton {{ background:{DT.C.accent}; color:#fff; "
                f"border:none; border-radius:{size//2}px; font-size:16px; }} "
                f"QPushButton:hover {{ background:{DT.C.accent_hover}; }}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{ background:transparent; color:{DT.C.text_muted}; "
                f"border:none; border-radius:{DT.R.md}px; font-size:16px; }} "
                f"QPushButton:hover {{ background:{DT.C.accent_soft}; color:{DT.C.text}; }}"
            )


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

class Input(QLineEdit):
    """Single-line input with token-driven styling and proper focus state."""

    def __init__(self, parent=None, placeholder: str = ""):
        super().__init__(parent)
        if placeholder:
            self.setPlaceholderText(placeholder)
        self._apply(False)

    def focusInEvent(self, e):
        self._apply(True);  super().focusInEvent(e)

    def focusOutEvent(self, e):
        self._apply(False); super().focusOutEvent(e)

    def _apply(self, focused: bool):
        self.setStyleSheet(DT.input_qss(focused=focused))


class TextArea(QTextEdit):
    """Multi-line input — auto-grows up to a cap."""

    def __init__(self, parent=None, placeholder: str = "", min_h: int = 44, max_h: int = 160):
        super().__init__(parent)
        if placeholder:
            self.setPlaceholderText(placeholder)
        self._min_h = min_h
        self._max_h = max_h
        self.setFixedHeight(min_h)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._apply(False)
        self.textChanged.connect(self._auto_size)

    def focusInEvent(self, e):
        self._apply(True);  super().focusInEvent(e)

    def focusOutEvent(self, e):
        self._apply(False); super().focusOutEvent(e)

    def _apply(self, focused: bool):
        self.setStyleSheet(DT.input_qss(focused=focused))

    def _auto_size(self):
        # Use document height (handles wrapped lines correctly, unlike a
        # naïve newline count).
        try:
            h = int(self.document().size().height()) + 16
            new_h = max(self._min_h, min(self._max_h, h))
            if new_h != self.height():
                self.setFixedHeight(new_h)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Pills, dots, dividers
# ---------------------------------------------------------------------------

class Pill(QLabel):
    def __init__(self, text: str = "", parent=None, *, tone: str = "neutral"):
        super().__init__(text, parent)
        self.setStyleSheet(DT.pill_qss(tone=tone))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(22)


class StatusDot(QLabel):
    """6-px coloured dot. Tones mirror Pill."""
    def __init__(self, parent=None, *, tone: str = "success"):
        super().__init__(parent)
        self.set_tone(tone)
        self.setFixedSize(8, 8)

    def set_tone(self, tone: str):
        col = {
            "success": DT.C.success,
            "warning": DT.C.warning,
            "error":   DT.C.error,
            "accent":  DT.C.accent,
            "neutral": DT.C.text_subtle,
        }.get(tone, DT.C.text_subtle)
        self.setStyleSheet(
            f"background:{col}; border-radius:4px;"
        )


class Divider(QFrame):
    def __init__(self, parent=None, *, vertical: bool = False):
        super().__init__(parent)
        if vertical:
            self.setFixedWidth(1)
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        else:
            self.setFixedHeight(1)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(f"background-color:{DT.C.border}; border:none;")


# ---------------------------------------------------------------------------
# EmptyState — for "no chats yet" / "no logs" / etc.
# ---------------------------------------------------------------------------

class EmptyState(QFrame):
    """Centered empty-state with title, subtitle, optional action chips.

    The whole panel fades + slides in on first show; chips animate in
    with a 60ms stagger for a polished, premium feel.
    """

    def __init__(self, title: str = "", subtitle: str = "",
                 chips: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent; border:none;")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(DT.S.xl, DT.S.xxxl, DT.S.xl, DT.S.xxxl)
        outer.setSpacing(DT.S.md)
        outer.addStretch(1)

        if title:
            t = Display(title)
            t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            outer.addWidget(t)
        if subtitle:
            s = Body(subtitle, muted=True)
            s.setAlignment(Qt.AlignmentFlag.AlignCenter)
            outer.addWidget(s)

        self._chip_buttons: list[QPushButton] = []
        if chips:
            outer.addSpacing(DT.S.lg)
            chip_grid = QGridLayout()
            chip_grid.setHorizontalSpacing(DT.S.sm)
            chip_grid.setVerticalSpacing(DT.S.sm)
            columns = 2 if len(chips) > 2 else max(1, len(chips))
            for idx, label in enumerate(chips):
                btn = QPushButton(label)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setMinimumHeight(38)
                btn.setMinimumWidth(150)
                btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                # Glass-pill chip — translucent body, top-edge highlight,
                # warmer hover with accent border.
                btn.setStyleSheet(
                    f"QPushButton {{ "
                    f"  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, "
                    f"    stop:0 {DT.C.glass_hi}, "
                    f"    stop:0.06 {DT.C.glass}, "
                    f"    stop:1 {DT.C.glass}); "
                    f"  color:{DT.C.text}; "
                    f"  border:1px solid {DT.C.glass_border}; "
                    f"  border-radius:{DT.R.md}px; "
                    f"  padding:10px 18px; font-size:{DT.T.body_size}px; "
                    f"  font-weight:500; "
                    f"}} "
                    f"QPushButton:hover {{ "
                    f"  background:{DT.C.accent_soft}; "
                    f"  border:1px solid {DT.C.accent}; "
                    f"  color:{DT.C.text}; "
                    f"}} "
                    f"QPushButton:pressed {{ padding-top:11px; padding-bottom:9px; }}"
                )
                self._chip_buttons.append(btn)
                row = idx // columns
                col = idx % columns
                span = columns if len(chips) % columns == 1 and idx == len(chips) - 1 else 1
                chip_grid.addWidget(btn, row, col, 1, span)
            for col in range(columns):
                chip_grid.setColumnStretch(col, 1)
            outer.addLayout(chip_grid)
        outer.addStretch(2)

        # Schedule entry animations on next event loop tick so the
        # widget tree has been laid out first.
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._animate_in)

    def _animate_in(self):
        # Hero (this frame as a whole): soft fade-in, but never from
        # zero opacity. A blank first frame makes the app look broken
        # during screenshots, slow machines, or offscreen QA captures.
        try:
            from PyQt6.QtWidgets import QGraphicsOpacityEffect
            eff = QGraphicsOpacityEffect(self)
            eff.setOpacity(0.72)
            self.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity", self)
            anim.setDuration(DT.M.slow_ms)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setStartValue(0.72)
            anim.setEndValue(1.0)
            anim.finished.connect(lambda: self.setGraphicsEffect(None))
            anim.start()
            self._anim = anim
        except Exception:
            pass

        # Chips: stagger fade+lift, 60ms apart.
        from PyQt6.QtCore import QTimer
        for i, btn in enumerate(self._chip_buttons):
            QTimer.singleShot(120 + 60 * i,
                              lambda b=btn: self._fade_chip(b))

    @staticmethod
    def _fade_chip(btn):
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        try:
            eff = QGraphicsOpacityEffect(btn)
            eff.setOpacity(0.55)
            btn.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity", btn)
            anim.setDuration(DT.M.base_ms)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setStartValue(0.55)
            anim.setEndValue(1.0)
            anim.finished.connect(lambda: btn.setGraphicsEffect(None))
            anim.start()
            btn._chip_anim = anim
        except Exception:
            pass

    def chip_buttons(self):
        return getattr(self, "_chip_buttons", [])


# ---------------------------------------------------------------------------
# Polish helper — re-trigger QSS evaluation on a widget tree (used after
# theme switch so the new tokens apply without rebuilding widgets).
# ---------------------------------------------------------------------------

def repolish_tree(root: QWidget) -> None:
    style = root.style()
    if style is None: return
    style.unpolish(root); style.polish(root)
    for child in root.findChildren(QWidget):
        try:
            style.unpolish(child); style.polish(child)
        except Exception:
            pass


__all__ = [
    "Display", "H1", "H2", "Body", "Muted", "Subtle",
    "Card",
    "PrimaryButton", "SecondaryButton", "GhostButton", "IconButton",
    "Input", "TextArea",
    "Pill", "StatusDot", "Divider", "EmptyState",
    "repolish_tree",
]
