"""onboarding_tour — first-launch welcome tour for Shell OS UI.

A modal-style overlay that walks a brand-new user through the main
features of Shell: chat, voice, the Ctrl+Alt+S quick launcher, the
Ctrl+K command palette, and where to find help. Shown exactly once,
controlled by a `~/.shell_chat_history/onboarding_done.flag` file.

Wiring (already done in `shell_cinematic_full.py`):

    from shell_ui.onboarding_tour import OnboardingTour
    self._tour = OnboardingTour(self)
    if self._tour.should_show():
        QTimer.singleShot(800, self._tour.show_tour)

To replay the tour later (avatar menu, settings, etc.) call:

    self._tour.force_show()

Standalone preview:
    python -m shell_ui.onboarding_tour
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import (
    Qt, QEvent, QPropertyAnimation, QEasingCurve, QTimer, QSize, QPoint,
)
from PyQt6.QtGui import (
    QPainter, QColor, QPixmap, QKeyEvent, QFont, QPaintEvent, QResizeEvent,
)
from PyQt6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QApplication,
    QGraphicsOpacityEffect, QGraphicsDropShadowEffect, QGraphicsBlurEffect,
    QSizePolicy,
)

logger = logging.getLogger("shell.ui.onboarding_tour")
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

# Allow running this module standalone for previewing.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    from shell_ui.design_tokens import C, S, T, R, M, SH, glass_card_qss
    from shell_ui.widgets import (
        Display, Body, Muted, GhostButton, PrimaryButton,
    )
except Exception:  # pragma: no cover — used when running this file directly.
    from design_tokens import C, S, T, R, M, SH, glass_card_qss  # type: ignore
    from widgets import (  # type: ignore
        Display, Body, Muted, GhostButton, PrimaryButton,
    )


# ===========================================================================
# Step model + canonical step list
# ===========================================================================

@dataclass(frozen=True)
class OnboardingStep:
    """One welcome card in the tour."""
    title: str
    body: str
    icon: str                              # emoji glyph rendered at top
    cta_label: str = "Next"                # button label on the right
    target_widget_name: Optional[str] = None  # for an optional spotlight


STEPS: List[OnboardingStep] = [
    OnboardingStep(
        title="Welcome to Shell",
        body=("An AI desktop control layer for chat, voice, tools, "
              "automation, and runtime diagnostics."),
        icon="🌟",
        cta_label="Next",
    ),
    OnboardingStep(
        title="Chat naturally",
        body=("Type a request in the message box. Shell will answer in text "
              "and use ready tools only when the route is safe."),
        icon="💬",
        cta_label="Next",
        target_widget_name="chat_page",
    ),
    OnboardingStep(
        title="Talk to Shell",
        body=("Switch to the Voice page or press the mic in the topbar. "
              "Voice shows clear setup states when a mic, provider, or API "
              "key needs attention."),
        icon="🎤",
        cta_label="Next",
        target_widget_name="voice_page",
    ),
    OnboardingStep(
        title="Press Ctrl+Alt+S anywhere on Windows",
        body=("A floating box opens above any app. Type your prompt — done."),
        icon="⚡",
        cta_label="Next",
    ),
    OnboardingStep(
        title="Press Ctrl+K to find commands",
        body=("Switch pages, change theme, run tools — all from one "
              "searchable panel."),
        icon="🎯",
        cta_label="Next",
    ),
    OnboardingStep(
        title="You're all set",
        body=("Open Settings for health checks, repair tools, API setup, "
              "and troubleshooting whenever something is not ready."),
        icon="✅",
        cta_label="Done",
    ),
]


# ===========================================================================
# Persistence
# ===========================================================================

def _flag_path() -> Path:
    """Where the 'tour was shown' marker lives.

    Uses the same `~/.shell_chat_history/` root as the chat history store
    and the notification center for consistency.
    """
    root = Path.home() / ".shell_chat_history"
    return root / "onboarding_done.flag"


def _has_seen_tour() -> bool:
    try:
        return _flag_path().exists()
    except Exception as _e:
        logger.debug("onboarding flag read failed: %s", _e)
        return False


def _mark_seen() -> None:
    try:
        p = _flag_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("1", encoding="utf-8")
    except Exception as _e:
        logger.debug("onboarding flag write failed: %s", _e)


# ===========================================================================
# Step indicator dots — 8px circles, hollow border for inactive
# ===========================================================================

class _StepDots(QWidget):
    """Row of small dots — filled accent for the current step,
    hollow border for the others. 8 px circles with 6 px gaps."""

    DOT_SIZE = 8
    DOT_GAP = 6

    def __init__(self, count: int, parent=None):
        super().__init__(parent)
        self._count = max(1, int(count))
        self._current = 0
        w = self._count * self.DOT_SIZE + (self._count - 1) * self.DOT_GAP
        self.setFixedSize(w, self.DOT_SIZE)

    def set_current(self, i: int) -> None:
        if 0 <= i < self._count and i != self._current:
            self._current = i
            self.update()

    def paintEvent(self, _ev: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        accent = QColor(C.accent)
        muted = QColor(C.text_subtle)
        # Border-only for inactive dots; matches the spec ("hollow border").
        for i in range(self._count):
            x = i * (self.DOT_SIZE + self.DOT_GAP)
            rect = (x, 0, self.DOT_SIZE, self.DOT_SIZE)
            if i == self._current:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(accent)
            else:
                pen = p.pen()
                pen.setColor(muted)
                pen.setWidth(1)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(*rect)
        p.end()


# ===========================================================================
# TourCard — the centered glass card showing one step
# ===========================================================================

class TourCard(QFrame):
    """Frameless, centered ~480 × 360 px glass card.

    Layout:
      • Large emoji icon (top, centered).
      • Title (Display, 28 px) — centered.
      • Body (muted, line-height 1.5) — centered, wrapped.
      • Bottom row: step dots (left) + Skip ghost-button + Next/Done primary.
    """

    CARD_W = 480
    CARD_H = 360

    def __init__(self, total_steps: int, parent=None):
        super().__init__(parent)
        self.setObjectName("tourCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(self.CARD_W, self.CARD_H)

        # Glass body via the central token helper. `elevated=True` gives a
        # bigger radius (R.xl); `strong=True` picks the more opaque variant
        # which reads as a proper modal card over the dim backdrop.
        self.setStyleSheet(
            f"#tourCard {{ {glass_card_qss(elevated=True, strong=True)} }}"
        )

        # Soft drop-shadow halo so the card visibly floats above the scrim.
        try:
            sh = QGraphicsDropShadowEffect(self)
            sh.setBlurRadius(SH.floating.blur)
            sh.setOffset(0, SH.floating.offset_y)
            sh.setColor(QColor(0, 0, 0, 110))
            self.setGraphicsEffect(sh)
        except Exception as _e:
            logger.debug("tour card shadow failed: %s", _e)

        # Layout
        outer = QVBoxLayout(self)
        outer.setContentsMargins(S.xl, S.xl, S.xl, S.lg)
        outer.setSpacing(S.md)

        # --- Icon ---
        self.icon_label = QLabel("")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_font = QFont(T.family)
        icon_font.setPointSize(38)
        self.icon_label.setFont(icon_font)
        self.icon_label.setStyleSheet(
            f"color:{C.accent}; background:transparent; border:none;"
        )
        outer.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignHCenter)

        # --- Title (Display, 28 px per spec) ---
        self.title_label = QLabel("")
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont(T.family, 28)
        title_font.setWeight(QFont.Weight.Bold)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet(
            f"color:{C.text}; background:transparent; border:none;"
        )
        outer.addWidget(self.title_label)

        # --- Body (muted, line-height 1.5 via stylesheet) ---
        self.body_label = QLabel("")
        self.body_label.setWordWrap(True)
        self.body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body_font = QFont(T.family, T.body_size)
        self.body_label.setFont(body_font)
        # Qt's QLabel doesn't honour CSS line-height, but it does honour
        # rich-text — wrap the body in a div with a line-height style.
        self.body_label.setTextFormat(Qt.TextFormat.RichText)
        self.body_label.setStyleSheet(
            f"color:{C.text_muted}; background:transparent; border:none;"
        )
        outer.addWidget(self.body_label)

        outer.addStretch(1)

        # --- Bottom row ---
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(S.md)

        self.dots = _StepDots(total_steps, self)
        bottom.addWidget(self.dots, 0, Qt.AlignmentFlag.AlignVCenter)
        bottom.addStretch(1)

        self.skip_btn = GhostButton("Skip tour")
        self.skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        bottom.addWidget(self.skip_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.next_btn = PrimaryButton("Next")
        self.next_btn.setMinimumWidth(96)
        bottom.addWidget(self.next_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        outer.addLayout(bottom)

    # -----------------------------------------------------------------
    # Step rendering
    # -----------------------------------------------------------------
    def render_step(self, step: OnboardingStep, index: int) -> None:
        self.icon_label.setText(step.icon)
        self.title_label.setText(step.title)
        # Build a tiny rich-text wrapper so we can apply line-height: 1.5
        # without breaking word-wrap. (`<p style=...>` works in QLabel.)
        self.body_label.setText(
            f"<div style='line-height:150%;'>{step.body}</div>"
        )
        self.next_btn.setText(step.cta_label or "Next")
        self.dots.set_current(index)


# ===========================================================================
# OnboardingTour — modal overlay that hosts the card
# ===========================================================================

class OnboardingTour(QWidget):
    """Translucent dim/blur backdrop covering the whole main window with
    a centered TourCard. Navigation: Next advances, Back goes back, Skip
    or Esc dismisses + persists the 'shown' flag, Done finishes the tour.

    Owner is the main window (passed as `parent`); the overlay re-parents
    itself to that window and resizes with it.
    """

    def __init__(self, main_window: QWidget):
        # `parent=main_window` so we appear inside its widget hierarchy
        # but float over everything else.
        super().__init__(main_window)
        self._main = main_window
        self._index = 0
        self._anim: Optional[QPropertyAnimation] = None
        self._fade_in_anim: Optional[QPropertyAnimation] = None
        self._snapshot_label: Optional[QLabel] = None

        # Fill the parent.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Translucent dark scrim — token-driven.
        self.setStyleSheet(
            f"OnboardingTour {{ background: {C.scrim}; }}"
        )

        # The card — centered manually in resizeEvent.
        self.card = TourCard(len(STEPS), self)
        self.card.skip_btn.clicked.connect(self._on_skip)
        self.card.next_btn.clicked.connect(self._on_next)

        # Initial geometry follows the parent.
        self._sync_geometry()
        self.hide()

        # Install on parent so we resize with it.
        try:
            self._main.installEventFilter(self)
        except Exception as _e:
            logger.debug("tour event filter install failed: %s", _e)

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------
    def should_show(self) -> bool:
        """True iff the tour has never been completed/skipped."""
        return not _has_seen_tour()

    def show_tour(self) -> None:
        """Show the tour iff not seen before. Idempotent."""
        if not self.should_show():
            return
        self._present()

    def force_show(self) -> None:
        """Re-run the tour even if the flag is set (for replay from
        avatar menu / settings)."""
        self._present()

    # -----------------------------------------------------------------
    # Presentation
    # -----------------------------------------------------------------
    def _present(self) -> None:
        try:
            self._index = 0
            self.card.render_step(STEPS[0], 0)
            self._sync_geometry()
            # Snapshot + blur the parent for a frosted backdrop effect.
            # Falls back to a plain dim if blur is too expensive.
            self._install_blurred_snapshot()
            self.raise_()
            self.show()
            self.setFocus(Qt.FocusReason.OtherFocusReason)
            # Fade the whole overlay in.
            try:
                eff = QGraphicsOpacityEffect(self)
                eff.setOpacity(0.0)
                self.setGraphicsEffect(eff)
                a = QPropertyAnimation(eff, b"opacity", self)
                a.setDuration(M.slow_ms)
                a.setStartValue(0.0)
                a.setEndValue(1.0)
                a.setEasingCurve(QEasingCurve.Type.OutCubic)
                a.finished.connect(lambda: self.setGraphicsEffect(None))
                a.start()
                self._fade_in_anim = a
            except Exception as _e:
                logger.debug("tour fade-in failed: %s", _e)
        except Exception as _e:
            logger.warning("OnboardingTour._present failed: %s", _e)

    def _install_blurred_snapshot(self) -> None:
        """Take a QPixmap snapshot of the parent main window, apply a
        QGraphicsBlurEffect to it, and lay it under the card. If that
        fails for any reason (very large windows, GPU-less environments)
        we fall back to plain dim — the scrim alone still looks fine.
        """
        # Tear down any old snapshot first.
        if self._snapshot_label is not None:
            try:
                self._snapshot_label.deleteLater()
            except Exception:
                pass
            self._snapshot_label = None
        try:
            if not isinstance(self._main, QWidget):
                return
            # Don't bother with blur on really big windows — it gets pricey
            # and the scrim alone reads fine.
            if (self._main.width() * self._main.height()) > 4_500_000:
                return
            pix: QPixmap = self._main.grab()
            if pix.isNull():
                return
            label = QLabel(self)
            label.setPixmap(pix)
            label.setScaledContents(True)
            label.setGeometry(0, 0, self.width(), self.height())
            blur = QGraphicsBlurEffect(label)
            blur.setBlurRadius(18)
            label.setGraphicsEffect(blur)
            label.lower()  # behind the card
            label.show()
            self._snapshot_label = label
        except Exception as _e:
            logger.debug("tour blurred snapshot failed: %s", _e)
            self._snapshot_label = None

    # -----------------------------------------------------------------
    # Navigation
    # -----------------------------------------------------------------
    def _on_next(self) -> None:
        if self._index >= len(STEPS) - 1:
            self._on_done()
            return
        self._goto(self._index + 1)

    def _on_back(self) -> None:
        if self._index <= 0:
            return
        self._goto(self._index - 1)

    def _on_skip(self) -> None:
        _mark_seen()
        self._dismiss()

    def _on_done(self) -> None:
        _mark_seen()
        self._dismiss()

    def _dismiss(self) -> None:
        try:
            eff = QGraphicsOpacityEffect(self)
            eff.setOpacity(1.0)
            self.setGraphicsEffect(eff)
            a = QPropertyAnimation(eff, b"opacity", self)
            a.setDuration(M.base_ms)
            a.setStartValue(1.0)
            a.setEndValue(0.0)
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            a.finished.connect(self._finish_dismiss)
            a.start()
            self._fade_in_anim = a
        except Exception as _e:
            logger.debug("tour fade-out failed: %s", _e)
            self._finish_dismiss()

    def _finish_dismiss(self) -> None:
        try:
            self.setGraphicsEffect(None)
        except Exception:
            pass
        if self._snapshot_label is not None:
            try:
                self._snapshot_label.deleteLater()
            except Exception:
                pass
            self._snapshot_label = None
        self.hide()

    def _goto(self, new_index: int) -> None:
        """Smooth cross-fade between steps — 220 ms OutCubic on a
        QGraphicsOpacityEffect attached to the card itself."""
        if not (0 <= new_index < len(STEPS)):
            return
        try:
            eff = QGraphicsOpacityEffect(self.card)
            eff.setOpacity(1.0)
            self.card.setGraphicsEffect(eff)

            out = QPropertyAnimation(eff, b"opacity", self)
            out.setDuration(220)
            out.setStartValue(1.0)
            out.setEndValue(0.0)
            out.setEasingCurve(QEasingCurve.Type.OutCubic)

            def _swap_and_fade_in():
                self._index = new_index
                self.card.render_step(STEPS[new_index], new_index)
                in_a = QPropertyAnimation(eff, b"opacity", self)
                in_a.setDuration(220)
                in_a.setStartValue(0.0)
                in_a.setEndValue(1.0)
                in_a.setEasingCurve(QEasingCurve.Type.OutCubic)
                in_a.finished.connect(
                    lambda: self.card.setGraphicsEffect(None)
                )
                in_a.start()
                self._anim = in_a

            out.finished.connect(_swap_and_fade_in)
            out.start()
            self._anim = out
        except Exception as _e:
            logger.debug("tour cross-fade failed: %s", _e)
            self._index = new_index
            self.card.render_step(STEPS[new_index], new_index)

    # -----------------------------------------------------------------
    # Geometry / events
    # -----------------------------------------------------------------
    def _sync_geometry(self) -> None:
        try:
            if not isinstance(self._main, QWidget):
                return
            self.setGeometry(0, 0, self._main.width(), self._main.height())
            # Centre the card.
            cx = (self.width() - self.card.width()) // 2
            cy = (self.height() - self.card.height()) // 2
            self.card.move(max(0, cx), max(0, cy))
            if self._snapshot_label is not None:
                self._snapshot_label.setGeometry(
                    0, 0, self.width(), self.height())
        except Exception as _e:
            logger.debug("tour sync_geometry failed: %s", _e)

    def resizeEvent(self, ev: QResizeEvent) -> None:
        self._sync_geometry()
        super().resizeEvent(ev)

    def eventFilter(self, obj, ev) -> bool:
        # Track parent window resizes so we always cover it fully.
        try:
            if obj is self._main and ev.type() == QEvent.Type.Resize:
                self._sync_geometry()
        except Exception:
            pass
        return False  # never consume

    def keyPressEvent(self, ev: QKeyEvent) -> None:
        key = ev.key()
        if key == Qt.Key.Key_Escape:
            self._on_skip()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space,
                   Qt.Key.Key_Right):
            self._on_next()
            return
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Backspace):
            self._on_back()
            return
        super().keyPressEvent(ev)


# ===========================================================================
# Standalone preview
# ===========================================================================

if __name__ == "__main__":  # pragma: no cover
    from PyQt6.QtWidgets import QMainWindow
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setWindowTitle("Onboarding tour preview")
    win.resize(1200, 720)
    # Give the snapshot something to blur.
    win.setStyleSheet(
        f"QMainWindow {{ background: {C.bg}; }}"
    )
    win.show()
    tour = OnboardingTour(win)
    QTimer.singleShot(400, tour.force_show)
    sys.exit(app.exec())


__all__ = [
    "OnboardingStep",
    "STEPS",
    "TourCard",
    "OnboardingTour",
]
