"""
SHELL BRAIN - OMNI BRAIN
Strategic planner with deterministic intent classification and UI design helpers.
"""

from __future__ import annotations

import logging
from typing import Dict, List

logger = logging.getLogger("omni_brain")


class OmniBrain:
    """
    Central strategic planner.

    Keeps compatibility with legacy helper methods used by HyperCortex fallback.
    """

    def __init__(self) -> None:
        self.knowledge_base: Dict[str, Dict[str, object]] = {
            "ecommerce": {
                "theme": "Practical-Commerce",
                "colors": {
                    "primary": "#ff0055",
                    "secondary": "#ff6a00",
                    "bg": "#05000a",
                    "card": "rgba(255,255,255,0.03)",
                },
                "components": ["MegaNav", "BentoGridProducts", "FluidCart", "CheckoutHolo"],
                "animations": "hover-lift-elastic, glide-in-staggered, pulse-buy",
            },
            "admin": {
                "theme": "Level10000-Command-Center",
                "colors": {
                    "primary": "#00f2ff",
                    "secondary": "#bd00ff",
                    "bg": "#0a0a0f",
                    "card": "rgba(0,242,255,0.05)",
                },
                "components": ["SidebarNavGlass", "ComplexDataGrid", "LiveAnalyticsCanvas", "UserOrbList"],
                "animations": "fade-in-blur, slide-up-spring",
            },
            "portfolio": {
                "theme": "Neon-Launch",
                "colors": {
                    "primary": "#bd00ff",
                    "secondary": "#ff0055",
                    "bg": "#020005",
                    "card": "rgba(189,0,255,0.04)",
                },
                "components": ["HeroCinematic", "SkillParticles", "ArchitectGallery", "ContactHolo"],
                "animations": "float-organic, glow-breathe, rotate-bg-slow",
            },
            "blog": {
                "theme": "Editorial-Elite",
                "colors": {
                    "primary": "#ff6b35",
                    "secondary": "#f7ca18",
                    "bg": "#0d0a08",
                    "card": "rgba(255,255,255,0.04)",
                },
                "components": ["ArticleMasonry", "PostCardImmersive", "CommentSectionSleek"],
                "animations": "fade-in-blur, slide-up-spring, hover-lift-elastic",
            },
            "landing": {
                "theme": "Conversion-Focused",
                "colors": {
                    "primary": "#00ff88",
                    "secondary": "#00d4ff",
                    "bg": "#001008",
                    "card": "rgba(0,255,136,0.05)",
                },
                "components": ["HeroSplash3D", "FeatureBentoGrid", "CTAMagnetic", "TestimonialOrbit"],
                "animations": "pulse-mag, zoom-in-subtle, gradient-aurora",
            },
        }

    def think_deeply(self, goal: str) -> dict:
        """
        Breaks down a complex goal into structured phases.
        """
        clean_goal = (goal or "").strip() or "Unspecified objective"
        lowered_goal = clean_goal.lower()

        intent = self._classify_intent(lowered_goal)
        phases = self._build_phases(intent)

        confidence_map = {
            "business": "92%",
            "security": "90%",
            "learning": "95%",
            "automation": "91%",
            "general": "88%",
        }
        analogy_map = {
            "business": "Like launching a rocket: design, test, then scale",
            "security": "Like reinforcing a fortress before a storm",
            "learning": "Like building muscles through progressive overload",
            "automation": "Like assembling a reliable production line",
            "general": "Like solving a puzzle by edge-first decomposition",
        }

        plan = {
            "meta": {
                "goal": clean_goal,
                "confidence": confidence_map[intent],
                "analogy": analogy_map[intent],
                "intent": intent,
            },
            "phases": phases,
        }

        logger.info("OmniBrain intent=%s, goal=%s", intent, clean_goal)
        return plan

    def _classify_intent(self, goal: str) -> str:
        if any(token in goal for token in ("startup", "business", "company", "revenue", "money", "sales")):
            return "business"

        # Security keywords are treated as defensive operations only.
        if any(token in goal for token in ("security", "secure", "vulnerability", "hack", "penetration", "audit")):
            return "security"

        if any(token in goal for token in ("learn", "study", "course", "practice", "skill", "exam")):
            return "learning"

        if any(token in goal for token in ("automate", "workflow", "pipeline", "script", "ops", "devops")):
            return "automation"

        return "general"

    def _build_phases(self, intent: str) -> List[Dict[str, str]]:
        if intent == "business":
            return [
                {"phase": 1, "name": "Market Recon", "action": "Map demand, competitors, and positioning."},
                {"phase": 2, "name": "MVP Build", "action": "Ship a testable product slice with fast feedback loops."},
                {"phase": 3, "name": "Go-To-Market", "action": "Run acquisition experiments and track conversion metrics."},
                {"phase": 4, "name": "Scale", "action": "Stabilize infra, unit economics, and growth channels."},
            ]

        if intent == "security":
            return [
                {"phase": 1, "name": "Asset Discovery", "action": "Inventory systems, secrets, and external attack surface."},
                {"phase": 2, "name": "Risk Assessment", "action": "Rank vulnerabilities by exploitability and impact."},
                {"phase": 3, "name": "Hardening", "action": "Apply least-privilege, patching, and secure defaults."},
                {"phase": 4, "name": "Validation", "action": "Run defensive tests and continuous monitoring alerts."},
            ]

        if intent == "learning":
            return [
                {"phase": 1, "name": "Curriculum", "action": "Create topic map from fundamentals to advanced outcomes."},
                {"phase": 2, "name": "Resources", "action": "Select curated docs, examples, and practice sets."},
                {"phase": 3, "name": "Implementation", "action": "Build mini-projects to encode long-term retention."},
                {"phase": 4, "name": "Assessment", "action": "Evaluate mastery with tests and targeted revision."},
            ]

        if intent == "automation":
            return [
                {"phase": 1, "name": "Process Mapping", "action": "Identify repetitive tasks and required triggers."},
                {"phase": 2, "name": "System Design", "action": "Define scripts, APIs, retries, and failure handling."},
                {"phase": 3, "name": "Execution", "action": "Implement workflows with observability and logging."},
                {"phase": 4, "name": "Optimization", "action": "Measure latency/cost and tune bottlenecks."},
            ]

        return [
            {"phase": 1, "name": "Analysis", "action": "Clarify constraints, scope, and expected outcomes."},
            {"phase": 2, "name": "Strategy", "action": "Select an execution approach with tradeoff awareness."},
            {"phase": 3, "name": "Execution", "action": "Implement milestones with feedback checkpoints."},
            {"phase": 4, "name": "Review", "action": "Validate result quality and document improvements."},
        ]

    # --- Legacy Methods (Backward Compatible) ---
    def get_ui_pattern(self, app_type: str) -> dict:
        """Returns the visual pattern for requested app type."""
        key = "portfolio"
        app_lower = (app_type or "").lower()

        if any(token in app_lower for token in ("shop", "commerce", "store")):
            key = "ecommerce"
        elif any(token in app_lower for token in ("admin", "dashboard")):
            key = "admin"
        elif any(token in app_lower for token in ("blog", "news", "article")):
            key = "blog"
        elif any(token in app_lower for token in ("landing", "promo", "marketing")):
            key = "landing"

        logger.info("OmniBrain visual mode selected=%s", key)
        return self.knowledge_base[key]

    def generate_css_variables(self, pattern: dict) -> str:
        colors = pattern["colors"]
        return (
            ":root {\n"
            f"    --primary: {colors['primary']};\n"
            f"    --secondary: {colors['secondary']};\n"
            f"    --bg: {colors['bg']};\n"
            f"    --glass: {colors['card']};\n"
            "    --text: #ffffff;\n"
            "    --font-main: 'Rajdhani', sans-serif;\n"
            "    --font-head: 'Orbitron', sans-serif;\n"
            "}\n"
        )

    def get_animation_css(self, pattern: dict) -> str:
        animations = (
            "@keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }\n"
            "@keyframes glow { 0% { box-shadow: 0 0 5px var(--primary); } 100% { box-shadow: 0 0 20px var(--primary), 0 0 10px var(--secondary); } }\n"
        )

        if "rotate-bg" in pattern.get("animations", ""):
            animations += "@keyframes rotateBg { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }\n"
        if "pulse-buy" in pattern.get("animations", ""):
            animations += "@keyframes pulseBuy { 0% { transform: scale(1); } 50% { transform: scale(1.05); } 100% { transform: scale(1); } }\n"

        return animations


omni_brain = OmniBrain()
