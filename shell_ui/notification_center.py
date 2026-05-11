"""notification_center — Mac-style persistent notification panel for Shell OS.

Complements the live `ToastManager`: toasts are ephemeral pop-ups in the
top-right of the screen, the Notification Center is the persistent
history the user can review later by clicking the bell icon in the top
bar.

Public API:
    NotificationItem    — dataclass for a single entry.
    NotificationStore   — in-memory deque (max 200) + Qt signal
                          `notifications_changed`. Optional persistence
                          to `~/.shell_chat_history/notifications.json`.
    NotificationCenter  — slide-in QFrame panel (360 px wide) overlaid
                          on the main window, with tabs / mark-all-read
                          / per-row context menu.

The panel is overlaid on the main window via `setParent(host)` and
`move()`. It does NOT replace any existing toast — every event creates
both a toast (via the existing path) AND a persistent notification.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque, List, Optional

from PyQt6.QtCore import (
    QEasingCurve, QEvent, QObject, QPoint, QPropertyAnimation, QRect, QSize,
    Qt, pyqtSignal,
)
from PyQt6.QtGui import QAction, QCursor, QPainter, QPainterPath, QPen, QPixmap, QColor
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

logger = logging.getLogger("shell_ui.notification_center")


# ---------------------------------------------------------------------------
# Token import — design system. Falls back to safe defaults so the module
# is importable in test contexts where design_tokens isn't on the path.
# ---------------------------------------------------------------------------
try:
    from shell_ui.design_tokens import (
        C as _DT_C, T as _DT_T, S as _DT_S, R as _DT_R, M as _DT_M,
        glass_card_qss as _DT_glass_card_qss,
    )

    def _tk():
        return _DT_C, _DT_T, _DT_S, _DT_R, _DT_M

    def _glass(strong: bool = True, elevated: bool = True) -> str:
        return _DT_glass_card_qss(strong=strong, elevated=elevated)
except Exception:
    class _Fallback:
        bg = "#0d1322"; surface = "#0d1322"; surface_2 = "#141d33"
        surface_3 = "#1c2944"
        border = "rgba(143,245,255,0.10)"
        border_strong = "rgba(143,245,255,0.20)"
        text = "#e8f4ff"; text_muted = "#8fa3bd"; text_subtle = "#5a6d87"
        accent = "#00f0ff"; accent_hover = "#5cf6ff"
        accent_soft = "rgba(0,240,255,0.12)"
        success = "#3ee3a8"; warning = "#ffc24b"; error = "#ff6b6b"
        glass = "rgba(22,30,50,0.55)"; glass_strong = "rgba(26,36,58,0.78)"
        glass_hi = "rgba(200,252,255,0.18)"
        glass_border = "rgba(143,245,255,0.18)"

    class _FT:
        family = "Segoe UI, system-ui, sans-serif"
        body_size = 14; small_size = 12; h2_size = 19

    class _FS:
        xs = 4; sm = 8; md = 12; lg = 16; xl = 24

    class _FR:
        xs = 6; sm = 8; md = 12; lg = 16; xl = 20; pill = 999

    class _FM:
        fast_ms = 180; base_ms = 280; slow_ms = 380

    def _tk():
        return _Fallback(), _FT(), _FS(), _FR(), _FM()

    def _glass(strong: bool = True, elevated: bool = True) -> str:
        C = _Fallback(); R = _FR()
        body = C.glass_strong if strong else C.glass
        rad = R.xl if elevated else R.lg
        return (
            f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"  stop:0 {C.glass_hi}, stop:0.04 {body}, stop:1 {body}); "
            f"border:1px solid {C.glass_border}; "
            f"border-top:1px solid {C.glass_hi}; "
            f"border-radius:{rad}px;"
        )


# ---------------------------------------------------------------------------
# Persistence path — same root as chat_history for consistency.
# ---------------------------------------------------------------------------

def _store_path() -> Path:
    root = Path.home() / ".shell_chat_history"
    try:
        root.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return root / "notifications.json"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

VALID_TONES = {"info", "success", "warning", "error"}
VALID_CATEGORIES = {"tool", "research", "safety", "system"}


@dataclass
class NotificationItem:
    """A single notification entry. Stored in `NotificationStore`."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    title: str = ""
    body: str = ""
    tone: str = "info"        # info | success | warning | error
    category: str = "system"  # tool | research | safety | system
    timestamp: datetime = field(default_factory=_now_utc)
    read: bool = False

    def __post_init__(self):
        if self.tone not in VALID_TONES:
            self.tone = "info"
        if self.category not in VALID_CATEGORIES:
            self.category = "system"
        # Normalise timestamp — accept str (ISO) or datetime.
        if isinstance(self.timestamp, str):
            try:
                self.timestamp = datetime.fromisoformat(self.timestamp)
            except Exception:
                self.timestamp = _now_utc()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "NotificationItem":
        try:
            ts_raw = d.get("timestamp")
            if isinstance(ts_raw, str):
                ts = datetime.fromisoformat(ts_raw)
            elif isinstance(ts_raw, datetime):
                ts = ts_raw
            else:
                ts = _now_utc()
            return cls(
                id=str(d.get("id") or uuid.uuid4().hex),
                title=str(d.get("title") or ""),
                body=str(d.get("body") or ""),
                tone=str(d.get("tone") or "info"),
                category=str(d.get("category") or "system"),
                timestamp=ts,
                read=bool(d.get("read", False)),
            )
        except Exception as e:
            logger.debug("NotificationItem.from_dict failed: %s", e)
            return cls(title="(corrupt entry)")


# ---------------------------------------------------------------------------
# Store — in-memory deque + persistence + Qt signal.
# ---------------------------------------------------------------------------

class NotificationStore(QObject):
    """Holds the notification history. Emits `notifications_changed`
    every time the list mutates (add / mark / clear)."""

    notifications_changed = pyqtSignal()

    MAX_ITEMS = 200

    def __init__(self, persist: bool = True, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._items: Deque[NotificationItem] = deque(maxlen=self.MAX_ITEMS)
        self._persist = bool(persist)
        if self._persist:
            self._load()

    # -- mutation -----------------------------------------------------
    def add(self, item: NotificationItem) -> NotificationItem:
        """Append an item to the front (newest first). Auto-saves."""
        if not isinstance(item, NotificationItem):
            return item
        self._items.appendleft(item)
        self._on_change()
        return item

    def add_simple(self, title: str, body: str = "",
                   tone: str = "info", category: str = "system") -> NotificationItem:
        """Convenience wrapper — build + add an item from primitives."""
        item = NotificationItem(
            title=str(title or "")[:240],
            body=str(body or "")[:600],
            tone=tone, category=category,
        )
        return self.add(item)

    def mark_read(self, item_id: str) -> bool:
        for it in self._items:
            if it.id == item_id and not it.read:
                it.read = True
                self._on_change()
                return True
        return False

    def mark_all_read(self) -> int:
        n = 0
        for it in self._items:
            if not it.read:
                it.read = True; n += 1
        if n:
            self._on_change()
        return n

    def remove(self, item_id: str) -> bool:
        for it in list(self._items):
            if it.id == item_id:
                try:
                    self._items.remove(it)
                except ValueError:
                    pass
                self._on_change()
                return True
        return False

    def clear(self) -> None:
        if not self._items:
            return
        self._items.clear()
        self._on_change()

    # -- queries ------------------------------------------------------
    def items(self) -> List[NotificationItem]:
        """Return list in newest-first order."""
        return list(self._items)

    def filtered(self, tab: str) -> List[NotificationItem]:
        """Filter by tab key: 'all' | 'unread' | 'tool' | 'research' | 'safety'."""
        tab = (tab or "all").lower()
        if tab == "all":
            return list(self._items)
        if tab == "unread":
            return [i for i in self._items if not i.read]
        return [i for i in self._items if i.category == tab]

    def unread_count(self) -> int:
        return sum(1 for i in self._items if not i.read)

    def __len__(self) -> int:
        return len(self._items)

    # -- internals ----------------------------------------------------
    def _on_change(self):
        if self._persist:
            self._save()
        try:
            self.notifications_changed.emit()
        except Exception as e:
            logger.debug("notifications_changed emit failed: %s", e)

    def _load(self):
        path = _store_path()
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                return
            # Cap to most recent 200 — file may contain more from older runs.
            for d in data[-self.MAX_ITEMS:]:
                if isinstance(d, dict):
                    self._items.appendleft(NotificationItem.from_dict(d))
            # appendleft reversed the order → flip to chronological-newest-left.
            try:
                self._items = deque(reversed(self._items), maxlen=self.MAX_ITEMS)
            except Exception:
                pass
        except Exception as e:
            logger.debug("notifications load failed: %s", e)

    def _save(self):
        path = _store_path()
        try:
            # Deque is newest-first (newest at index 0), so the FIRST
            # MAX_ITEMS entries are the freshest. The previous
            # `[-self.MAX_ITEMS:]` kept the OLDEST 200 and silently
            # discarded every new notification once the cap was reached.
            payload = [it.to_dict() for it in list(self._items)[:self.MAX_ITEMS]]
            # Atomic write — partial files would otherwise be parsed
            # at next launch and silently nuke the entire history.
            tmp = path.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception as e:
            logger.debug("notifications save failed: %s", e)


# ---------------------------------------------------------------------------
# Helpers — relative timestamp, tone colour.
# ---------------------------------------------------------------------------

def _relative_time(ts: datetime) -> str:
    try:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = _now_utc() - ts
        secs = int(delta.total_seconds())
        if secs < 5:
            return "now"
        if secs < 60:
            return f"{secs}s ago"
        mins = secs // 60
        if mins < 60:
            return f"{mins}m ago"
        hrs = mins // 60
        if hrs < 24:
            return f"{hrs}h ago"
        days = hrs // 24
        if days < 7:
            return f"{days}d ago"
        return ts.strftime("%b %d")
    except Exception:
        return ""


def _tone_color(tone: str) -> str:
    C, *_ = _tk()
    return {
        "info":    C.accent,
        "success": C.success,
        "warning": C.warning,
        "error":   C.error,
    }.get(tone, C.accent)


# ---------------------------------------------------------------------------
# Bell icon pixmap — used by the topbar bell button.
# ---------------------------------------------------------------------------

def make_bell_pixmap(size: int = 18, color: str = "#e8f4ff") -> QPixmap:
    """Hand-painted bell icon. Cached via local dict for cheap reuse."""
    key = (size, color)
    cache = make_bell_pixmap._cache  # type: ignore[attr-defined]
    if key in cache:
        return cache[key]
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    m = size * 0.18
    s = size - 2 * m
    cx = size / 2
    # Bell body — rounded dome with flared base.
    path = QPainterPath()
    top_y = m + s * 0.10
    bot_y = m + s * 0.74
    half_w_top = s * 0.06
    half_w_bot = s * 0.40
    path.moveTo(cx - half_w_bot, bot_y)
    # Left flare → up to the dome
    path.cubicTo(
        cx - half_w_bot, bot_y - s * 0.10,
        cx - half_w_top - s * 0.04, top_y + s * 0.30,
        cx - half_w_top, top_y,
    )
    # Dome top
    path.cubicTo(
        cx - half_w_top, top_y - s * 0.04,
        cx + half_w_top, top_y - s * 0.04,
        cx + half_w_top, top_y,
    )
    # Right side down
    path.cubicTo(
        cx + half_w_top + s * 0.04, top_y + s * 0.30,
        cx + half_w_bot, bot_y - s * 0.10,
        cx + half_w_bot, bot_y,
    )
    path.closeSubpath()
    p.drawPath(path)
    # Clapper — small dot beneath.
    p.setBrush(QColor(color))
    p.drawEllipse(QPoint(int(cx), int(bot_y + s * 0.14)), int(s * 0.07), int(s * 0.07))
    p.end()
    cache[key] = pix
    return pix


make_bell_pixmap._cache = {}  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# NotificationRow — single list item.
# ---------------------------------------------------------------------------

class NotificationRow(QFrame):
    """A single entry in the panel's scroll list. 64-72 px tall.

    Layout: coloured left bar | small icon | title (1-line trunc) +
                                  body (2-line trunc) + relative ts.
    """

    clicked = pyqtSignal(str)            # emits item.id on left-click
    delete_requested = pyqtSignal(str)
    mark_read_requested = pyqtSignal(str)

    def __init__(self, item: NotificationItem, parent=None):
        super().__init__(parent)
        self.item = item
        self._build()

    def _build(self):
        C, T, S, R, _M = _tk()
        self.setFixedHeight(72)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setObjectName("notif_row")
        self._apply_style(hovered=False)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, S.sm, S.md, S.sm)
        lay.setSpacing(S.sm)

        # Left coloured bar — full row height, 3 px wide, rounded.
        bar = QFrame(self)
        bar.setFixedWidth(3)
        bar.setStyleSheet(
            f"background-color:{_tone_color(self.item.tone)}; "
            f"border:none; border-radius:1px;"
        )
        lay.addWidget(bar)

        # Tone dot — small circle so the tone is readable even if the
        # left-bar gets visually lost on certain themes.
        dot = QLabel(self)
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(
            f"background-color:{_tone_color(self.item.tone)}; "
            f"border-radius:4px; border:none;"
        )
        # Vertical centre wrap
        dot_holder = QWidget(self)
        dh = QVBoxLayout(dot_holder)
        dh.setContentsMargins(S.xs, 0, 0, 0)
        dh.setSpacing(0)
        dh.addStretch(1); dh.addWidget(dot); dh.addStretch(1)
        lay.addWidget(dot_holder)

        # Text column.
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)

        # Header line: title (left) + relative timestamp (right).
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(S.sm)
        title = QLabel(self._truncate(self.item.title, 64))
        title.setStyleSheet(
            f"color:{C.text}; "
            f"font-family:'{T.family}'; font-size:{T.body_size}px; "
            f"font-weight:600; background:transparent; border:none;"
        )
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        hdr.addWidget(title, 1)

        ts = QLabel(_relative_time(self.item.timestamp))
        ts.setStyleSheet(
            f"color:{C.text_subtle}; "
            f"font-family:'{T.family}'; font-size:{T.small_size}px; "
            f"background:transparent; border:none;"
        )
        ts.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        hdr.addWidget(ts, 0)
        col.addLayout(hdr)

        # Body — 2 line truncation.
        body_text = self._truncate(self.item.body, 100)
        body = QLabel(body_text)
        body.setWordWrap(True)
        body.setStyleSheet(
            f"color:{C.text_muted}; "
            f"font-family:'{T.family}'; font-size:{T.small_size}px; "
            f"background:transparent; border:none;"
        )
        body.setMaximumHeight(34)  # ~2 lines at 12px
        col.addWidget(body)

        lay.addLayout(col, 1)

        # Unread dot — small accent ball at the right edge.
        if not self.item.read:
            unread = QLabel(self)
            unread.setFixedSize(8, 8)
            unread.setStyleSheet(
                f"background-color:{C.accent}; "
                f"border-radius:4px; border:none;"
            )
            ud_holder = QWidget(self)
            udh = QVBoxLayout(ud_holder)
            udh.setContentsMargins(0, 0, S.xs, 0)
            udh.setSpacing(0)
            udh.addStretch(1); udh.addWidget(unread); udh.addStretch(1)
            lay.addWidget(ud_holder)

    @staticmethod
    def _truncate(s: str, n: int) -> str:
        s = (s or "").strip()
        if len(s) <= n:
            return s
        return s[: max(1, n - 1)].rstrip() + "..."

    def _apply_style(self, hovered: bool):
        C, _T, _S, R, _M = _tk()
        bg = C.accent_soft if hovered else "transparent"
        self.setStyleSheet(
            f"#notif_row {{ background-color:{bg}; "
            f"border:none; border-radius:{R.md}px; }}"
        )

    # -- events -------------------------------------------------------
    def enterEvent(self, e):
        self._apply_style(hovered=True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._apply_style(hovered=False)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item.id)
        super().mousePressEvent(e)

    def contextMenuEvent(self, e):
        try:
            menu = QMenu(self)
            act_read = QAction("Mark as read", self)
            act_read.setEnabled(not self.item.read)
            act_read.triggered.connect(
                lambda: self.mark_read_requested.emit(self.item.id))
            menu.addAction(act_read)
            act_del = QAction("Delete", self)
            act_del.triggered.connect(
                lambda: self.delete_requested.emit(self.item.id))
            menu.addAction(act_del)
            menu.exec(e.globalPos())
        except Exception as ex:
            logger.debug("row context menu failed: %s", ex)


# ---------------------------------------------------------------------------
# Tab bar — horizontal pill tabs.
# ---------------------------------------------------------------------------

class _TabBar(QWidget):
    tab_changed = pyqtSignal(str)

    TABS = [
        ("all",      "All"),
        ("unread",   "Unread"),
        ("tool",     "Tools"),
        ("research", "Research"),
        ("safety",   "Safety"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = "all"
        self._buttons: dict[str, QPushButton] = {}
        self._build()

    def _build(self):
        C, T, S, R, _M = _tk()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(S.lg, S.sm, S.lg, S.sm)
        lay.setSpacing(S.xs)
        for key, label in self.TABS:
            btn = QPushButton(label, self)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(lambda _=False, k=key: self._activate(k))
            self._buttons[key] = btn
            lay.addWidget(btn)
        lay.addStretch(1)
        self._restyle()

    def _activate(self, key: str):
        if key == self._active:
            return
        self._active = key
        self._restyle()
        self.tab_changed.emit(key)

    def set_active(self, key: str):
        if key in self._buttons and key != self._active:
            self._active = key
            self._restyle()

    def _restyle(self):
        C, T, S, R, _M = _tk()
        for key, btn in self._buttons.items():
            active = (key == self._active)
            if active:
                qss = (
                    f"QPushButton {{ background-color:{C.accent_soft}; "
                    f"  color:{C.accent}; "
                    f"  border:1px solid {C.accent}; border-radius:{R.pill}px; "
                    f"  padding:4px 12px; "
                    f"  font-family:'{T.family}'; font-size:{T.small_size}px; "
                    f"  font-weight:600; }} "
                    f"QPushButton:hover {{ background-color:{C.accent_soft}; }}"
                )
            else:
                qss = (
                    f"QPushButton {{ background-color:transparent; "
                    f"  color:{C.text_muted}; "
                    f"  border:1px solid {C.border}; border-radius:{R.pill}px; "
                    f"  padding:4px 12px; "
                    f"  font-family:'{T.family}'; font-size:{T.small_size}px; "
                    f"  font-weight:500; }} "
                    f"QPushButton:hover {{ background-color:{C.accent_soft}; "
                    f"  color:{C.text}; }}"
                )
            btn.setStyleSheet(qss)


# ---------------------------------------------------------------------------
# NotificationCenter — the slide-in panel.
# ---------------------------------------------------------------------------

class NotificationCenter(QFrame):
    """Slide-in notification history panel. 360 px wide, full host height.

    Mounts as a child of `host` (the main window), positioned via `move()`
    on the right edge. Hidden by default.

    Public API:
        toggle()        — show/hide with a 260 ms ease-out slide.
        show_panel()    — explicit show.
        hide_panel()    — explicit hide.
        is_open() -> bool
        sync_position() — call this on host resize.
    """

    PANEL_WIDTH = 360
    SLIDE_MS = 260

    def __init__(self, host: QWidget, store: Optional[NotificationStore] = None,
                 parent: Optional[QWidget] = None):
        # Parent the panel to `host` so it overlays the main window.
        super().__init__(parent or host)
        self._host = host
        self._store = store or NotificationStore()
        self._active_tab = "all"
        self._open = False
        self._slide_anim: Optional[QPropertyAnimation] = None

        self.setObjectName("notif_center")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._apply_panel_style()

        self._build_ui()
        self._populate_rows()

        # Wire store signal.
        try:
            self._store.notifications_changed.connect(self._on_store_change)
        except Exception as e:
            logger.debug("notif store connect failed: %s", e)

        # Install a click-outside filter on the host so we close on
        # outside clicks (focus trap behaviour).
        self._click_filter = _ClickOutsideFilter(self)
        try:
            host.installEventFilter(self._click_filter)
        except Exception as e:
            logger.debug("notif click-outside install failed: %s", e)

        # Sync to host width changes.
        self._resize_filter = _HostResizeFilter(self)
        try:
            host.installEventFilter(self._resize_filter)
        except Exception as e:
            logger.debug("notif host-resize install failed: %s", e)

        # Initial geometry — placed off-screen to the right, hidden.
        self.setFixedWidth(self.PANEL_WIDTH)
        self.sync_position(initial=True)
        self.hide()

    # -- styling ------------------------------------------------------
    def _apply_panel_style(self):
        # Mac-vibrancy "light" overlay only (static QSS gradient).
        # NOTE: live GlassBackdrop was REMOVED — its 80ms parent.grab()
        # loop ran even while the panel was hidden, contributing to the
        # UI-thread saturation that dropped nav-button clicks.
        try:
            from shell_ui.design_tokens import vibrancy_layer_qss as _vib
            self.setStyleSheet(
                f"#notif_center {{ {_vib('light', radius=20)} }}"
            )
            self._backdrop = None
        except Exception:
            self.setStyleSheet(
                f"#notif_center {{ {_glass(strong=True, elevated=True)} }}"
            )
            self._backdrop = None

    # -- layout -------------------------------------------------------
    def _build_ui(self):
        C, T, S, R, _M = _tk()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- Header ----
        hdr = QFrame(self)
        hdr.setObjectName("notif_header")
        hdr.setStyleSheet(
            f"#notif_header {{ background:transparent; border:none; "
            f"border-bottom:1px solid {C.glass_border}; }}"
        )
        h = QHBoxLayout(hdr)
        h.setContentsMargins(S.lg, S.md, S.md, S.md)
        h.setSpacing(S.sm)

        title = QLabel("Notifications")
        title.setStyleSheet(
            f"color:{C.text}; font-family:'{T.family}'; "
            f"font-size:{T.h2_size}px; font-weight:700; background:transparent; "
            f"border:none;"
        )
        h.addWidget(title)
        h.addStretch(1)

        self._mark_link = QPushButton("Mark all read", hdr)
        self._mark_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mark_link.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._mark_link.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.accent}; "
            f"  border:none; padding:4px 8px; "
            f"  font-family:'{T.family}'; font-size:{T.small_size}px; "
            f"  font-weight:600; }} "
            f"QPushButton:hover {{ color:{C.accent_hover}; "
            f"  background-color:{C.accent_soft}; border-radius:{R.sm}px; }}"
        )
        self._mark_link.clicked.connect(self._on_mark_all)
        h.addWidget(self._mark_link)

        close_btn = QPushButton("✕", hdr)
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_btn.setToolTip("Close")
        close_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.text_muted}; "
            f"  border:none; border-radius:14px; "
            f"  font-size:14px; font-weight:600; }} "
            f"QPushButton:hover {{ background-color:{C.accent_soft}; "
            f"  color:{C.text}; }}"
        )
        close_btn.clicked.connect(self.hide_panel)
        h.addWidget(close_btn)

        root.addWidget(hdr)

        # ---- Tab bar ----
        self._tabs = _TabBar(self)
        self._tabs.tab_changed.connect(self._on_tab_change)
        root.addWidget(self._tabs)

        # ---- Scrollable list ----
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(
            "QScrollArea { background:transparent; border:none; } "
            f"QScrollBar:vertical {{ background:transparent; width:8px; "
            f"  margin:4px 2px 4px 0; }} "
            f"QScrollBar::handle:vertical {{ background:{C.border_strong}; "
            f"  border-radius:4px; min-height:30px; }} "
            f"QScrollBar::handle:vertical:hover {{ background:{C.accent}; }} "
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical "
            "{ height:0; background:none; } "
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical "
            "{ background:none; }"
        )

        self._list_host = QWidget()
        self._list_host.setStyleSheet("background:transparent; border:none;")
        self._list_lay = QVBoxLayout(self._list_host)
        self._list_lay.setContentsMargins(S.sm, S.sm, S.sm, S.sm)
        self._list_lay.setSpacing(2)
        self._list_lay.addStretch(1)

        self._scroll.setWidget(self._list_host)
        root.addWidget(self._scroll, 1)

        # ---- Empty state label (toggled by _populate_rows) ----
        self._empty_lbl = QLabel("No notifications yet", self._list_host)
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color:{C.text_subtle}; font-family:'{T.family}'; "
            f"font-size:{T.small_size}px; background:transparent; border:none; "
            f"padding:32px 16px;"
        )
        self._empty_lbl.hide()
        # Insert at the top of the list (above the stretch).
        self._list_lay.insertWidget(0, self._empty_lbl,
                                    alignment=Qt.AlignmentFlag.AlignCenter)

    # -- list rendering -----------------------------------------------
    def _clear_rows(self):
        # Remove every NotificationRow but keep the empty label + stretch.
        to_remove = []
        for i in range(self._list_lay.count()):
            it = self._list_lay.itemAt(i)
            if it is None:
                continue
            w = it.widget()
            if isinstance(w, NotificationRow):
                to_remove.append(w)
        for w in to_remove:
            self._list_lay.removeWidget(w)
            w.setParent(None)
            w.deleteLater()

    def _populate_rows(self):
        try:
            self._clear_rows()
            items = self._store.filtered(self._active_tab)
            if not items:
                self._empty_lbl.setText(self._empty_text_for(self._active_tab))
                self._empty_lbl.show()
            else:
                self._empty_lbl.hide()
                # Insert rows in newest-first order, ABOVE the stretch.
                # The stretch is the last item; we insert at position 1
                # (after the empty label which is hidden anyway).
                insert_at = 1
                for item in items:
                    row = NotificationRow(item, self._list_host)
                    row.clicked.connect(self._on_row_clicked)
                    row.mark_read_requested.connect(self._on_row_mark_read)
                    row.delete_requested.connect(self._on_row_delete)
                    self._list_lay.insertWidget(insert_at, row)
                    insert_at += 1
            # Refresh the mark-all button visibility.
            self._mark_link.setVisible(self._store.unread_count() > 0)
        except Exception as e:
            logger.debug("populate_rows failed: %s", e)

    def _empty_text_for(self, tab: str) -> str:
        return {
            "all":      "No notifications yet",
            "unread":   "Nothing unread — you're caught up",
            "tool":     "No tool activity yet",
            "research": "No research updates yet",
            "safety":   "No safety warnings — all clear",
        }.get(tab, "No notifications yet")

    # -- store signal hookup ------------------------------------------
    def _on_store_change(self):
        self._populate_rows()

    # -- row callbacks ------------------------------------------------
    def _on_row_clicked(self, item_id: str):
        self._store.mark_read(item_id)

    def _on_row_mark_read(self, item_id: str):
        self._store.mark_read(item_id)

    def _on_row_delete(self, item_id: str):
        self._store.remove(item_id)

    def _on_mark_all(self):
        self._store.mark_all_read()

    def _on_tab_change(self, key: str):
        self._active_tab = key
        self._populate_rows()

    # -- show / hide / animate ----------------------------------------
    def is_open(self) -> bool:
        return self._open

    def show_panel(self):
        if self._open:
            return
        self._open = True
        self.show()
        self.raise_()
        self.setFocus()
        self._animate_to(open_=True)

    def hide_panel(self):
        if not self._open:
            return
        self._open = False
        self._animate_to(open_=False)

    def toggle(self):
        if self._open:
            self.hide_panel()
        else:
            self.show_panel()

    def _animate_to(self, open_: bool):
        try:
            host_w = self._host.width()
            host_h = self._host.height()
            # Account for the topbar — leave 56 px clear at the top so
            # the panel slides under the bell button cleanly.
            top_offset = 56
            target_h = max(200, host_h - top_offset)
            on_geo  = QRect(host_w - self.PANEL_WIDTH, top_offset,
                            self.PANEL_WIDTH, target_h)
            off_geo = QRect(host_w, top_offset,
                            self.PANEL_WIDTH, target_h)
            start_geo = self.geometry()
            end_geo = on_geo if open_ else off_geo
            # Stop any in-flight animation first.
            if self._slide_anim is not None:
                try: self._slide_anim.stop()
                except Exception: pass
            anim = QPropertyAnimation(self, b"geometry", self)
            anim.setDuration(self.SLIDE_MS)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setStartValue(start_geo if start_geo.width() else off_geo)
            anim.setEndValue(end_geo)
            if not open_:
                anim.finished.connect(self.hide)
            anim.start()
            self._slide_anim = anim
        except Exception as e:
            logger.debug("notif slide anim failed: %s", e)

    def sync_position(self, initial: bool = False):
        """Reposition to the right edge of the host. Call on host resize."""
        try:
            host_w = self._host.width()
            host_h = self._host.height()
            top_offset = 56
            target_h = max(200, host_h - top_offset)
            if self._open:
                self.setGeometry(host_w - self.PANEL_WIDTH, top_offset,
                                 self.PANEL_WIDTH, target_h)
            else:
                # Park off-screen to the right.
                self.setGeometry(host_w, top_offset,
                                 self.PANEL_WIDTH, target_h)
        except Exception as e:
            logger.debug("notif sync_position failed: %s", e)

    # -- focus trap helper --------------------------------------------
    def contains_global_pos(self, gp: QPoint) -> bool:
        try:
            top_left = self.mapToGlobal(QPoint(0, 0))
            r = QRect(top_left, self.size())
            return r.contains(gp)
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Event filters — host resize + click-outside-to-close.
# ---------------------------------------------------------------------------

class _HostResizeFilter(QObject):
    """Repositions the panel when the host window resizes."""

    def __init__(self, panel: NotificationCenter):
        super().__init__(panel)
        self._panel = panel

    def eventFilter(self, obj, ev):  # noqa: N802
        try:
            if ev.type() == QEvent.Type.Resize:
                self._panel.sync_position()
        except Exception:
            pass
        return False


class _ClickOutsideFilter(QObject):
    """Close the panel when the user clicks anywhere outside it."""

    def __init__(self, panel: NotificationCenter):
        super().__init__(panel)
        self._panel = panel

    def eventFilter(self, obj, ev):  # noqa: N802
        try:
            if (ev.type() == QEvent.Type.MouseButtonPress
                    and self._panel.is_open()):
                gp = QCursor.pos()
                if not self._panel.contains_global_pos(gp):
                    # Defer hide so the original click still works.
                    self._panel.hide_panel()
        except Exception:
            pass
        return False


__all__ = [
    "NotificationItem",
    "NotificationStore",
    "NotificationCenter",
    "NotificationRow",
    "make_bell_pixmap",
]
