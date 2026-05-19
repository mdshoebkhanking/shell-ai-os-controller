"""command_palette — Mac-style Spotlight / VS Code Ctrl+K palette for Shell OS.

A frameless, always-on-top, centred-on-the-main-window panel that lists
quick actions: page-switching, theme-switching, chat tools, and quick-launch
shell commands. Search-as-you-type with token-overlap fuzzy scoring; ↑/↓
navigates rows, ↵ runs, Esc closes.

Wiring:
    from shell_ui.command_palette import CommandPalette
    palette = CommandPalette(main_window, callbacks={"page.chat": cb_fn, ...})
    QShortcut(QKeySequence("Ctrl+K"), main_window, activated=palette.toggle)

Standalone:
    python -m shell_ui.command_palette
"""
from __future__ import annotations

import logging
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = logging.getLogger("shell.ui.command_palette")
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

# Project root on sys.path so siblings import cleanly when run as a module.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from PyQt6.QtCore import (
    Qt, QPoint, QSize, QEvent, QTimer, QPropertyAnimation, QEasingCurve,
)
from PyQt6.QtGui import (
    QKeyEvent, QPainter, QColor, QPen, QPainterPath, QFont, QShortcut,
    QKeySequence,
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QFrame, QScrollArea, QGraphicsDropShadowEffect,
    QMainWindow, QSizePolicy,
)

try:
    from shell_ui.design_tokens import C, S, T, R, M, SH
except Exception:  # pragma: no cover — design tokens are required.
    from design_tokens import C, S, T, R, M, SH  # type: ignore


# ===========================================================================
# Action dataclass
# ===========================================================================

@dataclass
class Action:
    """One selectable row in the palette."""
    id: str
    title: str
    subtitle: str = ""
    icon: str = ""           # single emoji glyph (cheap, no asset pipeline)
    shortcut: str = ""       # right-aligned hint, e.g. "Ctrl+L"
    category: str = ""       # "Navigate", "Theme", "Tools", …
    keywords: List[str] = field(default_factory=list)
    callable: Optional[Callable[[], None]] = None

    def haystack(self) -> str:
        """Concatenated lowercase searchable string."""
        parts = [self.title, self.subtitle, self.category, " ".join(self.keywords)]
        return " ".join(parts).lower()


# ===========================================================================
# Fuzzy scoring — token-overlap with substring + prefix bonuses
# ===========================================================================

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _score(query: str, action: Action) -> float:
    """Score `action` against `query`. Higher is better; <=0 → no match."""
    q = query.strip().lower()
    if not q:
        return 1.0  # everything matches when nothing is typed
    hay = action.haystack()
    if not hay:
        return 0.0

    qtokens = _TOKEN_RE.findall(q)
    if not qtokens:
        return 0.0

    htokens = set(_TOKEN_RE.findall(hay))
    score = 0.0

    # Token overlap — every query token must hit *something*. We allow
    # prefix matches inside any haystack token so "scr" matches "screenshot".
    for qt in qtokens:
        hit = 0.0
        if qt in htokens:
            hit = 3.0
        else:
            for ht in htokens:
                if ht.startswith(qt):
                    hit = max(hit, 2.0)
                elif qt in ht:
                    hit = max(hit, 1.2)
        if hit == 0.0:
            return 0.0  # missing token → drop the action entirely
        score += hit

    # Bonuses — title matches and prefix matches feel more relevant.
    title_l = action.title.lower()
    if q in title_l:
        score += 4.0
    if title_l.startswith(q):
        score += 3.0
    if any(title_l.startswith(t) for t in qtokens):
        score += 1.5
    # Keyword exact match nudge.
    kw_set = {k.lower() for k in action.keywords}
    if any(t in kw_set for t in qtokens):
        score += 1.0
    return score


# ===========================================================================
# ActionRow — single visual row (icon · title/subtitle · shortcut hint)
# ===========================================================================

class ActionRow(QFrame):
    """Single row in the palette list. Clickable; visually selectable."""

    ROW_HEIGHT = 46

    def __init__(self, action: Action, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.action = action
        self._selected = False
        self.setObjectName("cmdp_row")
        self.setFixedHeight(self.ROW_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(S.md, 0, S.md, 0)
        lay.setSpacing(S.md)

        self.icon_lbl = QLabel(action.icon or "•")
        self.icon_lbl.setFixedWidth(28)
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_lbl.setStyleSheet(
            f"background:transparent; border:none; color:{C.accent}; "
            f"font-size:18px;"
        )
        lay.addWidget(self.icon_lbl)

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(1)

        self.title_lbl = QLabel(action.title)
        self.title_lbl.setStyleSheet(
            f"background:transparent; border:none; color:{C.text}; "
            f"font-family:{T.family}; font-size:{T.body_size + 1}px; "
            f"font-weight:600;"
        )
        text_box.addWidget(self.title_lbl)

        if action.subtitle:
            self.sub_lbl = QLabel(action.subtitle)
            self.sub_lbl.setStyleSheet(
                f"background:transparent; border:none; color:{C.text_muted}; "
                f"font-family:{T.family}; font-size:{T.small_size}px;"
            )
            text_box.addWidget(self.sub_lbl)
        else:
            self.sub_lbl = None

        lay.addLayout(text_box, 1)

        # Right-aligned: category pill + shortcut hint.
        if action.category:
            self.cat_lbl = QLabel(action.category)
            self.cat_lbl.setStyleSheet(
                f"background:transparent; border:1px solid {C.border}; "
                f"border-radius:{R.xs}px; "
                f"color:{C.text_subtle}; "
                f"padding:2px 8px; "
                f"font-family:{T.family}; font-size:{T.small_size - 1}px; "
                f"font-weight:600;"
            )
            lay.addWidget(self.cat_lbl, 0, Qt.AlignmentFlag.AlignRight)

        if action.shortcut:
            self.sc_lbl = QLabel(action.shortcut)
            self.sc_lbl.setStyleSheet(
                f"background:{C.surface_2}; border:1px solid {C.border}; "
                f"border-radius:{R.xs}px; "
                f"color:{C.text_muted}; "
                f"padding:2px 8px; "
                f"font-family:{T.family_mono}; font-size:{T.small_size}px;"
            )
            lay.addWidget(self.sc_lbl, 0, Qt.AlignmentFlag.AlignRight)

        self._apply_style()

    def set_selected(self, on: bool):
        if self._selected == on:
            return
        self._selected = on
        self._apply_style()

    def _apply_style(self):
        if self._selected:
            self.setStyleSheet(
                f"#cmdp_row {{ "
                f"  background-color:{C.accent_soft}; "
                f"  border:1px solid {C.accent}; "
                f"  border-radius:{R.md}px; "
                f"}}"
            )
        else:
            self.setStyleSheet(
                f"#cmdp_row {{ "
                f"  background-color:transparent; "
                f"  border:1px solid transparent; "
                f"  border-radius:{R.md}px; "
                f"}} "
                f"#cmdp_row:hover {{ "
                f"  background-color:{C.surface_2}; "
                f"}}"
            )

    def mousePressEvent(self, ev):  # noqa: N802
        if ev.button() == Qt.MouseButton.LeftButton:
            # Bubble up to the palette so it can run + close.
            p = self.parent()
            while p is not None and not isinstance(p, CommandPalette):
                p = p.parent()
            if isinstance(p, CommandPalette):
                p.run_action(self.action)
            ev.accept()
            return
        super().mousePressEvent(ev)


# ===========================================================================
# CommandPalette — the panel itself
# ===========================================================================

class CommandPalette(QWidget):
    """Centred, frameless, always-on-top palette. Spotlight-style.

    `callbacks` is an optional dict mapping action-id → zero-arg callable.
    Any registered callback overrides the built-in default (so the host UI
    can wire `page.chat` to its own page-switcher, etc.). Action ids the
    host doesn't supply fall back to a logger-warn no-op.
    """

    PALETTE_W = 640
    PALETTE_H = 440

    def __init__(self, parent: Optional[QWidget] = None,
                 callbacks: Optional[Dict[str, Callable[[], None]]] = None):
        # We deliberately keep `parent` so the palette inherits the main
        # window's QWindow ancestry (helps with focus restoration on hide)
        # but use FramelessWindowHint + Tool to render as its own top-level.
        super().__init__(parent)
        self._host = parent
        self._callbacks = dict(callbacks or {})
        self._actions: List[Action] = []
        self._rows: List[ActionRow] = []
        self._filtered: List[Action] = []
        self._selected_idx = 0

        self._build_ui()
        self._register_builtin_actions()
        self._refilter("")
        self.hide()

    # ----- UI -----
    def _build_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(QSize(self.PALETTE_W, self.PALETTE_H))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(S.lg, S.lg, S.lg, S.lg)
        outer.setSpacing(0)

        # Card body — Mac-vibrancy "light" overlay (popover strength).
        # NOTE: CommandPalette is a top-level OS window so we can't apply
        # GlassBackdrop here (parent.grab() can't reach across OS windows
        # without DWM/NSVisualEffectView). The vibrancy gradient + heavy
        # floating shadow keep it on-brand with the rest of the new look.
        self.card = QFrame(self)
        self.card.setObjectName("cmdp_card")
        try:
            from shell_ui.design_tokens import vibrancy_layer_qss as _vib
            self.card.setStyleSheet(f"#cmdp_card {{ {_vib('light', radius=R.xl)} }}")
        except Exception:
            self.card.setStyleSheet(
                f"#cmdp_card {{ "
                f"  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                f"    stop:0 {C.glass_hi}, "
                f"    stop:0.04 {C.glass_strong}, "
                f"    stop:1 {C.glass_strong}); "
                f"  border:1px solid {C.glass_border}; "
                f"  border-top:1px solid {C.glass_hi}; "
                f"  border-radius:{R.xl}px; "
                f"}}"
            )
        # Floating shadow underneath the card.
        try:
            eff = QGraphicsDropShadowEffect(self.card)
            eff.setBlurRadius(SH.floating.blur)
            eff.setOffset(0, SH.floating.offset_y)
            eff.setColor(QColor(0, 0, 0, 180))
            self.card.setGraphicsEffect(eff)
        except Exception as _e:
            logger.debug("shadow effect failed: %s", _e)
        outer.addWidget(self.card)

        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(S.lg, S.lg, S.lg, S.md)
        cl.setSpacing(S.md)

        # ----- Search row -----
        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(S.md)

        self.search_icon = QLabel("\U0001F50D")  # magnifying glass
        self.search_icon.setStyleSheet(
            f"background:transparent; border:none; color:{C.text_muted}; "
            f"font-size:18px;"
        )
        self.search_icon.setFixedWidth(24)
        self.search_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        search_row.addWidget(self.search_icon)

        self.search = QLineEdit(self.card)
        self.search.setPlaceholderText("Type to search…")
        self.search.setFixedHeight(40)
        self.search.setStyleSheet(
            f"QLineEdit {{ "
            f"  background:transparent; "
            f"  color:{C.text}; "
            f"  border:none; "
            f"  font-family:{T.family}; font-size:17px; font-weight:500; "
            f"  selection-background-color:{C.accent_soft}; "
            f"  selection-color:{C.text}; "
            f"}}"
        )
        self.search.installEventFilter(self)
        self.search.textChanged.connect(self._refilter)
        self.search.returnPressed.connect(self._run_selected)
        search_row.addWidget(self.search, 1)

        cl.addLayout(search_row)

        # Hairline divider
        sep = QFrame(self.card)
        sep.setFixedHeight(1)
        sep.setStyleSheet(
            f"background-color:{C.border}; border:none;"
        )
        cl.addWidget(sep)

        # ----- Scrollable list -----
        self.scroll = QScrollArea(self.card)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setStyleSheet(
            f"QScrollArea {{ background:transparent; border:none; }}"
            f"QScrollBar:vertical {{ "
            f"  background:transparent; width:8px; margin:2px; "
            f"}}"
            f"QScrollBar::handle:vertical {{ "
            f"  background:{C.border_strong}; border-radius:4px; min-height:20px; "
            f"}}"
            f"QScrollBar::handle:vertical:hover {{ background:{C.accent}; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ "
            f"  height:0; background:transparent; "
            f"}}"
        )
        self.list_host = QWidget()
        self.list_host.setStyleSheet("background:transparent;")
        self.list_lay = QVBoxLayout(self.list_host)
        self.list_lay.setContentsMargins(0, 0, 0, 0)
        self.list_lay.setSpacing(2)
        self.list_lay.addStretch(1)
        self.scroll.setWidget(self.list_host)
        cl.addWidget(self.scroll, 1)

        # ----- Footer -----
        self.footer = QLabel(
            "↑↓  navigate   ·   ↵  run   ·   esc  close"
        )
        self.footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer.setStyleSheet(
            f"background:transparent; border:none; color:{C.text_subtle}; "
            f"font-family:{T.family}; font-size:{T.small_size}px;"
        )
        cl.addWidget(self.footer)

    # ----- Action registration -----
    def register_action(self, action: Action):
        """Append a single action. Callable falls back to callbacks[id]."""
        if action.callable is None:
            action.callable = self._callbacks.get(action.id) or self._noop_for(action)
        self._actions.append(action)

    def register_actions(self, actions: List[Action]):
        for a in actions:
            self.register_action(a)

    def _noop_for(self, action: Action):
        aid = action.id
        def _runner():
            logger.warning("CommandPalette: no callback bound for action '%s' "
                           "(host UI did not register a handler).", aid)
        return _runner

    def _register_builtin_actions(self):
        """Populate the starter set so the palette is useful out-of-the-box."""
        starter = [
            # ---- Navigate (6) ----
            Action(id="page.chat", title="Go to Chat",
                   subtitle="Switch to the chat / conversation page",
                   icon="\U0001F4AC", shortcut="Ctrl+1", category="Navigate",
                   keywords=["chat", "conversation", "page", "go"]),
            Action(id="page.voice", title="Go to Voice",
                   subtitle="Switch to the voice / mic page",
                   icon="\U0001F3A4", shortcut="Ctrl+2", category="Navigate",
                   keywords=["voice", "mic", "speak", "page"]),
            Action(id="page.system", title="Go to System",
                   subtitle="Switch to the system dashboard",
                   icon="\U0001F4CA", shortcut="Ctrl+3", category="Navigate",
                   keywords=["system", "stats", "dashboard", "cpu", "ram"]),
            Action(id="page.agents", title="Go to Agents",
                   subtitle="Switch to agent orchestration",
                   icon="\U0001F9E0", shortcut="Ctrl+4", category="Navigate",
                   keywords=["agents", "orchestration", "planner", "memory", "workflow"]),
            Action(id="page.tools", title="Go to Tools",
                   subtitle="Switch to backend tools and MCP actions",
                   icon="\U0001F6E0", shortcut="Ctrl+5", category="Navigate",
                   keywords=["tools", "mcp", "backend", "actions", "features"]),
            Action(id="page.settings", title="Go to Settings",
                   subtitle="Switch to the settings page",
                   icon="⚙️", shortcut="Ctrl+6", category="Navigate",
                   keywords=["settings", "config", "prefs"]),

            # ---- Theme (4) ----
            Action(id="theme.dark", title="Theme: Dark",
                   subtitle="Apply the warm dark theme",
                   icon="\U0001F311", category="Theme",
                   keywords=["theme", "dark", "night"]),
            Action(id="theme.light", title="Theme: Light",
                   subtitle="Apply the warm light theme",
                   icon="☀️", category="Theme",
                   keywords=["theme", "light", "day"]),
            Action(id="theme.cyber", title="Theme: Cyber Neon",
                   subtitle="Cyan/violet cyberpunk look",
                   icon="⚡", category="Theme",
                   keywords=["theme", "cyber", "neon", "cyan"]),
            Action(id="theme.midnight", title="Theme: Midnight Purple",
                   subtitle="Deep violet ambient theme",
                   icon="\U0001F319", category="Theme",
                   keywords=["theme", "midnight", "purple", "violet"]),

            # ---- Chat / voice ----
            Action(id="chat.new", title="New Chat",
                   subtitle="Clear conversation and start a fresh session",
                   icon="\U0001F4DD", shortcut="Ctrl+N", category="Chat",
                   keywords=["new", "chat", "session", "fresh", "start"]),
            Action(id="chat.clear", title="Clear Chat",
                   subtitle="Remove all messages from the current chat",
                   icon="\U0001F9F9", category="Chat",
                   keywords=["clear", "chat", "wipe", "reset"]),
            Action(id="voice.toggle_output", title="Toggle Voice Output",
                   subtitle="Enable / disable Shell's text-to-speech replies",
                   icon="\U0001F50A", category="Voice",
                   keywords=["voice", "tts", "speak", "mute", "audio"]),

            # ---- Quick-launch shell tools ----
            Action(id="tool.screenshot", title="Take a Screenshot",
                   subtitle="Capture the screen via Shell's screenshot tool",
                   icon="\U0001F4F8", category="Tools",
                   keywords=["screenshot", "capture", "screen", "image"]),
            Action(id="tool.system_stats", title="Show System Stats",
                   subtitle="Display CPU, RAM, disk and network usage",
                   icon="\U0001F4C8", category="Tools",
                   keywords=["system", "stats", "cpu", "ram", "disk"]),
            Action(id="tool.youtube", title="Play YouTube Song",
                   subtitle="Ask Shell to play a song on YouTube",
                   icon="\U0001F3B5", category="Tools",
                   keywords=["youtube", "song", "music", "play"]),
            Action(id="tool.weather", title="What's the Weather",
                   subtitle="Get the current weather for your location",
                   icon="\U0001F324️", category="Tools",
                   keywords=["weather", "forecast", "temp", "rain"]),
            Action(id="tool.notepad", title="Open Notepad",
                   subtitle="Launch Notepad on the desktop",
                   icon="\U0001F5D2️", category="Tools",
                   keywords=["notepad", "open", "app", "launch"]),

            # ---- Settings deep-links ----
            Action(id="settings.reply_language", title="Open Settings: Reply Language",
                   subtitle="Jump to the reply-language preference",
                   icon="\U0001F310", category="Settings",
                   keywords=["settings", "language", "reply", "locale"]),
            Action(id="settings.api_keys", title="Open Settings: API Keys",
                   subtitle="Manage provider API keys",
                   icon="\U0001F511", category="Settings",
                   keywords=["settings", "api", "keys", "providers"]),

            # ---- Quick launcher toggle ----
            Action(id="ql.toggle", title="Toggle Quick-Launcher",
                   subtitle="Show / hide the Ctrl+Alt+S system-wide popup",
                   icon="✨", shortcut="Ctrl+Alt+S", category="Tools",
                   keywords=["quick", "launcher", "popup", "spotlight", "global"]),
        ]
        self.register_actions(starter)

    # ----- Filtering / rendering -----
    def _refilter(self, text: str = ""):
        q = text or ""
        scored = []
        for a in self._actions:
            s = _score(q, a)
            if s > 0:
                scored.append((s, a))
        scored.sort(key=lambda p: (-p[0], p[1].title.lower()))
        self._filtered = [a for _, a in scored]
        self._selected_idx = 0
        self._rebuild_rows()

    def _rebuild_rows(self):
        # Drop existing rows.
        for r in self._rows:
            r.setParent(None)
            r.deleteLater()
        self._rows.clear()

        # Remove the trailing stretch so we can re-append it after rows.
        for i in reversed(range(self.list_lay.count())):
            item = self.list_lay.itemAt(i)
            if item is not None and item.spacerItem() is not None:
                self.list_lay.takeAt(i)

        if not self._filtered:
            empty = QLabel("No matching actions")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"background:transparent; border:none; color:{C.text_subtle}; "
                f"padding:24px; font-family:{T.family}; "
                f"font-size:{T.body_size}px; font-style:italic;"
            )
            self.list_lay.addWidget(empty)
            self._rows.append(empty)  # so cleanup catches it next refilter
            self.list_lay.addStretch(1)
            return

        for a in self._filtered:
            row = ActionRow(a, self.list_host)
            self.list_lay.addWidget(row)
            self._rows.append(row)
        self.list_lay.addStretch(1)
        self._refresh_selection()

    def _refresh_selection(self):
        for i, r in enumerate(self._rows):
            if isinstance(r, ActionRow):
                r.set_selected(i == self._selected_idx)
        # Scroll the selected row into view.
        if 0 <= self._selected_idx < len(self._rows):
            target = self._rows[self._selected_idx]
            try:
                self.scroll.ensureWidgetVisible(target, 0, 12)
            except Exception as _e:
                logger.debug("ensureWidgetVisible failed: %s", _e)

    def _move_selection(self, delta: int):
        n = len(self._filtered)
        if n == 0:
            return
        self._selected_idx = (self._selected_idx + delta) % n
        self._refresh_selection()

    # ----- Run / show / hide -----
    def _run_selected(self):
        if 0 <= self._selected_idx < len(self._filtered):
            self.run_action(self._filtered[self._selected_idx])

    def run_action(self, action: Action):
        logger.info("CommandPalette: run action '%s'", action.id)
        self.dismiss()
        cb = action.callable
        if cb is None:
            logger.warning("Action '%s' has no callable", action.id)
            return
        try:
            cb()
        except Exception:
            import traceback
            logger.warning("Action '%s' raised:\n%s", action.id,
                           traceback.format_exc())

    def show_palette(self):
        self.search.clear()
        self._refilter("")
        self._position_centre()
        self.show()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(40, self._focus_search)
        # Soft fade-in for that Spotlight-y feel.
        try:
            self.setWindowOpacity(0.0)
            anim = QPropertyAnimation(self, b"windowOpacity", self)
            anim.setDuration(M.fast_ms)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(getattr(QEasingCurve.Type, M.ease_out_cubic))
            anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        except Exception as _e:
            logger.debug("show fade failed: %s", _e)
            self.setWindowOpacity(1.0)

    def dismiss(self):
        try:
            self.hide()
            # Restore focus to host if possible so the user lands back where
            # they were instead of the desktop.
            if self._host is not None:
                try:
                    self._host.activateWindow()
                except Exception as _e:
                    logger.debug("host activate failed: %s", _e)
        except Exception as _e:
            logger.debug("dismiss failed: %s", _e)

    def toggle(self):
        if self.isVisible():
            self.dismiss()
        else:
            self.show_palette()

    def _focus_search(self):
        try:
            self.search.setFocus(Qt.FocusReason.OtherFocusReason)
            self.search.selectAll()
        except Exception as _e:
            logger.debug("focus_search failed: %s", _e)

    def _position_centre(self):
        """Centre on the main window if we have one, otherwise on the screen."""
        host = self._host
        target_geo = None
        if isinstance(host, QWidget):
            try:
                target_geo = host.frameGeometry()
            except Exception as _e:
                logger.debug("host geometry failed: %s", _e)
        if target_geo is None:
            app = QApplication.instance()
            scr = app.primaryScreen() if app else None
            if scr is not None:
                target_geo = scr.availableGeometry()
        if target_geo is None:
            return
        x = target_geo.x() + (target_geo.width() - self.PALETTE_W) // 2
        # Slight upward bias — Spotlight sits ~1/3 down, not centred.
        y = target_geo.y() + (target_geo.height() - self.PALETTE_H) // 2 - 60
        y = max(target_geo.y() + 20, y)
        self.move(QPoint(x, y))

    # ----- Event handling -----
    def eventFilter(self, obj, ev):  # noqa: N802
        # Capture arrow / enter / esc on the search box so navigation works
        # while the search field has keyboard focus.
        if obj is self.search and ev.type() == QEvent.Type.KeyPress:
            ke: QKeyEvent = ev  # type: ignore
            k = ke.key()
            if k == Qt.Key.Key_Down:
                self._move_selection(+1)
                return True
            if k == Qt.Key.Key_Up:
                self._move_selection(-1)
                return True
            if k == Qt.Key.Key_PageDown:
                self._move_selection(+5)
                return True
            if k == Qt.Key.Key_PageUp:
                self._move_selection(-5)
                return True
            if k == Qt.Key.Key_Escape:
                self.dismiss()
                return True
            # Enter falls through to returnPressed → _run_selected.
        return super().eventFilter(obj, ev)

    def keyPressEvent(self, ev: QKeyEvent):  # noqa: N802
        k = ev.key()
        if k == Qt.Key.Key_Escape:
            self.dismiss()
            return
        if k == Qt.Key.Key_Down:
            self._move_selection(+1); return
        if k == Qt.Key.Key_Up:
            self._move_selection(-1); return
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._run_selected(); return
        super().keyPressEvent(ev)


# ===========================================================================
# Standalone test harness
# ===========================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    app = QApplication(sys.argv)

    # Dummy host window so the palette has something to centre on.
    host = QMainWindow()
    host.setWindowTitle("Command Palette test host")
    host.resize(1000, 600)
    label = QLabel("Press Ctrl+K to open the Command Palette\n(Esc to close)")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(
        f"background:{C.bg}; color:{C.text}; "
        f"font-family:{T.family}; font-size:{T.h2_size}px;"
    )
    host.setCentralWidget(label)
    host.show()

    # Dummy callbacks so action invocations show in the log.
    def _make_cb(name):
        def _cb():
            print(f"[host] action invoked: {name}")
        return _cb
    cbs = {
        "page.chat":     _make_cb("switch to chat page"),
        "page.voice":    _make_cb("switch to voice page"),
        "page.system":   _make_cb("switch to system page"),
        "page.agents":   _make_cb("switch to agents page"),
        "page.tools":    _make_cb("switch to tools page"),
        "page.settings": _make_cb("switch to settings page"),
        "theme.dark":    _make_cb("theme DARK"),
        "theme.light":   _make_cb("theme LIGHT"),
        "theme.cyber":   _make_cb("theme CYBER_NEON"),
        "theme.midnight": _make_cb("theme MIDNIGHT_PURPLE"),
    }
    palette = CommandPalette(host, callbacks=cbs)

    sc = QShortcut(QKeySequence("Ctrl+K"), host)
    sc.activated.connect(palette.toggle)

    # Auto-open after a tick so manual testers see it immediately.
    QTimer.singleShot(400, palette.show_palette)

    sys.exit(app.exec())
