"""Make/build mode abstraction for Shell local and cloud-enhanced outputs."""

from __future__ import annotations

import re
from enum import Enum
from typing import Callable

from shell_task_mode import classify_task_mode, online_full_version_ready


class TaskMode(str, Enum):
    LOCAL_BASIC = "LOCAL_BASIC"
    CLOUD_PRO = "CLOUD_PRO"


def detect_make_mode(command: str, *, route_tool: str = "") -> TaskMode:
    decision = classify_task_mode(command, route_tool=route_tool)
    if decision.requires_online and online_full_version_ready():
        return TaskMode.CLOUD_PRO
    return TaskMode.LOCAL_BASIC


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def local_make_pdf(title: str, source_text: str, *, summary: bool = False) -> str:
    """Return reliable Level 1 PDF body text; rendering stays in workspace tools."""
    clean_title = _clean_text(title) or "Shell Summary"
    clean_source = _clean_text(source_text)
    if not clean_source:
        clean_source = "No source text was provided."
    if summary:
        sentences = re.split(r"(?<=[.!?])\s+", clean_source)
        points = [sentence.strip() for sentence in sentences if sentence.strip()][:5]
        if len(points) <= 1:
            words = clean_source.split()
            points = [" ".join(words[index : index + 24]) for index in range(0, min(len(words), 120), 24)]
        bullets = "\n".join(f"- {point}" for point in points if point)
        return f"{clean_title}\n\nSummary\n{bullets or '- No summary points available.'}\n\nSource Notes\n{clean_source[:1200]}"
    return f"{clean_title}\n\n{clean_source}"


def cloud_make_pdf(
    title: str,
    source_text: str,
    cloud_generate: Callable[[str, str], str],
    *,
    summary: bool = False,
) -> str:
    """Ask cloud for better structure, but return text for local PDF rendering."""
    system_prompt = (
        "You are Shell AI's pro document writer. Return only PDF body text with a clear title, "
        "short sections, polished English, and useful bullets. Do not mention cloud or APIs."
    )
    instruction = "Create an improved summary PDF body" if summary else "Create a polished PDF body"
    prompt = f"{instruction}.\nTitle: {title}\nSource text:\n{source_text}"
    reply = _clean_text(cloud_generate(prompt, system_prompt))
    return reply or local_make_pdf(title, source_text, summary=summary)


def local_make_simple_website(topic: str) -> str:
    return f"Local static website template for {_clean_text(topic) or 'Shell site'}"


def cloud_make_advanced_website(topic: str, cloud_generate: Callable[[str, str], str]) -> str:
    return cloud_generate(f"Create an advanced website plan for {topic}", "Return concise structured website content.")


__all__ = [
    "TaskMode",
    "cloud_make_advanced_website",
    "cloud_make_pdf",
    "detect_make_mode",
    "local_make_pdf",
    "local_make_simple_website",
]
