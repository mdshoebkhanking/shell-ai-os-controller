"""shell_quick_launcher — system-wide Ctrl+Alt+S popup for Shell AI.

Frameless dark-blue popup that floats over any app on Windows when the
user presses Ctrl+Alt+S. Type a prompt + Enter, ships via Socket.IO to
the running hub, shows the reply in a status line. Esc closes.

Standalone:
    python -m shell_ui.shell_quick_launcher

From the main UI:
    self._ql_popup = QuickLauncher()
    self._ql_hotkey = GlobalHotkey(self._ql_popup)
    self._ql_hotkey.start()
"""
from __future__ import annotations

import logging
import os
import sys
import threading
from typing import Optional

logger = logging.getLogger("shell.ui.quick_launcher")
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

# Project root on sys.path so siblings import cleanly.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from PyQt6.QtCore import (
    Qt, QObject, QTimer, QPoint, pyqtSignal, pyqtSlot, QSize,
    QMetaObject, Q_ARG,
)
from PyQt6.QtGui import QCursor, QKeyEvent, QColor
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QGraphicsDropShadowEffect,
)

try:
    import socketio  # type: ignore
except Exception as _e:
    socketio = None
    logger.warning("python-socketio not available: %s", _e)

try:
    from shell_ui.design_tokens import T, text_for_fill
except Exception:
    class _FallbackType:
        family = "Arial"

    T = _FallbackType()

    def text_for_fill(_fill: str, *, dark: str = "#041018", light: str = "#ffffff") -> str:
        return light


# ===========================================================================
# Dark-blue palette (deliberate, fixed — does NOT theme-switch)
# ===========================================================================
DB_BG          = "#0a1428"   # deep navy popup body
DB_BG_INNER    = "#0f1d36"   # input fill
DB_BORDER      = "#1e3a5f"   # outer hairline
DB_BORDER_HI   = "#2a4f7f"   # focused / hovered hairline
DB_TEXT        = "#e8f0ff"   # main text
DB_TEXT_DIM    = "#8aa3c4"   # placeholder, muted
DB_TEXT_SUBTLE = "#5d7596"   # hints, status
DB_ACCENT      = "#3b8eea"   # CTA blue
DB_ACCENT_HOV  = "#4d9ff6"
DB_ACCENT_SOFT = "rgba(59,142,234,0.15)"
DB_SUCCESS     = "#3ee3a8"
DB_ERROR       = "#ff6b6b"
DB_ACCENT_TEXT = text_for_fill(DB_ACCENT)
DB_ERROR_TEXT  = text_for_fill(DB_ERROR)

POPUP_W = 620
POPUP_H = 200


def _hub_socket_auth():
    token = (os.environ.get("SHELL_HUB_TOKEN") or os.environ.get("SHELL_API_TOKEN") or "").strip()
    return {"token": token} if token else None


# ===========================================================================
# Global hotkey listener (Ctrl+Alt+S)
# ===========================================================================

class GlobalHotkey(QObject):
    """Marshals a system-wide Ctrl+Alt+S press to a Qt signal so the
    receiver activates on the GUI thread.

    Backend preference: `keyboard` on Windows/Linux, `pynput` first on
    macOS because the keyboard package requires administrator privileges.
    """

    triggered = pyqtSignal()

    def __init__(self, target_widget):
        super().__init__()
        self._target = target_widget
        self._backend: Optional[str] = None
        self._listener = None
        self._running = False
        # When the hotkey fires it MUST end up on the GUI thread.
        self.triggered.connect(self._on_trigger, Qt.ConnectionType.QueuedConnection)

    def _on_trigger(self):
        try:
            self._target.activate_from_hotkey()
        except Exception:
            import traceback
            logger.warning("hotkey trigger handler failed:\n%s",
                           traceback.format_exc())

    def start(self) -> bool:
        if self._running:
            return True
        if sys.platform == "darwin" and self._try_pynput():
            self._backend = "pynput"; self._running = True
            logger.info("GlobalHotkey: pynput backend live")
            return True
        if self._try_keyboard():
            self._backend = "keyboard"; self._running = True
            logger.info("GlobalHotkey: keyboard backend live")
            return True
        if self._try_pynput():
            self._backend = "pynput"; self._running = True
            logger.info("GlobalHotkey: pynput backend live")
            return True
        logger.warning("GlobalHotkey: no backend (install pynput or keyboard).")
        return False

    def stop(self):
        self._running = False
        if self._backend == "keyboard":
            try:
                import keyboard  # type: ignore
                keyboard.remove_hotkey("ctrl+alt+s")
            except Exception:
                pass
        elif self._backend == "pynput" and self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass

    def _try_keyboard(self) -> bool:
        try:
            import keyboard  # type: ignore
            keyboard.add_hotkey("ctrl+alt+s", self._fire, suppress=False)
            return True
        except Exception:
            return False

    def _try_pynput(self) -> bool:
        try:
            from pynput import keyboard as pk  # type: ignore
            self._listener = pk.GlobalHotKeys({"<ctrl>+<alt>+s": self._fire})
            self._listener.daemon = True
            self._listener.start()
            return True
        except Exception as _e:
            logger.debug("pynput failed: %s", _e)
            return False

    def _fire(self):
        try:
            self.triggered.emit()
        except Exception:
            pass


# ===========================================================================
# QuickLauncher popup
# ===========================================================================

class QuickLauncher(QWidget):
    """Dark-blue frameless popup. Always-on-top. Enter to send, Esc to
    close. Robust: no opacity animations, just show/hide.
    """

    def __init__(self):
        super().__init__()
        self._sio = None
        self._connected = False
        self._connect_thread: Optional[threading.Thread] = None
        self._waiting_reply = False
        # Drag-to-move state
        self._drag_origin: Optional[QPoint] = None
        self._drag_window_origin: Optional[QPoint] = None
        self._build_ui()
        self._wire()
        # Hidden at start.
        self.hide()
        # Spin up the Socket.IO client in a worker thread so init is fast.
        self._connect_thread = threading.Thread(
            target=self._connect_socketio, daemon=True)
        self._connect_thread.start()
        # Auto-close after 12s of inactivity.
        self._auto_close = QTimer(self)
        self._auto_close.setSingleShot(True)
        self._auto_close.timeout.connect(self.dismiss)

    # ----- UI -----
    def _build_ui(self):
        # Frameless + always-on-top. We DO NOT use Qt.WindowType.Tool —
        # on Windows, Tool windows become invisible after the first hide()
        # cycle until you click another window. Using a regular window
        # makes the popup show reliably every time at the cost of a
        # taskbar entry (acceptable trade — user wanted "always works").
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        # WA_TranslucentBackground lets us draw rounded corners through
        # QSS + a single inner card.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(QSize(POPUP_W, POPUP_H))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)

        # Card body — solid dark blue, rounded, with a soft glow halo.
        self.card = QFrame(self)
        self.card.setObjectName("ql_card")
        self.card.setStyleSheet(
            f"#ql_card {{ "
            f"  background-color:{DB_BG}; "
            f"  border:1px solid {DB_BORDER}; "
            f"  border-radius:14px; "
            f"}}"
        )
        # NOTE: QGraphicsDropShadowEffect on a QFrame samples its
        # rectangular bounding box, so the shadow renders as a hard
        # square around our rounded corners. We instead draw the shadow
        # via a paintEvent-style approach: extra outer margin + a soft
        # second-layer card behind that's *also* rounded.
        outer.addWidget(self.card)

        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(20, 16, 20, 16)
        cl.setSpacing(10)

        # ----- Header (acts as drag handle) -----
        # We make this a QWidget so it absorbs the mouse events; clicking
        # anywhere in the header lets the user drag the popup around.
        self.header = QWidget(self.card)
        self.header.setObjectName("ql_header")
        self.header.setCursor(Qt.CursorShape.SizeAllCursor)
        self.header.setStyleSheet("#ql_header { background: transparent; }")
        self.header.setFixedHeight(24)
        head = QHBoxLayout(self.header)
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)

        # Drag-grip glyph for affordance.
        grip = QLabel("⋮⋮")
        grip.setStyleSheet(
            f"color:{DB_TEXT_SUBTLE}; font-size:11px; "
            f"background:transparent; border:none;"
        )
        head.addWidget(grip)

        title = QLabel("Shell Quick Launch")
        title.setStyleSheet(
            f"color:{DB_ACCENT}; font-family:'{T.family}'; font-size:12px; "
            f"font-weight:700; letter-spacing:1px; "
            f"background:transparent; border:none;"
        )
        head.addWidget(title)

        head.addStretch(1)

        hint = QLabel("Enter to send  •  Esc to close")
        hint.setStyleSheet(
            f"color:{DB_TEXT_SUBTLE}; font-family:'{T.family}'; font-size:11px; "
            f"background:transparent; border:none;"
        )
        head.addWidget(hint)

        # Close × button
        self.close_btn = QPushButton("×", self.header)
        self.close_btn.setFixedSize(QSize(22, 22))
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.close_btn.setStyleSheet(
            f"QPushButton {{ "
            f"  background:transparent; color:{DB_TEXT_DIM}; "
            f"  border:none; border-radius:4px; "
            f"  font-size:16px; font-weight:600; "
            f"}} "
            f"QPushButton:hover {{ "
            f"  background:rgba(255,107,107,0.18); color:{DB_ERROR_TEXT}; "
            f"}}"
        )
        self.close_btn.clicked.connect(self.dismiss)
        head.addWidget(self.close_btn)

        cl.addWidget(self.header)

        # Input row: text + send button
        row = QHBoxLayout()
        row.setSpacing(10)
        self.input = QLineEdit(self.card)
        self.input.setPlaceholderText("Ask Shell anything…")
        self.input.setFixedHeight(44)
        self.input.setStyleSheet(
            f"QLineEdit {{ "
            f"  background-color:{DB_BG_INNER}; "
            f"  color:{DB_TEXT}; "
            f"  border:1px solid {DB_BORDER}; "
            f"  border-radius:10px; "
            f"  padding:0 14px; "
            f"  font-family:'{T.family}'; font-size:14px; "
            f"  selection-background-color:{DB_ACCENT_SOFT}; "
            f"}} "
            f"QLineEdit:focus {{ "
            f"  border:1px solid {DB_ACCENT}; "
            f"}}"
        )
        row.addWidget(self.input, 1)

        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedSize(QSize(80, 44))
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setStyleSheet(
            f"QPushButton {{ "
            f"  background-color:{DB_ACCENT}; color:{DB_ACCENT_TEXT}; "
            f"  border:none; border-radius:10px; "
            f"  font-family:'{T.family}'; font-size:13px; font-weight:600; "
            f"}} "
            f"QPushButton:hover {{ background-color:{DB_ACCENT_HOV}; }} "
            f"QPushButton:pressed {{ padding-top:1px; }}"
        )
        row.addWidget(self.send_btn)
        cl.addLayout(row)

        # Status line
        self.status = QLabel("Connecting to Shell hub…")
        self.status.setStyleSheet(
            f"color:{DB_TEXT_DIM}; font-family:'{T.family}'; font-size:12px; "
            f"background:transparent; border:none;"
        )
        self.status.setWordWrap(True)
        cl.addWidget(self.status)

    def _wire(self):
        self.input.returnPressed.connect(self._send)
        self.send_btn.clicked.connect(self._send)
        # Every keystroke pushes the auto-close out — popup never
        # vanishes while the user is actively typing.
        self.input.textChanged.connect(self._on_user_active)

    def _on_user_active(self, *_args):
        """Called on each keystroke / interaction — bumps auto-close."""
        # If we're waiting for a reply, don't restart the timer (still
        # frozen). Otherwise give 60 s of fresh idle time.
        if not self._waiting_reply:
            try: self._auto_close.start(60_000)
            except Exception: pass

    # ----- Socket.IO -----
    def _hub_urls(self):
        urls = []
        env = os.environ.get("SHELL_HUB_URL")
        if env:
            urls.append(env.rstrip("/"))
        try:
            hint = os.path.join(_PROJECT_ROOT, ".shell_hub_port")
            if os.path.exists(hint):
                with open(hint, "r", encoding="utf-8") as f:
                    p = f.read().strip()
                if p.isdigit():
                    urls.append(f"http://127.0.0.1:{p}")
        except Exception:
            pass
        for p in (5000, 5001, 5002, 5003):
            u = f"http://127.0.0.1:{p}"
            if u not in urls:
                urls.append(u)
        return urls

    def _connect_socketio(self):
        if socketio is None:
            self._set_status_from_thread("python-socketio missing — install it")
            return
        self._sio = socketio.Client(reconnection=True, reconnection_attempts=0)

        @self._sio.event
        def connect():
            self._connected = True
            self._set_status_from_thread("Ready")

        @self._sio.event
        def disconnect():
            self._connected = False
            self._set_status_from_thread("Hub disconnected")

        @self._sio.event
        def shell_response(data):
            if not isinstance(data, dict):
                return
            t = data.get("type")
            txt = str(data.get("text", "") or "")[:200]
            if t == "agent_reply" and txt:
                self._set_status_from_thread(f"✓  {txt}")
                # Re-arm a short auto-close so the user can read the
                # reply (8s) and then it slides away. Marshal to GUI
                # thread since we may be on the socketio worker.
                QMetaObject.invokeMethod(
                    self, "_after_reply",
                    Qt.ConnectionType.QueuedConnection,
                )

        for u in self._hub_urls():
            try:
                auth = _hub_socket_auth()
                if auth:
                    self._sio.connect(u, wait_timeout=4, auth=auth)
                else:
                    self._sio.connect(u, wait_timeout=4)
                logger.info("QuickLauncher connected to %s", u)
                return
            except Exception as e:
                logger.debug("connect %s failed: %s", u, e)
        self._set_status_from_thread("Hub unreachable")

    def _set_status_from_thread(self, txt: str):
        """Marshal a status update from any thread to the GUI thread.

        Uses QMetaObject.invokeMethod (proper Qt cross-thread API) instead
        of QTimer.singleShot which silently no-ops if called from a thread
        with no event loop (e.g. the socketio worker after teardown).
        """
        try:
            QMetaObject.invokeMethod(
                self.status,
                "setText",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, str(txt)),
            )
        except Exception:
            pass

    # ----- send -----
    def _send(self):
        text = self.input.text().strip()
        if not text:
            return
        if self._sio is None or not self._connected:
            self.status.setText("Hub offline — message not sent")
            return
        try:
            self._sio.emit("gui_input", {"type": "user_text", "text": text})
            self.input.clear()
            self.status.setText("Sent — waiting for reply…")
            # Pause auto-close indefinitely while we wait. The reply
            # handler re-arms a short close once we get the answer (so
            # slow agents — e.g. groq cold-start at 30 s — don't lose
            # the user's reply window).
            self._auto_close.stop()
            self._waiting_reply = True
        except Exception as e:
            self.status.setText(f"Send failed: {e}")

    # ----- show / hide -----
    def activate_from_hotkey(self):
        """Called by GlobalHotkey on Ctrl+Alt+S. Robust, simple.

        We deliberately AVOID:
          • `AttachThreadInput` ctypes hack — it deadlocks on some Win
            10/11 builds when the foreground app is dwm.exe.
          • Multiple deferred focus timers — they fight each other.
          • The Qt `Tool` window flag — it sometimes makes the popup
            invisible until another window is clicked.

        Instead: hide → reposition → show → raise → activateWindow,
        with one deferred focus attempt. Simpler is more reliable.
        """
        try:
            # Force hide first so re-show always re-creates the platform
            # window state. This fixes the "shows once, then nothing" case.
            self.hide()
            QApplication.processEvents()
            self._position_centre()
            self.setWindowState(Qt.WindowState.WindowActive)
            self.show()
            self.raise_()
            self.activateWindow()
            QTimer.singleShot(50, self._focus_input)
            # Generous 60 s idle window. Resets on every keystroke via
            # _on_user_active, freezes entirely while waiting for reply.
            self._auto_close.start(60_000)
            logger.info("QuickLauncher shown at %s", self.pos())
        except Exception:
            import traceback
            logger.warning("activate failed:\n%s", traceback.format_exc())

    def _focus_input(self):
        """Best-effort focus to the text field."""
        try:
            self.activateWindow()
            self.input.setFocus(Qt.FocusReason.OtherFocusReason)
            self.input.selectAll()
        except Exception:
            pass

    def dismiss(self):
        try:
            self._auto_close.stop()
            self._waiting_reply = False
            # Clear any in-flight drag state so the next show doesn't
            # inherit a stale drag origin.
            self._drag_origin = None
            self._drag_window_origin = None
            self.hide()
        except Exception:
            pass

    @pyqtSlot()
    def _after_reply(self):
        """Reply just landed — give the user a comfortable 30 s to read.

        Don't auto-close at all if the input still has focus — they're
        probably typing the next prompt and we'd be rude to interrupt.
        """
        self._waiting_reply = False
        try:
            if self.input.hasFocus():
                # Keep open as long as they're typing.
                return
            self._auto_close.start(30_000)
        except Exception:
            pass

    def _position_centre(self):
        app = QApplication.instance()
        if app is None:
            return
        screen = None
        try:
            screen = app.screenAt(QCursor.pos())
        except Exception:
            pass
        if screen is None:
            screen = app.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - POPUP_W) // 2
        y = geo.y() + (geo.height() - POPUP_H) // 2 - 60
        y = max(geo.y() + 20, y)
        self.move(QPoint(x, y))

    # ----- drag-to-move (header acts as title bar) -----
    def _click_in_header(self, ev) -> bool:
        """True if the click landed inside the header's geometry.

        We translate the popup-local point into card-local then check
        against the header's rect. This is more reliable than `childAt`
        because childAt returns the topmost *visible* widget which can
        be a transparent label inside the body, leading to false drag
        starts on the status line / input row.
        """
        try:
            local = ev.position().toPoint() if hasattr(ev, "position") else ev.pos()
            card_local = self.card.mapFrom(self, local)
            return self.header.geometry().contains(card_local)
        except Exception:
            return False

    def mousePressEvent(self, ev):  # noqa: N802
        if ev.button() == Qt.MouseButton.LeftButton and self._click_in_header(ev):
            self._drag_origin = ev.globalPosition().toPoint()
            self._drag_window_origin = self.frameGeometry().topLeft()
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):  # noqa: N802
        if (self._drag_origin is not None
                and ev.buttons() & Qt.MouseButton.LeftButton):
            delta = ev.globalPosition().toPoint() - self._drag_origin
            self.move(self._drag_window_origin + delta)
            # Pause auto-close while user is interacting.
            self._auto_close.start(12000)
            ev.accept()
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):  # noqa: N802
        self._drag_origin = None
        self._drag_window_origin = None
        super().mouseReleaseEvent(ev)

    # ----- key handling -----
    def keyPressEvent(self, ev: QKeyEvent):  # noqa: N802
        if ev.key() == Qt.Key.Key_Escape:
            self.dismiss()
            return
        super().keyPressEvent(ev)

    def closeEvent(self, ev):  # noqa: N802
        try:
            if self._sio is not None:
                self._sio.disconnect()
        except Exception:
            pass
        super().closeEvent(ev)


# ===========================================================================
# Standalone test
# ===========================================================================
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    launcher = QuickLauncher()
    hk = GlobalHotkey(launcher)
    if not hk.start():
        print("Hotkey backend missing — pip install pynput")
    print("Press Ctrl+Alt+S anywhere. Esc to close.")
    QTimer.singleShot(400, launcher.activate_from_hotkey)
    sys.exit(app.exec())
