"""Make/build mode abstraction for Shell local and cloud-enhanced outputs."""

from __future__ import annotations

import re
import random
from dataclasses import dataclass
from enum import Enum
from html import escape
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


@dataclass(frozen=True)
class WebsiteBrief:
    subject: str
    site_type: str
    vibe: str
    audience: str


@dataclass(frozen=True)
class WebsitePattern:
    key: str
    label: str
    family: str


@dataclass(frozen=True)
class WebsiteStyle:
    key: str
    css_vars: str
    body_class: str


WEBSITE_PATTERNS: tuple[WebsitePattern, ...] = (
    WebsitePattern("split_hero", "Split Hero", "saas"),
    WebsitePattern("bento_command", "Bento Command", "saas"),
    WebsitePattern("sidebar_story", "Sidebar Story", "portfolio"),
    WebsitePattern("editorial_minimal", "Editorial Minimal", "blog"),
    WebsitePattern("dark_launch", "Dark Launch", "product"),
    WebsitePattern("color_blocks", "Color Blocks", "creative"),
    WebsitePattern("proof_grid", "Proof Grid", "service"),
    WebsitePattern("timeline_pitch", "Timeline Pitch", "startup"),
    WebsitePattern("showcase_cards", "Showcase Cards", "portfolio"),
    WebsitePattern("calm_docs", "Calm Docs", "documentation"),
)


WEBSITE_STYLES: tuple[WebsiteStyle, ...] = (
    WebsiteStyle("ink_lime", ":root { --primary:#b7ff2a; --secondary:#72e7ff; --bg:#09100f; --text:#f4fff9; --glass:rgba(255,255,255,0.08); --font-main:'Segoe UI',system-ui,sans-serif; --font-head:'Trebuchet MS',system-ui,sans-serif; }", "style-ink"),
    WebsiteStyle("paper_cobalt", ":root { --primary:#2457ff; --secondary:#ff6b35; --bg:#f7f4ee; --text:#111827; --glass:rgba(255,255,255,0.72); --font-main:Georgia,'Times New Roman',serif; --font-head:Verdana,system-ui,sans-serif; }", "style-paper"),
    WebsiteStyle("night_pink", ":root { --primary:#ff4fd8; --secondary:#ffd166; --bg:#11101a; --text:#fff7fb; --glass:rgba(255,255,255,0.09); --font-main:'Segoe UI',system-ui,sans-serif; --font-head:'Arial Black',Impact,sans-serif; }", "style-night"),
    WebsiteStyle("clean_teal", ":root { --primary:#00a884; --secondary:#2563eb; --bg:#f8fbff; --text:#10212b; --glass:rgba(255,255,255,0.78); --font-main:'Segoe UI',system-ui,sans-serif; --font-head:'Segoe UI Semibold',system-ui,sans-serif; }", "style-clean"),
    WebsiteStyle("graphite_gold", ":root { --primary:#f5b94b; --secondary:#7dd3fc; --bg:#16181d; --text:#f8fafc; --glass:rgba(255,255,255,0.075); --font-main:'Segoe UI',system-ui,sans-serif; --font-head:'Courier New',monospace; }", "style-graphite"),
)


def _infer_website_brief(prompt: str) -> WebsiteBrief:
    text = _clean_text(prompt)
    lower = text.lower()
    subject = re.sub(
        r"\b(?:please|pls|make|create|build|generate|design|a|an|the|website|webpage|web\s+page|landing\s+page|site|for|about|mere|liye|banao|bana|kar\s+do|simple|modern|really|good|professional|2026)\b",
        " ",
        text,
        flags=re.I,
    )
    subject = re.sub(r"[^a-zA-Z0-9 &,\-]+", " ", subject)
    subject = re.sub(r"\s+", " ", subject).strip(" ,-") or "Your Project"

    if re.search(r"\b(portfolio|resume|personal|creator|designer|photographer|artist)\b", lower):
        site_type, audience = "portfolio", "clients and collaborators"
    elif re.search(r"\b(blog|newsletter|publication|journal|writing)\b", lower):
        site_type, audience = "blog", "readers"
    elif re.search(r"\b(ai|saas|software|app|platform|tool|os|controller|automation)\b", lower):
        site_type, audience = "saas", "power users"
    elif re.search(r"\b(restaurant|bakery|shop|salon|agency|service|clinic)\b", lower):
        site_type, audience = "service", "local customers"
    else:
        site_type, audience = "product", "visitors"

    vibe = "minimal" if "minimal" in lower else "colorful" if "color" in lower or "playful" in lower else "serious" if "serious" in lower else "modern"
    return WebsiteBrief(subject=subject.title(), site_type=site_type, vibe=vibe, audience=audience)


def _pick_pattern_and_style(brief: WebsiteBrief, variant_index: int | None = None) -> tuple[WebsitePattern, WebsiteStyle]:
    matching = list(WEBSITE_PATTERNS)
    if variant_index is None:
        variant_index = random.SystemRandom().randrange(0, 10_000)
    pattern = matching[variant_index % len(matching)]
    style = WEBSITE_STYLES[(variant_index // max(1, len(matching))) % len(WEBSITE_STYLES)]
    return pattern, style


def _copy_for_website(brief: WebsiteBrief) -> dict[str, object]:
    subject = brief.subject
    if brief.site_type == "saas":
        return {
            "eyebrow": "Local-first software",
            "headline": f"Control {subject} with less friction",
            "subhead": "A focused interface for people who want clear actions, quick feedback, and fewer repetitive steps.",
            "cta": "Explore the workflow",
            "cards": [
                ("Natural commands", "Turn everyday requests into structured actions without hunting through menus."),
                ("Built for operators", "Keep important controls, status, and next steps visible in one responsive page."),
                ("Ready to extend", "Start with a clean static site and add deeper product sections when needed."),
            ],
        }
    if brief.site_type == "portfolio":
        return {
            "eyebrow": "Selected work",
            "headline": f"A sharp home for {subject}",
            "subhead": "A clean portfolio that introduces the person, shows the work, and makes contact feel obvious.",
            "cta": "View highlights",
            "cards": [("Profile", "A concise intro that feels personal without becoming a long bio."), ("Projects", "Featured work arranged for fast scanning and credibility."), ("Contact", "A direct path for hiring, booking, or collaboration.")],
        }
    if brief.site_type == "blog":
        return {
            "eyebrow": "Independent publishing",
            "headline": f"Readable ideas from {subject}",
            "subhead": "A calm editorial page built around clear hierarchy, featured writing, and a simple subscription path.",
            "cta": "Read the latest",
            "cards": [("Featured essay", "Lead with the strongest piece instead of a generic feed."), ("Topics", "Group recurring themes so readers know what to expect."), ("Subscribe", "Offer a lightweight way to follow new posts.")],
        }
    return {
        "eyebrow": "Modern web presence",
        "headline": f"Make {subject} easy to understand",
        "subhead": f"A responsive landing page that explains the offer, builds trust, and guides {brief.audience} toward action.",
        "cta": "Start now",
        "cards": [("Clear offer", "Say what matters first with a focused headline and supporting proof."), ("Useful sections", "Organize benefits, details, and next steps into compact blocks."), ("Fast handoff", "Plain HTML and CSS make the result easy to edit or ship.")],
    }


def _render_offline_layout(brief: WebsiteBrief, pattern: WebsitePattern) -> str:
    copy = _copy_for_website(brief)
    cards = "".join(f"<article class='card'><h3>{escape(title)}</h3><p>{escape(body)}</p></article>" for title, body in copy["cards"])  # type: ignore[index]
    headline = escape(str(copy["headline"]))
    subhead = escape(str(copy["subhead"]))
    eyebrow = escape(str(copy["eyebrow"]))
    cta = escape(str(copy["cta"]))
    subject = escape(brief.subject)

    if pattern.key == "bento_command":
        return f"<nav class='site-nav'><div class='brand'>{subject}</div><div class='nav-links'><a href='#features'>Features</a><a href='#proof'>Proof</a></div></nav><header class='hero hero-bento'><p class='eyebrow'>{eyebrow}</p><h1>{headline}</h1><p>{subhead}</p><button class='btn'>{cta}</button><div class='bento-grid'>{cards}<article class='card metric'><strong>24/7</strong><span>Ready locally</span></article></div></header><main><section id='proof'><h2>Designed for momentum</h2><p>Every block is intentionally short, responsive, and easy to adapt.</p></section></main><footer class='site-footer'><small>{subject}</small></footer>"
    if pattern.key == "sidebar_story":
        return f"<aside class='side-rail'><strong>{subject}</strong><a href='#work'>Work</a><a href='#contact'>Contact</a></aside><main class='layout-sidebar'><section class='hero'><div><p class='eyebrow'>{eyebrow}</p><h1>{headline}</h1><p>{subhead}</p><button class='btn'>{cta}</button></div></section><section id='work'><h2>What visitors see first</h2><div class='card-grid'>{cards}</div></section></main>"
    if pattern.key == "editorial_minimal":
        return f"<main class='layout-editorial'><header class='hero'><div><p class='eyebrow'>{eyebrow}</p><h1>{headline}</h1><p>{subhead}</p><button class='btn'>{cta}</button></div></header><section><h2>A page with a point of view</h2><div class='card-grid'>{cards}</div></section></main><footer class='site-footer'><small>{subject}</small></footer>"
    if pattern.key == "dark_launch":
        return f"<nav class='site-nav'><div class='brand'>{subject}</div><div class='nav-links'><a href='#features'>System</a><a href='#contact'>Launch</a></div></nav><header class='hero hero-launch'><div><p class='eyebrow'>{eyebrow}</p><h1>{headline}</h1><p>{subhead}</p><button class='btn'>{cta}</button></div><div class='hero-badge'><strong>2026-ready</strong><small>Responsive, bold, and lightweight.</small></div></header><main><section id='features'><h2>What makes it useful</h2><div class='card-grid'>{cards}</div></section></main><footer class='site-footer'><small>{subject}</small></footer>"
    return f"<nav class='site-nav'><div class='brand'>{subject}</div><div class='nav-links'><a href='#home'>Home</a><a href='#features'>Features</a><a href='#contact'>Contact</a></div></nav><header id='home' class='hero'><div><p class='eyebrow'>{eyebrow}</p><h1>{headline}</h1><p>{subhead}</p><button class='btn'>{cta}</button></div><div class='hero-badge'><strong>{escape(pattern.label)}</strong><small>Different structure, same reliable local engine.</small></div></header><main><section id='features'><h2>Built around the visitor</h2><div class='card-grid'>{cards}</div></section><section id='contact'><h2>Ready for the next step</h2><div class='feature-list'><span>Responsive</span><span>Static HTML</span><span>Easy to edit</span></div></section></main><footer class='site-footer'><small>{subject}</small></footer>"


def offline_basic_website_blueprint(prompt: str, *, variant_index: int | None = None) -> dict[str, object]:
    """Local-only website architecture: classify prompt, pick pattern/style, render static UI."""
    brief = _infer_website_brief(prompt)
    pattern, style = _pick_pattern_and_style(brief, variant_index)
    return {
        "mode": TaskMode.LOCAL_BASIC.value,
        "brief": brief,
        "pattern": pattern.key,
        "style": style.key,
        "html_body": _render_offline_layout(brief, pattern),
        "css_vars": style.css_vars,
        "body_class": style.body_class,
        "js_logic": "document.documentElement.dataset.shellWebsiteMode = 'offline-basic';",
        "meta": {"archetype": pattern.key, "site_type": brief.site_type, "vibe": brief.vibe},
    }


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


def local_make_simple_website(topic: str, *, variant_index: int | None = None) -> str:
    blueprint = offline_basic_website_blueprint(topic, variant_index=variant_index)
    return str(blueprint["html_body"])


def cloud_make_advanced_website(topic: str, cloud_generate: Callable[[str, str], str]) -> str:
    system_prompt = (
        "You are Shell AI ONLINE_PRO website strategist. Use any provided web context, "
        "return concise JSON-like keys for site_type, pages, copy, layout, colors, and sections. "
        "Do not write files; Shell will render locally."
    )
    return cloud_generate(f"Research and design an advanced website for: {topic}", system_prompt)


def online_pro_website_blueprint(
    topic: str,
    cloud_generate: Callable[[str, str], str],
    *,
    fetch_web_context: Callable[[str], str] | None = None,
) -> dict[str, object]:
    """ONLINE_PRO plug-in point: research + cloud strategy, then local rendering remains Shell-owned."""
    web_context = _clean_text(fetch_web_context(topic)) if fetch_web_context else ""
    strategy = cloud_make_advanced_website(
        f"{topic}\n\nWeb context:\n{web_context}" if web_context else topic,
        cloud_generate,
    )
    local = offline_basic_website_blueprint(topic)
    return {
        **local,
        "mode": TaskMode.CLOUD_PRO.value,
        "cloud_strategy": strategy,
        "web_context_used": bool(web_context),
    }


__all__ = [
    "TaskMode",
    "cloud_make_advanced_website",
    "cloud_make_pdf",
    "detect_make_mode",
    "offline_basic_website_blueprint",
    "online_pro_website_blueprint",
    "local_make_pdf",
    "local_make_simple_website",
]
