"""
SHELL BRAIN - INFINITE CONTEXT MODULE (PROJECT AKASHIC)
Static knowledge base plus ranked retrieval helpers.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

INFINITE_KNOWLEDGE_BASE: Dict[str, Dict[str, str]] = {
    "SCIENCE_PHYSICS": {
        "Quantum Mechanics": "Study of matter/energy at atomic scale. Key Concepts: Superposition, Entanglement, Wave-Particle Duality.",
        "General Relativity": "Einstein's theory of gravity as curvature of spacetime. E=mc^2.",
        "Thermodynamics": "Laws of heat/energy. Entropy always increases (2nd Law).",
        "Standard Model": "Theory of fundamental particles: Quarks, Leptons, Bosons (Higgs).",
        "String Theory": "Hypothesis that particles are 1-dimensional vibrating strings.",
    },
    "SCIENCE_SPACE": {
        "Black Hole": "Region where gravity is so strong nothing escapes. Boundary: Event Horizon.",
        "Big Bang": "Universe origin ~13.8 billion years ago from a singularity.",
        "Dark Matter": "Invisible matter making up 27% of universe. Detectable only via gravity.",
        "Exoplanets": "Planets orbiting stars outside our solar system.",
        "Speed of Light": "299,792,458 m/s. Universal cosmic speed limit.",
    },
    "TECH_CODING": {
        "Python": "High-level, interpreted language. Great for AI, Web, Scripting. Zen: 'Readability counts'.",
        "JavaScript": "Language of the Web. Runs in browser (V8 engine) and server (Node.js).",
        "Rust": "Systems language. Memory safety without garbage collection. Blazingly fast.",
        "Docker": "Platform for containerization. 'Build once, run anywhere'.",
        "Kubernetes": "Container orchestration system. Manages scaling/deployment.",
        "Git": "Version control system created by Linus Torvalds.",
        "LLM": "Large Language Model. AI trained on massive text data (e.g., GPT, Gemini, Claude).",
    },
    "HISTORY_WORLD": {
        "WW2": "1939-1945. Allies vs Axis. Ended with Atomic Bomb & UN formation.",
        "Industrial Revolution": "18th-19th Century transition to manufacturing processes.",
        "Renaissance": "14th-17th Century cultural rebirth in Europe (Art, Science).",
        "Cold War": "Geopolitical tension between USA and USSR (1947-1991).",
        "Moon Landing": "Apollo 11, 1969. Neil Armstrong: 'One small step for man'.",
    },
    "HISTORY_INDIA": {
        "Independence": "August 15, 1947. Freedom from British Rule.",
        "Mughal Empire": "1526-1857. Known for Art, Architecture (Taj Mahal), Cuisine.",
        "Maurya Empire": "322-185 BCE. Chandragupta Maurya & Ashoka the Great.",
        "ISRO": "Indian Space Research Organisation. Mars Mission (Mangalyaan) cost < Gravity movie.",
        "Constitution": "Adopted 26 Jan 1950. Architect: Dr. B.R. Ambedkar.",
    },
    "INDIA_CULTURE": {
        "Diwali": "Festival of Lights. Victory of Light over Darkness.",
        "Holi": "Festival of Colors. Spring celebration.",
        "Yoga": "Ancient physical/mental practice originating in India.",
        "Bollywood": "Hindi Cinema industry based in Mumbai. Largest in world by output.",
        "Cricket": "Most popular sport. 1983 & 2011 World Cup wins are legendary.",
    },
    "GEOGRAPHY": {
        "Highest Peak": "Mount Everest (8848m).",
        "Longest River": "Nile (Africa).",
        "Largest Ocean": "Pacific Ocean.",
        "India Capital": "New Delhi.",
        "USA Capital": "Washington D.C.",
    },
    "POP_CULTURE": {
        "Matrix": "Simulated reality. 'Red Pill vs Blue Pill'.",
        "Star Wars": "Space Opera. 'May the Force be with you'.",
        "Avengers": "Marvel superheroes. 'Avengers Assemble'.",
        "Breaking Bad": "Chemistry teacher turns drug lord. 'I am the one who knocks'.",
        "Game of Thrones": "Fantasy drama. 'Winter is Coming'.",
    },
}

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "with",
}


def _tokenize(text: str) -> List[str]:
    tokens = _TOKEN_PATTERN.findall((text or "").lower())
    return [token for token in tokens if token not in _STOPWORDS]


def search_knowledge(topic: str, max_results: int = 3) -> List[Dict[str, str]]:
    """
    Ranked search over the static knowledge base.

    Returns a list of dicts with keys: category, key, value, score.
    """
    query_text = (topic or "").strip().lower()
    if not query_text:
        return []

    query_tokens = set(_tokenize(query_text))
    hits: List[Dict[str, str]] = []

    for category, items in INFINITE_KNOWLEDGE_BASE.items():
        for key, value in items.items():
            key_lower = key.lower()
            value_lower = value.lower()
            score = 0.0

            if query_text in key_lower:
                score += 8.0
            if key_lower in query_text:
                score += 5.0

            key_tokens = set(_tokenize(key_lower))
            value_tokens = set(_tokenize(value_lower))

            score += 2.5 * len(query_tokens & key_tokens)
            score += 1.0 * len(query_tokens & value_tokens)

            partial_hits = sum(1 for token in query_tokens if len(token) >= 4 and token in value_lower)
            score += 0.5 * partial_hits

            if score > 0:
                hits.append(
                    {
                        "category": category,
                        "key": key,
                        "value": value,
                        "score": f"{score:.2f}",
                    }
                )

    hits.sort(key=lambda item: (-float(item["score"]), item["key"]))
    return hits[: max(1, max_results)]


def get_knowledge(topic: str) -> Optional[str]:
    """Retrieves the best knowledge hit if available, else returns None."""
    ranked_hits = search_knowledge(topic, max_results=2)
    if not ranked_hits:
        return None

    best = ranked_hits[0]
    lines = [
        f"ARCHIVE HIT ({best['category']}):",
        f"{best['key']}: {best['value']}",
    ]

    if len(ranked_hits) > 1:
        lines.append(f"Related: {ranked_hits[1]['key']} ({ranked_hits[1]['category']})")

    return "\n".join(lines)


__all__ = ["INFINITE_KNOWLEDGE_BASE", "get_knowledge", "search_knowledge"]
