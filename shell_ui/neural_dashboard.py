from __future__ import annotations

import math
import os
import random
import time
from collections import deque

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


NEURAL_BG = "#030303"
NEURAL_PANEL = "rgba(9, 9, 11, 0.58)"
NEURAL_PANEL_STRONG = "rgba(12, 12, 14, 0.78)"
NEURAL_BORDER = "rgba(255, 255, 255, 0.07)"
NEURAL_BORDER_ACTIVE = "rgba(16, 185, 129, 0.42)"
NEURAL_TEXT = "#f4f4f5"
NEURAL_MUTED = "#71717a"
NEURAL_SUBTLE = "#52525b"
NEURAL_EMERALD = "#10b981"
NEURAL_EMERALD_BRIGHT = "#34d399"
NEURAL_CYAN = "#06b6d4"
NEURAL_PURPLE = "#a855f7"
NEURAL_ORANGE = "#f97316"
NEURAL_RED = "#ef4444"

_FONT = "Arial"
_MONO = "Menlo, Consolas, monospace"


def _panel_qss(radius: int = 18, active: bool = False) -> str:
    border = NEURAL_BORDER_ACTIVE if active else NEURAL_BORDER
    return (
        "QFrame {"
        f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {NEURAL_PANEL_STRONG}, stop:1 {NEURAL_PANEL});"
        f"border: 1px solid {border};"
        f"border-radius: {radius}px;"
        "}"
    )


def _label_qss(color: str = NEURAL_TEXT, size: int = 11, weight: int = 600, mono: bool = False) -> str:
    family = _MONO if mono else _FONT
    return (
        f"color: {color};"
        f"font-family: {family};"
        f"font-size: {size}px;"
        f"font-weight: {weight};"
        "background: transparent;"
        "border: none;"
    )


class NeuralMetricCard(QFrame):
    def __init__(self, label: str, accent: str, parent=None, *, compact: bool = False):
        super().__init__(parent)
        self._accent = accent
        self._compact = compact
        self.setStyleSheet(_panel_qss(radius=14))
        self.setMinimumHeight(42 if compact else 92)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10 if compact else 14, 7 if compact else 12, 10 if compact else 14, 7 if compact else 12)
        layout.setSpacing(4 if compact else 7)

        top = QHBoxLayout()
        self._label = QLabel(label.upper())
        self._label.setStyleSheet(_label_qss(NEURAL_MUTED, 9, 800, mono=True))
        top.addWidget(self._label)
        top.addStretch(1)
        self._status = QLabel("LIVE")
        self._status.setStyleSheet(_label_qss(accent, 8, 800, mono=True))
        if not compact:
            top.addWidget(self._status)
        layout.addLayout(top)

        self._value = QLabel("--")
        self._value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._value.setStyleSheet(_label_qss(NEURAL_TEXT, 10 if compact else 19, 900, mono=True))
        layout.addWidget(self._value)

        self._bar_shell = QFrame()
        self._bar_shell.setFixedHeight(3 if compact else 4)
        self._bar_shell.setStyleSheet(
            "QFrame { background: rgba(0,0,0,0.45); border: 1px solid rgba(255,255,255,0.04); border-radius: 2px; }"
        )
        bar_layout = QHBoxLayout(self._bar_shell)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)
        self._bar = QFrame()
        self._bar.setStyleSheet(f"QFrame {{ background: {accent}; border: none; border-radius: 2px; }}")
        self._bar.setFixedWidth(0)
        bar_layout.addWidget(self._bar)
        bar_layout.addStretch(1)
        layout.addWidget(self._bar_shell)

    def update_value(self, value: str, percent: float | None = None) -> None:
        self._value.setText(str(value))
        if percent is None:
            self._bar.setFixedWidth(0)
            return
        pct = max(0.0, min(100.0, float(percent)))
        width = int(max(0, self._bar_shell.width() - 2) * pct / 100.0)
        self._bar.setFixedWidth(width)


class NeuralTelemetryGraph(QWidget):
    """Compact live chart for dashboard telemetry without leaving the main view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(86)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._cpu: deque[float] = deque([0.0] * 80, maxlen=80)
        self._ram: deque[float] = deque([0.0] * 80, maxlen=80)
        self._net: deque[float] = deque([0.0] * 80, maxlen=80)

    def push(self, cpu: float, ram: float, net: float) -> None:
        self._cpu.append(max(0.0, min(100.0, float(cpu))))
        self._ram.append(max(0.0, min(100.0, float(ram))))
        self._net.append(max(0.0, min(100.0, float(net))))
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)

        grad = QLinearGradient(float(rect.left()), float(rect.top()), float(rect.right()), float(rect.bottom()))
        grad.setColorAt(0.0, QColor(6, 95, 70, 38))
        grad.setColorAt(1.0, QColor(0, 0, 0, 78))
        painter.setBrush(grad)
        painter.setPen(QPen(QColor(255, 255, 255, 14), 1))
        painter.drawRoundedRect(rect, 12, 12)

        painter.setPen(QPen(QColor(255, 255, 255, 12), 1))
        for idx in range(1, 4):
            y = rect.top() + rect.height() * idx / 4
            painter.drawLine(rect.left() + 8, int(y), rect.right() - 8, int(y))

        def draw_series(values: deque[float], color: QColor) -> None:
            if len(values) < 2:
                return
            path = QPainterPath()
            usable = rect.adjusted(10, 8, -10, -9)
            step = usable.width() / max(1, len(values) - 1)
            for i, value in enumerate(values):
                x = usable.left() + step * i
                y = usable.bottom() - (usable.height() * value / 100.0)
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            painter.setPen(QPen(color, 1.6))
            painter.drawPath(path)

        draw_series(self._ram, QColor(6, 182, 212, 185))
        draw_series(self._net, QColor(168, 85, 247, 150))
        draw_series(self._cpu, QColor(52, 211, 153, 210))

        painter.setPen(Qt.PenStyle.NoPen)
        for x, color in (
            (rect.right() - 62, QColor(52, 211, 153, 190)),
            (rect.right() - 42, QColor(6, 182, 212, 180)),
            (rect.right() - 22, QColor(168, 85, 247, 170)),
        ):
            painter.setBrush(color)
            painter.drawEllipse(int(x), rect.top() + 9, 5, 5)


class NeuralWidgetCard(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, title: str, subtitle: str, command: str, accent: str, parent=None):
        super().__init__(parent)
        self._command = command
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(62)
        self.setStyleSheet(
            "QFrame {"
            "background: rgba(5,5,5,0.54);"
            "border: 1px solid rgba(255,255,255,0.07);"
            "border-radius: 12px;"
            "}"
            "QFrame:hover {"
            "background: rgba(16,185,129,0.12);"
            "border: 1px solid rgba(52,211,153,0.34);"
            "}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 8)
        layout.setSpacing(4)
        row = QHBoxLayout()
        dot = QLabel()
        dot.setFixedSize(7, 7)
        dot.setStyleSheet(f"background:{accent}; border-radius:3px; border:none;")
        row.addWidget(dot)
        label = QLabel(title.upper())
        label.setStyleSheet(_label_qss(NEURAL_TEXT, 9, 900, mono=True))
        row.addWidget(label)
        row.addStretch(1)
        layout.addLayout(row)
        sub = QLabel(subtitle)
        sub.setWordWrap(False)
        sub.setStyleSheet(_label_qss(NEURAL_MUTED, 9, 600, mono=True))
        layout.addWidget(sub)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._command)
        super().mousePressEvent(event)


class NeuralTranscriptBubble(QFrame):
    def __init__(self, role: str, text: str, parent=None):
        super().__init__(parent)
        self._role = str(role or "shell")
        self._raw_text = str(text or "")
        is_user = self._role == "user"
        is_system = self._role == "system"
        bg = "rgba(6, 95, 70, 0.28)" if is_user else "rgba(24, 24, 27, 0.62)"
        border = "rgba(16, 185, 129, 0.28)" if is_user else "rgba(255,255,255,0.06)"
        color = "#d1fae5" if is_user else ("#fbbf24" if is_system else "#d4d4d8")
        self.setStyleSheet(
            "QFrame {"
            f"background: {bg}; border: 1px solid {border}; border-radius: 10px;"
            "}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 8, 11, 8)
        layout.setSpacing(4)
        self._role_label = QLabel("USER" if is_user else ("SYSTEM" if is_system else "SHELL"))
        self._role_label.setStyleSheet(_label_qss(NEURAL_EMERALD_BRIGHT if is_user else NEURAL_MUTED, 8, 900, mono=True))
        layout.addWidget(self._role_label)
        self._stream_label = QLabel(self._raw_text)
        self._stream_label.setWordWrap(True)
        self._stream_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._stream_label.setStyleSheet(_label_qss(color, 11, 600, mono=True) + "line-height: 145%;")
        layout.addWidget(self._stream_label)

    def setText(self, text: str) -> None:
        self._raw_text = str(text or "")
        self._stream_label.setText(self._raw_text)


class NeuralPulseOrb(QWidget):
    """Low-overhead native particle sphere for the Shell Neural dashboard."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(360, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._phase = 0.0
        self._speaking = False
        self._thinking = False
        rng = random.Random(42)
        self._points = [
            (
                rng.uniform(0, math.tau),
                math.asin(rng.uniform(-1.0, 1.0)),
                rng.uniform(0.78, 1.08),
                rng.uniform(0.36, 1.0),
            )
            for _ in range(920)
        ]
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_speaking(self, speaking: bool) -> None:
        self._speaking = bool(speaking)

    def set_thinking(self, thinking: bool) -> None:
        self._thinking = bool(thinking)

    def _tick(self) -> None:
        self._phase += 0.018 if not self._speaking else 0.044
        if self._phase > math.tau:
            self._phase -= math.tau
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = self.width()
        h = self.height()
        side = min(w, h)
        cx = w / 2
        cy = h / 2
        base_r = side * (0.31 if not self._speaking else 0.335)
        pulse = 1.0 + math.sin(self._phase * 2.6) * (0.035 if self._speaking else 0.014)

        grad = QRadialGradient(cx, cy, side * 0.42)
        grad.setColorAt(0.0, QColor(52, 211, 153, 66))
        grad.setColorAt(0.45, QColor(16, 185, 129, 22))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(cx - side * 0.42), int(cy - side * 0.42), int(side * 0.84), int(side * 0.84))

        ring_pen = QPen(QColor(16, 185, 129, 158 if self._speaking else 92), 1.2)
        painter.setPen(ring_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for idx, scale in enumerate((0.72, 0.88, 1.03, 1.20)):
            offset = math.sin(self._phase + idx) * 5
            radius = base_r * scale * pulse + offset
            painter.drawEllipse(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2))

        painter.setPen(Qt.PenStyle.NoPen)
        rot_y = self._phase * 0.42
        rot_z = self._phase * 0.16
        for lon, lat, radius_factor, alpha_factor in self._points:
            x3 = math.cos(lat) * math.cos(lon)
            y3 = math.sin(lat)
            z3 = math.cos(lat) * math.sin(lon)
            x_rot = x3 * math.cos(rot_y) - z3 * math.sin(rot_y)
            z_rot = x3 * math.sin(rot_y) + z3 * math.cos(rot_y)
            y_rot = y3 * math.cos(rot_z) - x_rot * math.sin(rot_z)
            x_rot = y3 * math.sin(rot_z) + x_rot * math.cos(rot_z)
            perspective = 0.78 + (z_rot + 1.0) * 0.18
            wobble = math.sin(self._phase * 2 + lon) * (8 if self._speaking else 3)
            radius = base_r * radius_factor * pulse + wobble
            x = cx + x_rot * radius * perspective
            y = cy + y_rot * radius * 0.82 * perspective
            alpha = int((120 if self._speaking else 64) * alpha_factor * perspective)
            color = QColor(52, 211, 153, max(18, min(220, alpha)))
            if self._thinking and z_rot > 0.1:
                color = QColor(6, 182, 212, max(18, min(210, alpha)))
            painter.setBrush(color)
            size = 2 if perspective < 1.04 else 3
            painter.drawEllipse(int(x), int(y), size, size)

        center = QRadialGradient(cx, cy, base_r * 0.22)
        center.setColorAt(0.0, QColor(244, 244, 245, 210))
        center.setColorAt(0.45, QColor(52, 211, 153, 122))
        center.setColorAt(1.0, QColor(16, 185, 129, 0))
        painter.setBrush(center)
        painter.setPen(Qt.PenStyle.NoPen)
        core = base_r * 0.24 * pulse
        painter.drawEllipse(int(cx - core), int(cy - core), int(core * 2), int(core * 2))


class NeuralDashboardPage(QWidget):
    """Shell-style primary interface with Shell backend compatibility."""

    message_sent = pyqtSignal(str)
    speak_requested = pyqtSignal(str)
    tool_prompt_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._pending_files: list[str] = []
        self._last_sent_files: list[str] = []
        self._current_conv_id: str | None = None
        self._messages: deque[tuple[str, str]] = deque(maxlen=250)
        self._thinking = False
        self._boot_started = time.perf_counter()
        self._last_stats = {"cpu": 0.0, "ram": 0.0, "temp": 0.0}
        self._network_level = 0.0

        self.setStyleSheet(f"background: {NEURAL_BG}; border: none; color: {NEURAL_TEXT};")
        self._build()

        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._refresh_stats)
        self._stats_timer.start(500)
        self._network_timer = QTimer(self)
        self._network_timer.timeout.connect(self._refresh_network)
        self._network_timer.start(1700)

        QTimer.singleShot(0, self.show_empty_state)

    def _build(self) -> None:
        root = QGridLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setHorizontalSpacing(16)
        root.setVerticalSpacing(16)
        root.setColumnStretch(0, 3)
        root.setColumnStretch(1, 6)
        root.setColumnStretch(2, 3)

        self._left_rail = self._build_left_rail()
        self._center_core = self._build_core()
        self._right_transcript = self._build_transcript()
        root.addWidget(self._left_rail, 0, 0)
        root.addWidget(self._center_core, 0, 1)
        root.addWidget(self._right_transcript, 0, 2)

    def _build_left_rail(self) -> QWidget:
        rail = QWidget()
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        optics = QFrame()
        optics.setStyleSheet(_panel_qss(radius=18))
        optics.setMinimumHeight(210)
        optics_lay = QVBoxLayout(optics)
        optics_lay.setContentsMargins(16, 16, 16, 16)
        optics_lay.setSpacing(10)
        row = QHBoxLayout()
        self._optic_dot = QLabel()
        self._optic_dot.setFixedSize(8, 8)
        self._optic_dot.setStyleSheet(f"background: {NEURAL_SUBTLE}; border-radius: 4px; border: none;")
        row.addWidget(self._optic_dot)
        optic_title = QLabel("OPTICS OFFLINE")
        optic_title.setStyleSheet(_label_qss(NEURAL_MUTED, 9, 900, mono=True))
        row.addWidget(optic_title)
        row.addStretch(1)
        optics_lay.addLayout(row)
        camera = QFrame()
        camera.setStyleSheet(
            "QFrame { background: rgba(0,0,0,0.46); border: 1px solid rgba(255,255,255,0.05); border-radius: 14px; }"
        )
        camera_lay = QVBoxLayout(camera)
        camera_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_signal = QLabel("NO SIGNAL")
        no_signal.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_signal.setStyleSheet(_label_qss(NEURAL_SUBTLE, 10, 800, mono=True))
        camera_lay.addWidget(no_signal)
        optics_lay.addWidget(camera, 1)
        layout.addWidget(optics)

        network = QFrame()
        network.setStyleSheet(_panel_qss(radius=18))
        network.setFixedHeight(142)
        net_lay = QVBoxLayout(network)
        net_lay.setContentsMargins(16, 14, 16, 14)
        net_lay.setSpacing(11)
        net_head = QHBoxLayout()
        title = QLabel("NETWORK TELEMETRY")
        title.setStyleSheet(_label_qss(NEURAL_MUTED, 9, 900, mono=True))
        net_head.addWidget(title)
        net_head.addStretch(1)
        self._uplink_badge = QLabel("STANDBY")
        self._uplink_badge.setStyleSheet(_label_qss(NEURAL_SUBTLE, 8, 900, mono=True))
        net_head.addWidget(self._uplink_badge)
        net_lay.addLayout(net_head)
        numbers = QGridLayout()
        numbers.setHorizontalSpacing(12)
        self._latency_label = self._small_metric("WSS LATENCY", "--")
        self._packet_label = self._small_metric("PACKET RATE", "--")
        self._routing_label = self._small_metric("ROUTING", "LOCAL")
        numbers.addWidget(self._latency_label, 0, 0)
        numbers.addWidget(self._packet_label, 0, 1)
        numbers.addWidget(self._routing_label, 0, 2)
        net_lay.addLayout(numbers)
        self._tx = NeuralMetricCard("TX", NEURAL_EMERALD, compact=True)
        self._rx = NeuralMetricCard("RX", NEURAL_CYAN, compact=True)
        txrx = QGridLayout()
        txrx.setSpacing(8)
        txrx.addWidget(self._tx, 0, 0)
        txrx.addWidget(self._rx, 0, 1)
        net_lay.addLayout(txrx)
        layout.addWidget(network)

        charts = QFrame()
        charts.setStyleSheet(_panel_qss(radius=18))
        charts_lay = QVBoxLayout(charts)
        charts_lay.setContentsMargins(14, 12, 14, 12)
        charts_lay.setSpacing(8)
        charts_head = QHBoxLayout()
        charts_title = QLabel("LIVE CHARTS")
        charts_title.setStyleSheet(_label_qss(NEURAL_MUTED, 9, 900, mono=True))
        charts_head.addWidget(charts_title)
        charts_head.addStretch(1)
        legend = QLabel("CPU  RAM  NET")
        legend.setStyleSheet(_label_qss(NEURAL_SUBTLE, 8, 800, mono=True))
        charts_head.addWidget(legend)
        charts_lay.addLayout(charts_head)
        self._telemetry_graph = NeuralTelemetryGraph()
        charts_lay.addWidget(self._telemetry_graph)
        layout.addWidget(charts)

        metrics = QFrame()
        metrics.setStyleSheet(_panel_qss(radius=18))
        metrics_lay = QVBoxLayout(metrics)
        metrics_lay.setContentsMargins(14, 14, 14, 14)
        metrics_lay.setSpacing(10)
        head = QLabel("CORE METRICS")
        head.setStyleSheet(_label_qss(NEURAL_MUTED, 9, 900, mono=True))
        metrics_lay.addWidget(head)
        grid = QGridLayout()
        grid.setSpacing(10)
        self._cpu_card = NeuralMetricCard("CPU Load", NEURAL_EMERALD)
        self._ram_card = NeuralMetricCard("RAM Usage", NEURAL_CYAN)
        self._temp_card = NeuralMetricCard("Temp", NEURAL_ORANGE)
        self._os_card = NeuralMetricCard("OS", NEURAL_PURPLE)
        grid.addWidget(self._cpu_card, 0, 0)
        grid.addWidget(self._ram_card, 0, 1)
        grid.addWidget(self._temp_card, 1, 0)
        grid.addWidget(self._os_card, 1, 1)
        metrics_lay.addLayout(grid)
        layout.addWidget(metrics, 1)
        return rail

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        width = self.width()
        try:
            self._right_transcript.setVisible(width >= 1180)
            self._left_rail.setVisible(width >= 960)
        except Exception:
            pass

    def _small_metric(self, label: str, value: str) -> QLabel:
        target = QLabel(f"<span style='color:{NEURAL_SUBTLE}'>{label}</span><br><span style='color:{NEURAL_TEXT}'>{value}</span>")
        target.setTextFormat(Qt.TextFormat.RichText)
        target.setStyleSheet(_label_qss(NEURAL_TEXT, 10, 900, mono=True))
        return target

    def _build_core(self) -> QWidget:
        core = QFrame()
        core.setStyleSheet(
            "QFrame {"
            "background: qradialgradient(cx:0.5, cy:0.45, radius:0.85, fx:0.5, fy:0.45,"
            " stop:0 rgba(16,185,129,0.14), stop:0.52 rgba(3,3,3,0.88), stop:1 rgba(3,3,3,0.98));"
            "border: 1px solid rgba(16,185,129,0.12); border-radius: 22px;"
            "}"
        )
        layout = QVBoxLayout(core)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        mode_row = QHBoxLayout()
        for label, active in (
            ("COMMAND", True),
            ("VOICE STREAM", False),
            ("DEEP RESEARCH", False),
            ("PROJECT RAG", False),
            ("REMOTE LINK", False),
        ):
            pill = QLabel(label)
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pill.setFixedHeight(28)
            pill.setStyleSheet(
                "QLabel {"
                f"background: {'rgba(16,185,129,0.18)' if active else 'rgba(255,255,255,0.04)'};"
                f"color: {NEURAL_EMERALD_BRIGHT if active else NEURAL_MUTED};"
                f"border: 1px solid {'rgba(16,185,129,0.28)' if active else 'rgba(255,255,255,0.05)'};"
                "border-radius: 8px;"
                "font-family: Menlo, Consolas, monospace; font-size: 9px; font-weight: 900;"
                "}"
            )
            mode_row.addWidget(pill)
        layout.addLayout(mode_row)

        self._orb = NeuralPulseOrb()
        layout.addWidget(self._orb, 1)

        widget_grid = QGridLayout()
        widget_grid.setSpacing(10)
        widgets = (
            ("Deep Research", "autonomous search pipeline", "start deep research", NEURAL_CYAN),
            ("Project RAG", "scan and index current codebase", "scan project", NEURAL_EMERALD),
            ("Remote Link", "localhost handoff records", "remote access status", NEURAL_PURPLE),
            ("Live Coding", "build context for edits", "coding assist", NEURAL_ORANGE),
        )
        for idx, (title, subtitle, command, accent) in enumerate(widgets):
            card = NeuralWidgetCard(title, subtitle, command, accent)
            card.clicked.connect(self._emit_widget_command)
            widget_grid.addWidget(card, idx // 2, idx % 2)
        layout.addLayout(widget_grid)

        controls = QFrame()
        controls.setStyleSheet(
            "QFrame { background: rgba(9,9,11,0.70); border: 1px solid rgba(16,185,129,0.22); border-radius: 26px; }"
        )
        controls.setFixedHeight(74)
        controls_lay = QHBoxLayout(controls)
        controls_lay.setContentsMargins(18, 8, 18, 8)
        controls_lay.setSpacing(16)
        self._vision_btn = self._round_control("OPTICS", NEURAL_MUTED)
        self._power_btn = self._round_control("LINK", NEURAL_EMERALD_BRIGHT, primary=True)
        self._mic_btn = self._round_control("MIC", NEURAL_EMERALD_BRIGHT)
        self._vision_btn.clicked.connect(lambda: self.message_sent.emit("start vision uplink"))
        self._power_btn.clicked.connect(lambda: self.message_sent.emit("start realtime voice session"))
        self._mic_btn.clicked.connect(lambda: self.message_sent.emit("toggle microphone"))
        controls_lay.addStretch(1)
        controls_lay.addWidget(self._vision_btn)
        controls_lay.addWidget(self._power_btn)
        controls_lay.addWidget(self._mic_btn)
        controls_lay.addStretch(1)
        layout.addWidget(controls)

        input_shell = QFrame()
        input_shell.setStyleSheet(_panel_qss(radius=20, active=True))
        input_lay = QHBoxLayout(input_shell)
        input_lay.setContentsMargins(18, 10, 12, 10)
        input_lay.setSpacing(10)
        self._input = QTextEdit()
        self._input.setPlaceholderText("Command Shell...")
        self._input.setFixedHeight(42)
        self._input.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._input.setStyleSheet(
            "QTextEdit {"
            "background: transparent; border: none;"
            f"color: {NEURAL_TEXT};"
            "font-family: Arial; font-size: 14px; padding: 9px 0;"
            "}"
        )
        self._input.installEventFilter(self)
        input_lay.addWidget(self._input, 1)
        send = QPushButton("SEND")
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setFixedSize(66, 38)
        send.setStyleSheet(
            "QPushButton {"
            f"background: {NEURAL_EMERALD}; color: #02110b; border: none; border-radius: 19px;"
            "font-family: Menlo, Consolas, monospace; font-size: 10px; font-weight: 900;"
            "}"
            f"QPushButton:hover {{ background: {NEURAL_EMERALD_BRIGHT}; }}"
        )
        send.clicked.connect(self._send)
        input_lay.addWidget(send)
        layout.addWidget(input_shell)
        return core

    def _round_control(self, text: str, color: str, primary: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(58 if not primary else 66, 46 if not primary else 54)
        btn.setStyleSheet(
            "QPushButton {"
            f"background: {'rgba(16,185,129,0.95)' if primary else 'rgba(255,255,255,0.05)'};"
            f"color: {'#02110b' if primary else color};"
            f"border: 1px solid {'rgba(52,211,153,0.9)' if primary else 'rgba(255,255,255,0.08)'};"
            f"border-radius: {27 if primary else 23}px;"
            "font-family: Menlo, Consolas, monospace; font-size: 9px; font-weight: 900;"
            "}"
            f"QPushButton:hover {{ border-color: {NEURAL_EMERALD_BRIGHT}; background: rgba(16,185,129,0.18); color: {NEURAL_EMERALD_BRIGHT}; }}"
        )
        return btn

    def _emit_widget_command(self, command: str) -> None:
        self.message_sent.emit(str(command or "").strip())

    def _build_transcript(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(_panel_qss(radius=18))
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        head = QHBoxLayout()
        title = QLabel("TRANSCRIPT")
        title.setStyleSheet(_label_qss(NEURAL_MUTED, 9, 900, mono=True))
        head.addWidget(title)
        head.addStretch(1)
        self._live_badge = QLabel("LIVE-LOG")
        self._live_badge.setStyleSheet(_label_qss("rgba(16,185,129,0.55)", 8, 900, mono=True))
        head.addWidget(self._live_badge)
        layout.addLayout(head)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 3px; background: transparent; }"
            f"QScrollBar::handle:vertical {{ background: {NEURAL_EMERALD}; border-radius: 1px; min-height: 32px; }}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        self._chat_w = QWidget()
        self._chat_w.setStyleSheet("background: transparent; border: none;")
        self._chat_lay = QVBoxLayout(self._chat_w)
        self._chat_lay.setContentsMargins(0, 6, 0, 6)
        self._chat_lay.setSpacing(10)
        self._chat_lay.addStretch(1)
        self._scroll.setWidget(self._chat_w)
        layout.addWidget(self._scroll, 1)

        self._thinking_label = QLabel("SHELL PROCESSING")
        self._thinking_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thinking_label.setFixedHeight(30)
        self._thinking_label.setStyleSheet(_label_qss(NEURAL_EMERALD_BRIGHT, 9, 900, mono=True))
        self._thinking_label.hide()
        layout.addWidget(self._thinking_label)
        return panel

    def eventFilter(self, obj, event):
        if obj == self._input and event.type() == event.Type.KeyPress:
            key = event.key()
            mods = event.modifiers()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (mods & Qt.KeyboardModifier.ShiftModifier):
                self._send()
                return True
            if key == Qt.Key.Key_Escape:
                self._input.clear()
                return True
        return super().eventFilter(obj, event)

    def _send(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._input.clear()
        self._last_sent_files = list(self._pending_files)
        self._pending_files = []
        self.add_message("user", text)
        self.message_sent.emit(text)

    def add_message(self, role: str, text: str, stream: bool = False):
        del stream
        bubble = NeuralTranscriptBubble(role, text)
        bubble.setMaximumWidth(520)
        wrapper = QHBoxLayout()
        wrapper.setContentsMargins(0, 0, 0, 0)
        if role == "user":
            wrapper.addStretch(1)
            wrapper.addWidget(bubble)
        else:
            wrapper.addWidget(bubble)
            wrapper.addStretch(1)
        insert_at = max(0, self._chat_lay.count() - 1)
        self._chat_lay.insertLayout(insert_at, wrapper)
        self._messages.append((role, text))
        self._remove_empty_state()
        self.request_stream_scroll(was_near_bottom=True)
        return bubble

    def _remove_empty_state(self) -> None:
        empty = getattr(self, "_empty_state", None)
        if empty is not None:
            empty.hide()
            empty.deleteLater()
            self._empty_state = None

    def show_empty_state(self):
        if getattr(self, "_empty_state", None) is not None:
            return self._empty_state
        empty = QFrame()
        empty.setStyleSheet(
            "QFrame { background: rgba(0,0,0,0.18); border: 1px dashed rgba(16,185,129,0.20); border-radius: 14px; }"
        )
        lay = QVBoxLayout(empty)
        lay.setContentsMargins(18, 24, 18, 24)
        lay.setSpacing(8)
        title = QLabel("NO DATA STREAM")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(_label_qss(NEURAL_SUBTLE, 10, 900, mono=True))
        lay.addWidget(title)
        hint = QLabel("Start with a command or activate the voice link.")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        hint.setStyleSheet(_label_qss(NEURAL_MUTED, 11, 500))
        lay.addWidget(hint)
        insert_at = max(0, self._chat_lay.count() - 1)
        self._chat_lay.insertWidget(insert_at, empty)
        self._empty_state = empty
        return empty

    def _clear_chat(self) -> None:
        while self._chat_lay.count() > 1:
            item = self._chat_lay.takeAt(0)
            if item is None:
                continue
            child_layout = item.layout()
            if child_layout is not None:
                while child_layout.count():
                    child = child_layout.takeAt(0)
                    if child and child.widget():
                        child.widget().deleteLater()
            elif item.widget():
                item.widget().deleteLater()
        self._messages.clear()
        self.show_empty_state()

    def set_thinking(self, thinking: bool) -> None:
        self._thinking = bool(thinking)
        self._thinking_label.setVisible(self._thinking)
        self._orb.set_thinking(self._thinking)

    def is_scroll_near_bottom(self) -> bool:
        bar = self._scroll.verticalScrollBar()
        return bar.maximum() - bar.value() < 80

    def request_stream_scroll(self, was_near_bottom: bool = True) -> None:
        if not was_near_bottom:
            return
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def on_tool_event(self, data: dict) -> None:
        if not isinstance(data, dict):
            return
        phase = data.get("phase", "event")
        tool = data.get("tool", "tool")
        preview = data.get("preview") or data.get("args_preview") or data.get("error") or ""
        self.add_message("system", f"{phase.upper()} {tool}: {str(preview)[:140]}")

    def refresh_workspace(self, open_path=None) -> None:
        suffix = f" - {open_path}" if open_path else ""
        self.add_message("system", f"WORKSPACE REFRESHED{suffix}")

    def set_workspace_visible(self, visible: bool) -> None:
        del visible

    def set_current_conversation_id(self, conv_id) -> None:
        self._current_conv_id = str(conv_id) if conv_id else None

    def _refresh_stats(self) -> None:
        cpu = ram = 0.0
        temp = 0.0
        try:
            import psutil

            cpu = float(psutil.cpu_percent(interval=None))
            ram = float(psutil.virtual_memory().percent)
            temps = getattr(psutil, "sensors_temperatures", lambda: {})()
            flat = [item.current for rows in (temps or {}).values() for item in rows if getattr(item, "current", None)]
            temp = float(flat[0]) if flat else 0.0
        except Exception:
            cpu = (math.sin(time.perf_counter() * 0.8) + 1) * 17
            ram = (math.sin(time.perf_counter() * 0.5 + 1.3) + 1) * 24
        self._last_stats = {"cpu": cpu, "ram": ram, "temp": temp}
        self._cpu_card.update_value(f"{cpu:.0f}%", cpu)
        self._ram_card.update_value(f"{ram:.0f}%", ram)
        self._temp_card.update_value(f"{temp:.0f}C" if temp else "--", min(temp, 100.0) if temp else 0)
        self._os_card.update_value(os.name.upper(), None)
        try:
            self._telemetry_graph.push(cpu, ram, self._network_level)
        except Exception:
            pass

    def _refresh_network(self) -> None:
        active = self._thinking or bool(self._messages)
        latency = random.randint(12, 45) if active else 0
        rate = random.random() * 8.5 + 0.5 if active else 0.0
        tx = random.randint(18, 100) if active else 0
        rx = random.randint(18, 100) if active else 0
        self._network_level = max(tx, rx)
        self._uplink_badge.setText("SECURE UPLINK" if active else "STANDBY")
        self._uplink_badge.setStyleSheet(_label_qss(NEURAL_EMERALD_BRIGHT if active else NEURAL_SUBTLE, 8, 900, mono=True))
        self._latency_label.setText(
            f"<span style='color:{NEURAL_SUBTLE}'>WSS LATENCY</span><br><span style='color:{NEURAL_TEXT}'>{latency}ms</span>"
            if active
            else f"<span style='color:{NEURAL_SUBTLE}'>WSS LATENCY</span><br><span style='color:{NEURAL_TEXT}'>--</span>"
        )
        self._packet_label.setText(
            f"<span style='color:{NEURAL_SUBTLE}'>PACKET RATE</span><br><span style='color:{NEURAL_TEXT}'>{rate:.2f} MB/s</span>"
            if active
            else f"<span style='color:{NEURAL_SUBTLE}'>PACKET RATE</span><br><span style='color:{NEURAL_TEXT}'>--</span>"
        )
        self._routing_label.setText(
            f"<span style='color:{NEURAL_SUBTLE}'>ROUTING</span><br><span style='color:{NEURAL_TEXT}'>{'GLOBAL' if active else 'LOCAL'}</span>"
        )
        self._tx.update_value(f"{tx}%", tx)
        self._rx.update_value(f"{rx}%", rx)
