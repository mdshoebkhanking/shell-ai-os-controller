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


def _looks_like_math(expr: str) -> bool:
    expr = expr.strip()
    if not re.search(r"\d", expr):
        return False
    return bool(re.search(r"[+\-*/%^()]|\b(sqrt|sin|cos|tan|log|factorial|pow)\b", expr, flags=re.I))


def _number(value: str) -> float:
    return float(str(value).replace(",", "").strip())


_WORKSPACE_PATH_TOKEN = r"[A-Za-z0-9][A-Za-z0-9._/-]{0,180}\.[A-Za-z0-9]{1,16}"
_EMAIL_TOKEN = r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}"
_EMAIL_ATTACHMENT_EXTS = "pdf|docx?|xlsx?|csv|txt|md|png|jpe?g|zip"


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
        return _route("shell_email_tool:email_smtp_login_test_tool", confidence=0.94)

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
        return _route("shell_email_tool:email_setup_status_tool", confidence=0.82)

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


def route_natural_command(text: str) -> dict[str, Any] | None:
    """Return a backend route for a common natural chat/voice command."""
    raw = _strip_shell_address(text)
    if not raw:
        return None
    lower = raw.lower()

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

    telegram = _telegram_route(raw, lower)
    if telegram:
        return telegram

    email = _email_route(raw, lower)
    if email:
        return email

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

    workspace_read = _workspace_file_read_route(raw, lower)
    if workspace_read:
        return workspace_read

    workspace_create = _workspace_file_create_route(raw, lower)
    if workspace_create:
        return workspace_create

    if lower.startswith(("search google", "google search", "google ")):
        query = re.sub(r"^(search\s+google|google\s+search|google)\s*(for)?\s*", "", raw, flags=re.I).strip()
        url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
        return _route("shell_desktop_tools:open_url_tool", {"url": url}, confidence=0.9)

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

    image_match = re.match(r"^(?:generate|create|make)\s+(?:an?\s+)?image\s+(?:of|for|:)?\s*(.+)$", raw, flags=re.I | re.S)
    if image_match:
        return _route("shell_image_ai:generate_image_tool", {"description": _strip_quotes(image_match.group(1))}, confidence=0.88)

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
                "from_unit": convert_match.group(2),
                "to_unit": convert_match.group(3),
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
