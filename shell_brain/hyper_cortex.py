"""
SHELL BRAIN - HYPER CORTEX
Multi-provider blueprint synthesizer with strict JSON normalization and safe fallback.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import requests

from .neuro_core_x import neuro_core
from .omni_brain import omni_brain

logger = logging.getLogger("hyper_cortex")


class HyperCortex:
    """
    Multi-vendor architecture strategist.

    Provider priority remains deterministic. If every remote provider fails,
    a local static blueprint is returned.
    """

    def __init__(self) -> None:
        self.providers: List[Dict[str, str]] = []
        self._load_providers()

    def _load_providers(self) -> None:
        self.providers = []

        provider_specs = [
            ("GOOGLE_API_KEY", "Gemini (Flash)", "gemini", "gemini-2.0-flash"),
            ("GROQ_API_KEY", "Groq (Llama-3.3)", "groq", "llama-3.3-70b-versatile"),
            ("OPENAI_API_KEY", "OpenAI (GPT-4o)", "openai", "gpt-4o"),
            ("ANTHROPIC_API_KEY", "Anthropic (Claude)", "anthropic", "claude-3-5-sonnet-20240620"),
        ]

        for env_key, name, provider_type, model in provider_specs:
            if os.getenv(env_key):
                self.providers.append({"name": name, "type": provider_type, "model": model})

        logger.info("HyperCortex loaded %d providers", len(self.providers))

    def refresh_providers(self) -> List[Dict[str, str]]:
        self._load_providers()
        return list(self.providers)

    def synergize_project(self, project_name: str, user_intent: str) -> dict:
        """
        Attempts remote providers in order, then returns a validated fallback blueprint.
        """
        clean_project = self._safe_text(project_name, "shell_project")
        clean_intent = self._safe_text(user_intent, "modern web app")
        prompt = self._build_prompt(clean_project, clean_intent)

        for provider in self.providers:
            logger.info("HyperCortex consulting provider=%s", provider["name"])
            try:
                raw_payload = self._call_provider(provider, prompt)
                blueprint = self._parse_blueprint(raw_payload, clean_project, clean_intent)
                logger.info("HyperCortex provider success=%s", provider["name"])
                return blueprint
            except Exception as exc:
                logger.warning("Provider %s failed: %s", provider["name"], exc)

        logger.warning("All providers failed or unavailable. Returning static fallback blueprint.")
        return self._static_fallback(clean_project, clean_intent)

    def _call_provider(self, provider: Dict[str, str], prompt: str) -> str:
        provider_type = provider["type"]
        model = provider["model"]

        if provider_type == "openai":
            return self._call_openai(model, prompt)
        if provider_type == "anthropic":
            return self._call_anthropic(model, prompt)
        if provider_type == "groq":
            return self._call_groq(model, prompt)
        if provider_type == "sambanova":
            return self._call_sambanova(model, prompt)
        if provider_type == "gemini":
            return self._call_gemini(model, prompt)

        raise ValueError(f"Unknown provider type: {provider_type}")

    def _post_json(self, url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: int = 20) -> Dict[str, Any]:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:400]}")
        return response.json()

    def _call_openai(self, model: str, prompt: str) -> str:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.7,
        }
        data = self._post_json("https://api.openai.com/v1/chat/completions", headers, payload)
        return data["choices"][0]["message"]["content"]

    def _call_anthropic(self, model: str, prompt: str) -> str:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": 4000,
            "messages": [{"role": "user", "content": prompt}],
        }
        data = self._post_json("https://api.anthropic.com/v1/messages", headers, payload)
        blocks = data.get("content", [])
        text_parts = [b.get("text", "") for b in blocks if isinstance(b, dict)]
        merged = "\n".join(part for part in text_parts if part)
        if not merged:
            raise RuntimeError("Anthropic returned no text payload")
        return merged

    def _call_groq(self, model: str, prompt: str) -> str:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not configured")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 8192,
        }
        data = self._post_json("https://api.groq.com/openai/v1/chat/completions", headers, payload)
        return data["choices"][0]["message"]["content"]

    def _call_sambanova(self, model: str, prompt: str) -> str:
        api_key = os.getenv("SAMBANOVA_API_KEY")
        if not api_key:
            raise RuntimeError("SAMBANOVA_API_KEY not configured")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 8192,
        }
        data = self._post_json("https://api.sambanova.ai/v1/chat/completions", headers, payload)
        return data["choices"][0]["message"]["content"]

    def _call_gemini(self, model: str, prompt: str) -> str:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY not configured")

        try:
            from google import genai
            from google.genai import types
        except Exception as exc:
            raise RuntimeError("google-genai package not installed") from exc

        client = genai.Client(api_key=api_key)

        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7,
                ),
            )
            if response.text:
                return response.text
        except Exception as e1:
            logger.warning("Gemini model %s failed: %s, trying gemini-2.5-flash", model, e1)
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.7,
                    ),
                )
                if response.text:
                    return response.text
            except Exception as e2:
                raise RuntimeError(f"All Gemini models failed: {e1}, {e2}") from e2

        raise RuntimeError("Gemini returned empty response")

    def _parse_blueprint(self, raw_payload: Any, project_name: str, user_intent: str) -> dict:
        if isinstance(raw_payload, dict):
            return self._normalize_blueprint(raw_payload, project_name, user_intent)

        content = str(raw_payload or "").strip()
        if not content:
            raise ValueError("Empty provider response")

        content = content.replace("```json", "").replace("```", "").strip()
        if content.lower().startswith("json"):
            content = content[4:].strip()

        parsed = None
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and end > start:
                parsed = json.loads(content[start : end + 1])

        if not isinstance(parsed, dict):
            raise ValueError("Provider response was not valid JSON object")

        return self._normalize_blueprint(parsed, project_name, user_intent)

    def _normalize_blueprint(self, blueprint: Dict[str, Any], project_name: str, user_intent: str) -> dict:
        meta = blueprint.get("meta") if isinstance(blueprint.get("meta"), dict) else {}
        frontend = blueprint.get("frontend") if isinstance(blueprint.get("frontend"), dict) else {}
        backend = blueprint.get("backend") if isinstance(blueprint.get("backend"), dict) else {}

        normalized = {
            "meta": {
                "name": self._safe_text(meta.get("name"), project_name),
                "type": self._safe_text(meta.get("type"), "Generated Architecture"),
                "complexity": self._safe_text(meta.get("complexity"), "High"),
                "archetype": self._safe_text(
                    meta.get("archetype"),
                    self._detect_web_archetype(user_intent),
                ),
            },
            "frontend": {
                "html_body": self._safe_text(frontend.get("html_body"), self._default_html_body(project_name, user_intent)),
                "full_css": self._safe_text(frontend.get("full_css"), ""),
                "css_vars": self._safe_text(frontend.get("css_vars"), self._default_css_vars()),
                "animations": self._safe_text(frontend.get("animations"), self._default_animations()),
                "js_logic": self._safe_text(frontend.get("js_logic"), self._default_js_logic()),
                "cdn_links": self._safe_str_list(frontend.get("cdn_links"), self._default_cdn_links()),
            },
            "backend": {
                "routes_code": self._safe_text(backend.get("routes_code"), self._default_routes_code()),
                "db_models": self._safe_text(backend.get("db_models"), ""),
                "python_packages": self._safe_str_list(
                    backend.get("python_packages"),
                    ["flask", "flask_sqlalchemy", "flask_cors"],
                ),
            },
        }
        return normalized

    def _build_prompt(self, project_name: str, user_intent: str) -> str:
        import random
        style_seeds = [
            ("glassmorphism — frosted panels, blur(16px) backdrop, translucent cards, subtle borders", "Inter", "DM Sans"),
            ("neobrutalism — thick 3-4px borders, bright saturated fills, offset box-shadows, raw shapes", "Space Grotesk", "Work Sans"),
            ("minimalist editorial — massive whitespace, elegant thin type, accent-only color, horizontal rules", "Cormorant Garamond", "Karla"),
            ("mesh gradient — vibrant multi-stop gradients, floating blobs, glass cards over gradient bg", "Outfit", "Plus Jakarta Sans"),
            ("retro 70s — warm tones, rounded shapes, groovy serif fonts, paper texture overlay", "Fraunces", "Nunito"),
            ("cyberpunk neon — deep black/charcoal bg, neon glow borders, monospace accents, scan-line effects", "Orbitron", "Fira Code"),
            ("organic nature — earthy olive/terracotta palette, rounded blobs, leaf-like SVG dividers", "Josefin Sans", "Lora"),
            ("corporate SaaS — clean grids, professional blues/purples, testimonial cards, pricing tables", "Manrope", "IBM Plex Sans"),
            ("dark luxury — black bg, gold/champagne accents, thin elegant serif, generous letter-spacing", "Cinzel", "Raleway"),
            ("playful creative — asymmetric grids, tilted cards, bold pop colors, bouncy animations", "Fredoka", "Quicksand"),
        ]
        style_data = random.choice(style_seeds)
        chosen_style, font_head, font_body = style_data
        
        is_tool = any(word in user_intent.lower() for word in ['calculator', 'tool', 'app', 'generator', 'editor', 'player', 'dashboard', 'converter', 'system'])

        if is_tool:
            html_instructions = """
=== HTML (html_body) ===
[ENGINEERING MODE]
Generate a production-grade, highly interactive web application UI.
1. CORE: Build the exact core interface for the requested tool (e.g., calculator keypad, dashboard panels, complex forms).
2. ARCHITECTURE: Use semantic HTML5, perfect ARIA labels for accessibility, and a modular DOM structure.
3. COMPLETENESS: Every input, button, slider, canvas, or panel required MUST be present. No placeholders.
4. UX/UI: Include micro-interactions structure, toast notification containers, loading states, and modal dialog roots if applicable.
5. STRICT RULE: ABSOLUTELY NO marketing sections (testimonials, pricing, hero banners) unless explicitly requested. This is a pure software tool.
"""
            js_instructions = """
=== JS (js_logic) ===
[EXECUTION MODE]
Write robust JavaScript to power this application.
1. PARADIGM: Use modern ES6+ classes or modular closures. Implement complex state management.
2. LOGIC: Implement the FULL logical requirements without cutting corners. (e.g., For a calculator: handle precision, order of operations, memory, edge cases like NaN/Infinity).
3. ROBUSTNESS: 100% error handling. Catch exceptions, validate all inputs, and prevent any unhandled states.
4. INTERACTIVITY: Bind all DOM elements precisely. Implement debouncing/throttling for performance where needed.
5. FEEDBACK: App must visually react to operations (triggering CSS transitions, disabling buttons during async, etc).
"""
            css_instructions = """
=== CSS (full_css) ===
[AESTHETICS MODE]
Create a polished, production-quality stylesheet.
1. VARIABLES: Define an exhaustive `:root` with exact HSL/RGB values for dynamic theming (--primary, --surface, --border, --shadow-sm to --shadow-xl).
2. LAYOUT: Thoughtful use of CSS Grid & Flexbox for precise alignment. 100% fluid and responsive across all devices.
3. VISUALS: Utilize advanced techniques: backdrop-filter (glassmorphism), complex multi-layered box-shadows, subtle gradients, and perfect typography tracking/leading.
4. ANIMATIONS: Define highly polished `@keyframes` for entrance, exit, and state changes. Use `cubic-bezier` for butter-smooth motion.
5. POLISH: Custom scrollbars, perfect focus rings, zero layout shifts, and hover/active micro-interactions on absolutely everything.
"""
        else:
            html_instructions = f"""
=== HTML (html_body) ===
[DESIGN MODE]
Generate a polished landing page or website.
1. SECTIONS: Design a breathtaking journey. Include sticky morphing Nav, cinematic Hero (<img src='https://picsum.photos/seed/{project_name.replace(' ','')}hero/1920/1080'>), gorgeous Bento-grid Features, immersive About, dynamic Stats, and an elegant Footer.
2. STRUCTURE: Use advanced HTML5 semantics. Prepare elements for scroll-driven animations (e.g., `data-aos`, `reveal` classes).
3. CONTENT: Write compelling, high-converting, professional copy. DO NOT use Lorem Ipsum.
"""
            js_instructions = """
=== JS (js_logic) ===
[INTERACTION MODE]
Implement cinematic scroll and interaction logic.
1. OBSERVERS: Complex `IntersectionObserver` logic to trigger staggered, cascading reveal animations as elements enter the viewport.
2. DYNAMICS: Navbar scroll-morphing (transparent to glass), parallax scrolling effects, and smooth anchor navigation.
3. PERFORMANCE: Highly optimized, jank-free 60FPS execution.
"""
            css_instructions = """
=== CSS (full_css) ===
[AESTHETICS MODE]
COMPLETE standalone stylesheet. MUST include:
1. THEMING: Consistent color system using `:root` variables.
2. TYPOGRAPHY: Fluid typography system (`clamp()`). Perfect hierarchy.
3. ANIMATIONS: Create 5+ incredible `@keyframes`. Implement complex staggered entrance animations (`.reveal`), magnetic button hover effects, and breathtaking glassmorphism details.
4. RESPONSIVE: Flawless adaptation from 320px to 4K displays.
"""

        return f"""
You are a practical AI systems architect. Write maintainable, testable code with clear UI structure.

Project: "{project_name}"
Brief: "{user_intent}"
Design Target: {chosen_style}
Fonts: Heading={font_head} | Body={font_body}

Return ONLY valid JSON:
{{
  "meta": {{"name": "{project_name}", "type": "production app", "complexity": "high", "archetype": "auto-detect"}},
  "frontend": {{
    "html_body": "FULL HTML",
    "full_css": "COMPLETE CSS STYLESHEET",
    "css_vars": ":root block",
    "animations": "@keyframes blocks",
    "js_logic": "Interactive JS",
    "cdn_links": ["font links"]
  }},
  "backend": {{"routes_code": "", "db_models": "", "python_packages": []}}
}}
{html_instructions}
{css_instructions}
{js_instructions}
=== CDN (cdn_links) ===
Google Fonts: {font_head} and {font_body} (weights 400,600,700)
<script src='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/js/all.min.js'></script>
<script src='https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js'></script>

CRITICAL: Return ONLY the JSON object. Do not wrap in Markdown. Ensure absolute perfection.
EXTREMELY IMPORTANT JSON RULES:
1. You MUST escape all double quotes (\\") inside the string values.
2. For HTML attributes, STRICTLY use single quotes (e.g., <div class='container'>) to avoid JSON escaping issues.
3. You MUST properly escape newlines (\\n) if you want multiple lines, or just write it as a single flat string. Do NOT break the JSON string formatting!
""".strip()

    def _static_fallback(self, project_name: str, user_intent: str) -> dict:
        archetype = self._detect_web_archetype(user_intent)
        core_archetype = self._map_archetype_for_core_modules(archetype)
        ui_pattern = omni_brain.get_ui_pattern(core_archetype)
        backend_logic = neuro_core.get_backend_structure(core_archetype)

        return {
            "meta": {
                "name": project_name,
                "type": ui_pattern.get("theme", "Fallback Architecture"),
                "complexity": "Static-Fallback",
                "archetype": archetype,
            },
            "frontend": {
                "html_body": self._build_fallback_html_body(project_name, user_intent, archetype),
                "css_vars": omni_brain.generate_css_variables(ui_pattern),
                "animations": omni_brain.get_animation_css(ui_pattern),
                "js_logic": self._fallback_js_logic(archetype),
                "cdn_links": self._default_cdn_links(),
                "components_needed": ui_pattern.get("components", []),
            },
            "backend": {
                "routes_code": "\n\n".join(backend_logic.get("routes", [])),
                "db_models": "\n\n".join(backend_logic.get("models", [])),
                "python_packages": ["flask", "flask_sqlalchemy", "flask_cors"],
            },
        }

    def _default_html_body(self, project_name: str, user_intent: str) -> str:
        archetype = self._detect_web_archetype(user_intent)
        return self._build_fallback_html_body(project_name, user_intent, archetype)

    def _default_css_vars(self) -> str:
        return ":root { --primary: #00d4ff; --secondary: #ff6b35; --bg: #0a0d14; --text: #ffffff; --glass: rgba(255,255,255,0.08); }"

    def _default_animations(self) -> str:
        return "@keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }"

    def _default_js_logic(self) -> str:
        return "document.addEventListener('DOMContentLoaded', () => { console.log('Shell builder ready'); });"

    def _detect_web_archetype(self, user_intent: str) -> str:
        intent = (user_intent or "").lower()
        if any(token in intent for token in ("shop", "store", "ecommerce", "e-commerce", "market", "product", "checkout", "cart")):
            return "ecommerce"
        if any(token in intent for token in ("restaurant", "cafe", "food", "menu", "dining", "hotel menu")):
            return "restaurant"
        if any(token in intent for token in ("blog", "article", "news", "editorial", "magazine", "content")):
            return "blog"
        if any(token in intent for token in ("saas", "software", "startup", "app", "platform", "product landing")):
            return "saas"
        if any(token in intent for token in ("agency", "studio", "marketing", "branding", "creative")):
            return "agency"
        if any(token in intent for token in ("dashboard", "admin", "analytics", "crm", "erp", "panel")):
            return "dashboard"
        if any(token in intent for token in ("landing", "promo", "campaign", "one page")):
            return "landing"
        return "portfolio"

    def _map_archetype_for_core_modules(self, archetype: str) -> str:
        if archetype in {"ecommerce", "blog", "portfolio", "landing", "admin"}:
            return archetype
        if archetype == "dashboard":
            return "admin"
        if archetype in {"restaurant", "saas"}:
            return "landing"
        if archetype == "agency":
            return "portfolio"
        return "portfolio"

    def _build_fallback_html_body(self, project_name: str, user_intent: str, archetype: str) -> str:
        title = project_name.replace("_", " ").title()
        intent = user_intent.strip() if user_intent else "Modern digital experience"

        if archetype == "ecommerce":
            return (
                "<nav class='site-nav'><div class='brand'>{title}</div><div class='nav-links'>"
                "<a href='#home'>Home</a><a href='#catalog'>Catalog</a><a href='#offers'>Offers</a><a href='#contact'>Contact</a>"
                "</div></nav>"
                "<header id='home' class='hero'><div><h1>{title} Marketplace</h1><p>{intent}</p>"
                "<button class='btn primary-cta'>Shop Best Sellers</button></div>"
                "<div class='hero-badge'><strong>Fast Shipping</strong><small>Nationwide delivery in 48h</small></div></header>"
                "<main>"
                "<section id='catalog'><h2>Trending Products</h2><div class='card-grid'>"
                "<article class='card'><h3>Neon Keyboard</h3><p>Hot-swappable RGB layout.</p></article>"
                "<article class='card'><h3>Ergo Chair</h3><p>Comfort-first productivity design.</p></article>"
                "<article class='card'><h3>Creator Mic</h3><p>Broadcast-grade voice clarity.</p></article>"
                "</div></section>"
                "<section id='offers'><h2>Why Customers Choose Us</h2><div class='feature-list'>"
                "<span>Secure checkout</span><span>Easy returns</span><span>Live support</span>"
                "</div></section>"
                "</main>"
                "<footer id='contact' class='site-footer'><small>Built with Shell OS 1.0.0 by mdshoebking</small></footer>"
            ).format(title=title, intent=intent)

        if archetype == "restaurant":
            return (
                "<nav class='site-nav'><div class='brand'>{title}</div><div class='nav-links'>"
                "<a href='#home'>Home</a><a href='#menu'>Menu</a><a href='#story'>Story</a><a href='#reserve'>Reserve</a>"
                "</div></nav>"
                "<header id='home' class='hero'><div><h1>{title}</h1><p>{intent}</p>"
                "<button class='btn primary-cta'>Reserve a Table</button></div>"
                "<div class='hero-badge'><strong>Open Today</strong><small>Lunch and dinner service</small></div></header>"
                "<main>"
                "<section id='menu'><h2>Signature Menu</h2><div class='card-grid'>"
                "<article class='card'><h3>Smoked Paneer Tikka</h3><p>Charcoal grilled with house spices.</p></article>"
                "<article class='card'><h3>Firewood Pizza</h3><p>Stone-baked crust, seasonal toppings.</p></article>"
                "<article class='card'><h3>Saffron Kulfi</h3><p>Classic dessert with modern plating.</p></article>"
                "</div></section>"
                "<section id='story'><h2>Our Story</h2><p>Crafted for memorable evenings, rooted in local ingredients.</p></section>"
                "</main>"
                "<footer id='reserve' class='site-footer'><small>Bookings page built with Shell OS 1.0.0 by mdshoebking</small></footer>"
            ).format(title=title, intent=intent)

        if archetype == "blog":
            return (
                "<nav class='site-nav'><div class='brand'>{title}</div><div class='nav-links'>"
                "<a href='#home'>Home</a><a href='#latest'>Latest</a><a href='#topics'>Topics</a><a href='#subscribe'>Subscribe</a>"
                "</div></nav>"
                "<header id='home' class='hero'><div><h1>{title} Journal</h1><p>{intent}</p>"
                "<button class='btn primary-cta'>Read Latest Post</button></div>"
                "<div class='hero-badge'><strong>Fresh Stories</strong><small>Weekly expert insights</small></div></header>"
                "<main>"
                "<section id='latest'><h2>Featured Articles</h2><div class='card-grid'>"
                "<article class='card'><h3>Design Systems 2026</h3><p>How teams scale UI consistency.</p></article>"
                "<article class='card'><h3>AI Product Ops</h3><p>What changed in modern workflows.</p></article>"
                "<article class='card'><h3>Fast Frontends</h3><p>Performance tactics that actually work.</p></article>"
                "</div></section>"
                "<section id='topics'><h2>Topics</h2><div class='feature-list'><span>Engineering</span><span>Business</span><span>UX</span></div></section>"
                "</main>"
                "<footer id='subscribe' class='site-footer'><small>Subscribe for thoughtful updates.</small></footer>"
            ).format(title=title, intent=intent)

        if archetype == "saas":
            return (
                "<nav class='site-nav'><div class='brand'>{title}</div><div class='nav-links'>"
                "<a href='#home'>Home</a><a href='#features'>Features</a><a href='#pricing'>Pricing</a><a href='#contact'>Contact</a>"
                "</div></nav>"
                "<header id='home' class='hero'><div><h1>{title} Platform</h1><p>{intent}</p>"
                "<button class='btn primary-cta'>Start Free Trial</button></div>"
                "<div class='hero-badge'><strong>99.9% Uptime</strong><small>Reliable cloud infrastructure</small></div></header>"
                "<main>"
                "<section id='features'><h2>Core Features</h2><div class='card-grid'>"
                "<article class='card'><h3>Team Workspaces</h3><p>Organize projects with clear ownership.</p></article>"
                "<article class='card'><h3>Automations</h3><p>Replace repetitive tasks with workflows.</p></article>"
                "<article class='card'><h3>Real-time Insights</h3><p>Track outcomes with live dashboards.</p></article>"
                "</div></section>"
                "<section id='pricing'><h2>Pricing</h2><div class='feature-list'><span>Starter</span><span>Growth</span><span>Enterprise</span></div></section>"
                "</main>"
                "<footer id='contact' class='site-footer'><small>Launch page built with Shell OS 1.0.0 by mdshoebking</small></footer>"
            ).format(title=title, intent=intent)

        if archetype == "agency":
            return (
                "<nav class='site-nav'><div class='brand'>{title}</div><div class='nav-links'>"
                "<a href='#home'>Home</a><a href='#services'>Services</a><a href='#work'>Work</a><a href='#contact'>Contact</a>"
                "</div></nav>"
                "<header id='home' class='hero'><div><h1>{title} Studio</h1><p>{intent}</p>"
                "<button class='btn primary-cta'>Book Strategy Call</button></div>"
                "<div class='hero-badge'><strong>Creative + Performance</strong><small>Brand, web, and growth in one team</small></div></header>"
                "<main>"
                "<section id='services'><h2>Services</h2><div class='card-grid'>"
                "<article class='card'><h3>Brand Identity</h3><p>Positioning, messaging, and visual language.</p></article>"
                "<article class='card'><h3>Website Engineering</h3><p>Fast responsive builds with clear UX.</p></article>"
                "<article class='card'><h3>Growth Campaigns</h3><p>Paid and organic strategies that compound.</p></article>"
                "</div></section>"
                "<section id='work'><h2>Recent Work</h2><p>Case studies available on request.</p></section>"
                "</main>"
                "<footer id='contact' class='site-footer'><small>Let's ship outcomes, not slides.</small></footer>"
            ).format(title=title, intent=intent)

        if archetype == "dashboard":
            return (
                "<nav class='site-nav'><div class='brand'>{title}</div><div class='nav-links'>"
                "<a href='#home'>Overview</a><a href='#metrics'>Metrics</a><a href='#alerts'>Alerts</a><a href='#ops'>Ops</a>"
                "</div></nav>"
                "<header id='home' class='hero'><div><h1>{title} Command Center</h1><p>{intent}</p>"
                "<button class='btn primary-cta'>Open Dashboard</button></div>"
                "<div class='hero-badge'><strong>Live Monitoring</strong><small>Systems updated in real time</small></div></header>"
                "<main>"
                "<section id='metrics'><h2>Core Metrics</h2><div class='card-grid'>"
                "<article class='card'><h3>Uptime</h3><p>99.94% this month</p></article>"
                "<article class='card'><h3>Active Users</h3><p>12,482 online</p></article>"
                "<article class='card'><h3>Latency</h3><p>P95: 78ms</p></article>"
                "</div></section>"
                "<section id='alerts'><h2>Alerts</h2><div class='feature-list'><span>CPU high</span><span>Login spike</span><span>Backup complete</span></div></section>"
                "</main>"
                "<footer id='ops' class='site-footer'><small>Operations mode enabled.</small></footer>"
            ).format(title=title, intent=intent)

        # Portfolio and landing share a presentation-first structure.
        heading = f"{title} Portfolio" if archetype == "portfolio" else f"{title} Launch"
        cta = "See Projects" if archetype == "portfolio" else "Get Started"
        return (
            "<nav class='site-nav'><div class='brand'>{title}</div><div class='nav-links'>"
            "<a href='#home'>Home</a><a href='#about'>About</a><a href='#highlights'>Highlights</a><a href='#contact'>Contact</a>"
            "</div></nav>"
            "<header id='home' class='hero'><div><h1>{heading}</h1><p>{intent}</p>"
            "<button class='btn primary-cta'>{cta}</button></div>"
            "<div class='hero-badge'><strong>Built to stand out</strong><small>Responsive and conversion-focused</small></div></header>"
            "<main>"
            "<section id='about'><h2>About</h2><p>Purpose-built experience tailored to your goal.</p></section>"
            "<section id='highlights'><h2>Highlights</h2><div class='card-grid'>"
            "<article class='card'><h3>Intent-aware layout</h3><p>Structure adapts to website type.</p></article>"
            "<article class='card'><h3>Responsive by default</h3><p>Looks clean across device sizes.</p></article>"
            "<article class='card'><h3>Fast delivery</h3><p>Generated instantly with safe fallback.</p></article>"
            "</div></section>"
            "</main>"
            "<footer id='contact' class='site-footer'><small>Built with Shell OS 1.0.0 by mdshoebking</small></footer>"
        ).format(title=title, heading=heading, intent=intent, cta=cta)

    def _fallback_js_logic(self, archetype: str) -> str:
        cta_message = {
            "ecommerce": "Opening product discovery flow...",
            "restaurant": "Launching reservation workflow...",
            "blog": "Loading featured article...",
            "saas": "Starting your trial setup...",
            "agency": "Opening strategy booking...",
            "dashboard": "Switching to monitoring view...",
            "portfolio": "Loading showcase...",
            "landing": "Continuing to next step...",
        }.get(archetype, "Continuing...")
        return (
            "document.addEventListener('DOMContentLoaded', () => {\n"
            "  const cards = document.querySelectorAll('.card');\n"
            "  cards.forEach((card, index) => {\n"
            "    card.style.opacity = '0';\n"
            "    card.style.transform = 'translateY(16px)';\n"
            "    setTimeout(() => {\n"
            "      card.style.transition = 'all 360ms ease';\n"
            "      card.style.opacity = '1';\n"
            "      card.style.transform = 'translateY(0)';\n"
            "    }, 120 * index);\n"
            "  });\n"
            "  const cta = document.querySelector('.primary-cta');\n"
            "  if (cta) {\n"
            "    cta.addEventListener('click', () => {\n"
            f"      alert('{cta_message}');\n"
            "    });\n"
            "  }\n"
            "});\n"
        )

    def _default_cdn_links(self) -> List[str]:
        return [
            "<script src='https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js'></script>",
            "<script src='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/js/all.min.js'></script>",
        ]

    def _default_routes_code(self) -> str:
        return "@app.route('/api/health')\ndef health():\n    return jsonify({'status': 'ok'})"

    def _safe_text(self, value: Any, default: str) -> str:
        text = str(value).strip() if value is not None else ""
        return text if text else default

    def _safe_str_list(self, value: Any, default: List[str]) -> List[str]:
        if isinstance(value, list):
            cleaned = [str(item).strip() for item in value if str(item).strip()]
            return cleaned if cleaned else list(default)
        return list(default)


hyper_cortex = HyperCortex()
