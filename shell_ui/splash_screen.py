"""splash_screen — Mac-style boot splash for Shell AI.

A frameless, transparent, always-on-top glass card that shows for ~3s while
the heavy `ShellHoloUI` constructor runs (typically 3–5s on cold start so
the user sees an instant, branded response instead of a black screen).

Token-driven: every colour, radius, font and motion duration comes from
`shell_ui.design_tokens` so it stays visually consistent with the rest of
the app and tracks future palette swaps.

Usage:

    from shell_ui.splash_screen import SplashScreen
    splash = SplashScreen(total_duration_ms=3000)
    splash.show()
    # ... build slow main window ...
    splash.dismiss()      # fades out smoothly, deletes itself

The splash is fail-soft: any error during construction is caught by the
caller (see `launch.py`) so a broken splash can never block the main app.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import (
    Qt,
    QPropertyAnimation,
    QEasingCurve,
    QTimer,
    pyqtProperty,
    pyqtSignal,
    QRect,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QLinearGradient,
    QPaintEvent,
    QGuiApplication,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QFrame,
)

APP_VERSION = "1.0.0"
APP_CREATOR = "mdshoebking"

from shell_ui.design_tokens import C, T, S, R, M, SH, accent_text_color, glass_card_qss


def _qcolor_with_alpha(hex_color: str, alpha: int) -> QColor:
    color = QColor(hex_color)
    if not color.isValid():
        return QColor(0, 240, 255, alpha)
    color.setAlpha(alpha)
    return color


# ---------------------------------------------------------------------------
# Official logo bubble — uses the same uploaded Shell logo as public branding.
# ---------------------------------------------------------------------------

class _LogoBubble(QLabel):
    """Official Shell logo with a soft startup glow.

    The splash should never show a placeholder "S" mark when the official
    logo is available.
    """

    SIZE = 64

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo_path = Path(__file__).with_name("shell_logo.png")
        pixmap = QPixmap(str(logo_path))
        if pixmap.isNull():
            self.setText("Shell")
            font = QFont(T.family.split(",")[0].strip(), 12)
            font.setBold(True)
            self.setFont(font)
        else:
            self.setPixmap(
                pixmap.scaled(
                    self.SIZE,
                    self.SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        self.setStyleSheet("QLabel { background: transparent; border: none; }")

        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(34)
        glow.setOffset(0, 0)
        glow.setColor(_qcolor_with_alpha(C.accent, 180))
        self.setGraphicsEffect(glow)


# ---------------------------------------------------------------------------
# Animated progress bar — thin accent fill + sweeping shimmer overlay.
# ---------------------------------------------------------------------------

class _ProgressBar(QWidget):
    """3px thin progress bar.

    `progress` is a 0.0–1.0 float exposed as a Qt property so we can drive
    it with QPropertyAnimation. A second timer animates a 1.5s shimmer
    sweep across the filled portion to give the bar life even when the
    progress value pauses.
    """

    BAR_WIDTH = 280
    BAR_HEIGHT = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(self.BAR_WIDTH, self.BAR_HEIGHT)
        self._progress: float = 0.0
        self._shimmer: float = -0.3  # sweep position, animated from -0.3 → 1.3

        # Shimmer loop — repaints every 16ms (~60 FPS) and advances the
        # sweep position. 1.5s loop so it feels smooth, not frantic.
        self._shimmer_timer = QTimer(self)
        self._shimmer_timer.setInterval(16)
        self._shimmer_timer.timeout.connect(self._tick_shimmer)
        self._shimmer_timer.start()

    # -- progress property (animatable) -------------------------------------

    def get_progress(self) -> float:
        return self._progress

    def set_progress(self, value: float) -> None:
        self._progress = max(0.0, min(1.0, float(value)))
        self.update()

    progress = pyqtProperty(float, fget=get_progress, fset=set_progress)

    # -- shimmer ------------------------------------------------------------

    def _tick_shimmer(self) -> None:
        # 1.5s loop → at 60 FPS that's 90 frames → 1.6/90 ≈ 0.0178 per frame.
        self._shimmer += 0.0178
        if self._shimmer > 1.3:
            self._shimmer = -0.3
        # Only repaint when there's fill to shimmer over — saves CPU at idle.
        if self._progress > 0.0:
            self.update()

    # -- paint --------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (Qt API)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Track — faint hairline at the same height.
        track = QColor(C.accent)
        track.setAlphaF(0.14)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(
            0, 0, self.BAR_WIDTH, self.BAR_HEIGHT,
            self.BAR_HEIGHT / 2, self.BAR_HEIGHT / 2,
        )

        if self._progress <= 0.0:
            return

        fill_w = int(self.BAR_WIDTH * self._progress)
        fill_rect = QRect(0, 0, fill_w, self.BAR_HEIGHT)

        # Base accent fill.
        p.setBrush(QColor(C.accent))
        p.drawRoundedRect(
            fill_rect,
            self.BAR_HEIGHT / 2, self.BAR_HEIGHT / 2,
        )

        # Shimmer sweep — narrow bright gradient that moves across the fill.
        # Clipped to the filled rect so the highlight never escapes the bar.
        p.save()
        p.setClipRect(fill_rect)
        sweep_x = self._shimmer * self.BAR_WIDTH
        sweep_w = self.BAR_WIDTH * 0.35
        grad = QLinearGradient(sweep_x, 0, sweep_x + sweep_w, 0)
        bright = QColor(255, 255, 255, 140)
        clear = QColor(255, 255, 255, 0)
        grad.setColorAt(0.0, clear)
        grad.setColorAt(0.5, bright)
        grad.setColorAt(1.0, clear)
        p.setBrush(grad)
        p.drawRect(int(sweep_x), 0, int(sweep_w), self.BAR_HEIGHT)
        p.restore()


# ---------------------------------------------------------------------------
# Splash screen — the public widget.
# ---------------------------------------------------------------------------

class SplashScreen(QWidget):
    """Boot splash card. See module docstring for usage.

    Signals:
        dismissed: emitted once the fade-out finishes and the widget is
            closed. Useful for chaining cleanup.
    """

    CARD_WIDTH = 480
    CARD_HEIGHT = 320

    FADE_IN_MS = 260
    FADE_OUT_MS = 220

    dismissed = pyqtSignal()

    def __init__(
        self,
        total_duration_ms: int = 3000,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._total_duration_ms = max(1000, int(total_duration_ms))
        self._dismissing = False

        # Frameless, always-on-top, transparent — the glass card itself is
        # painted by the inner _card frame so the outer widget stays clear.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.SplashScreen
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)

        # Opacity effect drives the fade-in / fade-out animations.
        self._opacity_eff = QGraphicsOpacityEffect(self)
        self._opacity_eff.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_eff)

        self._build_ui()
        self._center_on_primary_screen()

        # Progress animation — drives the bar 0 → 100% over 2.4s, leaving
        # a ~600ms tail at 100% before the auto-dismiss fires.
        self._progress_anim = QPropertyAnimation(self._progress_bar, b"progress", self)
        self._progress_anim.setDuration(2400)
        self._progress_anim.setStartValue(0.0)
        self._progress_anim.setEndValue(1.0)
        self._progress_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._progress_anim.valueChanged.connect(self._on_progress_changed)

        # Auto-dismiss safety net so the splash always goes away even if
        # the caller forgets to call `dismiss()`.
        self._auto_dismiss_timer = QTimer(self)
        self._auto_dismiss_timer.setSingleShot(True)
        self._auto_dismiss_timer.timeout.connect(self.dismiss)

    # -- UI construction ---------------------------------------------------

    def _build_ui(self) -> None:
        # Outer transparent layout — gives the glass card a small margin
        # so the drop shadow has room to breathe.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(S.lg, S.lg, S.lg, S.lg)
        outer.setSpacing(0)

        # Glass card frame — the actual visible surface.
        self._card = QFrame(self)
        self._card.setObjectName("SplashCard")
        self._card.setStyleSheet(
            f"#SplashCard {{ {glass_card_qss(elevated=True, strong=True)} }}"
        )
        outer.addWidget(self._card)

        # Drop shadow on the card — gives the splash a real lifted feel.
        card_shadow = QGraphicsDropShadowEffect(self._card)
        card_shadow.setBlurRadius(SH.floating.blur)
        card_shadow.setOffset(0, SH.floating.offset_y)
        card_shadow.setColor(QColor(0, 0, 0, 120))
        self._card.setGraphicsEffect(card_shadow)

        # Card body layout.
        body = QVBoxLayout(self._card)
        body.setContentsMargins(S.xxl, S.xxl, S.xxl, S.lg)
        body.setSpacing(S.md)
        body.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Logo — centred at the top.
        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(0, 0, 0, 0)
        logo_row.addStretch(1)
        logo_row.addWidget(_LogoBubble(self._card))
        logo_row.addStretch(1)
        body.addLayout(logo_row)

        # Wordmark — "Shell".
        title = QLabel("Shell", self._card)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color:{C.text};"
            f"font-family:{T.family};"
            f"font-size:{T.display_size}px;"
            f"font-weight:700;"
            f"letter-spacing:0.5px;"
            f"background:transparent;"
            f"border:none;"
        )
        body.addWidget(title)

        # Subtitle — version + creator.
        subtitle = QLabel(f"v{APP_VERSION}  —  Created by {APP_CREATOR}", self._card)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(
            f"color:{C.text_muted};"
            f"font-family:{T.family};"
            f"font-size:{T.small_size}px;"
            f"font-weight:500;"
            f"background:transparent;"
            f"border:none;"
        )
        body.addWidget(subtitle)

        body.addStretch(1)

        # Progress bar — centred horizontally.
        bar_row = QHBoxLayout()
        bar_row.setContentsMargins(0, 0, 0, 0)
        bar_row.addStretch(1)
        self._progress_bar = _ProgressBar(self._card)
        bar_row.addWidget(self._progress_bar)
        bar_row.addStretch(1)
        body.addLayout(bar_row)

        # Status line — cycles through "Loading…" / "Connecting hub…" / "Ready".
        self._status = QLabel("Loading…", self._card)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(
            f"color:{C.text_subtle};"
            f"font-family:{T.family};"
            f"font-size:{T.small_size}px;"
            f"background:transparent;"
            f"border:none;"
        )
        body.addWidget(self._status)

        # Bottom row — © credit pinned bottom-right.
        credit_row = QHBoxLayout()
        credit_row.setContentsMargins(0, S.sm, 0, 0)
        credit_row.addStretch(1)
        credit = QLabel("© MD Shoeb King", self._card)
        credit.setStyleSheet(
            f"color:{C.text_subtle};"
            f"font-family:{T.family};"
            f"font-size:10px;"
            f"background:transparent;"
            f"border:none;"
        )
        credit_row.addWidget(credit)
        body.addLayout(credit_row)

    # -- positioning -------------------------------------------------------

    def _center_on_primary_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.CARD_WIDTH) // 2
        y = geo.y() + (geo.height() - self.CARD_HEIGHT) // 2
        self.move(x, y)

    # -- status cycling ----------------------------------------------------

    def _on_progress_changed(self, value: float) -> None:
        # Bucketed status messages so the line changes feel deliberate
        # rather than chasing every floating-point step.
        if value < 0.33:
            new_text = "Loading…"
        elif value < 0.85:
            new_text = "Connecting hub…"
        else:
            new_text = "Ready"
        if self._status.text() != new_text:
            self._status.setText(new_text)

    # -- show / dismiss ----------------------------------------------------

    def show(self) -> None:  # noqa: D401 (Qt API)
        """Show the splash with a smooth fade-in."""
        super().show()
        self.raise_()
        self.activateWindow()

        # Fade-in.
        fade_in = QPropertyAnimation(self._opacity_eff, b"opacity", self)
        fade_in.setDuration(self.FADE_IN_MS)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade_in.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._fade_in_anim = fade_in  # keep alive

        # Kick off the progress fill + auto-dismiss safety net.
        self._progress_anim.start()
        self._auto_dismiss_timer.start(self._total_duration_ms)

    def dismiss(self) -> None:
        """Fade out and close. Safe to call multiple times."""
        if self._dismissing:
            return
        self._dismissing = True

        self._auto_dismiss_timer.stop()

        # Snap progress bar to 100% so the user sees a clean finish even
        # if dismiss arrived before the animation completed.
        self._progress_anim.stop()
        self._progress_bar.set_progress(1.0)
        self._status.setText("Ready")

        fade_out = QPropertyAnimation(self._opacity_eff, b"opacity", self)
        fade_out.setDuration(self.FADE_OUT_MS)
        fade_out.setStartValue(self._opacity_eff.opacity())
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        fade_out.finished.connect(self._on_fade_out_done)
        fade_out.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._fade_out_anim = fade_out  # keep alive

    def _on_fade_out_done(self) -> None:
        try:
            self.dismissed.emit()
        finally:
            # WA_DeleteOnClose handles cleanup.
            self.close()
