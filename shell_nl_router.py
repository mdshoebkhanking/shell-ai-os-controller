"""
Deterministic natural-language router for Shell backend tools.

This module intentionally avoids LLM calls. It maps common chat/voice phrases to
safe backend tool ids and JSON arguments so the UI can run useful actions even
when external AI providers are unavailable.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any


_AGENTS: dict[str, tuple[str, str]] = {
    "developer": ("shell_agents:developer_agent_tool", "task"),
    "code": ("shell_agents:developer_agent_tool", "task"),
    "coding": ("shell_agents:developer_agent_tool", "task"),
    "website": ("shell_agents:website_builder_agent_tool", "task"),
    "web": ("shell_agents:website_builder_agent_tool", "task"),
    "app": ("shell_agents:app_builder_agent_tool", "task"),
    "api": ("shell_agents:api_agent_tool", "task"),
    "database": ("shell_agents:database_agent_tool", "task"),
    "db": ("shell_agents:database_agent_tool", "task"),
    "system": ("shell_agents:system_agent_tool", "task"),
    "social": ("shell_agents:social_agent_tool", "task"),
    "security": ("shell_agents:security_agent_tool", "task"),
    "research": ("shell_agents:research_agent_tool", "task"),
    "file": ("shell_agents:file_agent_tool", "task"),
    "creative": ("shell_agents:creative_agent_tool", "task"),
    "productivity": ("shell_agents:productivity_agent_tool", "task"),
    "data": ("shell_agents:data_agent_tool", "task"),
    "network": ("shell_agents:network_agent_tool", "task"),
    "devops": ("shell_agents:devops_agent_tool", "task"),
    "browser": ("shell_agents:browser_agent_tool", "task"),
    "communication": ("shell_agents:communication_agent_tool", "task"),
    "learning": ("shell_agents:learning_agent_tool", "task"),
    "automation": ("shell_agents:automation_agent_tool", "task"),
    "testing": ("shell_agents:testing_agent_tool", "task"),
    "test": ("shell_agents:testing_agent_tool", "task"),
    "master": ("shell_agents:master_agent_tool", "task"),
    "finance": ("shell_extra_agents:finance_agent_tool", "query"),
    "legal": ("shell_extra_agents:legal_agent_tool", "query"),
    "health": ("shell_extra_agents:health_agent_tool", "query"),
    "cooking": ("shell_extra_agents:cooking_agent_tool", "query"),
    "travel": ("shell_extra_agents:travel_agent_tool", "query"),
    "study": ("shell_extra_agents:study_agent_tool", "query"),
    "language": ("shell_extra_agents:language_tutor_agent_tool", "query"),
    "language tutor": ("shell_extra_agents:language_tutor_agent_tool", "query"),
    "resume": ("shell_extra_agents:resume_agent_tool", "query"),
    "interview": ("shell_extra_agents:interview_agent_tool", "query"),
    "marketing": ("shell_extra_agents:marketing_agent_tool", "query"),
    "seo": ("shell_extra_agents:seo_agent_tool", "query"),
    "game design": ("shell_extra_agents:game_design_agent_tool", "query"),
    "story": ("shell_extra_agents:storyteller_agent_tool", "query"),
    "storyteller": ("shell_extra_agents:storyteller_agent_tool", "query"),
    "philosophy": ("shell_extra_agents:philosophy_agent_tool", "query"),
    "debate": ("shell_extra_agents:debate_agent_tool", "query"),
}


def _route(tool: str, args: dict[str, Any] | None = None, *, kind: str = "tool", confidence: float = 0.86) -> dict[str, Any]:
    route = {
        "tool": tool,
        "args": dict(args or {}),
        "kind": kind,
        "confidence": confidence,
    }
    try:
        from core.tools.metadata import infer_tool_metadata

        module, name = str(tool).split(":", 1) if ":" in str(tool) else ("", str(tool))
        meta = infer_tool_metadata({
            "id": tool,
            "name": name,
            "module": module,
            "kind": "windows_mcp_tool" if str(tool).startswith("windows-mcp:") else kind,
            "category": "windows" if str(tool).startswith("windows-mcp:") else "",
        })
        route["readiness"] = meta.readiness.to_dict()
        route["metadata"] = meta.to_dict()
    except Exception:
        pass
    return route


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _strip_quotes(text: str) -> str:
    return str(text or "").strip().strip("\"'` ")


def _after(text: str, markers: tuple[str, ...]) -> str:
    for marker in markers:
        pattern = rf"\b{re.escape(marker)}\b\s*[:=-]?\s*(.+)$"
        match = re.search(pattern, text, flags=re.I | re.S)
        if match:
            return _strip_quotes(match.group(1))
    return _strip_quotes(text)


def _json_payload(text: str) -> str:
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not starts:
        return ""
    return text[min(starts):].strip()


def _strip_shell_address(raw: str) -> str:
    """Remove natural address prefixes without breaking explicit shell commands."""
    text = _clean(raw)
    addressed = re.match(
        r"^(?:hey\s+|ok\s+)?shell\s*(?:se|please|,|:|-)\s+(.+)$",
        text,
        flags=re.I | re.S,
    )
    if addressed:
        return _clean(addressed.group(1))

    # Speech recognition often drops "se" in phrases like
    # "Shell, YouTube pe song play karo". Keep explicit terminal phrases such
    # as "shell echo hello" working, but treat media/browser intents as
    # addressed-to-Shell commands.
    loose = re.match(r"^(?:hey\s+|ok\s+)?shell\s+(.+)$", text, flags=re.I | re.S)
    if loose and re.search(
        r"\b(youtube|you\s*tube|google|play|song|gaana|gana|music|video|chalao|bajao|lagao)\b",
        loose.group(1),
        flags=re.I,
    ):
        return _clean(loose.group(1))
    return text


def _youtube_media_query(raw: str, lower: str) -> str:
    query = raw
    query = re.sub(r"\byou\s*tube\b", "youtube", query, flags=re.I)
    query = re.sub(
        r"\b(?:please|pls|youtube|on|pe|par|mein|me|mai|main|play|chalao|chala|chalaana|"
        r"bajao|baja|lagao|laga|sunao|suna|karo|kar\s+do|song|gaana|gana|music|video)\b",
        " ",
        query,
        flags=re.I,
    )
    query = _clean(query)
    media_suffix = ""
    if re.search(r"\b(song|gaana|gana)\b", lower):
        media_suffix = "song"
    elif re.search(r"\bmusic\b", lower):
        media_suffix = "music"
    elif re.search(r"\bvideo\b", lower):
        media_suffix = "video"
    if media_suffix and media_suffix not in query.lower():
        query = _clean(f"{query} {media_suffix}")
    return query or "music"


def _project_slug_from_text(raw: str, fallback: str = "shell_site") -> str:
    text = raw.lower()
    text = re.sub(
        r"\b(?:please|pls|make|create|build|generate|design|scaffold|website|webpage|web\s+page|"
        r"landing\s+page|site|app|application|software|dashboard|tool|banao|bana|banado|banaao|"
        r"bana\s+do|kar\s+do|for|ke\s+liye|ka|ki|ek|a|an)\b",
        " ",
        text,
        flags=re.I,
    )
    slug = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    slug = re.sub(r"_+", "_", slug)[:48].strip("_")
    return slug or fallback


def _build_subject_from_text(raw: str, *, kind: str) -> str:
    stop_words = (
        r"\b(?:please|pls|make|create|build|generate|design|scaffold|develop|code|website|webpage|web\s+page|"
        r"landing\s+page|site|app|application|software|dashboard|tool|banao|bana|banado|banaao|bana\s+do|"
        r"kar\s+do|with|for|ke\s+liye|ka|ki|ek|a|an)\b"
    )
    text = re.sub(stop_words, " ", str(raw or ""), flags=re.I)
    text = _clean(text)
    if text:
        return text
    return "business" if kind == "website" else "productivity"


def _build_brief_from_text(raw: str, *, kind: str) -> str:
    subject = _build_subject_from_text(raw, kind=kind)
    if kind == "website":
        return (
            f"Build a polished responsive website for {subject}. "
            "Include a strong hero, clear value proposition, feature/service sections, proof or highlights, "
            "and a contact/CTA section. Do not echo the request text as page copy."
        )
    return (
        f"Build a full-stack app for {subject}. "
        "Include a useful dashboard, create/read/update flows, persistent backend data, responsive UI, "
        "and clear empty/error states. Do not echo the request text as page copy."
    )


def _game_name_from_text(raw: str) -> str:
    lower = str(raw or "").lower()
    known_games = (
        ("space invaders", r"\b(space\s+invaders?|invaders?|alien|spaceship|shoot(?:er|ing)?)\b"),
        ("flappy bird", r"\b(flappy|flappy\s+bird)\b"),
        ("tic tac toe", r"\b(tic\s*tac\s*toe|noughts?|crosses|xo|x\s+and\s+o)\b"),
        ("breakout", r"\b(breakout|brick\s*breaker|arkanoid)\b"),
        ("tetris", r"\b(tetris|block\s*puzzle)\b"),
        ("snake", r"\b(snake|saanp)\b"),
        ("2048", r"\b2048\b"),
        ("pong", r"\bpong\b"),
        ("runner", r"\b(runner|dino|dinosaur|endless\s+runner|chrome\s+dino)\b"),
        ("reaction", r"\b(reaction|click\s+game|tap\s+game)\b"),
    )
    for name, pattern in known_games:
        if re.search(pattern, lower, flags=re.I):
            return name

    text = re.sub(_CREATION_VERB_RE, " ", str(raw or ""), flags=re.I)
    text = re.sub(
        r"\b(?:please|pls|game|khel|playable|html5|browser|web|with|controls?|keyboard|mouse|"
        r"for|ke\s+liye|ka|ki|ek|a|an)\b",
        " ",
        text,
        flags=re.I,
    )
    text = _clean(text)
    return text or "snake"


def _looks_like_math(expr: str) -> bool:
    expr = expr.strip()
    if not re.search(r"\d", expr):
        return False
    return bool(re.search(r"[+\-*/%^()]|\b(sqrt|sin|cos|tan|log|factorial|pow)\b", expr, flags=re.I))


def _image_generation_route(raw: str, lower: str) -> dict[str, Any] | None:
    image_noun = r"(?:image|photo|picture|pic|wallpaper|art|tasveer|chitra)"
    image_verb = r"(?:generate|genrate|ganerate|ganarete|ganarate|create|make|draw|design|banao|bana|banado|banaao|karo|kar\s+do)"
    speech_generate = r"(?:generate|genrate|ganerate|ganarete|ganarate|gana\s*re|gane\s*rate)"
    polite_tail = r"(?:karo|kar\s+do|karke\s+do|karke\s+de\s+do|de\s+do|do)?(?:\s+ok)?"

    image_match = re.match(
        rf"^(?:generate|create|make|draw|design|banao|bana|banado|banaao)\s+"
        rf"(?:an?\s+|ek\s+|achhi\s+|acchi\s+|high\s+quality\s+)*"
        rf"{image_noun}\s*"
        rf"(?:of|for|ki|ka|ke|:)?\s*(.+)$",
        raw,
        flags=re.I | re.S,
    )
    if not image_match:
        image_match = re.match(
            rf"^(.+?)\s+(?:ki|ka|ke)?\s*"
            rf"{image_noun}\s+"
            rf"{image_verb}\s*{polite_tail}$",
            raw,
            flags=re.I | re.S,
        )
    if not image_match:
        image_match = re.match(
            rf"^{image_noun}\s+{speech_generate}\s*{polite_tail}\s*(.+)$",
            raw,
            flags=re.I | re.S,
        )
    if not image_match or not re.search(image_noun, lower, flags=re.I):
        return None

    prompt = _strip_quotes(image_match.group(1))
    prompt = re.sub(r"\b(?:ok|please|pls|karo|kar\s+do|karke\s+do|karke\s+de\s+do|de\s+do|do)\b\s*$", "", prompt, flags=re.I).strip()
    prompt = re.sub(r"^(?:(?:mere\s+liye|mujhe|mojhe|koi|ek|a|an)\s+)+", "", prompt, flags=re.I).strip()
    return _route(
        "shell_image_ai:generate_image_tool",
        {
            "description": prompt or _strip_quotes(raw),
            "device_type": "pc",
            "style": "photorealistic",
            "quality": "excellent",
            "use_ai_enhancement": True,
            "use_cache": False,
            "force_fresh": True,
        },
        confidence=0.92,
    )


def _unit_alias(unit: str) -> str:
    normalized = str(unit or "").strip().lower().replace(" ", "_")
    aliases = {
        "meter": "m",
        "meters": "m",
        "metre": "m",
        "metres": "m",
        "centimeter": "cm",
        "centimeters": "cm",
        "centimetre": "cm",
        "centimetres": "cm",
        "kilometer": "km",
        "kilometers": "km",
        "kilometre": "km",
        "kilometres": "km",
        "millimeter": "mm",
        "millimeters": "mm",
        "millimetre": "mm",
        "millimetres": "mm",
        "gram": "g",
        "grams": "g",
        "kilogram": "kg",
        "kilograms": "kg",
        "liter": "l",
        "liters": "l",
        "litre": "l",
        "litres": "l",
        "second": "sec",
        "seconds": "sec",
        "minute": "min",
        "minutes": "min",
        "hour": "hr",
        "hours": "hr",
    }
    return aliases.get(normalized, normalized)


def _number(value: str) -> float:
    return float(str(value).replace(",", "").strip())


_WORKSPACE_PATH_TOKEN = r"[A-Za-z0-9][A-Za-z0-9._/-]{0,180}\.[A-Za-z0-9]{1,16}"
_EMAIL_TOKEN = r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}"
_EMAIL_ATTACHMENT_EXTS = "pdf|docx?|xlsx?|csv|txt|md|png|jpe?g|zip"
_CREATION_VERB_RE = (
    r"\b(make|create|build|generate|design|scaffold|develop|code|"
    r"banao|bana|banado|banaao|bana\s+do|kar\s+do)\b"
)
_GAME_INTENT_RE = (
    r"\b(game|khel|snake|tetris|pong|flappy|flappy\s+bird|2048|breakout|"
    r"space\s+invaders?|runner|dino|tic\s*tac\s*toe|reaction)\b"
)
_CODE_LANGUAGE_RE = (
    r"\b(python|py|javascript|typescript|java|kotlin|swift|c\+\+|cpp|c#|csharp|"
    r"go|golang|rust|php|ruby|sql|html|css|react|node|nodejs|express|fastapi|"
    r"flask|django|bash|shell\s+script|script|program|function|class|component|"
    r"algorithm|api|endpoint|regex|code|coding)\b"
)
_CODE_ACTION_RE = (
    r"\b(write|likho|likh\s+do|create|make|build|generate|develop|code|"
    r"banao|bana|banado|banaao|bana\s+do|kar\s+do)\b"
)


def _workspace_file_path_match(raw: str) -> tuple[str, tuple[int, int]] | None:
    quoted = re.search(r"[\"'`]([^\"'`]+?\.[A-Za-z0-9]{1,16})[\"'`]", raw)
    if quoted:
        return _strip_quotes(quoted.group(1)), quoted.span(1)

    patterns = (
        rf"\b(?:file|named|name|naam|path)\s+(?P<path>{_WORKSPACE_PATH_TOKEN})\b",
        rf"\b(?:create|make|new|banao|bana|banado|bana\s+do)\s+(?:a\s+)?(?:new\s+)?(?:file\s+)?(?P<path>{_WORKSPACE_PATH_TOKEN})\b",
        rf"\b(?P<path>{_WORKSPACE_PATH_TOKEN})\s+(?:file\s+)?(?:create|make|new|banao|bana|banado|bana\s+do)\b",
        rf"\b(?P<path>{_WORKSPACE_PATH_TOKEN})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.I)
        if match:
            return _strip_quotes(match.group("path")), match.span("path")
    return None


def _workspace_file_content(raw: str, path_span: tuple[int, int]) -> str:
    tail = raw[path_span[1]:].strip(" .,:;-")
    markers = (
        r"^(?:and\s+)?(?:with\s+)?(?:content|text)\s*[:=-]?\s*(.+)$",
        r"^(?:and\s+)?(?:write|likho|likh\s+do|daalo|dalo)\s*[:=-]?\s*(.+)$",
        r"^(?:me|mein|mai|main)\s+(?:ye\s+)?(?:write|likho|likh\s+do)\s*[:=-]?\s*(.+)$",
        r"^(?:ke\s+andar|inside)\s+(?:write|likho|likh\s+do)\s*[:=-]?\s*(.+)$",
    )
    for pattern in markers:
        match = re.search(pattern, tail, flags=re.I | re.S)
        if match:
            return _strip_quotes(match.group(1))

    global_marker = re.search(
        r"\b(?:with\s+content|content|with\s+text|text|write|likho|likh\s+do|daalo|dalo)\b\s*[:=-]?\s*(.+)$",
        raw,
        flags=re.I | re.S,
    )
    if global_marker:
        return _strip_quotes(global_marker.group(1))
    return ""


def _user_file_destination(lower: str) -> str:
    if re.search(r"\b(desktop|desk\s*top|dextop|dexdop|dexktop|destop)\b", lower, flags=re.I):
        return "desktop"
    if re.search(r"\b(documents?|document folder)\b", lower, flags=re.I):
        return "documents"
    if re.search(r"\b(downloads?|download folder)\b", lower, flags=re.I):
        return "downloads"
    if re.search(r"\b(workspace|shell workspace)\b", lower, flags=re.I):
        return "workspace"
    return ""


def _user_file_save_filename(raw: str) -> str:
    quoted = re.search(r"[\"'`]([^\"'`]+?\.[A-Za-z0-9]{1,16})[\"'`]", raw)
    if quoted:
        return _strip_quotes(quoted.group(1))
    match = re.search(
        rf"\b(?P<path>{_WORKSPACE_PATH_TOKEN})\b",
        raw,
        flags=re.I,
    )
    if match:
        return _strip_quotes(match.group("path")).split("/")[-1].split("\\")[-1]
    return ""


def _user_file_type(raw: str, lower: str, filename: str) -> str:
    if filename and "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    if re.search(r"\bpdf\b", lower, flags=re.I):
        return "pdf"
    if re.search(r"\b(markdown|md)\b", lower, flags=re.I):
        return "md"
    if re.search(r"\b(html|webpage)\b", lower, flags=re.I):
        return "html"
    if re.search(r"\b(json)\b", lower, flags=re.I):
        return "json"
    if re.search(r"\b(csv|spreadsheet)\b", lower, flags=re.I):
        return "csv"
    if re.search(r"\b(log)\b", lower, flags=re.I):
        return "log"
    if re.search(r"\b(note|notes|text|txt|file|document)\b", lower, flags=re.I):
        return "txt"
    return "txt"


def _user_file_save_content(raw: str, filename: str) -> str:
    topic_match = re.search(
        r"^(.+?)\s+(?:ke\s+bare\s+mein|ke\s+barre\s+main|ke\s+bare\s+main)\s+"
        r"(?:.+?\b)?(?:pdf|file|document|note|notes|text|txt)\b",
        raw,
        flags=re.I | re.S,
    )
    if topic_match:
        return _strip_quotes(topic_match.group(1))

    markers = (
        r"\b(?:with\s+content|content|with\s+text|text|write|likho|likh\s+do|daalo|dalo)\b\s*[:=-]?\s*(.+)$",
        r"\b(?:about|on|topic|ke\s+bare\s+mein|ke\s+barre\s+main|ke\s+bare\s+main)\b\s*[:=-]?\s*(.+?)(?:\s+(?:as\s+)?(?:pdf|file|document|note)\b|\s+(?:desktop|dextop|documents?|downloads?|workspace)\b|$)",
    )
    for pattern in markers:
        match = re.search(pattern, raw, flags=re.I | re.S)
        if match:
            return _strip_quotes(match.group(1))

    text = raw
    if filename:
        text = re.sub(re.escape(filename), " ", text, flags=re.I)
    text = re.sub(
        r"\b(?:please|pls|shell|create|make|new|save|write|generate|banao|bana|banado|banaao|"
        r"bana\s+do|kar\s+do|karke\s+do|file|pdf|document|note|notes|text|txt|as|on|to|in|"
        r"desktop|desk\s*top|dextop|documents?|downloads?|workspace|pe|par|mein|mai|main|ke|ka|ki|ek|a|an)\b",
        " ",
        text,
        flags=re.I,
    )
    text = _clean(text)
    return text


def _user_file_content_task(raw: str, content: str, file_type: str) -> str:
    topic = _clean(content)
    lower = str(raw or "").lower()
    if not topic:
        topic = _clean(raw)
    if str(file_type or "").lower() in {"html", "htm"}:
        if re.search(r"\b(login|signin|sign\s*in|auth|authentication)\b", lower):
            return (
                "Write a complete working standalone HTML login page. Include inline CSS, a real form, "
                "email/password fields, client-side validation, and a small success state. Return only HTML."
            )
        return f"Write a complete working standalone HTML file about {topic}. Include inline CSS and JavaScript if useful. Return only HTML."
    if re.search(r"\b(movie|film|short\s+film|script|screenplay|scene|dialogue|dialog)\b", lower):
        return f"Write an original movie script about {topic}."
    if re.search(r"\b(report|analysis|summary|essay|article)\b", lower):
        return f"Write a concise structured report about {topic}."
    if re.search(r"\b(letter|application|email\s+draft)\b", lower):
        return f"Write a polished letter about {topic}."
    if str(file_type or "").lower() == "pdf":
        return f"Write a polished PDF document about {topic}."
    return f"Write useful file content about {topic}."


def _user_file_save_route(raw: str, lower: str) -> dict[str, Any] | None:
    if not re.search(
        r"\b(save|create|make|new|write|generate|banao|bana|banado|banaao|bana\s+do|kar\s+do|karke\s+do)\b",
        lower,
        flags=re.I,
    ):
        return None
    if not re.search(r"\b(file|pdf|document|note|notes|text|txt|md|markdown|json|csv|html|report|letter)\b", lower, flags=re.I):
        return None
    destination = _user_file_destination(lower)
    filename = _user_file_save_filename(raw)
    file_type = _user_file_type(raw, lower, filename)
    if not destination:
        if file_type in {"html", "htm"} and re.search(r"\b(save|create|make|new|write|generate|banao|bana|banado|banaao|bana\s+do|kar\s+do|karke\s+do)\b", lower, flags=re.I):
            destination = "desktop"
        elif not re.search(r"\b(pdf|document|report|letter)\b", lower, flags=re.I):
            return None
        else:
            destination = "documents"
    if file_type in {"html", "htm"} and not filename and re.search(r"\b(login|signin|sign\s*in|auth|authentication)\b", lower, flags=re.I):
        filename = "login_page.html"
    content = _user_file_save_content(raw, filename)
    if file_type in {"html", "htm"} and re.search(r"\b(login|signin|sign\s*in|auth|authentication)\b", lower, flags=re.I):
        content = "login page"
    if file_type == "pdf" and re.search(r"\b(movie|film|short\s+film|script|screenplay|scene|dialogue|dialog)\b", lower, flags=re.I):
        content = "movie script"
        if not filename:
            filename = "movie_script.pdf"
    overwrite = bool(re.search(r"\b(overwrite|replace|update|badal|dobara)\b", lower, flags=re.I))
    return _route(
        "shell_workspace_tools:create_user_file_tool",
        {
            "filename": filename,
            "content": content,
            "content_request": _user_file_content_task(raw, content, file_type),
            "raw_request": _strip_quotes(raw),
            "destination": destination,
            "file_type": file_type,
            "overwrite": overwrite,
        },
        confidence=0.93,
    )


def _standalone_html_file_route(raw: str, lower: str) -> dict[str, Any] | None:
    has_html_or_page = bool(re.search(r"\b(html|htm|webpage|web\s+page|website|site|page)\b", lower, flags=re.I))
    has_save_target = bool(re.search(r"\b(save|desktop|desk\s*top|dextop|documents?|downloads?)\b", lower, flags=re.I))
    if not has_html_or_page and not has_save_target:
        return None
    if not re.search(r"\b(login|signin|sign\s*in|auth|authentication)\b", lower, flags=re.I):
        return None
    if not re.search(
        r"\b(create|make|new|write|generate|design|code|banao|bana|banado|banaao|bana\s+do|kar\s+do|working|work|save)\b",
        lower,
        flags=re.I,
    ):
        return None
    filename = _user_file_save_filename(raw) or "login_page.html"
    destination = _user_file_destination(lower) or "desktop"
    return _route(
        "shell_workspace_tools:create_user_file_tool",
        {
            "filename": filename,
            "content": "login page",
            "content_request": _user_file_content_task(raw, "login page", "html"),
            "raw_request": _strip_quotes(raw),
            "destination": destination,
            "file_type": "html",
            "overwrite": bool(re.search(r"\b(overwrite|replace|update|badal|dobara)\b", lower, flags=re.I)),
        },
        confidence=0.94,
    )


def _known_website_open_route(raw: str, lower: str) -> dict[str, Any] | None:
    if not re.search(r"\b(open|launch|start|khol|kholo|chalao|chala)\b", lower, flags=re.I):
        return None
    known_sites = {
        "instagram": "https://www.instagram.com/",
        "insta": "https://www.instagram.com/",
        "youtube": "https://www.youtube.com/",
        "you tube": "https://www.youtube.com/",
        "google": "https://www.google.com/",
        "facebook": "https://www.facebook.com/",
        "whatsapp": "https://web.whatsapp.com/",
        "gmail": "https://mail.google.com/",
        "twitter": "https://twitter.com/",
        "x": "https://x.com/",
        "github": "https://github.com/",
    }
    for name, url in known_sites.items():
        if re.search(rf"\b{re.escape(name)}\b", lower, flags=re.I):
            return _route("shell_desktop_tools:open_url_tool", {"url": url}, confidence=0.9)
    url_match = re.search(r"\b((?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,})(?:/[^\s]*)?", raw, flags=re.I)
    if url_match:
        url = url_match.group(0)
        if not url.lower().startswith(("http://", "https://")):
            url = "https://" + url
        return _route("shell_desktop_tools:open_url_tool", {"url": url}, confidence=0.88)
    return None


def _workspace_file_create_route(raw: str, lower: str) -> dict[str, Any] | None:
    if not re.search(r"\b(create|make|new|banao|bana|banado|file|likho|write)\b", lower, flags=re.I):
        return None
    match = _workspace_file_path_match(raw)
    if not match:
        return None
    path, span = match
    overwrite = bool(re.search(r"\b(overwrite|replace|update|badal|dobara)\b", lower, flags=re.I))
    return _route(
        "shell_workspace_tools:create_workspace_file_tool",
        {"path": path, "content": _workspace_file_content(raw, span), "overwrite": overwrite},
        confidence=0.93,
    )


def _workspace_file_read_route(raw: str, lower: str) -> dict[str, Any] | None:
    if re.search(
        r"\b(list|show|dikha|dikhao)\b.*\b(workspace|files?|file list)\b|\b(workspace|files?)\b.*\b(list|dikha|dikhao)\b",
        lower,
        flags=re.I,
    ):
        return _route("shell_workspace_tools:list_workspace_files_tool", {"limit": 200}, confidence=0.92)
    if re.search(r"\b(workspace status|workspace info|workspace path)\b", lower, flags=re.I):
        return _route("shell_workspace_tools:workspace_status_tool", confidence=0.88)
    if not re.search(r"\b(read|open|show|dikha|dikhao|view|dekh|dekho)\b", lower, flags=re.I):
        return None
    match = _workspace_file_path_match(raw)
    if not match:
        return None
    path, _span = match
    suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    if suffix in {"com", "org", "net", "io", "dev", "ai"} and not re.search(r"\b(file|workspace)\b", lower):
        return None
    return _route("shell_workspace_tools:read_workspace_file_tool", {"path": path}, confidence=0.92)


def _research_and_email_route(raw: str, lower: str) -> dict[str, Any] | None:
    """Detect 'research X and email to Y' compound commands."""
    has_research = re.search(
        r"\b(deep\s*research|deep\s*recerch|deep\s*reserch|research\s+kar|research\s+karke|research\s+kar\s+ke|"
        r"research\s+kardo|deep\s+research|deep\s+reserch|recerch|reserch)\b",
        lower,
        flags=re.I,
    )
    if not has_research:
        return None

    has_recipient = re.search(_EMAIL_TOKEN, raw, flags=re.I)
    if not has_recipient:
        return None

    has_email_intent = re.search(
        r"\b(email\s+kar|mail\s+kar|bhejdo|bhejo|bhejna|bhej\s+do|bhej|email\s+kardo|send|email\s+karo)\b",
        lower,
        flags=re.I,
    )
    if not has_email_intent:
        # If there's a recipient email in the message along with research, still treat as compound
        if not has_recipient:
            return None

    recipient = has_recipient.group(0)

    # Extract topic: remove the email address, research verbs, email send verbs
    topic = raw
    topic = re.sub(_EMAIL_TOKEN, " ", topic, flags=re.I)
    topic = re.sub(
        r"\b(deep\s*research|deep\s*recerch|deep\s*reserch|research|recerch|reserch|karke|kar\s+ke|kardo|kar\s+do|karo|"
        r"email|mail|bhejdo|bhejo|bhej\s+do|bhej|send|pe|par|mujhe|mojhe|main|ko|ok|please|pls|"
        r"shell|aur|aur\s+han|or\s+han|or|han)\b",
        " ",
        topic,
        flags=re.I,
    )
    topic = _clean(topic)

    if not topic or len(topic) < 2:
        return None

    return _route(
        "shell_email_tool:research_and_email_tool",
        {"topic": topic, "recipient": recipient},
        confidence=0.93,
    )


def _email_route(raw: str, lower: str) -> dict[str, Any] | None:
    has_email_word = re.search(r"\b(email|mail|smtp)\b", lower, flags=re.I)
    has_recipient = re.search(_EMAIL_TOKEN, raw, flags=re.I)
    has_send_intent = re.search(r"\b(send|bhejo|bhejna|mail\s+kar|email\s+kar|forward)\b", lower, flags=re.I)
    if not has_email_word and not (has_recipient and has_send_intent):
        return None

    if not has_send_intent and re.search(
        r"\b(smtp\s+test|email\s+test|login\s+test|auth\s+test|diagnose|diagnostic)\b",
        lower,
        flags=re.I,
    ):
        return _route("shell_email_tool:email_setup_status_tool", confidence=0.94)

    if re.search(
        r"\b(status|setup|configure|config|working|kaise|kyun|why|nahi|nai|not\s+working|can\s+shell|send\s+nahi)\b",
        lower,
        flags=re.I,
    ):
        return _route("shell_email_tool:email_setup_status_tool", confidence=0.94)

    if not has_send_intent:
        return None

    recipient_match = has_recipient
    if not recipient_match:
        return None

    attachments = []
    for quoted in re.finditer(r"[\"'`]([^\"'`]+?\.(?:" + _EMAIL_ATTACHMENT_EXTS + r"))[\"'`]", raw, flags=re.I):
        attachments.append(_strip_quotes(quoted.group(1)))
    if not attachments:
        for match in re.finditer(
            r"\b(?:attach|attachment|file|pdf|document)\s+([A-Za-z0-9][A-Za-z0-9 ._/\-]{0,180}\.(?:"
            + _EMAIL_ATTACHMENT_EXTS
            + r"))",
            raw,
            flags=re.I,
        ):
            attachments.append(_strip_quotes(match.group(1)))

    if re.search(r"\b(pdf|attachment|attach|document)\b", lower, flags=re.I) and not attachments:
        return _route("shell_email_tool:email_setup_status_tool", confidence=0.86)

    subject = "Shell AI message"
    subject_match = re.search(
        r"\b(?:subject|sub)\b\s*[:=-]?\s*(.+?)(?:\s+\b(?:body|message|msg|text|content)\b\s*[:=-]?\s*|$)",
        raw,
        flags=re.I | re.S,
    )
    if subject_match:
        subject = _strip_quotes(subject_match.group(1))
    elif attachments:
        subject = attachments[0].split("/")[-1].split("\\")[-1]

    body = ""
    body_match = re.search(
        r"\b(?:body|message|msg|text|content)\b\s*[:=-]?\s*(.+)$",
        raw,
        flags=re.I | re.S,
    )
    if body_match:
        body = _strip_quotes(body_match.group(1))

    if not body:
        body = _strip_quotes(raw[recipient_match.end():])
        body = re.sub(r"^\s*(?:subject|sub)\b\s*[:=-]?\s*.+$", "", body, flags=re.I | re.S).strip()
    if not body and attachments:
        body = "Attached file."

    if not subject_match and not body_match:
        test_body = re.sub(r"\b(to|ko|par|pe|email|mail|send|bhejo|bhejna|kar|do|yaar|fast|please|pls|ko\s+mail|ko\s+email|bhej|bhejdo|bhejo|bhej\s+do)\b", "", body.lower()).strip()
        if len(test_body) < 5:
            return None

    return _route(
        "shell_email_tool:send_email_tool",
        {
            "recipient": recipient_match.group(0),
            "subject": subject,
            "body": body,
            "attachments": ",".join(dict.fromkeys(attachments)),
        },
        confidence=0.91,
    )


def _telegram_route(raw: str, lower: str) -> dict[str, Any] | None:
    if not re.search(r"\b(telegram|teligram|telegram bot|bot)\b", lower, flags=re.I):
        return None
    if re.search(r"\b(status|state|chal raha|active|running)\b", lower, flags=re.I):
        return _route("shell_telegram:telegram_bot_status", confidence=0.92)
    if re.search(r"\b(start|chalu|chalao|activate|run)\b", lower, flags=re.I):
        return _route("shell_telegram:start_telegram_bot", confidence=0.9)
    if re.search(r"\b(stop|band|deactivate|close)\b", lower, flags=re.I):
        return _route("shell_telegram:stop_telegram_bot", confidence=0.9)
    return None


def _code_generation_route(raw: str, lower: str) -> dict[str, Any] | None:
    """Route generic code-writing asks to Shell's developer agent."""
    if re.search(r"\b(qr\s*code|barcode|verification\s+code|otp|pin\s+code|error\s+code)\b", lower, flags=re.I):
        return None
    direct_code_phrase = re.search(
        r"\b(?:code|coding|script|program|function|class|component|algorithm)\s+"
        r"(?:likho|likh\s+do|banao|bana|banado|banaao|write|create|make|build|generate|develop)\b",
        lower,
        flags=re.I,
    ) or re.search(
        r"\b(?:write|create|make|build|generate|develop|code|banao|bana|banado|banaao|bana\s+do)\s+"
        r"(?:a\s+|an\s+|the\s+)?(?:code|script|program|function|class|component|algorithm)\b",
        lower,
        flags=re.I,
    )
    if not direct_code_phrase and not (
        re.search(_CODE_ACTION_RE, lower, flags=re.I)
        and re.search(_CODE_LANGUAGE_RE, lower, flags=re.I)
    ):
        return None
    return _route(
        "shell_agents:developer_agent_tool",
        {"task": _strip_quotes(raw)},
        kind="agent",
        confidence=0.89,
    )


def _autonomous_route(raw: str, lower: str) -> dict[str, Any] | None:
    resume_match = re.match(
        r"^(?:autonomous|autonomy|auto|agentic)\s+resume\s+([a-zA-Z0-9_-]{6,})$|^resume\s+(?:autonomous|autonomy|agentic)\s+([a-zA-Z0-9_-]{6,})$",
        raw,
        flags=re.I,
    )
    if resume_match:
        task_id = _strip_quotes(resume_match.group(1) or resume_match.group(2))
        return _route(
            "shell_autonomous_agent:autonomous_goal_resume_tool",
            {"task_id": task_id, "dry_run": False, "learn": True, "verify": True, "auto_repair": True},
            confidence=0.93,
        )

    if re.search(
        r"\b(list|show|dikha|dikhao)\b.*\b(autonomous|autonomy|agentic|learned)\b.*\b(skills?|kaam|tasks?)\b",
        lower,
        flags=re.I,
    ) or re.search(r"\b(learned|autonomous|autonomy|agentic)\s+skills?\b", lower, flags=re.I):
        return _route("shell_autonomous_agent:autonomous_skill_list_tool", {"query": "", "limit": 10}, confidence=0.94)

    if re.search(
        r"\b(autonomous|autonomy|agentic)\s+(status|history|run\s+history|runs|report|latest)\b",
        lower,
        flags=re.I,
    ) or re.search(r"\b(status|history|run\s+history|runs|report|latest)\s+(of\s+)?(autonomous|autonomy|agentic)\b", lower, flags=re.I):
        return _route("shell_autonomous_agent:autonomous_goal_status_tool", {"task_id": "", "limit": 5}, confidence=0.93)

    dry_patterns = (
        r"^(?:autonomous|autonomy|auto|agentic)\s+(?:plan|preview|dry\s*run)\s+(.+)$",
        r"^agent\s+(?:plan|preview|dry\s*run)\s+(.+)$",
    )
    for pattern in dry_patterns:
        match = re.match(pattern, raw, flags=re.I | re.S)
        if match:
            goal = _strip_quotes(match.group(1))
            if goal:
                return _route(
                    "shell_autonomous_agent:autonomous_goal_run_tool",
                    {"goal": goal, "dry_run": True, "learn": False, "verify": False, "auto_repair": False},
                    confidence=0.93,
                )

    run_patterns = (
        r"^(?:autonomous|autonomy|auto|agentic)\s+(?:run|execute|do|handle|perform|task|goal)\s+(.+)$",
        r"^agent\s+(?:run|execute|do|handle|perform)\s+(.+)$",
        r"^(?:hard|complex)\s+task\s*[:=-]?\s*(.+)$",
        r"^(?:shell\s+)?(?:khud|apne\s+aap|automatically)\s+(.+)$",
    )
    for pattern in run_patterns:
        match = re.match(pattern, raw, flags=re.I | re.S)
        if match:
            goal = _strip_quotes(match.group(1))
            if goal:
                return _route(
                    "shell_autonomous_agent:autonomous_goal_run_tool",
                    {"goal": goal, "dry_run": False, "learn": True, "verify": True, "auto_repair": True},
                    confidence=0.93,
                )
    return None


def _desktop_folder_name(raw: str) -> str:
    patterns = (
        r"\bfolder\s+(?:called|named|naam\s+ka|naam\s+se)?\s*[\"'‘’“”]?([^\"'‘’“”]+?)[\"'‘’“”]?\s+(?:on|par|pe|mein|main)\s+(?:desktop|dextop)\b",
        r"\b(?:create|make|banao|bana|banado|banaao)\s+(?:a\s+)?folder\s+(?:called|named|naam\s+ka|naam\s+se)?\s*[\"'‘’“”]?(.+?)[\"'‘’“”]?\s*$",
    )
    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.I | re.S)
        if not match:
            continue
        name = match.group(1)
        name = re.sub(r"\b(?:and|or|aur|open|kholo|khol\s+do|osse|use|it|folder|desktop|dextop)\b.*$", "", name, flags=re.I).strip()
        return _strip_quotes(name)
    return ""


def _windows_workflow_route(raw: str, lower: str) -> dict[str, Any] | None:
    if re.search(r"\bdownloads?\b", lower) and re.search(r"\b(audit|clean|cleanup|clean\s+up|safe|safely|review)\b", lower):
        return _route(
            "shell_windows_workflows:organize_downloads_setups_pdfs_tool",
            {"zip_folder": "Setups", "pdf_folder": "PDFs", "dry_run": True},
            confidence=0.94,
        )

    if re.search(r"\bdownloads?\b", lower) and re.search(r"\b(zip|zips|pdf|pdfs|organize|sort|move)\b", lower):
        return _route(
            "shell_windows_workflows:organize_downloads_setups_pdfs_tool",
            {"zip_folder": "Setups", "pdf_folder": "PDFs", "dry_run": False},
            confidence=0.91,
        )

    if re.search(r"\b(?:create|make|banao|bana|banado|banaao)\b", lower) and re.search(r"\bfolder\b", lower) and re.search(r"\b(desktop|dextop)\b", lower):
        folder_name = _desktop_folder_name(raw) or "Shell Folder"
        return _route(
            "shell_windows_workflows:create_desktop_folder_tool",
            {"folder_name": folder_name, "open_folder": bool(re.search(r"\b(open|kholo|khol|launch)\b", lower))},
            confidence=0.93,
        )

    if re.search(r"\bstarting\s+work\b|\bwork\s+session\b|\bkaam\s+start\b", lower) and re.search(r"\b(vs\s*code|vscode|chrome|spotify)\b", lower):
        return _route(
            "shell_windows_workflows:open_work_session_tool",
            {
                "chrome_urls": ["https://github.com/", "http://localhost:5173/", "http://localhost:3000/"],
                "include_vscode": bool(re.search(r"\b(vs\s*code|vscode)\b", lower)),
                "include_chrome": "chrome" in lower,
                "include_spotify": "spotify" in lower,
            },
            confidence=0.89,
        )

    if re.search(r"\btask\s*manager\b", lower) and re.search(r"\b(high\s*cpu|cpu|background|close|kill|band)\b", lower):
        return _route("shell_windows_workflows:open_task_manager_high_cpu_review_tool", {"open_task_manager": True}, confidence=0.91)

    if re.search(r"\b(focus\s+assist|do\s+not\s+disturb|dnd|focus)\b", lower) and re.search(r"\b(turn\s+on|enable|start|on|chalu|chalu\s+karo)\b", lower):
        minutes_match = re.search(r"\b(\d{1,3})\s*(?:minutes?|mins?|minute|m)\b", lower)
        minutes = int(minutes_match.group(1)) if minutes_match else 30
        return _route("shell_windows_workflows:open_focus_assist_tool", {"minutes": minutes}, confidence=0.89)

    if re.search(r"\b(?:whats\s*app|whatsapp)\b", lower) and "spotify" in lower and re.search(r"\b(side\s+by\s+side|together|saath|open|launch)\b", lower):
        return _route("shell_windows_workflows:open_whatsapp_spotify_side_by_side_tool", confidence=0.91)

    if re.search(r"\bphotos?\b", lower) and re.search(r"\b(slideshow|slide\s*show|screenshots?|last\s+screenshots?)\b", lower):
        return _route("shell_windows_workflows:open_recent_screenshots_slideshow_tool", confidence=0.9)

    if re.search(r"\b(brightness|night\s+light|nightlight)\b", lower) and re.search(r"\b(reduce|lower|kam|enable|turn\s+on|on|chalu)\b", lower):
        level = 40
        percent_match = re.search(r"\b(\d{1,3})\s*%", lower)
        if percent_match:
            level = max(0, min(100, int(percent_match.group(1))))
        return _route("shell_windows_workflows:screen_comfort_tool", {"brightness_level": level, "enable_night_light": True}, confidence=0.9)

    return None


def route_natural_command(text: str) -> dict[str, Any] | None:
    """Return a backend route for a common natural chat/voice command."""
    raw = _strip_shell_address(text)
    if not raw:
        return None
    lower = raw.lower()

    windows_workflow = _windows_workflow_route(raw, lower)
    if windows_workflow:
        return windows_workflow

    if re.search(
        r"\b(computer|desktop|screen)\s+(control|automation|readiness|status|health|diagnostics?|capabilit(?:y|ies))\b",
        lower,
    ) or re.search(
        r"\b(control|automation|readiness|status|health|diagnostics?)\s+(of\s+)?(computer|desktop|screen)\b",
        lower,
    ) or re.search(r"\b(can\s+shell|shell)\s+control\s+(my\s+)?(computer|desktop|pc|mac|windows)\b", lower):
        return _route(
            "shell_computer_control:computer_control_status_tool",
            {"include_catalog": True},
            confidence=0.95,
        )

    desktop_agent_match = re.match(
        r"^(?:desktop|computer|screen)\s+agent\s*(?:plan|preview|control|:)?\s*(.+)$",
        raw,
        flags=re.I | re.S,
    )
    if desktop_agent_match:
        return _route(
            "shell_computer_control:desktop_agent_plan_tool",
            {"goal": _strip_quotes(desktop_agent_match.group(1))},
            confidence=0.93,
        )

    if re.search(
        r"\b(platform|ai\s*os|shell|runtime|system)\s+(status|health|readiness|diagnostics?|dashboard)\b",
        lower,
    ) or re.search(r"\b(status|health|readiness|diagnostics?)\s+(of\s+)?(platform|ai\s*os|shell|runtime)\b", lower):
        return _route(
            "shell_platform_supervisor:shell_platform_status_tool",
            {"include_catalog": True},
            confidence=0.95,
        )

    if re.search(r"\b(list|show|dikha|dikhao)\s+(all\s+)?agents\b", lower) or "kaun se agents" in lower:
        return _route("shell_agents:list_agents_tool", kind="agent", confidence=0.95)
    if re.search(r"\b(list|show|dikha|dikhao)\s+(all\s+)?tools\b", lower) or "kaun se tools" in lower:
        return _route("shell_agent_tools:list_all_tools", confidence=0.95)
    if re.search(r"\b(tool|tools)\s+(health|status|readiness)\b", lower):
        return _route("shell_agent_tools:system_health_dashboard", confidence=0.9)
    if re.search(
        r"\b(voice|speech|tts|audio|microphone|mic|speaker)\s+(status|health|readiness|check|working|ready)\b",
        lower,
    ) or re.search(
        r"\b(status|health|readiness|check)\s+(of\s+)?(voice|speech|tts|audio|microphone|mic|speaker)\b",
        lower,
    ) or re.search(r"\b(voice|audio|sound|speaker)\b.*\b(aa\s+rahi|aarahi|aarahe|sunai|sunaai|working|chal|chalu)\b", lower):
        return _route("shell_neural_voice:shell_streaming_voice_status_tool", confidence=0.91)

    telegram = _telegram_route(raw, lower)
    if telegram:
        return telegram

    # Only show Gmail status when user genuinely asks about setup/config/inbox reading
    # NOT when they are trying to send an email (send/bhejo/email kar etc.)
    # Also NOT when 'gmail' appears only as part of an email address like user@gmail.com
    _gmail_standalone = re.search(r"(?<![\w@])gmail(?!\.com[^\s]|\s*\.com[^\s])", lower, flags=re.I)
    _gmail_in_address = bool(re.search(r"[A-Za-z0-9._%+\-]+@gmail\.com", raw, flags=re.I))
    _gmail_as_product = bool(_gmail_standalone) or (not _gmail_in_address and "gmail" in lower)
    if _gmail_as_product and not _gmail_in_address and not re.search(
        r"\b(send|bhejo|bhejna|bhejdo|bhej|email\s+kar|mail\s+kar|forward|compose)\b",
        lower,
        flags=re.I,
    ) and re.search(
        r"\b(status|setup|configured|configure|connect|inbox|read|monitor|imap|api|integration|kaise|working|new|emails?|download|summary|summarize|summarise|invoice|payment|attachments?)\b",
        lower,
        flags=re.I,
    ):
        return _route("shell_email_tool:email_setup_status_tool", {"gmail_request": raw}, confidence=0.9)

    # Compound: research + email in one go (must check before plain email and research routes)
    research_email = _research_and_email_route(raw, lower)
    if research_email:
        return research_email

    email = _email_route(raw, lower)
    if email:
        return email

    autonomous = _autonomous_route(raw, lower)
    if autonomous:
        return autonomous

    agent_match = re.match(
        r"^(?:ask|use|run|call)?\s*([a-z ]+?)\s+agent\s*(?:to|for|se|:)?\s*(.*)$",
        lower,
        flags=re.I | re.S,
    )
    if agent_match:
        label = _clean(agent_match.group(1))
        task = _strip_quotes(raw[agent_match.end(1):])
        task = re.sub(r"^agent\s*(?:to|for|se|:)?\s*", "", task, flags=re.I).strip()
        if label in _AGENTS and task:
            tool_id, param = _AGENTS[label]
            return _route(tool_id, {param: task}, kind="agent", confidence=0.9)

    if re.search(
        r"\b(deep\s*(?:research|recerch)|research|recerch|fact\s*check|fact-check|multi\s*source|multi-source)\b",
        lower,
    ):
        task = re.sub(
            r"^\s*(?:deep\s*)?(?:research|recerch|fact\s*check|fact-check)\s*"
            r"(?:karo|kar|karna|about|on|for|ke\s+bare\s+mein|ke\s+barre\s+main|ke\s+bare\s+main|:)?\s*",
            "",
            raw,
            flags=re.I | re.S,
        ).strip()
        task = re.sub(
            r"\s+(?:par|pe|ke\s+bare\s+mein|ke\s+barre\s+main|ke\s+bare\s+main)\s+"
            r"(?:deep\s*)?(?:research|recerch|fact\s*check|fact-check)\s*(?:karo|kar|karna)?\s*$",
            "",
            task,
            flags=re.I | re.S,
        ).strip()
        return _route(
            "shell_agents:research_agent_tool",
            {"task": _strip_quotes(task) or _strip_quotes(raw)},
            kind="agent",
            confidence=0.88,
        )

    image_route = _image_generation_route(raw, lower)
    if image_route:
        return image_route

    standalone_html = _standalone_html_file_route(raw, lower)
    if standalone_html:
        return standalone_html

    user_file_save = _user_file_save_route(raw, lower)
    if user_file_save:
        return user_file_save

    if re.search(_CREATION_VERB_RE, lower) and re.search(r"\b(website|webpage|web\s+page|landing\s+page|site)\b", lower):
        return _route(
            "shell_code_engine:create_fullstack_app_tool",
            {
                "project_name": _project_slug_from_text(raw, "shell_site"),
                "app_type": _build_brief_from_text(raw, kind="website"),
            },
            confidence=0.91,
        )

    if re.search(_CREATION_VERB_RE, lower) and re.search(_GAME_INTENT_RE, lower):
        return _route(
            "shell_game_builder:build_game_tool",
            {"game": _game_name_from_text(raw), "custom_features": ""},
            confidence=0.93,
        )

    if re.search(_CREATION_VERB_RE, lower) and re.search(
        r"\b(app|application|software|dashboard|tool|todo|to\s*do|crm|tracker|manager)\b",
        lower,
    ):
        return _route(
            "shell_code_engine:create_fullstack_app_tool",
            {
                "project_name": _project_slug_from_text(raw, "shell_app"),
                "app_type": _build_brief_from_text(raw, kind="app"),
            },
            confidence=0.9,
        )

    workspace_read = _workspace_file_read_route(raw, lower)
    if workspace_read:
        return workspace_read

    workspace_create = _workspace_file_create_route(raw, lower)
    if workspace_create:
        return workspace_create

    code_generation = _code_generation_route(raw, lower)
    if code_generation:
        return code_generation

    if lower.startswith(("search google", "google search", "google ")):
        query = re.sub(r"^(search\s+google|google\s+search|google)\s*(for)?\s*", "", raw, flags=re.I).strip()
        url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
        return _route("shell_desktop_tools:open_url_tool", {"url": url}, confidence=0.9)

    if re.search(
        r"\b(play|chalao|chala|bajao|baja|lagao|laga|sunao|suna)\b",
        lower,
    ) and re.search(r"\b(song|gaana|gana|music|video)\b", lower):
        query = _youtube_media_query(raw, lower)
        return _route(
            "shell_browser_CTRL:play_youtube_video",
            {"query": query, "number": 1},
            confidence=0.9,
        )

    if re.search(r"\b(youtube|you\s*tube)\b", lower) and re.search(
        r"\b(play|chalao|chala|bajao|baja|lagao|laga|sunao|suna|song|gaana|gana|music|video)\b",
        lower,
    ):
        query = _youtube_media_query(raw, lower)
        return _route(
            "shell_browser_CTRL:play_youtube_video",
            {"query": query, "number": 1},
            confidence=0.92,
        )

    if lower.startswith(("search youtube", "youtube search", "youtube ")):
        query = re.sub(r"^(search\s+youtube|youtube\s+search|youtube)\s*(for)?\s*", "", raw, flags=re.I).strip()
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
        return _route("shell_desktop_tools:open_url_tool", {"url": url}, confidence=0.9)

    known_site = _known_website_open_route(raw, lower)
    if known_site:
        return known_site

    click_match = re.match(r"^(?:click|tap)\s+(?:at\s+)?(-?\d+)\s*,?\s+(-?\d+)$", raw, flags=re.I)
    if click_match:
        return _route(
            "shell_desktop_tools:desktop_click_tool",
            {"x": int(click_match.group(1)), "y": int(click_match.group(2)), "button": "left"},
            confidence=0.92,
        )

    type_match = re.match(r"^(?:type|write)\s+(.+)$", raw, flags=re.I | re.S)
    if type_match:
        return _route("shell_desktop_tools:desktop_type_tool", {"text": _strip_quotes(type_match.group(1)), "clear": False}, confidence=0.88)

    shortcut_match = re.match(r"^(?:press|hotkey|shortcut)\s+(.+)$", raw, flags=re.I | re.S)
    if shortcut_match:
        return _route("shell_desktop_tools:desktop_shortcut_tool", {"keys": _strip_quotes(shortcut_match.group(1))}, confidence=0.88)

    if re.search(r"\b(take|capture)\s+(a\s+)?screenshot\b|\bscreenshot\b", lower):
        return _route("shell_screenshot:take_screenshot_tool", {"filename": "shell_screenshot"}, confidence=0.9)

    app_match = re.match(r"^(?:open|launch|start)\s+(?:app\s+)?([a-zA-Z0-9 ._-]+)$", raw, flags=re.I)
    if app_match and not re.search(r"\b(url|https?://)\b", lower):
        return _route("shell_window_CTRL:open_app", {"app_title": _strip_quotes(app_match.group(1))}, confidence=0.88)

    close_app_match = re.match(
        r"^(?:close|quit|band|stop)\s+(?:app\s+)?([a-zA-Z0-9 ._-]+)$",
        raw,
        flags=re.I,
    )
    if close_app_match:
        return _route(
            "shell_window_CTRL:close_app",
            {"window_title": _strip_quotes(close_app_match.group(1))},
            confidence=0.88,
        )

    ps_match = re.match(r"^(?:run\s+)?(?:powershell|terminal|shell\s+command|command)\s+(.+)$", raw, flags=re.I | re.S)
    if ps_match:
        return _route("shell_terminal:run_command_tool", {"command": _strip_quotes(ps_match.group(1))}, confidence=0.86)

    npm_test_match = re.match(r"^(?:shell,\s*)?(?:run\s+)?npm\s+test\b.*$", raw, flags=re.I | re.S)
    if npm_test_match:
        return _route(
            "shell_terminal:run_command_tool",
            {"command": "npm test", "requires_approval": True, "permission_scope": "project"},
            confidence=0.91,
        )

    if re.match(r"^(?:shell,\s*)?(?:show\s+me\s+)?(?:git\s+status|what\s+changed(?:\s+today)?)\b.*$", raw, flags=re.I | re.S):
        return _route(
            "shell_terminal:run_command_tool",
            {"command": "git status --short", "requires_approval": True, "permission_scope": "project"},
            confidence=0.9,
        )

    if re.search(r"\b(open|show|tail|read)\b.*\b(latest\s+)?logs?\b|\b(latest\s+logs?)\b", lower, flags=re.I):
        return _route(
            "shell_terminal:run_command_tool",
            {
                "command": "find . -type f \\( -name '*.log' -o -name '*log*.txt' \\) -maxdepth 4 -print | head -20",
                "requires_approval": True,
                "permission_scope": "project",
            },
            confidence=0.86,
        )

    convert_match = re.match(
        r"^(?:convert\s+)?(-?\d+(?:\.\d+)?)\s*([a-zA-Z_]+)\s+(?:to|in)\s+([a-zA-Z_]+)$",
        raw,
        flags=re.I,
    )
    if convert_match:
        return _route(
            "shell_calculator:unit_convert_tool",
            {
                "value": _number(convert_match.group(1)),
                "from_unit": _unit_alias(convert_match.group(2)),
                "to_unit": _unit_alias(convert_match.group(3)),
            },
            confidence=0.94,
        )

    percent_match = re.match(r"^(?:what\s+is\s+)?(-?\d+(?:\.\d+)?)\s*%\s+of\s+(-?\d+(?:\.\d+)?)$", raw, flags=re.I)
    if percent_match:
        return _route(
            "shell_calculator:percentage_tool",
            {"value": _number(percent_match.group(2)), "percentage": _number(percent_match.group(1))},
            confidence=0.94,
        )

    calc_match = re.match(r"^(?:calculate|calc|solve|evaluate|math|what\s+is)\s+(.+)$", raw, flags=re.I | re.S)
    if calc_match and _looks_like_math(calc_match.group(1)):
        return _route("shell_calculator:calculate_tool", {"expression": calc_match.group(1).strip()}, confidence=0.94)
    if _looks_like_math(raw) and len(raw) <= 120:
        return _route("shell_calculator:calculate_tool", {"expression": raw}, confidence=0.82)

    stats_match = re.match(r"^(?:stats|statistics|mean|median)\s+(?:for|of)?\s*(.+)$", raw, flags=re.I | re.S)
    if stats_match:
        return _route("shell_calculator:statistics_tool", {"numbers": stats_match.group(1).strip()}, confidence=0.88)

    hash_match = re.match(r"^(?:(md5|sha1|sha256|sha512|sha3_256|sha3_512)\s+)?hash\s+(.+?)(?:\s+(?:with|using)\s+(md5|sha1|sha256|sha512|sha3_256|sha3_512))?$", raw, flags=re.I | re.S)
    if hash_match:
        algorithm = (hash_match.group(1) or hash_match.group(3) or "sha256").lower()
        text_to_hash = re.sub(r"^(?:of|for)\s+", "", hash_match.group(2).strip(), flags=re.I)
        return _route("shell_hash:hash_string_tool", {"text": _strip_quotes(text_to_hash), "algorithm": algorithm}, confidence=0.91)

    json_text = _json_payload(raw)
    if json_text and re.search(r"\b(format|pretty|beautify)\s+json\b|\bjson\s+(format|pretty|beautify)\b", lower):
        return _route("shell_json_tools:json_format_tool", {"json_string": json_text}, confidence=0.95)
    if json_text and re.search(r"\b(validate|check)\s+json\b|\bjson\s+(validate|check)\b", lower):
        return _route("shell_json_tools:json_validate_tool", {"json_string": json_text}, confidence=0.95)

    if re.search(r"\b(count|gino|kitne)\b.*\b(words?|chars?|characters?|lines?|sentences?|paragraphs?)\b|\bword\s+count\b", lower):
        payload = _after(raw, ("in", "of", "for", "text"))
        return _route("shell_text_tools:text_count_tool", {"text": payload}, confidence=0.9)

    reverse_match = re.match(r"^(?:reverse|ulta\s+kar|palat)\s+(?:text\s+)?(.+)$", raw, flags=re.I | re.S)
    if reverse_match:
        return _route("shell_text_tools:text_reverse_tool", {"text": _strip_quotes(reverse_match.group(1))}, confidence=0.88)

    case_match = re.match(
        r"^(?:convert\s+)?(.+?)\s+(?:to|in)\s+(upper|uppercase|lower|lowercase|title|camel|snake|kebab|pascal|constant)(?:\s+case)?$",
        raw,
        flags=re.I | re.S,
    )
    if not case_match:
        case_match = re.match(
            r"^(upper|uppercase|lower|lowercase|title|camel|snake|kebab|pascal|constant)(?:\s+case)?\s+(.+)$",
            raw,
            flags=re.I | re.S,
        )
        if case_match:
            case_type = case_match.group(1).lower().replace("uppercase", "upper").replace("lowercase", "lower")
            return _route("shell_text_tools:text_case_tool", {"text": _strip_quotes(case_match.group(2)), "case_type": case_type}, confidence=0.9)
    if case_match:
        case_type = case_match.group(2).lower().replace("uppercase", "upper").replace("lowercase", "lower")
        return _route("shell_text_tools:text_case_tool", {"text": _strip_quotes(case_match.group(1)), "case_type": case_type}, confidence=0.9)

    encode_match = re.match(r"^(encode|decode)\s+(.+?)\s+(?:as|from|with|using)\s+(base64|url|html|hex)$", raw, flags=re.I | re.S)
    if encode_match:
        action = encode_match.group(1).lower()
        tool_id = "shell_text_tools:text_encode_tool" if action == "encode" else "shell_text_tools:text_decode_tool"
        return _route(tool_id, {"text": _strip_quotes(encode_match.group(2)), "encoding": encode_match.group(3).lower()}, confidence=0.9)

    translate_match = re.match(r"^(?:translate|anuvad)\s+(.+?)\s+(?:to|in)\s+([a-zA-Z -]+)$", raw, flags=re.I | re.S)
    if translate_match:
        return _route(
            "shell_translator:translate_text_tool",
            {"text": _strip_quotes(translate_match.group(1)), "target_lang": translate_match.group(2).strip()},
            confidence=0.86,
        )

    if re.search(r"\b(system specs|system info|pc specs|computer specs)\b", lower):
        return _route("shell_system_pro:get_system_specs_tool", confidence=0.88)
    if re.search(r"\b(battery|battery status)\b", lower):
        return _route("shell_system_pro:get_battery_status_tool", confidence=0.86)
    if re.search(r"\b(running processes|process list|show processes)\b", lower):
        return _route("shell_system_pro:get_running_processes_tool", confidence=0.86)
    if re.search(r"\b(installed apps|installed programs|apps installed)\b", lower):
        return _route("shell_system_pro:get_installed_apps_tool", confidence=0.86)
    if re.search(r"\b(system uptime|uptime)\b", lower):
        return _route("shell_system_pro:get_system_uptime_tool", confidence=0.86)

    dice_match = re.match(r"^(?:roll\s+)?(?:(\d+)\s*)?d(?:ice)?\s*(\d+)?$", lower)
    if dice_match or "roll dice" in lower:
        num_dice = int((dice_match.group(1) if dice_match else "") or 1)
        sides = int((dice_match.group(2) if dice_match else "") or 6)
        return _route("shell_games:dice_roll_tool", {"num_dice": num_dice, "sides": sides}, confidence=0.88)
    if "coin flip" in lower or "flip coin" in lower:
        call = "heads" if "heads" in lower else ("tails" if "tails" in lower else "")
        return _route("shell_games:coin_flip_tool", {"call": call}, confidence=0.88)

    return None
