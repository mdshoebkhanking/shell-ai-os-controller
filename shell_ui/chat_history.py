"""chat_history — persistence + sidebar UI for past conversations.

Stores every chat session as JSON under `~/.shell_chat_history/sessions.json`
and renders a ChatGPT / Claude-style left-rail list of sessions sorted by
recent activity. Token-driven so a theme switch flows through automatically.

Public API:
    ChatSession           — dataclass for a single conversation.
    ChatHistoryStore      — load / save / delete sessions on disk.
    ChatHistoryList(QFrame) — scrollable widget; emits `session_clicked(id)`.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QSize
from PyQt6.QtGui import QCursor, QAction
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QWidget,
    QSizePolicy, QMenu, QInputDialog, QPushButton,
)

logger = logging.getLogger("shell_ui.chat_history")


# ---------------------------------------------------------------------------
# Token import — design system. Falls back to safe defaults so the module
# is importable in test contexts where design_tokens isn't on the path.
# ---------------------------------------------------------------------------
try:
    from shell_ui.design_tokens import C as _DT_C, T as _DT_T, S as _DT_S, R as _DT_R
    def _tk():
        return _DT_C, _DT_T, _DT_S, _DT_R
except Exception:
    class _Fallback:
        bg = "#0d1322"; surface = "#0d1322"; surface_2 = "#141d33"
        surface_3 = "#1c2944"
        border = "rgba(143,245,255,0.10)"
        border_strong = "rgba(143,245,255,0.20)"
        text = "#e8f4ff"; text_muted = "#8fa3bd"; text_subtle = "#5a6d87"
        accent = "#00f0ff"; accent_hover = "#5cf6ff"
        accent_soft = "rgba(0,240,255,0.12)"
    class _FT:
        family = "Segoe UI, system-ui, sans-serif"
        body_size = 14; small_size = 12
    class _FS:
        xs = 4; sm = 8; md = 12; lg = 16
    class _FR:
        sm = 8; md = 12; lg = 16
    def _tk():
        return _Fallback(), _FT(), _FS(), _FR()


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ChatSession:
    """A single conversation. `messages` is a list of `{role, text, ts}`."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    title: str = "New chat"
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    messages: List[Dict[str, str]] = field(default_factory=list)

    def add_message(self, role: str, text: str) -> None:
        self.messages.append({
            "role": str(role),
            "text": str(text),
            "ts": _now_iso(),
        })
        self.updated_at = _now_iso()

    def auto_title_from_first_user(self) -> None:
        """If the title is still the default, derive one from first user msg
        (first 6 words, max 50 chars)."""
        if (self.title or "").strip() and self.title != "New chat":
            return
        for m in self.messages:
            if m.get("role") == "user":
                txt = (m.get("text") or "").strip()
                if not txt:
                    continue
                words = txt.split()
                snippet = " ".join(words[:6])
                if len(snippet) > 50:
                    snippet = snippet[:47].rstrip() + "..."
                self.title = snippet or "New chat"
                return

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ChatSession":
        return cls(
            id=str(d.get("id") or uuid.uuid4().hex),
            title=str(d.get("title") or "New chat"),
            created_at=str(d.get("created_at") or _now_iso()),
            updated_at=str(d.get("updated_at") or _now_iso()),
            messages=list(d.get("messages") or []),
        )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class ChatHistoryStore:
    """Persists sessions as a single JSON file on disk.

    File: `~/.shell_chat_history/sessions.json`
    Schema: {"current_id": str|None, "sessions": [ChatSession.to_dict(), ...]}
    """

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root: Path = self._resolve_root(root)
        self.path: Path = self.root / "sessions.json"
        self._sessions: Dict[str, ChatSession] = {}
        self._current_id: Optional[str] = None
        self._load_from_disk()

    @staticmethod
    def _resolve_root(root: Optional[Path]) -> Path:
        candidates = []
        if root is not None:
            candidates.append(Path(root))
        env_root = os.environ.get("SHELL_CHAT_HISTORY_DIR", "").strip()
        if env_root:
            candidates.append(Path(env_root).expanduser())
        candidates.append(Path.home() / ".shell_chat_history")
        project_root = Path(__file__).resolve().parent.parent
        candidates.append(project_root / ".shell_chat_history")
        candidates.append(Path(os.environ.get("TMPDIR", "/tmp")) / "shell_chat_history")

        for candidate in candidates:
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                probe = candidate / ".write_test"
                probe.write_text("ok", encoding="utf-8")
                try:
                    probe.unlink()
                except Exception:
                    pass
                return candidate
            except Exception as e:
                logger.warning("could not use chat history dir %s: %s", candidate, e)

        fallback = Path(os.environ.get("TMPDIR", "/tmp"))
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

    # ---- Disk IO ----
    def _load_from_disk(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = self.path.read_text(encoding="utf-8")
            if not raw.strip():
                return
            data = json.loads(raw)
            for sd in (data.get("sessions") or []):
                try:
                    s = ChatSession.from_dict(sd)
                    self._sessions[s.id] = s
                except Exception as e:
                    logger.debug("skipping bad session row: %s", e)
            cid = data.get("current_id")
            if cid and cid in self._sessions:
                self._current_id = cid
        except Exception as e:
            # Corrupted file — start fresh, but back the bad file up so the
            # user can inspect it later instead of silently losing it.
            logger.warning("chat history JSON corrupted (%s); starting fresh", e)
            try:
                bak = self.path.with_suffix(".json.bak")
                self.path.replace(bak)
            except Exception:
                pass
            self._sessions = {}
            self._current_id = None

    def flush(self) -> None:
        """Write all sessions to disk. Atomic via tmp + replace."""
        try:
            data = {
                "current_id": self._current_id,
                "sessions": [s.to_dict() for s in self._sessions.values()],
            }
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.path)
        except Exception as e:
            logger.warning("chat history flush failed: %s", e)

    # ---- API ----
    def list_sessions(self) -> List[ChatSession]:
        """All sessions sorted by `updated_at` desc (most recent first)."""
        return sorted(self._sessions.values(), key=lambda s: s.updated_at, reverse=True)

    def load(self, session_id: str) -> Optional[ChatSession]:
        return self._sessions.get(session_id)

    def save(self, session: ChatSession) -> None:
        self._sessions[session.id] = session
        # Don't flush here — debounced by the UI layer's QTimer.

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        if self._current_id == session_id:
            self._current_id = None

    def new_session(self) -> ChatSession:
        s = ChatSession()
        self._sessions[s.id] = s
        self._current_id = s.id
        return s

    def current_session(self) -> ChatSession:
        """Return the active session (last touched, or fresh one if none)."""
        if self._current_id and self._current_id in self._sessions:
            return self._sessions[self._current_id]
        sessions = self.list_sessions()
        if sessions:
            self._current_id = sessions[0].id
            return sessions[0]
        return self.new_session()

    def set_current(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._current_id = session_id

    def rename(self, session_id: str, new_title: str) -> None:
        s = self._sessions.get(session_id)
        if s is None:
            return
        new_title = (new_title or "").strip() or "Untitled"
        if len(new_title) > 80:
            new_title = new_title[:80]
        s.title = new_title
        s.updated_at = _now_iso()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _relative_time(iso_str: str) -> str:
    """'2m ago' / '3h ago' / 'yesterday' / 'Apr 12' style relative label."""
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return "just now"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        if secs < 86400 * 2:
            return "yesterday"
        if secs < 86400 * 7:
            return f"{secs // 86400}d ago"
        return dt.strftime("%b %d")
    except Exception:
        return ""


def _truncate(text: str, n: int = 26) -> str:
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= n:
        return text
    return text[: max(1, n - 1)].rstrip() + "…"


# ---------------------------------------------------------------------------
# Row widget — one session
# ---------------------------------------------------------------------------

class _SessionRow(QFrame):
    """Single row in the history list. Click → emit on parent list.
    Right-click → context menu (Rename / Delete)."""

    def __init__(self, session: ChatSession, active: bool, parent_list: "ChatHistoryList"):
        super().__init__(parent_list)
        self.session = session
        self._active = active
        self._parent_list = parent_list
        self._hover = False
        self.setObjectName("SessionRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(48)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._open_context_menu)

        C, T, S, R = _tk()

        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 4, 10, 4)
        outer.setSpacing(8)

        # Inner column (title + relative time).
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)

        self._title_lbl = QLabel(_truncate(session.title or "Untitled", 26))
        self._title_lbl.setStyleSheet(
            f"color:{C.text}; font-family:'{T.family}'; font-size:{T.body_size - 1}px; "
            f"font-weight:600; background:transparent; border:none;"
        )
        col.addWidget(self._title_lbl)

        self._time_lbl = QLabel(_relative_time(session.updated_at))
        self._time_lbl.setStyleSheet(
            f"color:{C.text_subtle}; font-family:'{T.family}'; font-size:{T.small_size - 1}px; "
            f"background:transparent; border:none;"
        )
        col.addWidget(self._time_lbl)

        outer.addLayout(col, 1)
        self._restyle()

    def _restyle(self):
        C, T, S, R = _tk()
        if self._active:
            self.setStyleSheet(
                f"#SessionRow {{ background-color:{C.surface_2}; "
                f"border:none; border-left:3px solid {C.accent}; "
                f"border-radius:{R.sm}px; }}"
            )
        elif self._hover:
            self.setStyleSheet(
                f"#SessionRow {{ background-color:{C.accent_soft}; "
                f"border:none; border-left:3px solid transparent; "
                f"border-radius:{R.sm}px; }}"
            )
        else:
            self.setStyleSheet(
                f"#SessionRow {{ background-color:transparent; "
                f"border:none; border-left:3px solid transparent; "
                f"border-radius:{R.sm}px; }}"
            )

    def set_active(self, active: bool):
        self._active = active
        self._restyle()

    def enterEvent(self, e):
        self._hover = True
        self._restyle()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self._restyle()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            try:
                self._parent_list.session_clicked.emit(self.session.id)
            except Exception:
                pass
        super().mousePressEvent(e)

    def _open_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        C, T, S, R = _tk()
        menu.setStyleSheet(
            f"QMenu {{ background-color:{C.surface_3}; color:{C.text}; "
            f"  border:1px solid {C.border_strong}; border-radius:{R.sm}px; "
            f"  padding:4px; font-family:'{T.family}'; font-size:{T.small_size}px; }} "
            f"QMenu::item {{ padding:6px 14px; border-radius:{R.sm - 2}px; }} "
            f"QMenu::item:selected {{ background-color:{C.accent_soft}; color:{C.text}; }}"
        )
        rename_act = QAction("Rename", self)
        delete_act = QAction("Delete", self)
        menu.addAction(rename_act)
        menu.addAction(delete_act)
        rename_act.triggered.connect(self._on_rename)
        delete_act.triggered.connect(self._on_delete)
        menu.exec(self.mapToGlobal(pos))

    def _on_rename(self):
        try:
            new, ok = QInputDialog.getText(
                self, "Rename chat", "New title:", text=self.session.title
            )
            if ok and new.strip():
                self._parent_list.rename_requested.emit(self.session.id, new.strip())
        except Exception as e:
            logger.debug("rename failed: %s", e)

    def _on_delete(self):
        try:
            self._parent_list.delete_requested.emit(self.session.id)
        except Exception as e:
            logger.debug("delete failed: %s", e)


# ---------------------------------------------------------------------------
# List widget
# ---------------------------------------------------------------------------

class ChatHistoryList(QFrame):
    """Token-driven scrollable list of chat sessions.

    Signals:
        session_clicked(str) — user left-clicked a row (id).
        rename_requested(str, str) — id, new_title.
        delete_requested(str) — id.
    """

    session_clicked = pyqtSignal(str)
    rename_requested = pyqtSignal(str, str)
    delete_requested = pyqtSignal(str)

    def __init__(self, store: ChatHistoryStore, parent=None):
        super().__init__(parent)
        self.store = store
        self.setObjectName("ChatHistoryList")
        self.setStyleSheet(
            "#ChatHistoryList { background:transparent; border:none; }"
        )

        C, T, S, R = _tk()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        # Section header.
        header = QLabel("CHATS")
        header.setStyleSheet(
            f"color:{C.text_subtle}; font-family:'{T.family}'; "
            f"font-size:{T.small_size - 2}px; font-weight:700; "
            f"letter-spacing:2px; padding:4px 12px 2px 12px; "
            f"background:transparent; border:none;"
        )
        outer.addWidget(header)

        # Scroll area for the rows.
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(
            "QScrollArea { background:transparent; border:none; }"
            "QScrollBar:vertical { width:3px; background:transparent; margin:4px 0; }"
            f"QScrollBar::handle:vertical {{ background:{C.border_strong}; "
            f"  border-radius:1px; min-height:30px; }}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background:transparent; }"
        )

        self._inner = QWidget()
        self._inner.setStyleSheet("background:transparent; border:none;")
        self._inner_lay = QVBoxLayout(self._inner)
        self._inner_lay.setContentsMargins(2, 2, 2, 2)
        self._inner_lay.setSpacing(2)
        self._inner_lay.addStretch(1)
        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll, 1)

        self._rows: List[_SessionRow] = []
        self._empty_lbl: Optional[QLabel] = None
        self.refresh()

    # ---- Public API ----
    def refresh(self) -> None:
        """Clear and re-render every row from the store."""
        # Clear existing rows.
        for r in self._rows:
            r.setParent(None)
            r.deleteLater()
        self._rows.clear()
        if self._empty_lbl is not None:
            self._empty_lbl.setParent(None)
            self._empty_lbl.deleteLater()
            self._empty_lbl = None

        # Drop the trailing stretch and rebuild it after rows.
        while self._inner_lay.count():
            it = self._inner_lay.takeAt(0)
            if it.widget():
                it.widget().setParent(None)

        sessions = self.store.list_sessions()
        # Read the current id WITHOUT auto-creating a new session — that
        # would inflate the list and double-render rows.
        current_id = self.store._current_id  # type: ignore[attr-defined]

        if not sessions:
            C, T, S, R = _tk()
            self._empty_lbl = QLabel("No conversations yet")
            self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._empty_lbl.setStyleSheet(
                f"color:{C.text_subtle}; font-family:'{T.family}'; "
                f"font-size:{T.small_size}px; font-style:italic; "
                f"padding:18px 8px; background:transparent; border:none;"
            )
            self._inner_lay.addWidget(self._empty_lbl)
        else:
            for s in sessions:
                row = _SessionRow(s, active=(s.id == current_id), parent_list=self)
                self._rows.append(row)
                self._inner_lay.addWidget(row)

        self._inner_lay.addStretch(1)

    def set_active(self, session_id: str) -> None:
        """Highlight the row matching `session_id`."""
        for r in self._rows:
            r.set_active(r.session.id == session_id)
