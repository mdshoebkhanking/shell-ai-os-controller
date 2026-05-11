"""
Shell AI — EXTRA SUB-AGENTS (Pack v1)
======================================
15 additional specialist function-tools that delegate to MultiAIBrain.

These complement the 22 agents in `shell_agents.py` with concrete,
user-facing specialisations: finance, legal, health, cooking, travel,
study, language tutor, resume, interview, marketing, SEO, game design,
storyteller, philosophy, and debate.

Each tool is a thin wrapper around `_ask_brain(...)` that injects a
domain-specific system prompt and returns the model's text response.

Usage:
    from shell_extra_agents import (
        finance_agent_tool, legal_agent_tool, health_agent_tool,
        cooking_agent_tool, travel_agent_tool, study_agent_tool,
        language_tutor_agent_tool, resume_agent_tool, interview_agent_tool,
        marketing_agent_tool, seo_agent_tool, game_design_agent_tool,
        storyteller_agent_tool, philosophy_agent_tool, debate_agent_tool,
    )
"""

from __future__ import annotations

# Prefer the project's wrapped function_tool so these agents inherit
# Shell's middleware (rate limit, circuit breaker, error tracker).
try:
    from shell_safe_executor import god_tier_tool as function_tool  # type: ignore
except Exception:  # pragma: no cover — runtime fallback
    from livekit.agents import function_tool  # type: ignore

import asyncio
import logging
import time

logger = logging.getLogger("shell_extra_agents")

_BRAIN_UNAVAILABLE_UNTIL = 0.0


# ═══════════════════════════════════════════════════════════════
#  Brain helper — single shared call path for every sub-agent
# ═══════════════════════════════════════════════════════════════

async def _ask_brain(
    prompt: str,
    system: str,
    mode: str = "SMART",
    timeout: int = 30,
    temperature: float = 0.7,
) -> str:
    """Call MultiAIBrain.generate_response with sensible defaults.

    Returns the raw text response. On any failure (brain not loaded,
    timeout, network) returns a short error string so the LLM can
    surface it to the user instead of crashing the tool call.
    """
    global _BRAIN_UNAVAILABLE_UNTIL
    if time.time() < _BRAIN_UNAVAILABLE_UNTIL:
        return _provider_unavailable_message()

    try:
        from brain.core import MultiAIBrain
        brain = MultiAIBrain.get_instance()
        response = await asyncio.wait_for(
            brain.generate_response(
                prompt=prompt,
                system_prompt=system,
                mode=mode,
                use_cache=False,
                temperature=temperature,
            ),
            timeout=timeout,
        )
        if _is_provider_failure(response):
            _BRAIN_UNAVAILABLE_UNTIL = time.time() + 60.0
            logger.warning("extra_agent provider chain unavailable: %s", str(response)[:300])
            return _provider_unavailable_message()
        return response
    except asyncio.TimeoutError:
        logger.warning("extra_agent brain timeout (%ds)", timeout)
        _BRAIN_UNAVAILABLE_UNTIL = time.time() + 20.0
        return _provider_unavailable_message("AI provider timed out")
    except Exception as e:
        logger.exception("extra_agent brain call failed")
        _BRAIN_UNAVAILABLE_UNTIL = time.time() + 20.0
        return _provider_unavailable_message()


def _is_provider_failure(response: object) -> bool:
    text = str(response or "").lower()
    return (
        "all brains failed" in text
        or "api key missing" in text
        or "resource_exhausted" in text
        or "payment_method_required" in text
        or "rate limit reached" in text
    )


def _provider_unavailable_message(reason: str = "AI providers are temporarily unavailable") -> str:
    return (
        f"{reason}. This extra agent is loaded, but model reasoning is in degraded mode. "
        "Check API keys/quota or retry after the provider cooldown."
    )


# ═══════════════════════════════════════════════════════════════
#  1) FINANCE
# ═══════════════════════════════════════════════════════════════

@function_tool
async def finance_agent_tool(query: str) -> str:
    """Personal finance specialist — budgets, taxes (India focus), ROI,
    investments, EMI calc, SIP planning. Replies in Hinglish with bullets
    and worked numeric examples."""
    return await _ask_brain(
        prompt=query,
        system=(
            "You are FinanceAgent — a friendly Hinglish personal-finance "
            "advisor for Indian users. Reply in clear bullet points with "
            "concrete numeric examples (use INR by default). Cover relevant "
            "topics: budgeting, tax slabs, SIP/mutual funds, FD vs equity, "
            "EMI math, compound interest, emergency fund sizing. End every "
            "answer with: 'Not financial advice — consult a SEBI advisor.'"
        ),
        mode="SMART",
    )


# ═══════════════════════════════════════════════════════════════
#  2) LEGAL
# ═══════════════════════════════════════════════════════════════

@function_tool
async def legal_agent_tool(query: str) -> str:
    """Legal drafting helper — drafts simple NDAs, freelance contracts,
    rental agreements, MoUs. Explains clauses in Hinglish. Not a lawyer."""
    return await _ask_brain(
        prompt=query,
        system=(
            "You are LegalAgent — a plain-English / Hinglish drafting "
            "assistant. When asked for a contract (NDA, freelance, rental, "
            "MoU, employment offer), produce a clean numbered draft with "
            "[BRACKETED] placeholders for names, dates, amounts. After the "
            "draft, add a 'Clause Notes' section explaining each clause "
            "in 1-2 simple Hinglish lines. Always end with: 'This is a "
            "template, not legal advice — get it reviewed by a lawyer "
            "before signing.'"
        ),
        mode="SMART",
        temperature=0.4,
    )


# ═══════════════════════════════════════════════════════════════
#  3) HEALTH
# ═══════════════════════════════════════════════════════════════

@function_tool
async def health_agent_tool(query: str) -> str:
    """Health & fitness assistant — diet plans, workout routines, basic
    symptom triage, sleep tips. Always recommends seeing a doctor."""
    return await _ask_brain(
        prompt=query,
        system=(
            "You are HealthAgent — a careful, friendly Hinglish health & "
            "fitness coach. You can suggest balanced diet plans (with "
            "macros), workout routines (with sets/reps/rest), sleep "
            "hygiene tips, and discuss symptoms at a general level. "
            "NEVER diagnose. NEVER prescribe medication or dosages. "
            "If the user describes anything serious (chest pain, severe "
            "bleeding, suicidal thoughts, breathing trouble), immediately "
            "tell them to call emergency services or visit an ER. "
            "Always end with: 'Consult a qualified doctor before acting "
            "on this.'"
        ),
        mode="SMART",
    )


# ═══════════════════════════════════════════════════════════════
#  4) COOKING
# ═══════════════════════════════════════════════════════════════

@function_tool
async def cooking_agent_tool(query: str) -> str:
    """Cooking & meal planning — recipes from available ingredients,
    weekly meal plans, portion math, substitution suggestions."""
    return await _ask_brain(
        prompt=query,
        system=(
            "You are CookingAgent — a warm, practical Hinglish home-cook "
            "assistant. Given ingredients, output a recipe with: title, "
            "serves N, prep+cook time, ingredient list with grams/cups, "
            "step-by-step method (numbered), and 1-2 tips. For meal "
            "plans, give a 7-day grid with breakfast/lunch/dinner. "
            "Suggest reasonable substitutions for missing items. Default "
            "to Indian veg unless user specifies otherwise."
        ),
        mode="SMART",
    )


# ═══════════════════════════════════════════════════════════════
#  5) TRAVEL
# ═══════════════════════════════════════════════════════════════

@function_tool
async def travel_agent_tool(query: str) -> str:
    """Travel planner — itineraries, packing lists, visa/budget tips,
    transport options for Indian travellers."""
    return await _ask_brain(
        prompt=query,
        system=(
            "You are TravelAgent — an enthusiastic Hinglish travel "
            "planner. For trip requests output: day-by-day itinerary "
            "(morning/afternoon/evening), estimated daily budget in INR, "
            "transport tips (train/flight/bus), 1-2 must-eat foods, "
            "packing list, and visa/permit notes if applicable. Flag "
            "monsoon/peak-season caveats. Add a final 'Money-saving "
            "tips' bullet list."
        ),
        mode="SMART",
    )


# ═══════════════════════════════════════════════════════════════
#  6) STUDY
# ═══════════════════════════════════════════════════════════════

@function_tool
async def study_agent_tool(query: str) -> str:
    """Study companion — concept explainers, quiz generation, flashcards,
    exam prep timetables."""
    return await _ask_brain(
        prompt=query,
        system=(
            "You are StudyAgent — a patient Hinglish tutor. Detect what "
            "the user wants: (a) explain a concept (use ELI12 + analogy "
            "+ worked example), (b) generate a quiz (5-10 MCQs with "
            "answers at the end), (c) make flashcards (Q/A pairs, "
            "Anki-friendly), or (d) build a study timetable (daily "
            "blocks with revision Sundays). Always include a 'Common "
            "mistakes' section."
        ),
        mode="SMART",
    )


# ═══════════════════════════════════════════════════════════════
#  7) LANGUAGE TUTOR
# ═══════════════════════════════════════════════════════════════

@function_tool
async def language_tutor_agent_tool(query: str) -> str:
    """Language tutor — translation drills, grammar correction, vocab,
    pronunciation tips for any language pair."""
    return await _ask_brain(
        prompt=query,
        system=(
            "You are LanguageTutorAgent — a multilingual tutor. Detect "
            "source/target languages from the query (default: "
            "Hindi <-> English). For translation drills give: 5 "
            "sentences, the answer, and a 1-line grammar note. For "
            "corrections, mark errors inline with **bold**, then "
            "rewrite cleanly, then list the rules violated. For vocab "
            "asks, give word + meaning + 2 example sentences + a memory "
            "hook. Encourage with a short closing line."
        ),
        mode="SMART",
    )


# ═══════════════════════════════════════════════════════════════
#  8) RESUME
# ═══════════════════════════════════════════════════════════════

@function_tool
async def resume_agent_tool(query: str) -> str:
    """Resume / cover-letter rewriter — tailors a CV bullet list or
    cover letter to a specific job description."""
    return await _ask_brain(
        prompt=query,
        system=(
            "You are ResumeAgent — an ATS-savvy resume writer. Expect "
            "the user to give you (a) their current resume / experience "
            "and (b) the target job description. Output: rewritten "
            "Summary (3 lines), 5-7 STAR-format bullets per relevant "
            "role using strong action verbs, a Skills section keyword-"
            "matched to the JD, and a tailored 250-word cover letter. "
            "Mark inserted JD keywords in **bold** so the user sees the "
            "match. Keep tone confident, never inflated."
        ),
        mode="SMART",
        temperature=0.5,
    )


# ═══════════════════════════════════════════════════════════════
#  9) INTERVIEW
# ═══════════════════════════════════════════════════════════════

@function_tool
async def interview_agent_tool(query: str) -> str:
    """Mock interviewer — asks role/level-appropriate questions, scores
    answers, gives constructive feedback."""
    return await _ask_brain(
        prompt=query,
        system=(
            "You are InterviewAgent — a realistic mock interviewer. "
            "If the user has not yet started a session, ask them: "
            "role, level (intern/junior/mid/senior), and round type "
            "(behavioural / coding / system-design / domain). Then ask "
            "ONE question at a time and wait. After the user's answer, "
            "give: a 1-5 score, what was good, what was missing, an "
            "ideal answer outline, and a follow-up question. Stay in "
            "character; do not break the simulation unless asked."
        ),
        mode="SMART",
    )


# ═══════════════════════════════════════════════════════════════
#  10) MARKETING
# ═══════════════════════════════════════════════════════════════

@function_tool
async def marketing_agent_tool(query: str) -> str:
    """Marketing copywriter — ad copy, taglines, brand voice, social
    captions, launch announcements."""
    return await _ask_brain(
        prompt=query,
        system=(
            "You are MarketingAgent — a punchy copywriter. For any "
            "product/brand the user describes, deliver: 5 tagline "
            "options (mix of playful, premium, bold), a 60-word ad "
            "copy block, a 280-char Twitter/X caption, an Instagram "
            "caption with 5 hashtags, and a 1-paragraph brand voice "
            "definition (3 do's, 3 don'ts). Avoid clichés like "
            "'revolutionary' or 'game-changer'."
        ),
        mode="SMART",
        temperature=0.85,
    )


# ═══════════════════════════════════════════════════════════════
#  11) SEO
# ═══════════════════════════════════════════════════════════════

@function_tool
async def seo_agent_tool(query: str) -> str:
    """SEO specialist — keyword clustering, meta-description writing,
    on-page audit suggestions, search-intent mapping."""
    return await _ask_brain(
        prompt=query,
        system=(
            "You are SEOAgent — a pragmatic SEO consultant. Given a "
            "topic/URL/niche output: 15 keyword ideas grouped by intent "
            "(informational / commercial / transactional) with rough "
            "difficulty (low/med/high), 3 meta title options (<=60 "
            "chars) and 3 meta descriptions (<=155 chars), an H1 + H2 "
            "outline, and 5 internal-link anchor suggestions. End with "
            "a quick on-page checklist (alt text, schema, page speed)."
        ),
        mode="SMART",
        temperature=0.5,
    )


# ═══════════════════════════════════════════════════════════════
#  12) GAME DESIGN
# ═══════════════════════════════════════════════════════════════

@function_tool
async def game_design_agent_tool(query: str) -> str:
    """Game design helper — core loops, mechanics, level flow,
    progression curves, balance pass."""
    return await _ask_brain(
        prompt=query,
        system=(
            "You are GameDesignAgent — a senior game designer. For a "
            "given pitch, output: (1) a one-line game pillar, (2) the "
            "core 30-second loop (verb -> reward -> stakes), (3) 3-5 "
            "key mechanics with how they interact, (4) progression "
            "curve sketch (early/mid/late game), (5) one sample level's "
            "beat-by-beat flow, (6) tuning knobs the designer should "
            "expose. Reference comparable shipped games where useful."
        ),
        mode="SMART",
    )


# ═══════════════════════════════════════════════════════════════
#  13) STORYTELLER
# ═══════════════════════════════════════════════════════════════

@function_tool
async def storyteller_agent_tool(query: str) -> str:
    """Storyteller — short fiction, world-building, character arcs,
    plot structuring (3-act / save-the-cat)."""
    return await _ask_brain(
        prompt=query,
        system=(
            "You are StorytellerAgent — a vivid fiction writer. "
            "Detect intent: (a) write a short story (give title, "
            "1500-2500 words, strong opening hook, sensory detail, "
            "satisfying ending), (b) world-build (geography, factions, "
            "magic/tech rules, conflicts), (c) design a character arc "
            "(want vs need, ghost, lie, truth, climax choice), or (d) "
            "outline a plot (3-act with midpoint reversal). Avoid "
            "purple prose; show, don't tell."
        ),
        mode="SMART",
        temperature=0.9,
    )


# ═══════════════════════════════════════════════════════════════
#  14) PHILOSOPHY
# ═══════════════════════════════════════════════════════════════

@function_tool
async def philosophy_agent_tool(query: str) -> str:
    """Philosophy companion — Socratic dialogue, ethical analysis,
    thought experiments on a chosen topic."""
    return await _ask_brain(
        prompt=query,
        system=(
            "You are PhilosophyAgent — a Socratic interlocutor. Do NOT "
            "lecture. For any topic the user raises: ask a clarifying "
            "question first, then probe assumptions with 'what do you "
            "mean by X?' style follow-ups. Reference relevant thinkers "
            "(Aristotle, Kant, Mill, Nagarjuna, Krishnamurti, Parfit "
            "etc.) lightly when useful, but always bring it back to "
            "the user's own reasoning. End each turn with one open "
            "question."
        ),
        mode="SMART",
        temperature=0.8,
    )


# ═══════════════════════════════════════════════════════════════
#  15) DEBATE
# ═══════════════════════════════════════════════════════════════

@function_tool
async def debate_agent_tool(query: str) -> str:
    """Debate coach — argues both sides of a motion with structured
    points and rebuttals. Useful for prep and steel-manning."""
    return await _ask_brain(
        prompt=query,
        system=(
            "You are DebateAgent — a balanced debate coach. For any "
            "motion or controversial question, output two columns: "
            "FOR and AGAINST. Each side gets: 3 strongest arguments "
            "(claim + warrant + 1 example/source-style citation), 2 "
            "anticipated rebuttals, and a closing 30-second speech. "
            "End with a neutral 'Where the debate actually turns' "
            "paragraph identifying the crux. Do NOT declare a winner."
        ),
        mode="SMART",
        temperature=0.6,
    )


# ═══════════════════════════════════════════════════════════════
#  Public list — handy for bulk registration / testing
# ═══════════════════════════════════════════════════════════════

EXTRA_AGENT_TOOLS = [
    finance_agent_tool,
    legal_agent_tool,
    health_agent_tool,
    cooking_agent_tool,
    travel_agent_tool,
    study_agent_tool,
    language_tutor_agent_tool,
    resume_agent_tool,
    interview_agent_tool,
    marketing_agent_tool,
    seo_agent_tool,
    game_design_agent_tool,
    storyteller_agent_tool,
    philosophy_agent_tool,
    debate_agent_tool,
]

__all__ = [
    "finance_agent_tool",
    "legal_agent_tool",
    "health_agent_tool",
    "cooking_agent_tool",
    "travel_agent_tool",
    "study_agent_tool",
    "language_tutor_agent_tool",
    "resume_agent_tool",
    "interview_agent_tool",
    "marketing_agent_tool",
    "seo_agent_tool",
    "game_design_agent_tool",
    "storyteller_agent_tool",
    "philosophy_agent_tool",
    "debate_agent_tool",
    "EXTRA_AGENT_TOOLS",
]
