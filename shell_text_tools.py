#!/usr/bin/env python3
"""
Shell Text Tools — Text manipulation and transformation utilities.
All tools use Python stdlib only: base64, urllib.parse, html, difflib, re, textwrap.
"""

import re
import base64
import difflib
import urllib.parse
import html as html_lib
import logging
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_text_tools")

# Lorem ipsum corpus
_LOREM_PARAGRAPHS = [
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.",
    "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.",
    "Curabitur pretium tincidunt lacus. Nulla gravida orci a odio. Nullam varius, turpis et commodo pharetra, est eros bibendum elit, nec luctus magna felis sollicitudin mauris. Integer in mauris eu nibh euismod gravida.",
    "Praesent blandit laoreet nibh. Fusce convallis metus id felis luctus adipiscing. Pellentesque egestas, neque sit amet convallis pulvinar, justo nulla eleifend augue, ac auctor orci leo non est.",
    "Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt explicabo.",
    "Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt. Neque porro quisquam est, qui dolorem ipsum quia dolor sit amet.",
    "At vero eos et accusamus et iusto odio dignissimos ducimus qui blanditiis praesentium voluptatum deleniti atque corrupti quos dolores et quas molestias excepturi sint occaecati cupiditate non provident.",
    "Similique sunt in culpa qui officia deserunt mollitia animi, id est laborum et dolorum fuga. Et harum quidem rerum facilis est et expedita distinctio. Nam libero tempore, cum soluta nobis est eligendi optio cumque.",
]


# ═══════════════════════════════════════════════════════════════
#  TOOL 1: TEXT COUNT
# ═══════════════════════════════════════════════════════════════

@function_tool
async def text_count_tool(text: str) -> str:
    """
    Count words, characters, lines, sentences, and paragraphs in text.
    Args:
        text: The text to analyze.
    """
    try:
        chars = len(text)
        chars_no_space = len(text.replace(" ", "").replace("\n", "").replace("\t", ""))
        words = len(text.split())
        lines = len(text.splitlines()) if text else 0
        sentences = len(re.split(r'[.!?]+', text.strip())) - 1 if text.strip() else 0
        paragraphs = len([p for p in text.split("\n\n") if p.strip()]) if text else 0

        return (
            f"Text Statistics:\n"
            f"  Characters (with spaces):    {chars:,}\n"
            f"  Characters (without spaces):  {chars_no_space:,}\n"
            f"  Words:                        {words:,}\n"
            f"  Lines:                        {lines:,}\n"
            f"  Sentences:                    {max(sentences, 0):,}\n"
            f"  Paragraphs:                   {max(paragraphs, 1) if text.strip() else 0:,}"
        )
    except Exception as e:
        return f"Error counting text: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 2: TEXT CASE CONVERSION
# ═══════════════════════════════════════════════════════════════

@function_tool
async def text_case_tool(text: str, case_type: str) -> str:
    """
    Convert text to different cases.
    Args:
        text: The text to convert.
        case_type: Target case — one of: upper, lower, title, camel, snake, kebab, pascal, constant.
    """
    try:
        ct = case_type.lower().strip()
        words = re.split(r'[\s_\-]+', text)
        clean_words = [w for w in words if w]

        if ct == "upper":
            result = text.upper()
        elif ct == "lower":
            result = text.lower()
        elif ct == "title":
            result = text.title()
        elif ct == "camel":
            result = clean_words[0].lower() + "".join(w.capitalize() for w in clean_words[1:]) if clean_words else ""
        elif ct == "pascal":
            result = "".join(w.capitalize() for w in clean_words)
        elif ct == "snake":
            result = "_".join(w.lower() for w in clean_words)
        elif ct == "kebab":
            result = "-".join(w.lower() for w in clean_words)
        elif ct == "constant":
            result = "_".join(w.upper() for w in clean_words)
        else:
            return f"Unknown case type: '{case_type}'. Supported: upper, lower, title, camel, pascal, snake, kebab, constant."

        return f"[{ct}] {result}"
    except Exception as e:
        return f"Error converting case: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 3: TEXT REVERSE
# ═══════════════════════════════════════════════════════════════

@function_tool
async def text_reverse_tool(text: str) -> str:
    """
    Reverse the given text.
    Args:
        text: The text to reverse.
    """
    try:
        reversed_text = text[::-1]
        return f"Reversed ({len(text)} chars):\n{reversed_text}"
    except Exception as e:
        return f"Error reversing text: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 4: LOREM IPSUM GENERATOR
# ═══════════════════════════════════════════════════════════════

@function_tool
async def text_lorem_tool(paragraphs: int) -> str:
    """
    Generate lorem ipsum placeholder text.
    Args:
        paragraphs: Number of paragraphs to generate (1-20).
    """
    try:
        count = max(1, min(paragraphs, 20))
        result = []
        for i in range(count):
            result.append(_LOREM_PARAGRAPHS[i % len(_LOREM_PARAGRAPHS)])
        output = "\n\n".join(result)
        word_count = len(output.split())
        return f"Lorem Ipsum ({count} paragraphs, {word_count} words):\n\n{output}"
    except Exception as e:
        return f"Error generating lorem ipsum: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 5: TEXT DIFF
# ═══════════════════════════════════════════════════════════════

@function_tool
async def text_diff_tool(text1: str, text2: str) -> str:
    """
    Show differences between two texts using unified diff format.
    Args:
        text1: First text (original).
        text2: Second text (modified).
    """
    try:
        lines1 = text1.splitlines(keepends=True)
        lines2 = text2.splitlines(keepends=True)

        diff = list(difflib.unified_diff(lines1, lines2, fromfile="text1", tofile="text2", lineterm=""))
        if not diff:
            return "No differences found — texts are identical."

        # Count changes
        added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))

        diff_text = "\n".join(diff)
        return (
            f"Diff Summary: {added} additions, {removed} deletions\n"
            f"{'=' * 50}\n{diff_text}"
        )
    except Exception as e:
        return f"Error computing diff: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 6: TEXT ENCODE
# ═══════════════════════════════════════════════════════════════

@function_tool
async def text_encode_tool(text: str, encoding: str) -> str:
    """
    Encode text using various encoding schemes.
    Args:
        text: The text to encode.
        encoding: Encoding type — one of: base64, url, html, hex.
    """
    try:
        enc = encoding.lower().strip()
        if enc == "base64":
            result = base64.b64encode(text.encode("utf-8")).decode("ascii")
        elif enc == "url":
            result = urllib.parse.quote(text)
        elif enc == "html":
            result = html_lib.escape(text)
        elif enc == "hex":
            result = text.encode("utf-8").hex()
        else:
            return f"Unknown encoding: '{encoding}'. Supported: base64, url, html, hex."

        return f"[{enc} encoded] ({len(text)} chars -> {len(result)} chars):\n{result}"
    except Exception as e:
        return f"Error encoding text: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 7: TEXT DECODE
# ═══════════════════════════════════════════════════════════════

@function_tool
async def text_decode_tool(text: str, encoding: str) -> str:
    """
    Decode text from various encoding schemes.
    Args:
        text: The encoded text to decode.
        encoding: Encoding type — one of: base64, url, html, hex.
    """
    try:
        enc = encoding.lower().strip()
        if enc == "base64":
            result = base64.b64decode(text.encode("ascii")).decode("utf-8")
        elif enc == "url":
            result = urllib.parse.unquote(text)
        elif enc == "html":
            result = html_lib.unescape(text)
        elif enc == "hex":
            result = bytes.fromhex(text).decode("utf-8")
        else:
            return f"Unknown encoding: '{encoding}'. Supported: base64, url, html, hex."

        return f"[{enc} decoded] ({len(text)} chars -> {len(result)} chars):\n{result}"
    except Exception as e:
        return f"Error decoding text: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 8: TEXT TO URL SLUG
# ═══════════════════════════════════════════════════════════════

@function_tool
async def text_slug_tool(text: str) -> str:
    """
    Convert text to a URL-friendly slug.
    Lowercases, removes special characters, replaces spaces with hyphens.
    Args:
        text: The text to slugify.
    """
    try:
        slug = text.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        slug = slug.strip('-')
        return f"Slug: {slug}"
    except Exception as e:
        return f"Error creating slug: {e}"
