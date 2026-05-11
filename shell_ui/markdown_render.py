"""markdown_render — proper markdown -> Qt-friendly HTML for ChatBubble.

Qt's QLabel rich-text engine accepts a *subset* of HTML 4 + a tiny bit of
CSS via inline `style="..."` only. Stylesheets in <style> blocks and most
modern CSS (flex, var(), pseudo-classes, etc.) are silently ignored. So
every colour / font / padding here is emitted inline.

We also have to coexist with the existing fenced-code-block parser in
`ChatBubble.__init__` which splits the raw text on ```...``` *before*
calling us — so we deliberately leave triple-backtick fences untouched
and only handle inline-code with single backticks.

The function `render(md)` first tries the `markdown` PyPI package (gives
us robust inline parsing + nested lists). If unavailable it falls through
to a hand-rolled regex renderer that mirrors the original
`ChatBubble._markdown_to_html` behaviour but with design-token colours.

All colours / fonts come from `shell_ui.design_tokens` so a palette swap
(`set_palette(...)`) flows through to chat bubbles automatically the next
time a message is rendered.
"""
from __future__ import annotations

import html as _html
import re

from shell_ui.design_tokens import C, T

# ---------------------------------------------------------------------------
# Detect optional `markdown` package once at import time.
# ---------------------------------------------------------------------------
try:  # pragma: no cover - import side-effect only
    import markdown as _md_lib  # type: ignore
    _HAS_MD = True
except Exception:  # pragma: no cover
    _md_lib = None
    _HAS_MD = False


# ---------------------------------------------------------------------------
# Inline-style helpers — Qt rich-text only honours `style="..."` inline.
# ---------------------------------------------------------------------------

def _style_code() -> str:
    return (
        f"background:{C.surface_2};"
        f"color:{C.accent};"
        f"font-family:{T.family_mono};"
        f"font-size:{T.mono_size}px;"
        f"padding:1px 5px;"
        f"border-radius:4px;"
    )


def _style_link() -> str:
    return f"color:{C.accent};text-decoration:underline;"


def _style_header(size: int) -> str:
    return (
        f"color:{C.text};"
        f"font-family:{T.family};"
        f"font-size:{size}px;"
        f"font-weight:700;"
    )


def _style_blockquote() -> str:
    return (
        f"border-left:3px solid {C.accent};"
        f"padding-left:10px;"
        f"color:{C.text_muted};"
        f"margin:4px 0;"
        f"font-style:italic;"
    )


def _style_hr() -> str:
    return f"border:0;border-top:1px solid {C.border_strong};margin:6px 0;"


def _style_bold() -> str:
    return f"color:{C.text};font-weight:700;"


def _style_italic() -> str:
    return f"color:{C.text};font-style:italic;"


# ---------------------------------------------------------------------------
# Inline markdown — bold, italic, strikethrough, inline-code, links.
# Order matters: bold (**) before italic (*), code before links so the
# inside of a link is not re-tokenised, etc.
# ---------------------------------------------------------------------------

_RE_CODE   = re.compile(r"`([^`\n]+?)`")
_RE_BOLD_S = re.compile(r"\*\*(.+?)\*\*")
_RE_BOLD_U = re.compile(r"__(.+?)__")
_RE_ITAL_S = re.compile(r"(?<![\*\w])\*(?!\s)(.+?)(?<!\s)\*(?![\*\w])")
_RE_ITAL_U = re.compile(r"(?<![_\w])_(?!\s)(.+?)(?<!\s)_(?![_\w])")
_RE_STRIKE = re.compile(r"~~(.+?)~~")
_RE_LINK   = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _inline(text: str) -> str:
    """Apply inline markdown to a single line. Inline-code is extracted
    first and replaced with placeholders so its contents are not further
    munged by bold/italic regexes."""
    code_segments: list[str] = []

    def _stash_code(m: re.Match) -> str:
        idx = len(code_segments)
        code_segments.append(_html.escape(m.group(1)))
        return f"\x00CODE{idx}\x00"

    t = _RE_CODE.sub(_stash_code, text)

    # Now safe to escape the rest of the text. We escape, then re-insert
    # markdown HTML. This protects against `<script>` and friends in the
    # raw model output.
    t = _html.escape(t)

    # Bold / italic / strike. Order: bold first (greedy ** before *).
    t = _RE_BOLD_S.sub(lambda m: f'<b style="{_style_bold()}">{m.group(1)}</b>', t)
    t = _RE_BOLD_U.sub(lambda m: f'<b style="{_style_bold()}">{m.group(1)}</b>', t)
    t = _RE_ITAL_S.sub(lambda m: f'<i style="{_style_italic()}">{m.group(1)}</i>', t)
    t = _RE_ITAL_U.sub(lambda m: f'<i style="{_style_italic()}">{m.group(1)}</i>', t)
    t = _RE_STRIKE.sub(r"<s>\1</s>", t)

    # Links — html.escape will have turned `[text](url)` into the same
    # ASCII so the regex still matches.
    t = _RE_LINK.sub(
        lambda m: f'<a href="{m.group(2)}" style="{_style_link()}">{m.group(1)}</a>',
        t,
    )

    # Restore inline-code segments.
    def _unstash(m: re.Match) -> str:
        idx = int(m.group(1))
        return f'<code style="{_style_code()}">{code_segments[idx]}</code>'

    t = re.sub(r"\x00CODE(\d+)\x00", _unstash, t)
    return t


# ---------------------------------------------------------------------------
# Block-level fallback renderer (used when the `markdown` package isn't
# installed). Mirrors the original ChatBubble._markdown_to_html flow but
# with design-token colours and proper escaping.
# ---------------------------------------------------------------------------

_RE_OL_ITEM = re.compile(r"^(\d+)\.\s+(.+)$")


def _fallback_render(text: str) -> str:
    out: list[str] = []
    list_type: str | None = None  # None | "ul" | "ol"

    def _close_list() -> None:
        nonlocal list_type
        if list_type:
            out.append(f"</{list_type}>")
            list_type = None

    for raw_line in text.split("\n"):
        line = raw_line.rstrip()
        stripped = line.strip()

        # Skip lines that are part of a fenced code block — those are
        # handled by ChatBubble's own splitter. We just preserve them
        # verbatim so the splitter sees them.
        if stripped.startswith("```"):
            _close_list()
            out.append(_html.escape(line))
            continue

        # Headers (h1/h2/h3 -> sized strong text).
        if stripped.startswith("### "):
            _close_list()
            out.append(
                f'<div style="{_style_header(T.h2_size)}margin:6px 0 2px 0">'
                f'{_inline(stripped[4:])}</div>'
            )
            continue
        if stripped.startswith("## "):
            _close_list()
            out.append(
                f'<div style="{_style_header(T.h1_size)}margin:8px 0 2px 0">'
                f'{_inline(stripped[3:])}</div>'
            )
            continue
        if stripped.startswith("# "):
            _close_list()
            out.append(
                f'<div style="{_style_header(T.h1_size + 2)}margin:10px 0 4px 0">'
                f'{_inline(stripped[2:])}</div>'
            )
            continue

        # Horizontal rule.
        if stripped in ("---", "***", "___"):
            _close_list()
            out.append(f'<hr style="{_style_hr()}">')
            continue

        # Blockquote.
        if stripped.startswith("> "):
            _close_list()
            out.append(
                f'<div style="{_style_blockquote()}">{_inline(stripped[2:])}</div>'
            )
            continue

        # Unordered list (- or *).
        if stripped.startswith("- ") or stripped.startswith("* "):
            if list_type != "ul":
                _close_list()
                out.append('<ul style="margin:2px 0;padding-left:20px">')
                list_type = "ul"
            out.append(f"<li>{_inline(stripped[2:])}</li>")
            continue

        # Ordered list (1. 2. 3.).
        m = _RE_OL_ITEM.match(stripped)
        if m:
            if list_type != "ol":
                _close_list()
                out.append('<ol style="margin:2px 0;padding-left:24px">')
                list_type = "ol"
            out.append(f"<li>{_inline(m.group(2))}</li>")
            continue

        # Blank line — paragraph break.
        if not stripped:
            _close_list()
            out.append("<br>")
            continue

        # Plain paragraph text.
        _close_list()
        out.append(f"{_inline(stripped)}<br>")

    _close_list()
    return "".join(out)


# ---------------------------------------------------------------------------
# Library-backed renderer — uses python-markdown when available.
# We post-process the HTML to inject inline `style="..."` so Qt actually
# honours the colours (Qt rich-text ignores stylesheets).
# ---------------------------------------------------------------------------

def _lib_render(text: str) -> str:  # pragma: no cover - depends on optional dep
    # `fenced_code` is intentionally NOT enabled — ChatBubble splits on
    # ``` before calling us, so any backticks we see are inline.
    html = _md_lib.markdown(
        text,
        extensions=["nl2br", "sane_lists"],
        output_format="html5",
    )

    # Inject design-token inline styles into the bare tags python-markdown
    # produces. Qt's renderer ignores <style>/CSS so we have to do this.
    html = html.replace("<code>", f'<code style="{_style_code()}">')
    html = html.replace("<strong>", f'<b style="{_style_bold()}">').replace("</strong>", "</b>")
    html = html.replace("<em>", f'<i style="{_style_italic()}">').replace("</em>", "</i>")
    html = html.replace("<ul>", '<ul style="margin:2px 0;padding-left:20px">')
    html = html.replace("<ol>", '<ol style="margin:2px 0;padding-left:24px">')
    html = html.replace("<blockquote>", f'<blockquote style="{_style_blockquote()}">')
    html = html.replace("<hr />", f'<hr style="{_style_hr()}">').replace("<hr>", f'<hr style="{_style_hr()}">')
    html = html.replace("<h1>", f'<div style="{_style_header(T.h1_size + 2)}margin:10px 0 4px 0">').replace("</h1>", "</div>")
    html = html.replace("<h2>", f'<div style="{_style_header(T.h1_size)}margin:8px 0 2px 0">').replace("</h2>", "</div>")
    html = html.replace("<h3>", f'<div style="{_style_header(T.h2_size)}margin:6px 0 2px 0">').replace("</h3>", "</div>")
    html = html.replace("<h4>", f'<div style="{_style_header(T.body_strong_size + 2)}margin:6px 0 2px 0">').replace("</h4>", "</div>")

    # Style links — python-markdown emits bare <a href="...">.
    html = re.sub(
        r'<a href="([^"]+)">',
        lambda m: f'<a href="{m.group(1)}" style="{_style_link()}">',
        html,
    )

    return html


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------

def render(md: str) -> str:
    """Convert a markdown string to Qt-rich-text-friendly HTML.

    Never raises — on any internal error we fall back to an HTML-escaped
    plain rendering so the chat bubble always shows *something*.
    """
    if not md:
        return ""
    try:
        if _HAS_MD:
            return _lib_render(md)
        return _fallback_render(md)
    except Exception:  # pragma: no cover — defensive
        return _html.escape(md).replace("\n", "<br>")
