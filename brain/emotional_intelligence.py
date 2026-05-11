"""
Emotional Intelligence module for Shell AI.
Pure-Python sentiment analysis, tone adaptation, frustration detection,
and satisfaction tracking. No external dependencies or AI calls required.
"""

import json
import os
import re
import time
from typing import Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SATISFACTION_FILE = os.path.join(DATA_DIR, "satisfaction.json")


class SentimentAnalyzer:
    """Keyword and heuristic based sentiment scoring."""

    POSITIVE_WORDS = {
        "great", "thanks", "awesome", "love", "perfect", "excellent", "good",
        "nice", "wonderful", "amazing", "fantastic", "brilliant", "cool",
        "sweet", "happy", "glad", "pleased", "satisfied", "helpful",
        "impressive", "outstanding", "superb", "magnificent", "fabulous",
        "delightful", "splendid", "terrific", "marvelous", "fine", "beautiful",
        "best", "better", "thank", "appreciate", "works", "working", "solved",
        "fixed", "correct", "right", "exactly", "yes", "yep", "yeah", "sure",
        "absolutely", "definitely", "indeed", "precisely", "certainly", "agreed",
        "bravo", "cheers", "exciting", "elegant",
    }

    NEGATIVE_WORDS = {
        "bad", "terrible", "hate", "awful", "broken", "frustrated", "annoying",
        "wrong", "error", "fail", "failed", "crash", "bug", "slow", "useless",
        "stupid", "dumb", "worst", "worse", "horrible", "disgusting",
        "pathetic", "rubbish", "trash", "garbage", "nonsense", "ridiculous",
        "absurd", "crap", "sucks", "ugly", "poor", "weak", "lazy", "boring",
        "confusing", "confused", "stuck", "lost", "impossible", "stop", "quit",
        "enough", "no", "nope", "nah", "never", "nothing", "none",
        "annoyed", "angry", "furious", "irritated", "disappointing",
    }

    NEGATIVE_PHRASES = [
        "doesn't work", "not working", "can't", "won't", "don't like",
        "no way", "give up", "fed up",
    ]

    def analyze(self, text: str) -> Dict:
        """
        Analyse sentiment of *text*.

        Returns:
            dict with keys:
                sentiment  – "positive" | "negative" | "neutral"
                score      – float in [-1.0, 1.0]
                frustration – bool
        """
        lower = text.lower()
        words = re.findall(r"[a-z']+", lower)

        pos_count = sum(1 for w in words if w in self.POSITIVE_WORDS)
        neg_count = sum(1 for w in words if w in self.NEGATIVE_WORDS)

        # Check negative phrases
        for phrase in self.NEGATIVE_PHRASES:
            if phrase in lower:
                neg_count += 1

        total = pos_count + neg_count
        if total == 0:
            raw_score = 0.0
        else:
            raw_score = (pos_count - neg_count) / total

        # ALL-CAPS bias: if more than half the alphabetical chars are uppercase
        alpha_chars = [c for c in text if c.isalpha()]
        caps_ratio = (
            sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
            if alpha_chars
            else 0.0
        )
        if caps_ratio > 0.5 and len(alpha_chars) > 3:
            raw_score -= 0.3

        # Excessive punctuation (!!!, ???)
        if re.search(r"[!?]{3,}", text):
            raw_score -= 0.15

        score = max(-1.0, min(1.0, raw_score))

        if score > 0.15:
            sentiment = "positive"
        elif score < -0.15:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        frustration = sentiment == "negative" and (
            caps_ratio > 0.5 or neg_count >= 2 or bool(re.search(r"[!?]{3,}", text))
        )

        return {"sentiment": sentiment, "score": round(score, 3), "frustration": frustration}


class ToneAdapter:
    """Generates system-prompt modifiers based on detected emotion."""

    def get_system_prompt_modifier(
        self,
        sentiment_result: Dict,
        user_history: Optional[List[str]] = None,
    ) -> str:
        user_history = user_history or []

        # Detect repeated topic: extract keywords from last 3 messages
        if len(user_history) >= 3:
            recent = user_history[-3:]
            keyword_sets = [
                set(re.findall(r"[a-z]+", msg.lower())) - {"the", "a", "an", "is", "it", "to", "and", "or", "i"}
                for msg in recent
            ]
            if len(keyword_sets) == 3:
                common = keyword_sets[0] & keyword_sets[1] & keyword_sets[2]
                if len(common) >= 2:
                    return (
                        "User may be confused. Explain more clearly with examples."
                    )

        sentiment = sentiment_result.get("sentiment", "neutral")
        frustration = sentiment_result.get("frustration", False)

        if frustration or sentiment == "negative":
            return (
                "Be empathetic and patient. Acknowledge frustration. "
                "Provide clear, step-by-step help."
            )
        if sentiment == "positive":
            return "Match enthusiasm. Be concise and direct."

        return ""


class FrustrationDetector:
    """Multi-signal frustration detector."""

    def detect(
        self,
        message: str,
        conversation_history: Optional[List[str]] = None,
    ) -> Dict:
        conversation_history = conversation_history or []
        signals = 0

        # 1. ALL CAPS ratio
        alpha_chars = [c for c in message if c.isalpha()]
        caps_ratio = (
            sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
            if alpha_chars
            else 0.0
        )
        if caps_ratio > 0.5 and len(alpha_chars) > 3:
            signals += 1

        # 2. Excessive punctuation
        if re.search(r"[!?]{3,}", message):
            signals += 1

        # 3. Negative word count
        lower = message.lower()
        words = re.findall(r"[a-z']+", lower)
        neg_count = sum(1 for w in words if w in SentimentAnalyzer.NEGATIVE_WORDS)
        if neg_count >= 2:
            signals += 1

        # 4. Repeated questions (same keywords in last 3 messages)
        if len(conversation_history) >= 2:
            current_kw = set(re.findall(r"[a-z]{3,}", lower))
            for prev in conversation_history[-3:]:
                prev_kw = set(re.findall(r"[a-z]{3,}", prev.lower()))
                overlap = current_kw & prev_kw
                if len(overlap) >= 3:
                    signals += 1
                    break

        # 5. Short angry message
        if len(words) < 10 and neg_count >= 1:
            signals += 1

        level = min(signals, 3)

        suggested_actions = {
            0: "No action needed.",
            1: "Be more detailed in your response.",
            2: "Slow down, be precise, and apologize for any confusion.",
            3: "Apologize sincerely, offer alternative approaches, and ask the user what they need.",
        }

        return {
            "frustrated": level >= 1,
            "level": level,
            "suggested_action": suggested_actions[level],
        }


class SatisfactionTracker:
    """Persists interaction satisfaction scores to disk."""

    def __init__(self) -> None:
        self._scores: List[Dict] = []
        self._load()

    def _load(self) -> None:
        if os.path.exists(SATISFACTION_FILE):
            try:
                with open(SATISFACTION_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._scores = data if isinstance(data, list) else []
            except (json.JSONDecodeError, OSError):
                self._scores = []

    def _save(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SATISFACTION_FILE, "w", encoding="utf-8") as f:
            json.dump(self._scores, f, indent=2)

    def record_interaction(
        self,
        user_msg: str,
        assistant_msg: str,
        follow_up: Optional[str] = None,
    ) -> None:
        """Infer satisfaction from the optional follow-up message."""
        analyzer = SentimentAnalyzer()

        if follow_up:
            result = analyzer.analyze(follow_up)
            score = round((result["score"] + 1.0) / 2.0, 3)  # map [-1,1] -> [0,1]
        else:
            score = 0.5  # neutral assumption when no follow-up

        self._scores.append({"score": score, "ts": time.time()})
        # Keep last 500 entries
        if len(self._scores) > 500:
            self._scores = self._scores[-500:]
        self._save()

    def get_average_score(self) -> float:
        if not self._scores:
            return 0.5
        return round(sum(s["score"] for s in self._scores) / len(self._scores), 3)

    def get_satisfaction_trend(self) -> str:
        if len(self._scores) < 6:
            return "stable"
        half = len(self._scores) // 2
        first_avg = sum(s["score"] for s in self._scores[:half]) / half
        second_avg = sum(s["score"] for s in self._scores[half:]) / (len(self._scores) - half)
        diff = second_avg - first_avg
        if diff > 0.05:
            return "improving"
        if diff < -0.05:
            return "declining"
        return "stable"


class EmotionalIntelligence:
    """Facade that wraps all emotional-intelligence components."""

    def __init__(self) -> None:
        self.sentiment = SentimentAnalyzer()
        self.tone = ToneAdapter()
        self.frustration = FrustrationDetector()
        self.satisfaction = SatisfactionTracker()

    def process(self, message: str, history: Optional[List[str]] = None) -> Dict:
        """Run full emotional analysis on a message."""
        history = history or []
        sent = self.sentiment.analyze(message)
        frust = self.frustration.detect(message, history)
        modifier = self.tone.get_system_prompt_modifier(sent, history)
        return {
            "sentiment": sent,
            "frustration": frust,
            "tone_modifier": modifier,
        }


# Module-level singleton
emotional_ai = EmotionalIntelligence()
