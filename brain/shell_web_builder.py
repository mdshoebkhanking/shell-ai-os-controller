from __future__ import annotations

import asyncio
import colorsys
import hashlib
import json
import logging
import os
import re
import socket
import threading
import shutil
import webbrowser
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import quote

try:
    from shell_safe_executor import god_tier_tool as function_tool
except Exception:
    try:
        from livekit.agents import function_tool
    except Exception:
        def function_tool(func):
            return func

logger = logging.getLogger("shell_web_builder")

# --- NEURAL INTEGRATION (Optional) ---
try:
    from shell_brain.hyper_cortex import hyper_cortex

    NEURAL_ENGINE_ACTIVE = True
except ImportError:
    NEURAL_ENGINE_ACTIVE = False
    hyper_cortex = None  # type: ignore[assignment]

_PREVIEW_SERVERS: Dict[str, ThreadingHTTPServer] = {}
_PREVIEW_LOCK = threading.Lock()


def _safe_title(project_name: str) -> str:
    clean = (project_name or "").strip().replace("_", " ")
    return clean.title() if clean else "Shell Project"


def _escape_html_attr(value: str) -> str:
    text = str(value or "")
    return (
        text.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _hash_int(value: str) -> int:
    return int(hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()[:8], 16)


def _hex_from_hsl(hue: float, sat: float, light: float) -> str:
    h = (hue % 360.0) / 360.0
    s = max(0.0, min(1.0, sat))
    l = max(0.0, min(1.0, light))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))


def _hex_to_rgb(color_hex: str) -> Tuple[int, int, int]:
    clean = color_hex.strip().lstrip("#")
    if len(clean) != 6:
        return (255, 255, 255)
    return (int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16))


def _dynamic_palette(site_type: str, description: str, seed: int) -> Dict[str, str]:
    base_hues = {
        "ecommerce": 12,
        "restaurant": 26,
        "blog": 32,
        "saas": 206,
        "agency": 168,
        "dashboard": 214,
        "landing": 142,
        "portfolio": 286,
    }
    text = (description or "").lower()
    hue = float(base_hues.get(site_type, 286))

    if any(word in text for word in ("finance", "bank", "corporate", "business", "analytics")):
        hue = 212
    elif any(word in text for word in ("eco", "organic", "nature", "green", "environment")):
        hue = 140
    elif any(word in text for word in ("fashion", "beauty", "luxury", "premium", "elite")):
        hue = 330
    elif any(word in text for word in ("tech", "cyber", "ai", "futuristic", "gaming", "neon")):
        hue = 195
    elif any(word in text for word in ("food", "spicy", "cafe", "restaurant", "kitchen")):
        hue = 24

    hue = (hue + (seed % 44) - 22) % 360

    saturation = 0.74
    if any(word in text for word in ("minimal", "clean", "simple", "professional")):
        saturation = 0.52
    if any(word in text for word in ("bold", "vibrant", "energetic", "fun")):
        saturation = 0.84
    if any(word in text for word in ("neon", "cyber", "electric")):
        saturation = 0.9

    primary = _hex_from_hsl(hue, saturation, 0.57)
    secondary = _hex_from_hsl((hue + 34 + (seed % 18)) % 360, min(0.95, saturation + 0.05), 0.61)
    accent = _hex_from_hsl((hue + 180) % 360, min(0.95, saturation), 0.66)
    bg = _hex_from_hsl((hue + 210) % 360, 0.48, 0.08)

    pr, pg, pb = _hex_to_rgb(primary)
    glass = f"rgba({pr}, {pg}, {pb}, 0.14)"
    return {
        "primary": primary,
        "secondary": secondary,
        "accent": accent,
        "bg": bg,
        "glass": glass,
    }


def _svg_photo_placeholder(label: str, primary: str, secondary: str) -> str:
    safe_label = _escape_html_attr(label)
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='800' viewBox='0 0 1200 800'>"
        f"<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
        f"<stop offset='0%' stop-color='{primary}'/><stop offset='100%' stop-color='{secondary}'/></linearGradient></defs>"
        "<rect width='1200' height='800' fill='#0b1220'/>"
        "<circle cx='920' cy='130' r='210' fill='url(#g)' opacity='0.28'/>"
        "<circle cx='250' cy='650' r='240' fill='url(#g)' opacity='0.22'/>"
        f"<text x='70' y='720' fill='#ffffff' font-size='52' font-family='Segoe UI, Arial, sans-serif'>{safe_label}</text>"
        "</svg>"
    )
    return "data:image/svg+xml;utf8," + quote(svg)


def _photo_pack(project_name: str, site_type: str, description: str, primary: str, secondary: str) -> List[Dict[str, str]]:
    tags_map = {
        "ecommerce": ["shopping", "store", "product"],
        "restaurant": ["food", "restaurant", "cafe"],
        "blog": ["workspace", "reading", "editorial"],
        "saas": ["technology", "teamwork", "dashboard"],
        "agency": ["creative", "studio", "branding"],
        "dashboard": ["analytics", "monitoring", "data"],
        "landing": ["startup", "presentation", "growth"],
        "portfolio": ["design", "project", "showcase"],
    }
    tags = tags_map.get(site_type, ["creative", "website", "visual"])
    seed_base = _sanitize_folder_name(f"{project_name}_{description}_{site_type}") or "shell"

    pack: List[Dict[str, str]] = []
    for i, tag in enumerate(tags):
        seed = _sanitize_folder_name(f"{seed_base}_{tag}_{i}") or f"{site_type}_{i}"
        remote = f"https://picsum.photos/seed/{seed}/960/640"
        fallback = _svg_photo_placeholder(f"{tag.title()} Visual", primary, secondary)
        pack.append(
            {
                "src": remote,
                "fallback": fallback,
                "alt": f"{tag.title()} image",
            }
        )
    return pack


def _inject_card_photos(html: str, photos: List[Dict[str, str]]) -> str:
    if not photos or "<article class='card'>" not in html:
        return html

    chunks = html.split("<article class='card'>")
    if len(chunks) <= 1:
        return html

    rendered = [chunks[0]]
    for idx, chunk in enumerate(chunks[1:]):
        photo = photos[idx % len(photos)]
        img_tag = (
            "<article class='card'>"
            f"<img class='card-photo' src='{photo['src']}' data-fallback='{photo['fallback']}' "
            f"alt='{_escape_html_attr(photo['alt'])}' loading='lazy' referrerpolicy='no-referrer'>"
        )
        rendered.append(img_tag + chunk)

    return "".join(rendered)


def _detect_site_type(text: str) -> str:
    lowered = (text or "").lower()
    if any(token in lowered for token in ("shop", "store", "ecommerce", "e-commerce", "market", "product", "cart")):
        return "ecommerce"
    if any(token in lowered for token in ("restaurant", "cafe", "food", "menu", "dining")):
        return "restaurant"
    if any(token in lowered for token in ("blog", "article", "news", "magazine", "content")):
        return "blog"
    if any(token in lowered for token in ("saas", "startup", "software", "platform", "app")):
        return "saas"
    if any(token in lowered for token in ("agency", "studio", "branding", "marketing", "creative")):
        return "agency"
    if any(token in lowered for token in ("dashboard", "admin", "analytics", "panel", "crm")):
        return "dashboard"
    if any(token in lowered for token in ("landing", "promo", "campaign", "one page")):
        return "landing"
    return "portfolio"


def _sanitize_folder_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', " ", str(name or ""))
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]", "", cleaned)
    return cleaned[:64] or "shell_site"


def _ensure_unique_folder(base_dir: str, desired_name: str) -> str:
    base_name = _sanitize_folder_name(desired_name)
    candidate = base_name
    idx = 2
    while os.path.exists(os.path.join(base_dir, candidate)):
        candidate = f"{base_name}_{idx}"
        idx += 1
    return candidate


def _looks_like_shell_site(folder_path: str) -> bool:
    return (
        os.path.exists(os.path.join(folder_path, "index.html"))
        and os.path.exists(os.path.join(folder_path, "css", "style.css"))
        and os.path.exists(os.path.join(folder_path, "js", "script.js"))
    )


def _prepare_project_folder(base_dir: str, desired_name: str) -> str:
    base_name = _sanitize_folder_name(desired_name)
    target = os.path.join(base_dir, base_name)

    if not os.path.exists(target):
        return base_name

    marker_file = os.path.join(target, "build_report.json")
    if os.path.exists(marker_file) or _looks_like_shell_site(target):
        try:
            shutil.rmtree(target)
            return base_name
        except Exception as remove_error:
            logger.warning("Failed to refresh existing project folder '%s': %s", target, remove_error)

    return _ensure_unique_folder(base_dir, base_name)


def _extract_project_name_from_request(user_request: str, fallback_site_type: str) -> str:
    raw = str(user_request or "")

    quoted = re.search(r"['\"]([^'\"]{3,80})['\"]", raw)
    if quoted:
        return _sanitize_folder_name(quoted.group(1))

    explicit = re.search(
        r"(?:project\s*name|folder\s*name|site\s*name|name)\s*(?:is|=|:)?\s*([a-zA-Z0-9 _-]{3,80})",
        raw,
        flags=re.IGNORECASE,
    )
    if explicit:
        return _sanitize_folder_name(explicit.group(1))

    tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    return _sanitize_folder_name(f"{fallback_site_type}_site_{tag}")


def _enrich_request_brief(user_request: str, site_type: str) -> str:
    base = (user_request or "").strip()
    if not base:
        base = f"{site_type} website"

    enhancements = {
        "ecommerce": "Include trust badges, product cards, and clear checkout CTA.",
        "restaurant": "Include menu highlights, reservations CTA, and ambience-focused hero.",
        "blog": "Include featured posts, category chips, and readable editorial spacing.",
        "saas": "Include product value proposition, feature blocks, and pricing intent.",
        "agency": "Include services, case-study style highlights, and conversion CTA.",
        "dashboard": "Include KPI cards, alert indicators, and operations navigation.",
        "landing": "Include hero, benefits, social proof, and clear CTA hierarchy.",
        "portfolio": "Include project highlights, skills/story section, and contact CTA.",
    }
    return f"{base} {enhancements.get(site_type, '')}".strip()


def _open_url(url: str) -> bool:
    try:
        if webbrowser.open_new_tab(url):
            return True
    except Exception as open_tab_error:
        logger.warning("open_new_tab failed for %s: %s", url, open_tab_error)

    try:
        if webbrowser.open(url):
            return True
    except Exception as open_error:
        logger.warning("webbrowser.open failed for %s: %s", url, open_error)

    return False


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(sock.getsockname()[1])


def _start_preview_server(project_path: str) -> str:
    normalized_path = os.path.abspath(project_path)
    with _PREVIEW_LOCK:
        existing_server = _PREVIEW_SERVERS.get(normalized_path)
        if existing_server:
            host, port = existing_server.server_address
            return f"http://{host}:{port}/index.html"

        port = _find_free_port()
        handler = partial(SimpleHTTPRequestHandler, directory=normalized_path)
        server = ThreadingHTTPServer(("127.0.0.1", port), handler)
        server.daemon_threads = True

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        _PREVIEW_SERVERS[normalized_path] = server
        logger.info("Started local preview server for %s at port %d", normalized_path, port)
        return f"http://127.0.0.1:{port}/index.html"


def _open_local_html(index_path: str) -> bool:
    index_abs = os.path.abspath(index_path)
    file_url = Path(index_abs).as_uri()

    if not os.path.exists(index_abs):
        logger.warning("Index file missing at open time: %s", index_abs)
        return False

    if os.name == "nt":
        try:
            os.startfile(index_abs)  # type: ignore[attr-defined]
            return True
        except Exception as os_error:
            logger.warning("os.startfile fallback failed: %s", os_error)

    return _open_url(file_url)


def _open_project_preview(project_path: str, index_path: str) -> Tuple[bool, str, str]:
    file_url = Path(os.path.abspath(index_path)).as_uri()

    # Primary path: stable file URI (no local server dependency).
    if _open_local_html(index_path):
        return True, file_url, "file_uri"

    # Secondary path: local HTTP preview server fallback.
    preview_url = ""
    try:
        preview_url = _start_preview_server(project_path)
        if preview_url and _open_url(preview_url):
            return True, preview_url, "local_http"
    except Exception as server_error:
        logger.warning("Local preview server fallback failed: %s", server_error)

    fallback_url = preview_url if preview_url else file_url
    return False, fallback_url, "none"


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_bundle_diagnostics(project_path: str) -> Dict[str, Any]:
    required = {
        "index": os.path.join(project_path, "index.html"),
        "css": os.path.join(project_path, "css", "style.css"),
        "js": os.path.join(project_path, "js", "script.js"),
    }
    status: Dict[str, Any] = {"ok": True, "files": {}, "missing": []}

    for key, path in required.items():
        exists = os.path.exists(path)
        info: Dict[str, Any] = {"exists": exists, "path": path}
        if exists:
            size = os.path.getsize(path)
            info["bytes"] = size
            info["sha256"] = _sha256_file(path)
            if size <= 0:
                status["ok"] = False
                status["missing"].append(f"{key} (empty)")
        else:
            status["ok"] = False
            status["missing"].append(key)
        status["files"][key] = info

    return status


def _write_build_report(
    project_path: str,
    project_name: str,
    detected_type: str,
    preview_url: str,
    open_mode: str,
    diagnostics: Dict[str, Any],
) -> str:
    timestamp = datetime.now().isoformat()
    build_id = hashlib.sha1(f"{project_name}|{timestamp}".encode("utf-8", errors="ignore")).hexdigest()[:12]

    report = {
        "build_id": build_id,
        "project_name": project_name,
        "detected_type": detected_type,
        "generated_at": timestamp,
        "preview_url": preview_url,
        "open_mode": open_mode,
        "diagnostics": diagnostics,
    }
    report_path = os.path.join(project_path, "build_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return report_path


def _local_html(title: str, description: str, site_type: str, palette: Dict[str, str] | None = None) -> str:
    text = description.strip() if description else "Built with Shell smart web builder."
    palette = palette or {"primary": "#00d4ff", "secondary": "#2de2a6"}
    photos = _photo_pack(
        project_name=title,
        site_type=site_type,
        description=description,
        primary=palette.get("primary", "#00d4ff"),
        secondary=palette.get("secondary", "#2de2a6"),
    )

    def with_photos(markup: str) -> str:
        return _inject_card_photos(markup, photos)

    if site_type == "ecommerce":
        return with_photos(
            (
            "<nav class='site-nav'><div class='brand'>{title}</div><div class='nav-links'>"
            "<a href='#home'>Home</a><a href='#catalog'>Catalog</a><a href='#deals'>Deals</a><a href='#contact'>Contact</a>"
            "</div></nav>"
            "<header id='home' class='hero'><div><h1>{title} Store</h1><p>{text}</p>"
            "<button class='btn primary-cta'>Shop Now</button></div>"
            "<div class='hero-badge'><strong>Free Shipping</strong><small>On select products</small></div></header>"
            "<main>"
            "<section id='catalog'><h2>Popular Picks</h2><div class='card-grid'>"
            "<article class='card'><h3>Starter Bundle</h3><p>Best value setup for new users.</p></article>"
            "<article class='card'><h3>Pro Bundle</h3><p>Performance-first curated kit.</p></article>"
            "<article class='card'><h3>Creator Bundle</h3><p>Designed for content workflows.</p></article>"
            "</div></section>"
            "<section id='deals'><h2>Customer Promise</h2><div class='feature-list'>"
            "<span>Secure Checkout</span><span>Easy Returns</span><span>Fast Support</span>"
            "</div></section>"
            "</main>"
            "<footer id='contact' class='site-footer'><small>Shell AI storefront generator</small></footer>"
            ).format(title=title, text=text)
        )

    if site_type == "restaurant":
        return with_photos(
            (
            "<nav class='site-nav'><div class='brand'>{title}</div><div class='nav-links'>"
            "<a href='#home'>Home</a><a href='#menu'>Menu</a><a href='#story'>Story</a><a href='#reserve'>Reserve</a>"
            "</div></nav>"
            "<header id='home' class='hero'><div><h1>{title}</h1><p>{text}</p>"
            "<button class='btn primary-cta'>Reserve Table</button></div>"
            "<div class='hero-badge'><strong>Open Daily</strong><small>Lunch and dinner</small></div></header>"
            "<main>"
            "<section id='menu'><h2>Chef Specials</h2><div class='card-grid'>"
            "<article class='card'><h3>Smoked Tikka</h3><p>Char-grilled signature platter.</p></article>"
            "<article class='card'><h3>Stone Pizza</h3><p>Wood-fired artisanal slices.</p></article>"
            "<article class='card'><h3>Saffron Dessert</h3><p>House favorite sweet finish.</p></article>"
            "</div></section>"
            "<section id='story'><h2>Our Story</h2><p>Hospitality-first dining with modern flavors.</p></section>"
            "</main>"
            "<footer id='reserve' class='site-footer'><small>Reservation workflow ready</small></footer>"
            ).format(title=title, text=text)
        )

    if site_type == "blog":
        return with_photos(
            (
            "<nav class='site-nav'><div class='brand'>{title}</div><div class='nav-links'>"
            "<a href='#home'>Home</a><a href='#latest'>Latest</a><a href='#topics'>Topics</a><a href='#subscribe'>Subscribe</a>"
            "</div></nav>"
            "<header id='home' class='hero'><div><h1>{title} Journal</h1><p>{text}</p>"
            "<button class='btn primary-cta'>Read Latest</button></div>"
            "<div class='hero-badge'><strong>Weekly Publishing</strong><small>Practical insights</small></div></header>"
            "<main>"
            "<section id='latest'><h2>Featured Posts</h2><div class='card-grid'>"
            "<article class='card'><h3>Design Systems</h3><p>How teams scale interfaces.</p></article>"
            "<article class='card'><h3>Product Strategy</h3><p>Turning ideas into shipped value.</p></article>"
            "<article class='card'><h3>Engineering Notes</h3><p>Patterns for fast development.</p></article>"
            "</div></section>"
            "<section id='topics'><h2>Topics</h2><div class='feature-list'><span>UX</span><span>Code</span><span>Business</span></div></section>"
            "</main>"
            "<footer id='subscribe' class='site-footer'><small>Newsletter section can be connected to API</small></footer>"
            ).format(title=title, text=text)
        )

    if site_type == "saas":
        return with_photos(
            (
            "<nav class='site-nav'><div class='brand'>{title}</div><div class='nav-links'>"
            "<a href='#home'>Home</a><a href='#features'>Features</a><a href='#pricing'>Pricing</a><a href='#contact'>Contact</a>"
            "</div></nav>"
            "<header id='home' class='hero'><div><h1>{title} Platform</h1><p>{text}</p>"
            "<button class='btn primary-cta'>Start Free Trial</button></div>"
            "<div class='hero-badge'><strong>99.9% Uptime</strong><small>Cloud-ready deployment</small></div></header>"
            "<main>"
            "<section id='features'><h2>Core Features</h2><div class='card-grid'>"
            "<article class='card'><h3>Workflow Automation</h3><p>Replace repetitive operations.</p></article>"
            "<article class='card'><h3>Live Analytics</h3><p>Track outcomes in real-time.</p></article>"
            "<article class='card'><h3>Team Permissions</h3><p>Role-based access controls.</p></article>"
            "</div></section>"
            "<section id='pricing'><h2>Pricing</h2><div class='feature-list'><span>Starter</span><span>Growth</span><span>Enterprise</span></div></section>"
            "</main>"
            "<footer id='contact' class='site-footer'><small>SaaS launch page generated by Shell AI</small></footer>"
            ).format(title=title, text=text)
        )

    if site_type == "agency":
        return with_photos(
            (
            "<nav class='site-nav'><div class='brand'>{title}</div><div class='nav-links'>"
            "<a href='#home'>Home</a><a href='#services'>Services</a><a href='#work'>Work</a><a href='#contact'>Contact</a>"
            "</div></nav>"
            "<header id='home' class='hero'><div><h1>{title} Studio</h1><p>{text}</p>"
            "<button class='btn primary-cta'>Book Call</button></div>"
            "<div class='hero-badge'><strong>Brand + Web + Growth</strong><small>Execution-focused team</small></div></header>"
            "<main>"
            "<section id='services'><h2>Services</h2><div class='card-grid'>"
            "<article class='card'><h3>Brand Strategy</h3><p>Positioning and identity system.</p></article>"
            "<article class='card'><h3>Web Engineering</h3><p>Performance-first websites.</p></article>"
            "<article class='card'><h3>Growth Campaigns</h3><p>Paid and organic growth loops.</p></article>"
            "</div></section>"
            "<section id='work'><h2>Recent Work</h2><p>Case-study sections can be wired to CMS.</p></section>"
            "</main>"
            "<footer id='contact' class='site-footer'><small>Built for client acquisition</small></footer>"
            ).format(title=title, text=text)
        )

    if site_type == "dashboard":
        return with_photos(
            (
            "<nav class='site-nav'><div class='brand'>{title}</div><div class='nav-links'>"
            "<a href='#home'>Overview</a><a href='#metrics'>Metrics</a><a href='#alerts'>Alerts</a><a href='#ops'>Ops</a>"
            "</div></nav>"
            "<header id='home' class='hero'><div><h1>{title} Dashboard</h1><p>{text}</p>"
            "<button class='btn primary-cta'>Open Console</button></div>"
            "<div class='hero-badge'><strong>Live Monitoring</strong><small>Updated every few seconds</small></div></header>"
            "<main>"
            "<section id='metrics'><h2>Key Metrics</h2><div class='card-grid'>"
            "<article class='card'><h3>Uptime</h3><p>99.94% this month</p></article>"
            "<article class='card'><h3>Latency</h3><p>P95 under 90ms</p></article>"
            "<article class='card'><h3>Active Users</h3><p>12K+ currently online</p></article>"
            "</div></section>"
            "<section id='alerts'><h2>Alerts</h2><div class='feature-list'><span>CPU spike</span><span>Auth retry</span><span>Backup success</span></div></section>"
            "</main>"
            "<footer id='ops' class='site-footer'><small>Operations-first layout</small></footer>"
            ).format(title=title, text=text)
        )

    heading = f"{title} Portfolio" if site_type == "portfolio" else f"{title} Launch"
    cta = "See Projects" if site_type == "portfolio" else "Get Started"
    return with_photos(
        (
        "<nav class='site-nav'><div class='brand'>{title}</div><div class='nav-links'>"
        "<a href='#home'>Home</a><a href='#about'>About</a><a href='#highlights'>Highlights</a><a href='#contact'>Contact</a>"
        "</div></nav>"
        "<header id='home' class='hero'><div><h1>{heading}</h1><p>{text}</p>"
        "<button class='btn primary-cta'>{cta}</button></div>"
        "<div class='hero-badge'><strong>Intent-aware design</strong><small>Responsive and fast loading</small></div></header>"
        "<main>"
        "<section id='about'><h2>About</h2><p>Tailored to your project intent and audience.</p></section>"
        "<section id='highlights'><h2>Highlights</h2><div class='card-grid'>"
        "<article class='card'><h3>Custom Structure</h3><p>Website type-based layout generation.</p></article>"
        "<article class='card'><h3>Responsive by Default</h3><p>Optimized for mobile and desktop.</p></article>"
        "<article class='card'><h3>Easy to Extend</h3><p>Clear sections for future edits.</p></article>"
        "</div></section>"
        "</main>"
        "<footer id='contact' class='site-footer'><small>Generated by Shell AI</small></footer>"
        ).format(title=title, heading=heading, text=text, cta=cta)
    )


def _design_variant(project_name: str, content_description: str, site_type: str) -> Dict[str, str]:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    seed_input = f"{project_name}|{content_description}|{site_type}|{stamp}".encode("utf-8", errors="ignore")
    seed = int(hashlib.sha1(seed_input).hexdigest()[:8], 16)

    font_pairs = [
        ("Sora", "Space Grotesk"),
        ("Manrope", "Urbanist"),
        ("Outfit", "Exo 2"),
        ("Poppins", "Montserrat"),
    ]
    textures = [
        "radial-gradient(circle at 10% 10%, rgba(255,255,255,0.08), transparent 35%)",
        "radial-gradient(circle at 85% 10%, rgba(255,255,255,0.08), transparent 36%)",
        "linear-gradient(130deg, rgba(255,255,255,0.06), transparent 34%)",
        "radial-gradient(circle at 50% -10%, rgba(255,255,255,0.07), transparent 40%)",
    ]
    tone = ["executive", "kinetic", "minimal", "editorial"][seed % 4]
    font_main, font_head = font_pairs[seed % len(font_pairs)]
    texture = textures[(seed // 3) % len(textures)]
    card_radius = str(12 + (seed % 10))
    glow = str(16 + (seed % 24))

    return {
        "font_main": font_main,
        "font_head": font_head,
        "texture": texture,
        "tone": tone,
        "card_radius": card_radius,
        "glow": glow,
    }


def _local_blueprint(project_name: str, content_description: str) -> Dict[str, Any]:
    title = _safe_title(project_name)
    site_type = _detect_site_type(content_description)
    variant = _design_variant(project_name, content_description, site_type)

    palettes: Dict[str, Dict[str, str]] = {
        "ecommerce": {"primary": "#ff4d6d", "secondary": "#00d4ff", "bg": "#0d1117", "glass": "rgba(255,255,255,0.08)"},
        "restaurant": {"primary": "#ff9f1c", "secondary": "#e71d36", "bg": "#151515", "glass": "rgba(255,255,255,0.07)"},
        "blog": {"primary": "#ff7b00", "secondary": "#ffd166", "bg": "#111827", "glass": "rgba(255,255,255,0.08)"},
        "saas": {"primary": "#00d4ff", "secondary": "#2de2a6", "bg": "#081425", "glass": "rgba(255,255,255,0.09)"},
        "agency": {"primary": "#00f5d4", "secondary": "#f15bb5", "bg": "#0e0e16", "glass": "rgba(255,255,255,0.08)"},
        "dashboard": {"primary": "#4daafc", "secondary": "#2ecc71", "bg": "#131722", "glass": "rgba(255,255,255,0.08)"},
        "landing": {"primary": "#00ff88", "secondary": "#00d4ff", "bg": "#0a0d14", "glass": "rgba(255,255,255,0.08)"},
        "portfolio": {"primary": "#bd00ff", "secondary": "#00f2ff", "bg": "#050510", "glass": "rgba(255,255,255,0.06)"},
    }
    chosen = palettes.get(site_type, palettes["portfolio"])

    css_vars = (
        ":root {\n"
        f"    --primary: {chosen['primary']};\n"
        f"    --secondary: {chosen['secondary']};\n"
        f"    --bg: {chosen['bg']};\n"
        "    --text: #ffffff;\n"
        f"    --glass: {chosen['glass']};\n"
        f"    --font-main: '{variant['font_main']}', sans-serif;\n"
        f"    --font-head: '{variant['font_head']}', sans-serif;\n"
        f"    --radius-md: {variant['card_radius']}px;\n"
        f"    --accent-glow: {variant['glow']}px;\n"
        f"    --bg-layer: {variant['texture']};\n"
        "}\n"
    )

    js_alert = {
        "ecommerce": "Opening shopping flow...",
        "restaurant": "Opening table reservation flow...",
        "blog": "Loading featured stories...",
        "saas": "Starting your free trial...",
        "agency": "Opening discovery call form...",
        "dashboard": "Switching to live dashboard...",
        "portfolio": "Opening project showcase...",
        "landing": "Taking you to the next section...",
    }.get(site_type, "Continuing...")

    js_logic = (
        "document.addEventListener('DOMContentLoaded', () => {\n"
        "  const cards = document.querySelectorAll('.card');\n"
        "  cards.forEach((card, index) => {\n"
        "    card.style.opacity = '0';\n"
        "    card.style.transform = 'translateY(16px)';\n"
        "    setTimeout(() => {\n"
        "      card.style.transition = 'all 320ms ease';\n"
        "      card.style.opacity = '1';\n"
        "      card.style.transform = 'translateY(0)';\n"
        "    }, 90 * index);\n"
        "  });\n"
        "  const cta = document.querySelector('.primary-cta');\n"
        "  if (cta) {\n"
        "    cta.addEventListener('click', () => {\n"
        f"      alert('{js_alert}');\n"
        "    });\n"
        "  }\n"
        "});\n"
    )

    return {
        "meta": {
            "name": title,
            "type": "Local Smart Blueprint",
            "complexity": "Adaptive",
            "archetype": site_type,
            "tone": variant["tone"],
        },
        "frontend": {
            "html_body": _local_html(title, content_description, site_type),
            "css_vars": css_vars,
            "animations": (
                "@keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }\n"
                "@keyframes glow { 0% { box-shadow: 0 0 6px var(--primary); } 100% { box-shadow: 0 0 20px var(--secondary); } }\n"
                "@keyframes fadeUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }\n"
            ),
            "js_logic": js_logic,
            "cdn_links": [
                "<link rel='preconnect' href='https://fonts.googleapis.com'>",
                "<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>",
                f"<link href='https://fonts.googleapis.com/css2?family={variant['font_main'].replace(' ', '+')}:wght@400;600;700&family={variant['font_head'].replace(' ', '+')}:wght@500;700&display=swap' rel='stylesheet'>",
            ],
        },
    }


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _compose_css(css_vars: str, animations: str) -> str:
    safe_vars = css_vars.strip() if css_vars else ":root { --primary:#00d4ff; --secondary:#2de2a6; --bg:#0a0d14; --text:#fff; --glass:rgba(255,255,255,.08); --font-main:'Sora',sans-serif; --font-head:'Space Grotesk',sans-serif; --radius-md:14px; --accent-glow:20px; --bg-layer: radial-gradient(circle at 10% 10%, rgba(255,255,255,0.08), transparent 35%); }"
    safe_animations = animations.strip() if animations else ""

    return f"""{safe_vars}

* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

html, body {{
    width: 100%;
}}

body {{
    font-family: var(--font-main, 'Sora', sans-serif);
    background: var(--bg-layer, radial-gradient(circle at 10% 10%, rgba(255,255,255,0.08), transparent 35%)), var(--bg, #0a0d14);
    color: var(--text, #ffffff);
    line-height: 1.6;
}}

a {{
    color: inherit;
}}

img {{
    max-width: 100%;
    height: auto;
    display: block;
    border-radius: calc(var(--radius-md) - 6px);
    object-fit: cover;
}}

.site-nav {{
    position: sticky;
    top: 0;
    z-index: 50;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 6vw;
    background: color-mix(in srgb, var(--bg) 86%, black 14%);
    border-bottom: 1px solid rgba(255,255,255,0.08);
    backdrop-filter: blur(8px);
}}

.site-nav ul,
nav ul {{
    list-style: none;
    margin: 0;
    padding: 0;
}}

nav:not(.site-nav) {{
    position: sticky;
    top: 0;
    z-index: 50;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 6vw;
    background: color-mix(in srgb, var(--bg) 86%, black 14%);
    border-bottom: 1px solid rgba(255,255,255,0.08);
    backdrop-filter: blur(8px);
}}

nav:not(.site-nav) ul {{
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
}}

nav:not(.site-nav) a {{
    text-decoration: none;
    opacity: 0.9;
}}

nav:not(.site-nav) a:hover {{
    color: var(--primary);
}}

.brand {{
    font-family: var(--font-head, 'Space Grotesk', sans-serif);
    font-weight: 700;
    letter-spacing: 0.04em;
}}

.nav-links {{
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
}}

.nav-links a {{
    color: var(--text, #ffffff);
    text-decoration: none;
    opacity: 0.86;
}}

.nav-links a:hover {{
    opacity: 1;
    color: var(--primary);
}}

.hero {{
    min-height: 68vh;
    padding: 6rem 6vw 3rem;
    display: grid;
    grid-template-columns: 1.2fr 1fr;
    gap: 1.25rem;
    align-items: center;
}}

.hero h1 {{
    font-family: var(--font-head, 'Space Grotesk', sans-serif);
    font-size: clamp(2rem, 4vw, 3.6rem);
    line-height: 1.12;
    margin-bottom: 1rem;
}}

.hero p {{
    max-width: 58ch;
    opacity: 0.9;
}}

.hero-badge {{
    border: 1px solid rgba(255,255,255,0.12);
    background: var(--glass, rgba(255,255,255,0.08));
    border-radius: var(--radius-md, 14px);
    padding: 1rem 1.1rem;
    box-shadow: 0 20px 40px rgba(0,0,0,0.26);
    animation: float 7s ease-in-out infinite;
}}

.hero-badge strong {{
    display: block;
    margin-bottom: 0.2rem;
}}

main {{
    padding: 1rem 6vw 4rem;
}}

section {{
    margin-top: 2.4rem;
}}

section h2 {{
    font-family: var(--font-head, 'Space Grotesk', sans-serif);
    font-size: clamp(1.4rem, 2.4vw, 2.1rem);
    margin-bottom: 1rem;
}}

.card-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem;
}}

.card {{
    border: 1px solid rgba(255,255,255,0.12);
    background: var(--glass, rgba(255,255,255,0.08));
    border-radius: var(--radius-md, 14px);
    padding: 1rem;
    animation: fadeUp 0.45s ease both;
}}

.feature-list {{
    display: flex;
    gap: 0.65rem;
    flex-wrap: wrap;
}}

.feature-list span {{
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 999px;
    padding: 0.35rem 0.8rem;
    font-size: 0.9rem;
}}

.btn {{
    margin-top: 1rem;
    border: none;
    border-radius: 999px;
    padding: 0.7rem 1.2rem;
    font-weight: 700;
    cursor: pointer;
    background: linear-gradient(120deg, var(--primary), var(--secondary));
    color: #07131f;
    transition: transform 220ms ease, box-shadow 220ms ease;
}}

.btn:hover {{
    transform: translateY(-2px);
    box-shadow: 0 12px 30px rgba(0,0,0,0.3), 0 0 var(--accent-glow, 18px) color-mix(in srgb, var(--primary) 55%, transparent);
}}

.site-footer {{
    padding: 1.5rem 6vw 2.2rem;
    border-top: 1px solid rgba(255,255,255,0.08);
    opacity: 0.86;
}}

.image-fallback {{
    border: 1px dashed rgba(255,255,255,0.3);
    background: rgba(255,255,255,0.05);
    border-radius: var(--radius-md, 12px);
    padding: 1.2rem;
    text-align: center;
    font-size: 0.9rem;
    color: rgba(255,255,255,0.85);
}}

@media (max-width: 900px) {{
    .hero {{
        grid-template-columns: 1fr;
        min-height: auto;
        padding-top: 4.5rem;
    }}
    .nav-links {{
        gap: 0.65rem;
        font-size: 0.95rem;
    }}
}}

{safe_animations}
"""


@function_tool
async def build_website_on_desktop_tool(project_name: str, content_description: str) -> str:
    """
    Builds a context-aware static website on the user's Desktop and opens it.

    Args:
        project_name: Name of the folder to create on Desktop.
        content_description: Website intent/description from user.
    """
    try:
        # 1. Resolve Desktop Path
        user_profile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        desktop_path = os.path.join(user_profile, "Desktop")
        os.makedirs(desktop_path, exist_ok=True)

        requested_name = _sanitize_folder_name(project_name)
        final_project_name = _prepare_project_folder(desktop_path, requested_name)
        project_path = os.path.join(desktop_path, final_project_name)

        os.makedirs(project_path, exist_ok=True)
        os.makedirs(os.path.join(project_path, "css"), exist_ok=True)
        os.makedirs(os.path.join(project_path, "js"), exist_ok=True)

        logger.info("Building website at: %s", project_path)

        # 2. Generate Architecture Blueprint
        blueprint: Dict[str, Any] = {}
        detected_type = _detect_site_type(content_description)

        if NEURAL_ENGINE_ACTIVE and hyper_cortex is not None:
            try:
                blueprint = await asyncio.to_thread(
                    hyper_cortex.synergize_project,  # type: ignore[attr-defined]
                    final_project_name,
                    content_description,
                )
            except Exception as neural_error:
                logger.warning("Neural blueprint generation failed: %s", neural_error)

        if not isinstance(blueprint, dict) or "frontend" not in blueprint:
            blueprint = _local_blueprint(final_project_name, content_description)

        meta = blueprint.get("meta") if isinstance(blueprint.get("meta"), dict) else {}
        frontend = blueprint.get("frontend") if isinstance(blueprint.get("frontend"), dict) else {}

        title = _safe_title(final_project_name)
        detected_type = str(meta.get("archetype") or detected_type)

        html_body = str(frontend.get("html_body") or _local_html(title, content_description, detected_type))
        # Strip any duplicate <!DOCTYPE html>...<body> that AI may inject into html_body
        import re
        html_body = re.sub(r'<!DOCTYPE[^>]*>.*?<body[^>]*>', '', html_body, flags=re.DOTALL | re.IGNORECASE)
        html_body = re.sub(r'</body>\s*</html>\s*$', '', html_body, flags=re.IGNORECASE)

        full_css = str(frontend.get("full_css") or "").strip()
        css_vars = str(frontend.get("css_vars") or "")
        animations = str(frontend.get("animations") or "")
        js_logic = str(frontend.get("js_logic") or "")

        # Sanitize CDN links: wrap bare URLs in proper <link> or <script> tags
        raw_cdn = _as_list(frontend.get("cdn_links"))
        asset_tags = []
        for tag in raw_cdn:
            tag = tag.strip()
            if not tag:
                continue
            if tag.startswith("<"):
                asset_tags.append(tag)
            elif "fonts.googleapis.com" in tag or tag.endswith(".css"):
                asset_tags.append(f"<link href='{tag}' rel='stylesheet'>")
            elif tag.endswith(".js"):
                asset_tags.append(f"<script src='{tag}'></script>")
            else:
                asset_tags.append(f"<link href='{tag}' rel='stylesheet'>")
        head_assets = "\n    ".join(asset_tags)
        description_meta = _escape_html_attr(content_description or f"{detected_type} website generated by Shell AI")

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="{description_meta}">
    <title>{title}</title>
    {head_assets}
    <link rel="preload" href="css/style.css" as="style">
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <noscript>
      <div style="padding:12px; background:#1f2937; color:#fff; font:14px sans-serif;">
        JavaScript is disabled. This site can still be viewed, but interactions are limited.
      </div>
    </noscript>
    {html_body}
    <script defer src="js/script.js"></script>
</body>
</html>"""

        # Use AI-generated full CSS if available, else fall back to template
        if full_css and len(full_css) > 100:
            css_content = full_css
        else:
            css_content = _compose_css(css_vars, animations)

        js_content = (
            js_logic
            if js_logic.strip()
            else (
                "document.addEventListener('DOMContentLoaded', () => {"
                "  console.log('Shell smart web builder ready');"
                "});"
            )
        )
        js_content += """

document.addEventListener('DOMContentLoaded', () => {
  // Compatibility layer for provider-generated generic markup.
  const navLists = document.querySelectorAll('nav ul');
  navLists.forEach((ul) => {
    ul.style.listStyle = 'none';
    ul.style.margin = '0';
    ul.style.padding = '0';
    if (!ul.classList.contains('nav-links')) {
      ul.style.display = 'flex';
      ul.style.gap = '1rem';
      ul.style.flexWrap = 'wrap';
    }
  });

  const navLinks = document.querySelectorAll('nav a');
  navLinks.forEach((a) => {
    a.style.textDecoration = 'none';
  });

  // If provider references non-existent local images, show graceful fallback.
  const images = document.querySelectorAll('img');
  images.forEach((img) => {
    const applyFallback = () => {
      if (img.dataset.shellFallbackApplied === '1') {
        return;
      }
      img.dataset.shellFallbackApplied = '1';
      const holder = document.createElement('div');
      holder.className = 'image-fallback';
      holder.textContent = img.getAttribute('alt') || 'Image unavailable';
      img.style.display = 'none';
      img.insertAdjacentElement('afterend', holder);
    };

    img.addEventListener('error', applyFallback);
    if (img.complete && img.naturalWidth === 0) {
      applyFallback();
    }
  });
});
"""

        # 3. Write Files
        with open(os.path.join(project_path, "index.html"), "w", encoding="utf-8") as f:
            f.write(html_content)

        with open(os.path.join(project_path, "css", "style.css"), "w", encoding="utf-8") as f:
            f.write(css_content)

        with open(os.path.join(project_path, "js", "script.js"), "w", encoding="utf-8") as f:
            f.write(js_content)

        diagnostics = _collect_bundle_diagnostics(project_path)

        # 4. Auto-open with stronger fallbacks
        index_path = os.path.join(project_path, "index.html")
        opened, preview_url, open_mode = _open_project_preview(project_path, index_path)
        open_status = (
            f"Opened in browser via {open_mode}."
            if opened
            else "Saved successfully (auto-open skipped)."
        )
        report_path = _write_build_report(
            project_path=project_path,
            project_name=final_project_name,
            detected_type=detected_type,
            preview_url=preview_url,
            open_mode=open_mode,
            diagnostics=diagnostics,
        )
        diag_summary = "PASS" if diagnostics.get("ok") else f"WARN missing={','.join(diagnostics.get('missing', []))}"

        return (
            "✅ **Website Built Successfully!**\n"
            f"📂 Saved to: `{project_path}`\n"
            f"📁 Folder Name: `{final_project_name}`\n"
            f"🧠 Detected Type: `{detected_type}`\n"
            f"🔎 Bundle Check: `{diag_summary}`\n"
            f"🌐 Preview URL: `{preview_url}`\n"
            f"🧾 Build Report: `{report_path}`\n"
            f"🚀 Status: {open_status}"
        )

    except Exception as e:
        logger.error("Web build failed: %s", e)
        return f"❌ Failed to build website: {e}"


@function_tool
async def smart_build_website_to_desktop_tool(user_request: str, project_name: str = "") -> str:
    """
    One-shot website builder from natural language.

    Always saves website on Desktop and attempts to auto-open it.

    Args:
        user_request: Natural language request, e.g. "build me a dashboard website for logistics company".
        project_name: Optional custom folder name. If empty, inferred from request.
    """
    try:
        request_text = (user_request or "").strip()
        site_type = _detect_site_type(request_text)
        final_name = _sanitize_folder_name(project_name) if project_name.strip() else _extract_project_name_from_request(request_text, site_type)
        enriched_brief = _enrich_request_brief(request_text, site_type)

        result = await build_website_on_desktop_tool(
            project_name=final_name,
            content_description=enriched_brief,
        )

        return (
            "✅ Smart desktop website command executed.\n"
            f"🧠 Interpreted Type: `{site_type}`\n"
            f"🗂️ Requested Folder: `{final_name}`\n"
            f"{result}"
        )
    except Exception as e:
        logger.error("Smart desktop web build failed: %s", e)
        return f"❌ Smart build failed: {e}"
