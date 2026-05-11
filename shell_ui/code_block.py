"""code_block — Mac-style syntax-highlighted code box for chat bubbles.

Renders a fenced ```language ... ``` block as an embedded widget with:
  * dark surface, hairline border, Mac traffic-light style header
  * monospace body with line numbers down the left
  * a small "Copy" button (top-right) that copies raw code to clipboard
  * Pygments syntax highlighting (monokai theme) when pygments is available;
    falls back to a plain monospace block otherwise.

All colours come from ``shell_ui.design_tokens`` so the widget tracks the
active palette automatically.
"""
from __future__ import annotations

import html as _html

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QVBoxLayout, QWidget,
)

from shell_ui.design_tokens import C, T, S, R

# ------------------------------------------------------------------ pygments
_PYG_OK = False
try:
    from pygments import highlight as _pyg_highlight
    from pygments.lexers import get_lexer_by_name, guess_lexer, TextLexer
    from pygments.formatters import HtmlFormatter
    from pygments.util import ClassNotFound
    _PYG_OK = True
except Exception:  # pragma: no cover - pygments missing
    _PYG_OK = False


def _resolve_lexer(language: str, code: str):
    """Return a pygments lexer for ``language`` or guess; fall back to plain."""
    lang = (language or "").strip().lower()
    if lang:
        try:
            return get_lexer_by_name(lang, stripall=False)
        except ClassNotFound:
            pass
    try:
        return guess_lexer(code)
    except Exception:
        return TextLexer()


def _highlight_html(language: str, code: str) -> str:
    """Render ``code`` to inline-styled HTML using pygments (monokai)."""
    if not _PYG_OK:
        # Plain fallback — escape and wrap in <pre>.
        esc = _html.escape(code)
        return (
            f'<pre style="margin:0;color:{C.text};'
            f'font-family:{T.family_mono};font-size:{T.mono_size}px;'
            f'white-space:pre;">{esc}</pre>'
        )

    lexer = _resolve_lexer(language, code)
    try:
        formatter = HtmlFormatter(
            style="monokai",
            noclasses=True,           # inline styles (works inside QTextEdit)
            nowrap=False,
            nobackground=True,
        )
    except Exception:
        formatter = HtmlFormatter(style="default", noclasses=True,
                                  nowrap=False, nobackground=True)
    body = _pyg_highlight(code, lexer, formatter)
    # pygments wraps the result in <div class="highlight"><pre>...</pre></div>;
    # nudge the <pre> font so QTextEdit renders correctly.
    style = (
        f'font-family:{T.family_mono};font-size:{T.mono_size}px;'
        f'color:{C.text};line-height:1.45;'
    )
    return body.replace(
        "<pre>", f'<pre style="margin:0;{style}">'
    )


# ====================================================================== widget
class CodeBlock(QFrame):
    """Embedded Mac-style fenced-code widget for chat bubbles."""

    def __init__(self, language: str, code: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._language = (language or "").strip()
        self._code = code or ""

        self.setObjectName("CodeBlock")
        self.setStyleSheet(
            f"#CodeBlock {{"
            f"  background-color:{C.surface};"
            f"  border:1px solid {C.border};"
            f"  border-top:1px solid {C.border_strong};"
            f"  border-radius:{R.lg}px;"
            f"}}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_header())
        outer.addWidget(self._build_divider())
        outer.addWidget(self._build_body(), 1)

    # ---------------------------------------------------------------- header
    def _build_header(self) -> QWidget:
        bar = QWidget(self)
        bar.setFixedHeight(34)
        bar.setStyleSheet(
            f"background-color:{C.surface_2};"
            f"border-top-left-radius:{R.lg}px;"
            f"border-top-right-radius:{R.lg}px;"
            f"border:none;"
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(S.md, 0, S.sm, 0)
        row.setSpacing(S.sm)

        lang_text = self._language.upper() if self._language else "CODE"
        lang_lbl = QLabel(lang_text, bar)
        lang_lbl.setStyleSheet(
            f"color:{C.text_muted};"
            f"font-family:{T.family_mono};"
            f"font-size:{T.small_size}px;"
            f"font-weight:600;"
            f"letter-spacing:1.5px;"
            f"background:transparent;border:none;"
        )
        row.addWidget(lang_lbl)
        row.addStretch(1)

        self._copy_btn = QPushButton("Copy", bar)
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.setFixedHeight(22)
        self._apply_copy_style(False)
        self._copy_btn.clicked.connect(self._copy)
        row.addWidget(self._copy_btn)
        return bar

    def _apply_copy_style(self, flashed: bool) -> None:
        bg = C.accent_soft if flashed else "transparent"
        fg = C.accent if flashed else C.text_muted
        self._copy_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color:{bg};"
            f"  color:{fg};"
            f"  border:1px solid {C.border_strong};"
            f"  border-radius:{R.sm}px;"
            f"  padding:2px 10px;"
            f"  font-family:{T.family};"
            f"  font-size:{T.small_size}px;"
            f"  font-weight:600;"
            f"}}"
            f"QPushButton:hover {{"
            f"  color:{C.accent};"
            f"  border:1px solid {C.accent};"
            f"  background-color:{C.accent_soft};"
            f"}}"
        )

    def _build_divider(self) -> QWidget:
        line = QFrame(self)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color:{C.border}; border:none;")
        return line

    # ------------------------------------------------------------------ body
    def _build_body(self) -> QWidget:
        wrap = QWidget(self)
        wrap.setStyleSheet("background:transparent;border:none;")
        h = QHBoxLayout(wrap)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # Line-number gutter
        gutter = QTextEdit(wrap)
        gutter.setReadOnly(True)
        gutter.setFrameShape(QFrame.Shape.NoFrame)
        gutter.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        gutter.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        gutter.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        gutter.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        n_lines = max(1, self._code.count("\n") + 1)
        digits = max(2, len(str(n_lines)))
        gutter_w = 14 + digits * 8
        gutter.setFixedWidth(gutter_w)
        gutter_html = "<br>".join(str(i) for i in range(1, n_lines + 1))
        gutter.setHtml(
            f'<div style="text-align:right;'
            f'color:{C.text_subtle};'
            f'font-family:{T.family_mono};'
            f'font-size:{T.mono_size}px;'
            f'line-height:1.45;'
            f'padding:{S.sm}px {S.xs}px {S.sm}px 0;">{gutter_html}</div>'
        )
        gutter.setStyleSheet(
            f"QTextEdit {{"
            f"  background-color:{C.surface};"
            f"  border:none;"
            f"  border-bottom-left-radius:{R.lg}px;"
            f"}}"
        )
        h.addWidget(gutter)

        # Code body — horizontally scrollable, no wrap.
        body = QTextEdit(wrap)
        body.setReadOnly(True)
        body.setFrameShape(QFrame.Shape.NoFrame)
        body.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        body.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        body.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        # Force a real monospace font so caret/measurement match pygments output.
        mono = QFont()
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setFamily("Cascadia Mono")
        mono.setPointSize(max(9, T.mono_size - 3))
        body.setFont(mono)
        body.setStyleSheet(
            f"QTextEdit {{"
            f"  background-color:{C.surface};"
            f"  color:{C.text};"
            f"  border:none;"
            f"  padding:{S.sm}px {S.md}px {S.sm}px {S.sm}px;"
            f"  border-bottom-right-radius:{R.lg}px;"
            f"  selection-background-color:{C.accent_soft};"
            f"  selection-color:{C.text};"
            f"}}"
            f"QScrollBar:horizontal {{"
            f"  background:transparent; height:8px; margin:0;"
            f"}}"
            f"QScrollBar::handle:horizontal {{"
            f"  background:{C.border_strong}; border-radius:4px; min-width:30px;"
            f"}}"
            f"QScrollBar::add-line:horizontal,"
            f"QScrollBar::sub-line:horizontal {{ width:0; }}"
        )
        body.setHtml(_highlight_html(self._language, self._code))

        # Auto-size height to content (capped) so the bubble grows naturally.
        doc = body.document()
        doc.setDocumentMargin(0)
        line_h = body.fontMetrics().lineSpacing()
        approx = max(1, self._code.count("\n") + 1)
        target = min(420, line_h * approx + 2 * S.sm + 14)  # +14 for h-scrollbar
        body.setMinimumHeight(min(target, 64))
        body.setMaximumHeight(target)
        gutter.setFixedHeight(target)

        h.addWidget(body, 1)
        return wrap

    # --------------------------------------------------------------- actions
    def _copy(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        try:
            app.clipboard().setText(self._code)
        except Exception:
            return
        self._copy_btn.setText("Copied!")
        self._apply_copy_style(True)
        QTimer.singleShot(1200, self._reset_copy_btn)

    def _reset_copy_btn(self) -> None:
        try:
            self._copy_btn.setText("Copy")
            self._apply_copy_style(False)
        except RuntimeError:
            # widget already destroyed — ignore.
            pass


__all__ = ["CodeBlock"]
